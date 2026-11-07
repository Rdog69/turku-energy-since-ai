"""Cut a small, spot-free demo sample out of app_demo_data/ for the hosted dashboard preview.

    python -m src.export.demo_sample --period test --days 2

Picks the most eventful consecutive days (most alerts) so the preview shows something worth seeing,
and writes app_demo_sample/<period>/ with the same structure the dashboard reads
(index.json, origins/*.json, track_record.json). Built from app_demo_data/ (synthetic spot), so it
contains no Nord Pool data and can be committed and uploaded to the hosted preview.
"""
from __future__ import annotations

import argparse
import json
import shutil

import pandas as pd

from src import config


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", default="test")
    ap.add_argument("--days", type=int, default=2)
    args = ap.parse_args(argv)
    src = config.REPO_ROOT / "app_demo_data" / args.period
    out = config.REPO_ROOT / "app_demo_sample" / args.period
    index = json.loads((src / "index.json").read_text(encoding="utf-8"))
    assert index["demo"], "refusing to sample non-demo data"

    files = sorted((src / "origins").glob("*.json"))
    rows = []
    for f in files:
        d = json.loads(f.read_text(encoding="utf-8"))
        assert d["demo"], f"{f.name} is not demo data"
        rows.append({"file": f, "origin": pd.Timestamp(d["origin"]),
                     "score": sum({"high": 3, "medium": 2, "low": 1}[a["severity"]] for a in d["alerts"])})
    df = pd.DataFrame(rows)
    df["day"] = df["origin"].dt.tz_convert("Europe/Helsinki").dt.date
    by_day = df.groupby("day")["score"].sum()
    window = by_day.rolling(args.days).sum()
    end_day = window.idxmax()
    days = list(by_day.index[by_day.index.get_loc(end_day) - args.days + 1: by_day.index.get_loc(end_day) + 1])
    pick = df.loc[df["day"].isin(days)].sort_values("origin")

    if out.exists():
        shutil.rmtree(out)
    (out / "origins").mkdir(parents=True)
    for f in pick["file"]:
        shutil.copy(f, out / "origins" / f.name)
    index["origins"] = [o.strftime("%Y-%m-%dT%H:%M:%SZ") for o in pick["origin"]]
    index["sample_days"] = [str(d) for d in days]
    (out / "index.json").write_text(json.dumps(index), encoding="utf-8")
    shutil.copy(src / "track_record.json", out / "track_record.json")
    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file()) / 1024
    print(f"wrote {len(pick)} origins for {days} to {out.relative_to(config.REPO_ROOT)} ({size:.0f} KB)")


if __name__ == "__main__":
    main()
