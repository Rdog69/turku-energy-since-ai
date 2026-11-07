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
from src.features.build import (FEATURE_COLUMNS, FINGRID_RT2_COLUMNS, FINGRID_RT_COLUMNS, MEMORY_COLUMNS, TARGET_COLUMNS,
                                build_features)

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
        cols = FEATURE_COLUMNS + MEMORY_COLUMNS + [c for c in FINGRID_RT_COLUMNS + FINGRID_RT2_COLUMNS if c in full] + ["data_cutoff"]
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


def test_nordic_weather_ignores_unpublished_runs():
    """Same truncation test for the neighbouring-area weather (Sweden, Norway, Denmark, Estonia)."""
    from src.data.weather import load_nordic
    from src.features.build import NORDIC_COLUMNS
    nordic = load_nordic()
    if nordic is None:
        pytest.skip("Nordic weather runs not downloaded (python -m src.data.open_meteo --points nordic)")
    origins = _origins(n_random=6, seed=3)
    full = build_features(LONG, origins, with_targets=False, nordic=nordic)
    for t in origins:
        truncated = LONG.loc[LONG["first_usable_origin_utc"] <= t]
        part = build_features(truncated, pd.DatetimeIndex([t]), with_targets=False,
                              nordic={a: w.truncated(t) for a, w in nordic.items()})
        a = full.loc[full["origin"] == t, NORDIC_COLUMNS].reset_index(drop=True)
        b = part[NORDIC_COLUMNS].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"nordic features at {t}")


def _icon():
    from src.data.open_meteo import OUT_DIR
    from src.data.weather import WeatherIndex
    path = OUT_DIR / "icon_eu.parquet"
    if not path.exists():
        pytest.skip("ICON-EU runs not downloaded (python -m src.data.open_meteo --model icon_eu)")
    return WeatherIndex.load(path=path)


def test_icon_features_ignore_unpublished_runs():
    """Truncate BOTH weather models to runs usable at t: ICON and spread features must not change."""
    from src.features.build import WEATHER2_COLUMNS
    weather, icon = _weather(), _icon()
    origins = _origins(n_random=6, seed=4)
    full = build_features(LONG, origins, with_targets=False, weather=weather, weather2=icon)
    assert full["om_icon_wind_idx"].notna().mean() > 0.95, "ICON coverage unexpectedly low"
    for t in origins:
        truncated = LONG.loc[LONG["first_usable_origin_utc"] <= t]
        part = build_features(truncated, pd.DatetimeIndex([t]), with_targets=False,
                              weather=weather.truncated(t), weather2=icon.truncated(t))
        a = full.loc[full["origin"] == t, WEATHER2_COLUMNS].reset_index(drop=True)
        b = part[WEATHER2_COLUMNS].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"icon features at {t}")


def test_icon_run_used_was_published():
    from src.data.availability import to_ns
    icon = _icon()
    # publication rule: first usable = ceil_hour(run init + 5 h)
    assert ((icon.run_fu - icon.run_init) == 5 * 3_600_000_000_000).all()
    o = to_ns(_origins(n_random=20, seed=5))
    _, run = icon.lookup(o, o, "wind_idx")
    found = run >= 0
    fu = icon.run_fu[np.searchsorted(icon.run_init, run[found])]
    assert (fu <= o[found]).all()


def _wind_points():
    from src.models.wind_power import load_points
    pts = load_points()
    if not pts:
        pytest.skip("weather runs not downloaded")
    return pts


def test_wind_hat_features_ignore_unpublished_runs():
    """Learned wind production: drop every weather run not yet usable at t, features must not change."""
    from src.features.build import WINDHAT_COLUMNS
    from src.models.wind_power import WindPowerMap
    wm = WindPowerMap(_wind_points()).fit(build_index(LONG), VALIDATION_FIRST_ORIGIN)
    origins = _origins(n_random=6, seed=6)
    full = build_features(LONG, origins, with_targets=False, wind_map=wm)
    assert full["om_wind_hat"].notna().mean() > 0.9, "wind production coverage unexpectedly low"
    for t in origins:
        truncated = LONG.loc[LONG["first_usable_origin_utc"] <= t]
        part = build_features(truncated, pd.DatetimeIndex([t]), with_targets=False, wind_map=wm.truncated(t))
        a = full.loc[full["origin"] == t, WINDHAT_COLUMNS].reset_index(drop=True)
        b = part[WINDHAT_COLUMNS].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"wind production features at {t}")


def test_wind_map_fit_uses_only_data_published_by_cutoff():
    """Fitting with everything vs with only rows/runs usable at the cutoff must give the same weights."""
    from src.models.wind_power import WindPowerMap
    cutoff = pd.Timestamp("2026-07-31T21:00Z")          # start of the August check
    pts = _wind_points()
    a = WindPowerMap(pts).fit(build_index(LONG), cutoff)
    trunc = LONG.loc[LONG["first_usable_origin_utc"] <= cutoff]
    b = WindPowerMap({n: p.truncated(cutoff) for n, p in pts.items()}).fit(build_index(trunc), cutoff)
    np.testing.assert_allclose(a.coef, b.coef)
    assert a.intercept == pytest.approx(b.intercept)
    assert a.n_fit == b.n_fit > 1000


def test_town_features_ignore_unpublished_runs():
    """Town weather (solar and temperature revisions): drop every run not yet usable at t."""
    from src.data.weather import load_towns
    from src.features.build import TOWN_SOLAR_COLUMNS, TOWN_TEMP_COLUMNS
    towns = load_towns()
    if towns is None:
        pytest.skip("town weather not downloaded (python -m src.data.open_meteo --points solar)")
    cols = TOWN_SOLAR_COLUMNS + TOWN_TEMP_COLUMNS
    origins = _origins(n_random=6, seed=7)
    full = build_features(LONG, origins, with_targets=False, towns=towns)
    assert full["om_temp_town"].notna().mean() > 0.95, "town weather coverage unexpectedly low"
    for t in origins:
        truncated = LONG.loc[LONG["first_usable_origin_utc"] <= t]
        part = build_features(truncated, pd.DatetimeIndex([t]), with_targets=False, towns=towns.truncated(t))
        a = full.loc[full["origin"] == t, cols].reset_index(drop=True)
        b = part[cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"town features at {t}")


def test_history_rows_follow_package_rules_and_availability():
    """Pre-June history (config.HISTORY_PATH): rows are never usable earlier than the package's own
    publication rule allows, and features built with them ignore rows not yet published at t."""
    from src.config import DATA_START
    from src.data.load import load_history, with_history
    from src.features.build import HISTORY_COLUMNS
    hist = load_history(LONG)
    if hist is None:
        pytest.skip("history not imported (external_data/history/pkg_history.parquet)")
    assert (hist["timestamp_utc"] < DATA_START).all()
    for sid, g in hist.groupby("series_id"):
        p = LONG.loc[LONG["series_id"] == sid]
        lag = p["first_usable_origin_utc"] - p["timestamp_utc"]
        if (lag > pd.Timedelta(0)).all():   # measured series
            need = g["timestamp_utc"].dt.minute.map(lag.groupby(p["timestamp_utc"].dt.minute).max())
            assert ((g["first_usable_origin_utc"] - g["timestamp_utc"]) >= need).all(), sid

    combined = with_history(LONG)
    rng = np.random.default_rng(3)
    hours = pd.date_range("2025-03-06T00:00Z", "2026-05-31T20:00Z", freq="h")
    # history edges: 15-min day-ahead start (1 Oct 2025 CET), DST end 2025, the switch to the package
    fixed = ["2025-09-30T21:00Z", "2025-09-30T23:00Z", "2025-10-26T01:00Z", "2026-05-31T18:00Z",
             "2026-05-31T21:00Z", "2026-06-01T02:00Z"]
    origins = pd.DatetimeIndex(pd.to_datetime(fixed, utc=True)
                               .append(hours[rng.choice(len(hours), 6, replace=False)])).unique().sort_values()
    full = build_features(combined, origins, with_targets=False)
    assert full.loc[full["origin"] < DATA_START, "last_gap"].notna().mean() > 0.95
    cols = (FEATURE_COLUMNS + MEMORY_COLUMNS + HISTORY_COLUMNS
            + [c for c in FINGRID_RT_COLUMNS + FINGRID_RT2_COLUMNS if c in full] + ["data_cutoff"])
    for t in origins:
        truncated = combined.loc[combined["first_usable_origin_utc"] <= t]
        part = build_features(truncated, pd.DatetimeIndex([t]), with_targets=False)
        # Series that start in June 2026 (ENTSO-E, Fingrid real-time) have no rows yet at a history
        # origin, so the truncated build has no columns for them: they must be all-NaN in full too.
        part = part.reindex(columns=full.columns)
        a = full.loc[full["origin"] == t, cols].reset_index(drop=True)
        b = part[cols].reset_index(drop=True)
        pd.testing.assert_frame_equal(a, b, check_dtype=False, obj=f"history features at {t}")


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
