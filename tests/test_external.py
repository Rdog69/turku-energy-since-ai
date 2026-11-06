"""Tests for the master external Fingrid data (src/data/external_long.py) and its availability rules.

Files are read from external_data/fingrid/. Tests skip when the files (or the starter package) are
missing. The rule checks below compute the expected first_usable_origin_utc independently of the
loader (plain datetime / zoneinfo arithmetic), straight from the documented rules in SOURCES.md.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import pytest

from src.data import external_long as xl
from src.data.availability import SeriesIndex, available_at
from src.data.load import LONG_COLUMNS

HELSINKI = ZoneInfo("Europe/Helsinki")
HAVE_FILES = (xl.EXT_DIR / "rt_main.csv.gz").exists() and (xl.EXT_DIR / "extra_main.csv.gz").exists()
needs_files = pytest.mark.skipif(not HAVE_FILES, reason="external_data/fingrid/*_main.csv.gz missing")

Q = pd.Timedelta(minutes=15)
# 15-min series: period end = timestamp + 15 min. Hourly series (value repeated per quarter of the
# hour): period end = end of the hour.
HOURLY = {"fg176_imbalance_power_fi_se", "fg243_mfrr_up_bids_sum", "fg251_mfrr_last_down_bid_price"}
PERIOD_DELAY_MIN = {"fg75_wind_15min": 30, "fg268_wind_capacity": 24 * 60, "fg243_mfrr_up_bids_sum": 60,
                    "fg176_imbalance_power_fi_se": 60, "fg251_mfrr_last_down_bid_price": 60}


def _raw(name: str) -> pd.DataFrame:
    return xl._read(xl.EXT_DIR / name)


@pytest.fixture(scope="module")
def default_long():
    return xl.load_external_long()


# --- default scope --------------------------------------------------------------------------

@needs_files
def test_default_loads_only_main_window_and_expected_series(default_long):
    d = default_long
    assert list(d.columns) == LONG_COLUMNS
    assert d["timestamp_utc"].min() >= pd.Timestamp("2026-05-25", tz="UTC")
    assert d["timestamp_utc"].max() < pd.Timestamp("2026-11-03", tz="UTC")
    ids = set(d["series_id"])
    assert {"fg198_surplus_deficit_rt", "fg186_surplus_deficit_cum_rt", "fg192_production_rt",
            "fg242_production_plan_da", "fg243_mfrr_up_bids_sum", "fg75_wind_15min",
            "fg268_wind_capacity"} <= ids
    assert not any(s.startswith(("fg319", "fg369", "fg246", "fg165")) for s in ids), \
        "package history must not be loaded by default"
    assert not d.duplicated(["series_id", "timestamp_utc"]).any()
    assert str(d["timestamp_utc"].dt.tz) == "UTC" and str(d["first_usable_origin_utc"].dt.tz) == "UTC"


@needs_files
def test_pending_history_is_opt_in():
    assert xl.load_external_long(period="main").equals(xl.load_external_long())
    if (xl.EXT_DIR / "rt_last_autumn.csv.gz").exists():
        old = xl.load_external_long(period="last_autumn")
        assert len(old) and old["timestamp_utc"].max() < pd.Timestamp("2025-12-01", tz="UTC")
    if (xl.EXT_DIR / "package_history.csv.gz").exists():
        hist = xl.load_external_long("fingrid_package", "history")
        assert len(hist) and hist["timestamp_utc"].max() < pd.Timestamp("2026-06-01", tz="UTC")
    with pytest.raises(ValueError):
        xl.load_external_long(period="2025")
    with pytest.raises(ValueError):
        xl.load_external_long(groups=("nope",))


@needs_files
def test_frank_duplicates_dropped(default_long):
    assert not set(default_long["dataset_id"].astype(int)) & set(xl.FRANK_DUPLICATES)
    assert not set(default_long["series_id"]) & set(xl.FRANK_DUPLICATES.values())
    # with the flag off they are there, and fu agree with Frank's copy wherever both exist
    full = xl.load_external_long(drop_frank_duplicates=False)
    from src.data.fingrid import load_long_extra
    frank = load_long_extra()
    if frank is None:
        pytest.skip("Frank's fingrid_rt.parquet missing")
    for ds, fid in xl.FRANK_DUPLICATES.items():
        a = frank[frank["series_id"] == fid].set_index("timestamp_utc")["first_usable_origin_utc"]
        b = full[full["dataset_id"].astype(int) == ds].set_index("timestamp_utc")["first_usable_origin_utc"]
        both = a.index.intersection(b.index)
        assert len(both) > 10000
        assert (a.loc[both] == b.loc[both]).all(), fid


# --- availability rules ----------------------------------------------------------------------

@needs_files
def test_rt_series_fu_is_quarter_end_plus_30min_ceil_hour():
    rt = _raw("rt_main.csv.gz")
    assert len(rt)
    expected = (rt["timestamp_utc"] + Q + pd.Timedelta(minutes=30)).dt.ceil("h")
    assert (rt["first_usable_origin_utc"] == expected).all()
    # and the loader reproduces it for the non-duplicate series
    d = xl.load_external_long("fingrid_rt")
    exp = (d["timestamp_utc"] + Q + pd.Timedelta(minutes=30)).dt.ceil("h")
    assert (d["first_usable_origin_utc"] == exp).all()


@needs_files
def test_period_series_fu_is_period_end_plus_delay_ceil_hour():
    ex = _raw("extra_main.csv.gz")
    for sid, delay in PERIOD_DELAY_MIN.items():
        g = ex[ex["series_id"] == sid]
        assert len(g), sid
        ts = g["timestamp_utc"]
        end = ts.dt.floor("h") + pd.Timedelta(hours=1) if sid in HOURLY else ts + Q
        expected = (end + pd.Timedelta(minutes=delay)).dt.ceil("h")
        assert (g["first_usable_origin_utc"] == expected).all(), sid
        assert delay == xl.DELAY_RULES[sid].delay_min, f"{sid}: test and fetcher disagree on the delay"


@needs_files
def test_242_published_18_local_on_day_before_delivery():
    g = _raw("extra_main.csv.gz").query("series_id == 'fg242_production_plan_da'")
    assert len(g)
    day_start, expected = [], []
    for ts in g["timestamp_utc"]:
        local = ts.to_pydatetime().astimezone(HELSINKI)
        d = local.date()
        day_start.append(datetime.combine(d, time(0), tzinfo=HELSINKI))
        pub = datetime.combine(d - timedelta(days=1), time(18), tzinfo=HELSINKI)
        expected.append(pd.Timestamp(pub).tz_convert("UTC").ceil("h"))
    fu = g["first_usable_origin_utc"].reset_index(drop=True)
    assert (fu == pd.Series(expected, dtype=fu.dtype)).all()
    # usable strictly before the delivery day starts (and so before every delivery quarter)
    assert (fu <= pd.Series(pd.to_datetime(day_start, utc=True), dtype=fu.dtype)).all()
    assert (fu < g["timestamp_utc"].reset_index(drop=True)).all()
    # the loader's rule function gives the same answer
    rule = xl.rule_first_usable("fg242_production_plan_da", g["timestamp_utc"])
    assert (rule.reset_index(drop=True) == fu).all()


def _all_available_periods():
    out = []
    for g, files in xl.FILES.items():
        for p, name in files.items():
            if (xl.EXT_DIR / name).exists():
                out.append((g, p))
    return out


@needs_files
@pytest.mark.parametrize("group,period", _all_available_periods())
def test_measured_series_usable_at_least_15min_after_timestamp(group, period):
    """Universal invariant: a measured value cannot be known before its quarter has ended."""
    d = xl.load_external_long(group, period)
    measured = d.loc[~d["series_id"].isin(xl.PLAN_SERIES)]
    assert len(measured)
    assert (measured["first_usable_origin_utc"] >= measured["timestamp_utc"] + Q).all()
    # plans/forecasts are published before delivery but never before the day before
    plans = d.loc[d["series_id"].isin(xl.PLAN_SERIES)]
    if len(plans):
        assert (plans["first_usable_origin_utc"] >= plans["timestamp_utc"] - pd.Timedelta(hours=48)).all()


@needs_files
@pytest.mark.parametrize("group,period", _all_available_periods())
def test_loaded_fu_never_earlier_than_documented_rule(group, period):
    d = xl.load_external_long(group, period)
    for sid, g in d.groupby("series_id"):
        rule = xl.rule_first_usable(sid, g["timestamp_utc"])
        assert (g["first_usable_origin_utc"] >= rule).all(), sid


def test_loader_makes_too_early_fu_conservative():
    ts = pd.date_range("2026-07-01T00:00Z", periods=8, freq="15min")
    df = pd.DataFrame({"series_id": "fg198_surplus_deficit_rt", "source": "fingrid", "dataset_id": "198",
                       "timestamp_utc": ts, "value": 1.0, "unit": "MW",
                       "first_usable_origin_utc": ts + Q})   # file claims usable right at quarter end
    out, pushed = xl._conservative_fu(df)
    assert pushed["fg198_surplus_deficit_rt"] == 8
    assert (out["first_usable_origin_utc"] == (ts + Q + pd.Timedelta(minutes=30)).ceil("h")).all()
    late = df.assign(first_usable_origin_utc=ts + pd.Timedelta(days=3))   # later than the rule: kept
    out2, pushed2 = xl._conservative_fu(late)
    assert pushed2["fg198_surplus_deficit_rt"] == 0
    assert (out2["first_usable_origin_utc"] == late["first_usable_origin_utc"]).all()
    with pytest.raises(ValueError):
        xl._conservative_fu(df.assign(series_id="fg999_unknown"))


@needs_files
def test_main_files_agree_with_documented_rules():
    """Nothing in the default files is pushed later by the loader (they obey their own rules)."""
    assert xl.fu_audit(period="main") == {}


# --- integration with load_long_all / existing features ---------------------------------------

def _package_available():
    try:
        from src.data.load import load_long
        load_long()
        return True
    except FileNotFoundError:
        return False


needs_package = pytest.mark.skipif(not _package_available(), reason="starter package not found")


@needs_files
@needs_package
def test_load_long_all_contains_external_series_without_clashes():
    from src.data.load import load_long_all
    long = load_long_all()
    ids = set(long["series_id"])
    assert {"fg_wind_rt", "fg_freq_rt", "fg198_surplus_deficit_rt", "fg242_production_plan_da"} <= ids
    assert not long.duplicated(["series_id", "timestamp_utc"]).any()
    assert list(long.columns) == LONG_COLUMNS


@needs_files
@needs_package
def test_existing_features_unchanged_by_external_series():
    """Features built from load_long_all() (now with the master series) are bit-identical to the
    ones built from the old table (package + Frank's Fingrid series only), weather included."""
    from src.data.availability import build_index
    from src.data.fingrid import load_long_extra
    from src.data.load import load_long, load_long_all
    from src.features.build import FEATURE_COLUMNS, FINGRID_RT_COLUMNS, WEATHER_COLUMNS, build_features

    old = pd.concat([load_long(), load_long_extra()[LONG_COLUMNS]], ignore_index=True)
    new = load_long_all()
    assert len(new) > len(old)
    weather = None
    try:
        from src.data.weather import WeatherIndex
        weather = WeatherIndex.load("ecmwf_ifs025")
    except FileNotFoundError:
        pass
    rng = np.random.default_rng(7)
    hours = pd.date_range("2026-06-03T00:00Z", "2026-11-01T21:00Z", freq="h")
    # 18 random origins plus the DST change and the first validation / test origins
    origins = pd.DatetimeIndex(hours[rng.choice(len(hours), 18, replace=False)]).union(
        pd.to_datetime(["2026-10-25T00:00Z", "2026-09-06T21:00Z", "2026-10-04T21:00Z"]))
    f_old = build_features(old, origins, index=build_index(old), with_targets=False, weather=weather)
    f_new = build_features(new, origins, index=build_index(new), with_targets=False, weather=weather)
    cols = FEATURE_COLUMNS + FINGRID_RT_COLUMNS + (WEATHER_COLUMNS if weather is not None else [])
    assert len(f_old) == len(f_new) > 0
    assert f_old[FINGRID_RT_COLUMNS].notna().any().all()
    pd.testing.assert_frame_equal(f_old[cols].reset_index(drop=True), f_new[cols].reset_index(drop=True),
                                  check_exact=True)


# --- generic availability check on every external series --------------------------------------

@needs_files
def test_latest_equals_newest_reference_row_for_every_external_series(default_long):
    origins = pd.to_datetime(["2026-06-01T03:00Z", "2026-07-15T11:00Z", "2026-09-06T21:00Z",
                              "2026-10-04T21:00Z", "2026-10-25T00:00Z", "2026-10-25T01:00Z",
                              "2026-11-01T21:00Z"], utc=True)
    for sid, rows in default_long.groupby("series_id"):
        idx = SeriesIndex(rows)
        ts, val = idx.latest(origins)
        for k, t in enumerate(origins):
            usable = available_at(rows, t)
            if usable.empty:
                assert ts[k] == -1 and np.isnan(val[k]), (sid, t)
                continue
            newest = usable.loc[usable["timestamp_utc"].idxmax()]
            assert ts[k] == newest["timestamp_utc"].as_unit("ns").value, (sid, t)
            assert val[k] == pytest.approx(newest["value"]), (sid, t)
