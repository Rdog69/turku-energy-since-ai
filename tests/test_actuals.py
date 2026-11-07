"""The actuals builder reproduces the organisers' file, and fold B respects the training cutoff."""
from __future__ import annotations

import io

import pandas as pd
import pytest

from src import config
from src.backtest.actuals import FLOAT_FORMAT, build_actuals
from src.data.availability import build_index
from src.data.load import load_long

try:
    LONG = load_long()
    PACKAGE = config.package_dir()
except FileNotFoundError:
    LONG = None

pytestmark = pytest.mark.skipif(LONG is None, reason="starter package not found")


def test_builder_matches_organisers_validation_actuals():
    p = config.PERIODS["validation"]
    ours = build_actuals(LONG, p["start"], p["end"])
    theirs = pd.read_csv(PACKAGE / "data" / "actuals_validation.csv", dtype=str, keep_default_na=False)
    assert list(ours.columns) == list(theirs.columns)
    assert len(ours) == len(theirs) == 28 * 96
    # Exact match of the written file, byte for byte (numbers, rounding, timestamps, labels).
    buf = io.StringIO()
    ours.to_csv(buf, index=False, lineterminator="\n", float_format=FLOAT_FORMAT)
    expected = (PACKAGE / "data" / "actuals_validation.csv").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert buf.getvalue() == expected
    # And numerically, as a second line of defence against formatting-only agreement.
    for col in ("imbalance_price", "spot_price"):
        assert (ours[col].astype(float) - theirs[col].astype(float)).abs().max() < 1e-9


def test_fold_b_actuals_complete():
    p = config.PERIODS["fold_b"]
    ours = build_actuals(LONG, p["start"], p["end"])
    assert len(ours) == 31 * 96
    assert not ours.isna().any().any()
    assert ours["delivery_start_utc"].iloc[0] == "2026-07-31T21:00:00Z"
    assert ours["delivery_start_utc"].iloc[-1] == "2026-08-31T20:45:00Z"
    assert set(ours["direction"]) <= {"up", "down", "none"}


def test_fold_b_training_rows_respect_cutoff():
    from src.backtest.run import training_table
    cutoff = config.FOLD_B_FIRST_ORIGIN
    train = training_table(LONG, build_index(LONG), cutoff)
    assert len(train) > 10_000
    assert (train["y_first_usable"] <= cutoff).all()
    assert (train["origin"] < cutoff).all()
    assert train["delivery"].max() < cutoff + pd.Timedelta(hours=10)
