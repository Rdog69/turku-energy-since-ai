"""Log one model's scores to the team scoreboard: one JSON file per owner, model, period and scorer.

Official scores (the organisers' score.py summary):

    python scoreboard/log_score.py --owner Frank --model v6_hf --period validation \
        --summary results/v6_hf/validation/score/score_summary.csv --pre-june yes \
        --sources package,fingrid_rt,ecmwf,icon_eu,nordic_wind,pre_june_history \
        --description "LightGBM quantiles + direction, trained with pre-June history"

Lab scores (your own scorer; only when you can't run score.py):

    python scoreboard/log_score.py --owner Abdo --model team5050 --period fold_b --scorer lab \
        --mae 27.27 --pinball 6.57 --spike-brier 0.0677 --direction-brier 0.4281 --pre-june yes

Logging the same owner/model/period/scorer again replaces your earlier entry. Rules: scoreboard/README.md.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from common import ENTRIES, PERIODS, REPO, SCORES  # noqa: E402

SUMMARY_COLUMNS = {"mae": "mae_p50", "pinball": "calibration_pinball_mean", "spike_brier": "brier_spike_mean",
                   "direction_brier": "brier_direction", "coverage": "coverage_p10_p90"}


def git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO, text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def slug(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", s).strip("-").lower()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--owner", required=True, help="whose model it is (first name)")
    ap.add_argument("--model", required=True, help="the model's name in its owner's code")
    ap.add_argument("--period", required=True, choices=sorted(PERIODS),
                    help="validation = September, fold_b = August. The test month is never logged.")
    ap.add_argument("--scorer", choices=["official", "lab"], default="official")
    ap.add_argument("--summary", help="score_summary.csv written by the organisers' score.py")
    for k in SCORES:
        ap.add_argument("--" + k.replace("_", "-"), type=float, help=f"{k} (lab scores, or to override)")
    ap.add_argument("--pre-june", required=True, choices=["yes", "no"],
                    help="did training use any data from before 1 June 2026?")
    ap.add_argument("--sources", default="package", help="comma-separated data sources (README lists the names)")
    ap.add_argument("--description", default="", help="one line: what the model is")
    ap.add_argument("--notes", default="", help="what changed, caveats")
    ap.add_argument("--forecast-file", default="", help="branch:path of the scored forecast file, if it's in git")
    ap.add_argument("--branch", help="defaults to the current git branch")
    ap.add_argument("--commit", help="defaults to the current git commit")
    ap.add_argument("--logged-by", default="", help="who logged it, if not the owner (e.g. an agent)")
    a = ap.parse_args(argv)

    scores: dict[str, float] = {}
    if a.summary:
        with open(a.summary, newline="", encoding="utf-8") as f:
            row = next(csv.DictReader(f))
        scores = {k: float(row[c]) for k, c in SUMMARY_COLUMNS.items() if row.get(c) not in (None, "")}
    for k in SCORES:
        v = getattr(a, k)
        if v is not None:
            scores[k] = v
    missing = [k for k in SCORES[:4] if k not in scores]
    if missing:
        ap.error(f"missing scores {missing}: pass --summary or the values")
    if a.scorer == "official" and not a.summary:
        ap.error("official scores come from --summary (the organisers' score.py); otherwise use --scorer lab")
    for k, v in scores.items():
        if not math.isfinite(v) or v < 0:
            ap.error(f"{k} must be a finite number >= 0")
    if "coverage" in scores and not 0 <= scores["coverage"] <= 1:
        ap.error("coverage must be a share between 0 and 1")

    entry = {
        "owner": a.owner, "model": a.model, "period": a.period, "scorer": a.scorer,
        **{k: round(scores[k], 6) for k in SCORES if k in scores},
        "pre_june_data": a.pre_june == "yes",
        "sources": [s.strip() for s in a.sources.split(",") if s.strip()],
        "description": a.description, "notes": a.notes, "forecast_file": a.forecast_file,
        "branch": a.branch if a.branch is not None else git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": a.commit if a.commit is not None else git("rev-parse", "--short", "HEAD"),
        "logged_by": a.logged_by,
        "logged_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    ENTRIES.mkdir(exist_ok=True)
    path = ENTRIES / f"{slug(a.owner)}__{slug(a.model)}__{a.period}__{a.scorer}.json"
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"logged {path.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
