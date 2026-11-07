"""Build a scoring actuals file for any backtest period from the package's long data.

Same format as the organisers' data/actuals_validation.csv:

    delivery_start_utc, imbalance_price, spot_price, direction, first_usable_origin_utc

* imbalance_price = fi_imbalance_price, spot_price = fi_spot_price (EUR/MWh);
  direction = fi_mfrr_direction (1 = up, -1 = down, 0 = none).
* first_usable_origin_utc: when the imbalance price became usable.
* One row per quarter-hour from 00:00 local on the first date to 24:00 local on the last.

tests/test_actuals.py checks that this reproduces the organisers' validation file exactly.
Approach from Pavlo's branch (femboystorming-pavlo, src/backtest/actuals.py).

Actuals are only used for scoring, never as features. The file holds spot prices, so it stays
in results/ (git-ignored) and is never published.

    python -m src.backtest.actuals --period fold_b
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from src import config
from src.data.load import DIRECTION, IMBALANCE, SPOT, load_long

DIRECTION_NAMES = {1: "up", -1: "down", 0: "none"}
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
FLOAT_FORMAT = "%.10g"      # the organisers' file writes 28 and 10.3, not 28.0 and 10.300000
COLUMNS = ["delivery_start_utc", "imbalance_price", "spot_price", "direction", "first_usable_origin_utc"]


def build_actuals(long: pd.DataFrame, first_date: str, last_date: str,
                  timezone: str = "Europe/Helsinki") -> pd.DataFrame:
    """Actuals for every quarter-hour of the local dates first_date..last_date (inclusive)."""
    first = pd.Timestamp(first_date).tz_localize(timezone).tz_convert("UTC")
    end = (pd.Timestamp(last_date) + pd.Timedelta(days=1)).tz_localize(timezone).tz_convert("UTC")
    rows = long.loc[long["series_id"].isin([IMBALANCE, DIRECTION, SPOT])
                    & (long["timestamp_utc"] >= first) & (long["timestamp_utc"] < end)]
    value = rows.pivot(index="timestamp_utc", columns="series_id", values="value")
    usable = rows.loc[rows["series_id"] == IMBALANCE].set_index("timestamp_utc")["first_usable_origin_utc"]
    quarters = pd.date_range(first, end, freq="15min", inclusive="left")
    value = value.reindex(quarters)
    out = pd.DataFrame({
        "delivery_start_utc": quarters.strftime(TS_FORMAT),
        "imbalance_price": value[IMBALANCE].to_numpy(),
        "spot_price": value[SPOT].to_numpy(),
        "direction": value[DIRECTION].map(DIRECTION_NAMES).to_numpy(),
        "first_usable_origin_utc": usable.reindex(quarters).dt.strftime(TS_FORMAT).to_numpy(),
    })
    return out[COLUMNS]


def write_actuals(period: str, path: Path | None = None) -> Path:
    p = config.PERIODS[period]
    path = path or config.RESULTS_DIR / "actuals" / f"actuals_{period}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    build_actuals(load_long(), p["start"], p["end"]).to_csv(
        path, index=False, lineterminator="\n", float_format=FLOAT_FORMAT)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=sorted(config.PERIODS), required=True)
    args = ap.parse_args(argv)
    print(f"wrote {write_actuals(args.period)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
