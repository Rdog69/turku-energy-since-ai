"""The actuals builder must reproduce the organisers' own validation actuals exactly,
so scores on other periods (August) are computed the same way as the official ones."""
from __future__ import annotations

import pandas as pd
import pytest

from src import config
from src.backtest.actuals import FLOAT_FORMAT, build_actuals

try:
    PKG = config.package_dir()
except FileNotFoundError:
    PKG = None

pytestmark = pytest.mark.skipif(PKG is None, reason="starter package not found")


def test_rebuilds_organisers_validation_actuals():
    from src.data.load import load_long
    p = config.PERIODS["validation"]
    ours = build_actuals(load_long(), p["start"], p["end"])
    text = ours.to_csv(index=False, lineterminator="\n", float_format=FLOAT_FORMAT)
    official = (PKG / "data" / "actuals_validation.csv").read_text(encoding="utf-8")
    assert text.replace("\r\n", "\n") == official.replace("\r\n", "\n")


def test_fold_b_covers_august_without_gaps():
    from src.data.load import load_long
    p = config.PERIODS["fold_b"]
    a = build_actuals(load_long(), p["start"], p["end"])
    assert len(a) == 31 * 96
    assert a["delivery_start_utc"].iloc[0] == "2026-07-31T21:00:00Z"
    assert a["imbalance_price"].notna().mean() > 0.99
    assert set(a["direction"].dropna()) <= {"up", "down", "none"}
