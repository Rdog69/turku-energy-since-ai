"""Replay forecast updates into the n8n alert workflow, as if they were arriving live.

    python -m src.automation.replay --period test --start 2026-10-12T00:00Z --hours 24 --every 2

Every forecast origin becomes one POST to the n8n webhook ("Imbalance alert relay"), which keeps
updates with a high-severity situation in the next 3 h, formats a message and logs it.

Payloads are spot-free: status, alert and suggestion texts, and the briefing. No spot prices or
absolute price forecasts leave this machine (Nord Pool licence); a guard checks every payload.

Webhook URL: --url, or N8N_WEBHOOK_URL in .env, or the default below.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request

import pandas as pd

from src import config

DEFAULT_URL = "https://frankponce.app.n8n.cloud/webhook/imbalance-alert"
ABSOLUTE_PRICE = re.compile(r"\bnow -?\d+ ?€/MWh", re.I)


def payload(doc: dict) -> dict:
    p = {
        "origin": doc["origin"],
        "origin_local": doc["origin_local"],
        "status": doc["status"],
        "alerts": [{"type": a["type"], "severity": a["severity"], "window_local": a["window_local"],
                    "message": a["message"]} for a in doc["alerts"]],
        "suggestions": [{"text": s["text"], "window_local": s["window_local"]} for s in doc["suggestions"]],
        "conflicts": [c["message"] for c in doc["conflicts"]],
        "explanation": (doc.get("explanation") or {}).get("text"),
    }
    text = json.dumps(p, ensure_ascii=False)
    if ABSOLUTE_PRICE.search(text) or '"spot"' in text or '"p50"' in text:
        raise ValueError(f"payload for {doc['origin']} would reveal prices; not sent")
    return p


def env_url() -> str | None:
    if os.environ.get("N8N_WEBHOOK_URL"):
        return os.environ["N8N_WEBHOOK_URL"]
    path = config.REPO_ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip().startswith("N8N_WEBHOOK_URL="):
                return line.split("=", 1)[1].strip().strip('"')
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="test")
    ap.add_argument("--start", default=None, help="first origin (UTC), default: first of the period")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--every", type=float, default=2.0, help="seconds between updates")
    ap.add_argument("--url", default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)
    url = args.url or env_url() or DEFAULT_URL

    root = config.RESULTS_DIR / "dashboard" / args.period / "origins"
    files = sorted(root.glob("*.json"))
    if args.start:
        start = pd.Timestamp(args.start)
        files = [f for f in files if pd.Timestamp(f.stem, tz="UTC") >= start]
    files = files[: args.hours]
    sent = alerts = 0
    for f in files:
        p = payload(json.loads(f.read_text(encoding="utf-8")))
        alerts += p["status"] == "alert"
        if args.dry_run:
            print(p["origin_local"], p["status"], (p["alerts"][:1] or [{"message": ""}])[0]["message"])
        else:
            req = urllib.request.Request(url, data=json.dumps(p).encode(), method="POST",
                                         headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=30).read()
            sent += 1
            print(f"{p['origin_local']}  {p['status']:<5}  sent", flush=True)
            time.sleep(args.every)
    print(f"{len(files)} updates, {alerts} with status alert, {sent} sent to {'(dry run)' if args.dry_run else url}")


if __name__ == "__main__":
    main()
