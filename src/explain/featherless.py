"""Plain-language situation briefings with an LLM on Featherless (OpenAI-compatible API).

    python -m src.explain.featherless --period test --workers 4
    python -m src.explain.featherless --period test --limit 5      # try a few first

For each forecast origin in results/dashboard/<period>/origins/*.json:

1. Build a fact sheet from the deterministic rules (alerts, conflicts, suggestions, drivers,
   grid context). **No spot prices and no absolute price forecasts** go into the prompt: Nord Pool
   data must not be shared with third parties. Only gaps to spot, probabilities and grid facts.
2. Ask the model for a 2-3 sentence briefing in the style of the challenge brief's example.
3. Check every number in the answer appears in the fact sheet. If one doesn't (a made-up number),
   fall back to a template briefing. The model can't invent facts on the dashboard.
4. Cache the answer per origin and write it into the origin's JSON as `explanation`.

The LLM only produces text after the forecast is made. It is never a model input, so it can't
leak future data or change any score.

Needs FEATHERLESS_API_KEY in .env.
"""
from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from src import config

API = "https://api.featherless.ai/v1/chat/completions"
# Tested 6 Nov on six origins: Qwen2.5-32B 6/6 clean; Qwen2.5-72B produced "!!!!" runs;
# Mistral-Small-24B failed the number check 3/6; Llama 3.3 70B is gated (needs a HF licence link).
MODEL = "Qwen/Qwen2.5-32B-Instruct"
CACHE = config.RESULTS_DIR / "explanations"

SYSTEM = (
    "You write short briefings for an electricity trader and a power-plant shift supervisor at a "
    "Finnish energy company. You get facts from a forecasting system for the Finnish imbalance price "
    "over the next 10 hours. Write 2-3 plain sentences: what to look at first, why (the main drivers), "
    "and how certain it is. Use local times as given. Use ONLY numbers that appear in the facts; never "
    "invent numbers, plants or events. Don't give orders: phrase actions as things worth checking. "
    "No greeting, no bullet points, no markdown."
)

EXAMPLE = (
    "Example of the style: 'The risk of an exceptionally high price has increased for 16:00-18:00. The "
    "forecast is driven mainly by a lower wind forecast, higher consumption and the cross-border flow "
    "situation. Uncertainty is high, so the production plan and market position are worth checking.'"
)


def api_key() -> str:
    path = config.REPO_ROOT / ".env"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("FEATHERLESS_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("FEATHERLESS_API_KEY missing in .env")


def fact_sheet(doc: dict) -> dict:
    """Spot-free facts for the prompt."""
    blocks = doc["blocks"][:4]
    return {
        "forecast_made_at_local": doc["origin_local"],
        "status": doc["status"],
        "next_hours": [{
            "window": b["window_local"],
            "expected_gap_to_spot_eur_mwh": None if b["p50"] is None else round(b["p50"] - b["spot"]),
            "chance_up_regulation": f"{b['p_up']:.0%}",
            "chance_exceptionally_high": f"{b['spike_high']:.0%}",
            "chance_exceptionally_low": f"{b['spike_low']:.0%}",
            "uncertainty_range_eur_mwh": None if b["width"] is None else round(b["width"]),
        } for b in blocks],
        "alerts": [a["message"] for a in doc["alerts"] if a["type"] != "forecast_change"][:4],
        "forecast_changes": [a["message"] for a in doc["alerts"] if a["type"] == "forecast_change"][:2],
        "conflicting_signals": [c["message"] for c in doc["conflicts"]],
        "main_drivers": [d["label"] for d in doc["drivers"][:4]],
        "grid_now": {k: v for k, v in doc["context"].items()
                     if k in ("wind_fc_mw", "wind_now_vs_forecast_mw", "frequency_deviation_hz",
                              "nuclear_change_6h_mw", "weather_wind_revision_mw")},
        "suggestions_to_review": [s["text"] for s in doc["suggestions"][:3]],
    }


SPOT_LEAK = re.compile(r"\bnow -?\d+ ?€/MWh|spot (price )?(is|of|at) -?\d", re.I)


def assert_spot_free(facts: dict) -> None:
    """Refuse to send anything that contains or reveals a spot price (Nord Pool licence)."""
    text = json.dumps(facts, ensure_ascii=False)
    forbidden_keys = {"spot", "p10", "p50", "p90", "price", "last_imb"}
    def walk(x):
        if isinstance(x, dict):
            for k, v in x.items():
                if k in forbidden_keys:
                    raise ValueError(f"fact sheet contains forbidden key {k!r}")
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(facts)
    if SPOT_LEAK.search(text):
        raise ValueError("fact sheet text contains an absolute price")


def template(facts: dict) -> str:
    """Deterministic fallback briefing."""
    parts = []
    if facts["alerts"]:
        parts.append(facts["alerts"][0])
    else:
        nh = facts["next_hours"][0]
        parts.append(f"No exceptional situation flagged for {nh['window']}; "
                     f"up-regulation chance {nh['chance_up_regulation']}.")
    if facts["main_drivers"]:
        parts.append("Main drivers: " + ", ".join(d.lower() for d in facts["main_drivers"][:3]) + ".")
    if facts["conflicting_signals"]:
        parts.append(facts["conflicting_signals"][0] + " Worth an expert look.")
    elif facts["suggestions_to_review"]:
        parts.append(facts["suggestions_to_review"][0])
    return " ".join(parts)


_NUM = re.compile(r"(?<![\w.])[-+]?\d+(?:[.,]\d+)?")


def numbers_ok(text: str, facts: dict) -> bool:
    """Every number in the text must appear in the facts (times like 16:00 count as numbers too)."""
    allowed = set(_NUM.findall(json.dumps(facts, ensure_ascii=False)))
    allowed |= {n.lstrip("+-") for n in allowed}
    for n in _NUM.findall(text):
        if n.lstrip("+-") not in allowed and n not in {"10", "1", "2", "3"}:  # "next 10 hours" etc.
            return False
    return True


def looks_clean(text: str) -> bool:
    """Reject degenerate output: symbol runs, restarts, runaway length."""
    if not text or len(text) > 700 or len(text) < 40:
        return False
    if re.search(r"([^\w\s])\1{2,}", text):          # "!!!", "???", "..." runs
        return False
    first = text[:40]
    if text.count(first) > 1:                        # the model restarted its answer
        return False
    return True


def ask(facts: dict, key: str) -> str:
    body = json.dumps({
        "model": MODEL, "temperature": 0.2, "max_tokens": 160,
        "messages": [{"role": "system", "content": SYSTEM + " " + EXAMPLE},
                     {"role": "user", "content": "Facts:\n" + json.dumps(facts, ensure_ascii=False, indent=1)}],
    }).encode()
    req = urllib.request.Request(API, data=body, headers={"Authorization": "Bearer " + key,
                                                          "Content-Type": "application/json"})
    for attempt in range(5):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=120))
            return r["choices"][0]["message"]["content"].strip(), r.get("usage", {})
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) or e.code >= 500:
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            time.sleep(5 * (attempt + 1))
    raise RuntimeError("Featherless request failed repeatedly")


def explain_file(path: Path, period: str, key: str) -> dict:
    doc = json.loads(path.read_text(encoding="utf-8"))
    facts = fact_sheet(doc)
    assert_spot_free(facts)   # raises before anything is sent
    cache = CACHE / period / path.name
    if cache.exists():
        result = json.loads(cache.read_text(encoding="utf-8"))
    else:
        try:
            text, usage = ask(facts, key)
            ok = looks_clean(text) and numbers_ok(text, facts)
            result = {"text": text if ok else template(facts), "source": "llm" if ok else "template_fallback",
                      "llm_text": text, "model": MODEL, "usage": usage}
        except Exception as e:  # network trouble: never block the dashboard
            result = {"text": template(facts), "source": "template_error", "error": str(e)[:200]}
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    doc["explanation"] = {"text": result["text"], "source": result["source"],
                          "model": result.get("model")}
    path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return result


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["validation", "test"], default="test")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--demo", action="store_true", help="annotate app_demo_data/ instead (reuses the cache)")
    ap.add_argument("--pattern", default="*.json", help="origin files to do, e.g. '20261012T*.json'")
    args = ap.parse_args(argv)
    key = api_key()
    root = (config.REPO_ROOT / "app_demo_data" / args.period) if args.demo else (
        config.RESULTS_DIR / "dashboard" / args.period)
    files = sorted((root / "origins").glob(args.pattern))[: args.limit]
    t0 = time.time()
    with ThreadPoolExecutor(args.workers) as ex:
        results = list(ex.map(lambda p: explain_file(p, args.period, key), files))
    src = {}
    tokens = 0
    cost = 0.0
    for r in results:
        src[r["source"]] = src.get(r["source"], 0) + 1
        tokens += (r.get("usage") or {}).get("total_tokens", 0)
        cost += (r.get("usage") or {}).get("cost", 0) or 0
    print(f"{len(files)} origins in {time.time() - t0:.0f}s; sources {src}; "
          f"new tokens {tokens}, reported cost ${cost:.4f}")


if __name__ == "__main__":
    main()
