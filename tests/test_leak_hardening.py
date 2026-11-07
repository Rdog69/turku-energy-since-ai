"""Hardening tests for the availability layer and the submission writer (S17).

* `SeriesIndex.latest` is compared with an obviously-correct slow reference (filter by
  first_usable <= origin, take the newest timestamp), for timestamp AND value, on adversarial
  cases: a quarter published later than a newer one, nothing usable yet, first_usable exactly at
  the origin, and random series.
* Duplicate timestamps are rejected.
* `write_submission` refuses a data_cutoff after the origin and writes an empty cutoff when no
  measured data was usable.
* `training_table` only contains origins before the cutoff and targets published by the cutoff,
  for the validation, fold B and test cutoffs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import config
from src.data.availability import SeriesIndex, build_index, to_ns

T0 = pd.Timestamp("2026-07-01T00:00Z")


def _rows(ts_min, fu_min, values=None):
    ts = [T0 + pd.Timedelta(minutes=m) for m in ts_min]
    fu = [T0 + pd.Timedelta(minutes=m) for m in fu_min]
    values = list(range(1, len(ts) + 1)) if values is None else values
    return pd.DataFrame({"timestamp_utc": ts, "first_usable_origin_utc": fu, "value": np.asarray(values, float)})


def slow_latest(rows: pd.DataFrame, origin: pd.Timestamp):
    """Reference: newest timestamp among rows usable at the origin, and its value."""
    usable = rows.loc[rows["first_usable_origin_utc"] <= origin]
    if usable.empty:
        return -1, np.nan
    row = usable.loc[usable["timestamp_utc"].idxmax()]
    return int(to_ns(row["timestamp_utc"])[0]), float(row["value"])


def check_against_reference(rows: pd.DataFrame, origins: pd.DatetimeIndex):
    ts, vals = SeriesIndex(rows).latest(origins)
    for i, o in enumerate(origins):
        ref_ts, ref_val = slow_latest(rows, o)
        assert ts[i] == ref_ts, f"timestamp mismatch at {o}"
        if np.isnan(ref_val):
            assert np.isnan(vals[i]), f"value should be NaN at {o}"
        else:
            assert vals[i] == ref_val, f"value mismatch at {o}"


def test_latest_non_monotonic_publication():
    # the quarter at +15 min is published AFTER the newer quarter at +30 min
    rows = _rows([0, 15, 30, 45], [60, 180, 90, 240])
    origins = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=m) for m in (59, 60, 89, 90, 120, 179, 180, 210, 240, 600)])
    check_against_reference(rows, origins)
    ts, _ = SeriesIndex(rows).latest(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=120)]))
    assert ts[0] == to_ns(T0 + pd.Timedelta(minutes=30))[0]   # not the unpublished +15 / +45 quarters


def test_latest_nothing_usable_is_explicit():
    rows = _rows([0, 15], [60, 75])
    ts, vals = SeriesIndex(rows).latest(pd.DatetimeIndex([T0 + pd.Timedelta(minutes=30)]))
    assert ts[0] == -1 and np.isnan(vals[0])


def test_latest_first_usable_exactly_at_origin():
    rows = _rows([0, 15], [60, 120])
    idx = SeriesIndex(rows)
    at = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=120)])
    ts, vals = idx.latest(at)
    assert ts[0] == to_ns(T0 + pd.Timedelta(minutes=15))[0] and vals[0] == 2.0     # usable at fu == origin
    before = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=120) - pd.Timedelta(nanoseconds=1)])
    ts, vals = idx.latest(before)
    assert ts[0] == to_ns(T0)[0] and vals[0] == 1.0                                # not 1 ns earlier
    assert np.isnan(idx.value_at(to_ns(T0 + pd.Timedelta(minutes=15)), to_ns(before))[0])


def test_latest_random_series_match_reference():
    rng = np.random.default_rng(7)
    for _ in range(25):
        n = int(rng.integers(1, 60))
        ts_min = np.sort(rng.choice(2000, n, replace=False)) * 15
        fu_min = ts_min + rng.integers(0, 600, n)                  # irregular publication delays
        rows = _rows(ts_min, fu_min, rng.normal(size=n))
        origins = pd.DatetimeIndex([T0 + pd.Timedelta(minutes=int(m)) for m in rng.integers(-100, 40000, 40)])
        check_against_reference(rows, origins)


def test_duplicate_timestamps_are_rejected():
    rows = _rows([0, 15, 15], [60, 75, 80])
    with pytest.raises(ValueError, match="duplicate"):
        SeriesIndex(rows)
    long = rows.assign(series_id="x")
    with pytest.raises(ValueError):
        build_index(long)


# ----------------------------------------------------------------------------- write_submission
def _submission_inputs(cutoff, n=3):
    from src.config import HORIZON_STEPS
    origin = pd.Timestamp("2026-09-07T00:00Z")
    steps = np.arange(1, n + 1)
    feats = pd.DataFrame({"origin": origin, "step": steps,
                          "delivery": [origin + pd.Timedelta(minutes=15 * (s - 1)) for s in steps],
                          "data_cutoff": cutoff})
    pred = pd.DataFrame({"p10": -1.0, "p50": 0.0, "p90": 1.0, "p_up": 0.4, "p_down": 0.59, "p_none": 0.01,
                         "p_spike_high": 0.1, "p_spike_low": 0.1, "top_drivers": "a;b;c"}, index=feats.index)
    return feats, pred, steps, origin


def _template(path, feats):
    cols = ["forecast_origin_utc", "delivery_start_utc", "step", "p10", "p50", "p90", "p_up", "p_down",
            "p_none", "p_spike_high", "p_spike_low", "data_cutoff_utc", "top_drivers"]
    t = pd.DataFrame({c: "" for c in cols}, index=feats.index)
    t["forecast_origin_utc"] = feats["origin"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    t["step"] = feats["step"]
    t.to_csv(path, index=False)


def test_write_submission_rejects_cutoff_after_origin(tmp_path):
    from src.backtest.run import write_submission
    feats, pred, _, origin = _submission_inputs(pd.Timestamp("2026-09-07T00:15Z"))
    _template(tmp_path / "t.csv", feats)
    with pytest.raises(ValueError, match="data_cutoff"):
        write_submission(feats, pred, tmp_path / "t.csv", tmp_path / "out.csv")


def test_write_submission_writes_empty_cutoff_when_nothing_was_usable(tmp_path):
    from src.backtest.run import write_submission
    feats, pred, _, _ = _submission_inputs(pd.Timestamp("2026-09-06T22:00Z"))
    # what build_features emits when no measured quarter was usable
    feats["data_cutoff"] = pd.to_datetime(np.full(len(feats), np.iinfo(np.int64).min), utc=True)
    _template(tmp_path / "t.csv", feats)
    write_submission(feats, pred, tmp_path / "t.csv", tmp_path / "out.csv")
    out = pd.read_csv(tmp_path / "out.csv")
    assert out["data_cutoff_utc"].isna().all()                          # empty, not 1677-09-21


def test_write_submission_keeps_a_valid_cutoff(tmp_path):
    from src.backtest.run import write_submission
    feats, pred, _, _ = _submission_inputs(pd.Timestamp("2026-09-06T22:00Z"))
    _template(tmp_path / "t.csv", feats)
    write_submission(feats, pred, tmp_path / "t.csv", tmp_path / "out.csv")
    out = pd.read_csv(tmp_path / "out.csv")
    assert (out["data_cutoff_utc"] == "2026-09-06T22:00:00Z").all()


# ----------------------------------------------------------------------------- training_table
@pytest.fixture(scope="module")
def long_and_index():
    from src.data.load import load_long_all
    try:
        long = load_long_all()
    except FileNotFoundError:
        pytest.skip("starter package not found")
    return long, build_index(long)


@pytest.mark.parametrize("name,cutoff", [
    ("validation", config.VALIDATION_FIRST_ORIGIN),
    ("fold_b", config.FOLD_B_FIRST_ORIGIN),
    ("test", config.TRAIN_CUTOFF),
])
def test_training_table_respects_the_cutoff(long_and_index, name, cutoff):
    from src.backtest.run import training_table
    long, index = long_and_index
    train = training_table(long, index, cutoff)
    assert len(train) > 0
    assert (train["origin"] < cutoff).all(), f"{name}: training origin at or after the cutoff"
    assert (train["y_first_usable"] <= cutoff).all(), f"{name}: target published after the cutoff"
    assert (train["data_cutoff"] < train["origin"]).all()
