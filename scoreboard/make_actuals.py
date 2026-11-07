"""Build the actuals file for August (or September) from the starter package, for the organisers' score.py.

    python scoreboard/make_actuals.py --period fold_b        # -> scoreboard/_local/actuals_fold_b.csv

Same columns as the organisers' data/actuals_validation.csv (delivery_start_utc, imbalance_price,
spot_price, direction, first_usable_origin_utc), one row per quarter-hour of the period's local dates.
For --period validation it reproduces the organisers' file exactly (checked on brainstorming-frank,
tests/test_actuals.py). The file holds spot prices: it stays in scoreboard/_local/ (git-ignored).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LOCAL, PERIODS, package_dir  # noqa: E402

IMBALANCE, DIRECTION, SPOT = "fi_imbalance_price", "fi_mfrr_direction", "fi_spot_price"
NAMES = {1: "up", -1: "down", 0: "none"}
TS = "%Y-%m-%dT%H:%M:%SZ"


def read_long(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path, dtype={"dataset_id": str})
    for col in ("timestamp_utc", "first_usable_origin_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def build(pkg: Path, start: str, end: str, tz: str = "Europe/Helsinki") -> pd.DataFrame:
    data = pkg / "data"
    try:
        inputs = read_long(data / "inputs.parquet")
    except (ImportError, FileNotFoundError, ValueError):
        inputs = read_long(data / "inputs.csv")
    long = pd.concat([inputs, read_long(data / "spot_nordpool.csv")], ignore_index=True)
    first = pd.Timestamp(start).tz_localize(tz).tz_convert("UTC")
    stop = (pd.Timestamp(end) + pd.Timedelta(days=1)).tz_localize(tz).tz_convert("UTC")
    rows = long.loc[long["series_id"].isin([IMBALANCE, DIRECTION, SPOT])
                    & (long["timestamp_utc"] >= first) & (long["timestamp_utc"] < stop)]
    value = rows.pivot(index="timestamp_utc", columns="series_id", values="value")
    usable = rows.loc[rows["series_id"] == IMBALANCE].set_index("timestamp_utc")["first_usable_origin_utc"]
    q = pd.date_range(first, stop, freq="15min", inclusive="left")
    value = value.reindex(q)
    return pd.DataFrame({
        "delivery_start_utc": q.strftime(TS),
        "imbalance_price": value[IMBALANCE].to_numpy(),
        "spot_price": value[SPOT].to_numpy(),
        "direction": value[DIRECTION].map(NAMES).to_numpy(),
        "first_usable_origin_utc": usable.reindex(q).dt.strftime(TS).to_numpy(),
    })


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", choices=sorted(PERIODS), default="fold_b")
    ap.add_argument("--package", help="starter package folder (the one with score.py)")
    ap.add_argument("--out", help="output CSV (default scoreboard/_local/actuals_<period>.csv)")
    a = ap.parse_args(argv)
    p = PERIODS[a.period]
    out = Path(a.out) if a.out else LOCAL / f"actuals_{a.period}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    build(package_dir(a.package), p["start"], p["end"]).to_csv(out, index=False, lineterminator="\n", float_format="%.10g")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
