"""Leakage tests. If any of these fail, the submission would score 0. Fix before anything else.

The strongest check is `test_features_ignore_unpublished_rows`: for an origin t, building the
features from the full data must give exactly the same result as building them from data where
every row with first_usable_origin_utc > t has been deleted. Any feature that peeks at the future
changes when the future disappears.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.config import VALIDATION_FIRST_ORIGIN, TEST_FIRST_ORIGIN
from src.data.availability import build_index, wide_at
from src.data.load import IMBALANCE, SPOT, load_long_all
from src.features.build import FEATURE_COLUMNS, FINGRID_RT_COLUMNS, TARGET_COLUMNS, build_features

try:
    LONG = load_long_all()   # package + downloaded Fingrid real-time series, if present
except FileNotFoundError:  # teammates without the package can still run the rest
    LONG = None

pytestmark = pytest.mark.skipif(LONG is None, reason="starter package not found")

# Edges and awkward times: data start, around spot publication (11:00/12:00 UTC),
# the DST change (25 Oct 00:00-01:00 UTC), period boundaries, plus random hours.
FIXED = ["2026-06-01T03:00Z", "2026-07-15T10:00Z", "2026-07-15T11:00Z", "2026-07-15T12:00Z",
         "2026-09-06T21:00Z", "2026-10-04T20:00Z", "2026-10-04T21:00Z", "2026-10-24T23:00Z",
         "2026-10-25T00:00Z", "2026-10-25T01:00Z", "2026-10-26T11:00Z", "2026-11-01T21:00Z"]


def _origins(n_random=12, seed=0):
    rng = np.random.default_rng(seed)
    all_hours = pd.date_range("2026-06-01T03:00Z", "2026-11-01T21:00Z", freq="h")
    picks = all_hours[rng.choice(len(all_hours), n_random, replace=False)]
    return pd.DatetimeIndex(pd.to_datetime(FIXED, utc=True).append(picks)).unique().sort_values()


@pytest.fixture(scope="module")
def full_features():
    origins = _origins()
    return origins, build_features(LONG, origins, with_targets=False)


def test_features_ignore_unpublished_rows(full_features):
    origins, full = full_features
    for t in origins:
        truncated = LONG.loc[LONG["first_usable_origin_utc"] <= t]
        part = build_features(truncated, pd.DatetimeIndex([t]), with_targets=False)
        cols = FEATURE_COLUMNS + [c for c in FINGRID_RT_COLUMNS if c in full] + ["data_cutoff"]
        a = full.loc[full["origin"] == t, cols].reset_index(drop=True)
        b = part[cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"features at {t}")


def test_matches_reference_filter(full_features):
    """Spot-check the fast lookups against the organisers' rows_available_at() logic."""
    origins, full = full_features
    for t in origins[::3]:
        wide = wide_at(LONG, t)
        rows = full.loc[full["origin"] == t].set_index("delivery")
        # day-ahead value at each delivery quarter
        for col, sid in (("spot", SPOT), ("wind_fc", "fi_wind_fc_da")):
            ref = wide[sid].reindex(rows.index) if sid in wide else pd.Series(np.nan, rows.index)
            np.testing.assert_allclose(rows[col].to_numpy(), ref.to_numpy(), equal_nan=True)
        # newest usable imbalance price and the gap to spot at that quarter
        imb = wide[IMBALANCE].dropna()
        ts = imb.index[-1]
        assert rows["last_imb"].iloc[0] == pytest.approx(imb.iloc[-1])
        assert rows["last_gap"].iloc[0] == pytest.approx(imb.iloc[-1] - wide.loc[ts, SPOT])
        last4 = (wide[IMBALANCE] - wide[SPOT]).loc[:ts].dropna().iloc[-4:]
        assert rows["mean_gap_last4"].iloc[0] == pytest.approx(last4.mean())


def test_data_cutoff_before_origin(full_features):
    _, full = full_features
    assert (full["data_cutoff"] < full["origin"]).all()


def test_targets_are_not_features():
    assert not set(TARGET_COLUMNS) & set(FEATURE_COLUMNS)
    assert not any(c.startswith("y_") for c in FEATURE_COLUMNS)


def test_spot_and_wind_cover_full_horizon(full_features):
    _, full = full_features
    assert full["spot"].notna().all()
    assert full["wind_fc"].notna().all()


def _weather():
    from src.data.open_meteo import OUT_DIR
    from src.data.weather import WeatherIndex
    path = OUT_DIR / "ecmwf_ifs025.parquet"
    if not path.exists():
        pytest.skip("weather runs not downloaded (python -m src.data.open_meteo)")
    return WeatherIndex.load(path=path)


def test_weather_features_ignore_unpublished_runs():
    """Same truncation test for the weather runs: drop every run not yet usable at t."""
    from src.features.build import WEATHER_COLUMNS
    weather = _weather()
    origins = _origins(n_random=8, seed=1)
    full = build_features(LONG, origins, with_targets=False, weather=weather)
    assert full["om_wind_idx"].notna().mean() > 0.95, "weather coverage unexpectedly low"
    for t in origins:
        truncated = LONG.loc[LONG["first_usable_origin_utc"] <= t]
        part = build_features(truncated, pd.DatetimeIndex([t]), with_targets=False,
                              weather=weather.truncated(t))
        a = full.loc[full["origin"] == t, WEATHER_COLUMNS].reset_index(drop=True)
        b = part[WEATHER_COLUMNS].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"weather features at {t}")


def test_weather_run_used_was_published():
    from src.data.availability import to_ns
    weather = _weather()
    origins = _origins(n_random=20, seed=2)
    o = to_ns(origins)
    _, run = weather.lookup(o, o, "wind_idx")
    found = run >= 0
    fu = weather.run_fu[np.searchsorted(weather.run_init, run[found])]
    assert (fu <= o[found]).all()


def test_training_rows_known_before_cutoff():
    """Training rows for the validation run must have targets published before it starts."""
    index = build_index(LONG)
    origins = pd.date_range("2026-08-30T00:00Z", VALIDATION_FIRST_ORIGIN, freq="h", inclusive="left")
    f = build_features(LONG, origins, index=index)
    train = f.loc[f["y_first_usable"] <= VALIDATION_FIRST_ORIGIN]
    assert len(train) > 0
    assert (train["y_first_usable"] <= VALIDATION_FIRST_ORIGIN).all()
    assert (train["delivery"] < VALIDATION_FIRST_ORIGIN).all()
    assert VALIDATION_FIRST_ORIGIN < TEST_FIRST_ORIGIN
