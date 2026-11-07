"""Rank every model in scoreboard/entries/ and print the breakdown.

    python scoreboard/leaderboard.py                 # markdown: winner, ranking, each month
    python scoreboard/leaderboard.py --csv out.csv   # every entry as one CSV row (spreadsheet, dashboard)

How the ranking works:
- For each month, a model's score is the points-weighted % by which it beats the organisers' baseline
  (MAE 30, pinball 20, spikes 20, direction 10: the starter-package README, Level 1). The baseline for
  August is the organisers' own baseline.ipynb code run on August (scoreboard/baseline.py).
- Overall = the average over September and August. Models scored on only one month come after the rest.
- Where a model has both an official and a lab entry for a month, the official one counts.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import PERIODS, SCORES, gain, load_entries  # noqa: E402

FIELDS = ["owner", "model", "period", "scorer", *SCORES, "pre_june_data", "sources", "description", "notes",
          "forecast_file", "branch", "commit", "logged_by", "logged_at_utc"]


def is_baseline(e: dict) -> bool:
    return e["owner"].lower() == "organisers" and e["model"] == "baseline"


def best_entries(entries: list[dict]) -> dict:
    """One entry per (owner, model, period): official beats lab, then the newest."""
    out: dict = {}
    for e in entries:
        key = (e["owner"], e["model"], e["period"])
        rank = (e["scorer"] == "official", e.get("logged_at_utc", ""))
        if key not in out or rank > (out[key]["scorer"] == "official", out[key].get("logged_at_utc", "")):
            out[key] = e
    return out


def ranking(entries: list[dict]) -> list[dict]:
    chosen = best_entries(entries)
    base = {p: e for (o, m, p), e in chosen.items() if is_baseline(e)}
    models: dict = {}
    for (owner, model, period), e in chosen.items():
        if is_baseline(e) or period not in base:
            continue
        r = models.setdefault((owner, model), {"owner": owner, "model": model, "months": {}, "lab": False,
                                               "pre_june_data": False, "description": ""})
        r["months"][period] = gain(base[period], e)
        r["lab"] |= e["scorer"] == "lab"
        r["pre_june_data"] |= bool(e.get("pre_june_data"))
        r["description"] = r["description"] or e.get("description", "")
    rows = list(models.values())
    for r in rows:
        r["complete"] = all(p in r["months"] for p in PERIODS)
        r["average"] = sum(r["months"].values()) / len(r["months"])
    return sorted(rows, key=lambda r: (not r["complete"], -r["average"]))


def fmt(v, nd=1, pct=True):
    return "" if v is None else (f"{v:.{nd}f} %" if pct else f"{v:.{nd}f}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", help="write every entry to this CSV file")
    a = ap.parse_args(argv)
    entries = load_entries()
    if a.csv:
        with open(a.csv, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS + ["is_baseline"], extrasaction="ignore", lineterminator="\n")
            w.writeheader()
            for e in entries:
                w.writerow({**e, "sources": ";".join(e.get("sources", [])), "is_baseline": is_baseline(e)})
        print(f"wrote {a.csv} ({len(entries)} entries)")
        return 0

    rows = ranking(entries)
    if not rows:
        print("No scored models yet. Log one with scoreboard/log_score.py.")
        return 0
    top = rows[0]
    months = " and ".join(PERIODS[p]["label"] for p in PERIODS)
    print(f"## Winner: {top['model']} ({top['owner']})\n")
    print(f"{fmt(top['average'])} better than the organisers' baseline, weighted by points, averaged over {months}."
          + (f" Runner-up: {rows[1]['model']} ({rows[1]['owner']}), {fmt(rows[1]['average'])}." if len(rows) > 1 else "") + "\n")
    print("## Ranking\n")
    head = ["#", "Model", "Owner", "Average"] + [PERIODS[p]["label"] for p in PERIODS] + ["Pre-June data", "Note"]
    print("| " + " | ".join(head) + " |\n|" + "---|" * len(head))
    for i, r in enumerate(rows, 1):
        note = ("lab-scored month" if r["lab"] else "") + ("" if r["complete"] else (", " if r["lab"] else "") + "one month only")
        cells = [str(i), r["model"], r["owner"], fmt(r["average"])] + [fmt(r["months"].get(p)) for p in PERIODS] \
            + ["yes" if r["pre_june_data"] else "no", note]
        print("| " + " | ".join(cells) + " |")
    chosen = best_entries(entries)
    for p, meta in PERIODS.items():
        es = [e for (o, m, pp), e in chosen.items() if pp == p]
        if not es:
            continue
        print(f"\n## {meta['label']}: {meta['about']}\n")
        print("| Model | Owner | MAE | Pinball | Spike Brier | Direction Brier | Coverage | Scorer |\n|---|---|---|---|---|---|---|---|")
        for e in sorted(es, key=lambda e: e["mae"]):
            print(f"| {e['model']} | {e['owner']} | {e['mae']:.2f} | {e['pinball']:.2f} | {e['spike_brier']:.4f} | "
                  f"{e['direction_brier']:.4f} | {fmt(e.get('coverage', None) and e['coverage'] * 100)} | {e['scorer']} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
