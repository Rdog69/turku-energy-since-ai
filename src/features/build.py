"""Leakage-safe feature table: one row per (forecast origin, step).

Every value comes from `SeriesIndex.value_at` (a row at a given timestamp, usable at the origin)
or `SeriesIndex.latest` (the newest usable row at the origin), so the availability rule is
enforced in one place. `tests/test_availability.py` rebuilds a sample of rows with the slow
reference filter and checks that they match.

Package data only (v1). External sources get added here once they have an honest
first_usable_origin_utc.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import HORIZON_STEPS, SPIKE_MARGIN, STEP
from src.data.availability import SeriesIndex, build_index, to_ns
from src.data.load import DIRECTION, IMBALANCE, SPOT

NS_PER_QUARTER = STEP.value

# Series known in advance for the delivery quarter (day-ahead products and calendar).
DELIVERY_SERIES = {
    SPOT: "spot",
    "fi_wind_fc_da": "wind_fc",
    "fi_consumption_fc_da": "cons_fc",
    "fi_solar_fc_da": "solar_fc",
    "fi_ee_capacity_da": "cap_fi_ee",
    "ee_fi_capacity_da": "cap_ee_fi",
    "cal_hour_local": "hour",
    "cal_weekday_local": "weekday",
    "cal_is_holiday_fi": "holiday",
    "cal_is_dst": "dst",
}

# Realised series: we use their newest usable value at the origin.
LATEST_SERIES = {
    IMBALANCE: "last_imb",
    DIRECTION: "last_dir",
    "fi_mfrr_up_activated": "last_mfrr_up_mw",
    "fi_mfrr_down_activated": "last_mfrr_down_mw",
    "fi_mfrr_up_price": "last_mfrr_up_price",
    "fi_mfrr_down_price": "last_mfrr_down_price",
    "fi_consumption": "last_cons",
    "fi_production": "last_prod",
    "fi_se1_flow": "last_flow_se1",
    "fi_se3_flow": "last_flow_se3",
    "fi_no4_flow": "last_flow_no4",
    "fi_ee_flow": "last_flow_ee",
    "se1_imbalance_price_long": "last_se1_imb",
    "se3_imbalance_price_long": "last_se3_imb",
    "ee_imbalance_price_long": "last_ee_imb",
}

TARGET_COLUMNS = ["y_price", "y_gap", "y_dir", "y_spike_high", "y_spike_low", "y_first_usable"]


def _grid(origins: pd.DatetimeIndex) -> pd.DataFrame:
    steps = np.arange(1, HORIZON_STEPS + 1)
    o = np.repeat(to_ns(origins), HORIZON_STEPS)
    k = np.tile(steps, len(origins))
    d = o + (k - 1) * NS_PER_QUARTER
    return pd.DataFrame({
        "origin": pd.to_datetime(o, utc=True),
        "step": k,
        "delivery": pd.to_datetime(d, utc=True),
    })


def add_weather(f: pd.DataFrame, index: dict[str, SeriesIndex], weather) -> pd.DataFrame:
    """Weather-run features (see src/data/weather.py). All lookups are availability-aware."""
    o = to_ns(f["origin"])
    d = to_ns(f["delivery"])
    wind, run = weather.lookup(o, d, "wind_idx")
    # The run that was available when Fingrid published the day-ahead wind forecast for this
    # quarter: look it up "as of" that publication time (always <= origin when the DA row is
    # usable, and clipped to the origin to be safe).
    da_time = np.minimum(index["fi_wind_fc_da"].first_usable_at(d), o)
    wind_da, _ = weather.lookup(da_time, d, "wind_idx")
    f["om_wind_idx"] = wind
    f["om_wind_idx_da"] = wind_da
    f["om_wind_rev"] = wind - wind_da
    f["om_wind_speed"], _ = weather.lookup(o, d, "wind_speed")
    f["om_temp"], _ = weather.lookup(o, d, "temp")
    f["om_icing"], _ = weather.lookup(o, d, "icing")
    f["om_lead_h"] = np.where(run >= 0, (d - run) / 3.6e12, np.nan)
    # Revision scaled to MW using the day-ahead forecast as the capacity reference.
    f["om_wind_rev_mw"] = f["om_wind_rev"] * f["wind_fc"] / np.fmax(f["om_wind_idx_da"], 0.05)
    return f


NORDIC_AREAS = ("se", "no", "dk", "ee")


def add_weather_nordic(f: pd.DataFrame, index: dict[str, SeriesIndex], nordic: dict) -> pd.DataFrame:
    """Neighbouring areas' wind and its revision since the day-ahead forecast was made.

    Same availability rule as the Finnish weather: newest run usable at the origin, compared with
    the run usable when Fingrid published its day-ahead wind forecast for that quarter.
    """
    o = to_ns(f["origin"])
    d = to_ns(f["delivery"])
    da_time = np.minimum(index["fi_wind_fc_da"].first_usable_at(d), o)
    revs = []
    for area in NORDIC_AREAS:
        w = nordic.get(area)
        if w is None:
            f[f"om_{area}_wind_idx"] = np.nan
            f[f"om_{area}_wind_rev"] = np.nan
            continue
        now, _ = w.lookup(o, d, "wind_idx")
        then, _ = w.lookup(da_time, d, "wind_idx")
        f[f"om_{area}_wind_idx"] = now
        f[f"om_{area}_wind_rev"] = now - then
        revs.append(now - then)
    f["om_nordic_wind_rev"] = np.nanmean(np.vstack(revs), axis=0) if revs else np.nan
    return f


def add_weather2(f: pd.DataFrame, index: dict[str, SeriesIndex], weather, icon) -> pd.DataFrame:
    """Second weather model (ICON-EU) and its disagreement with ECMWF.

    Ported from Pavlo's branch (femboystorming-pavlo, split_all_icon). Same availability-aware
    lookups as add_weather: the newest ICON run usable at the origin, and the ICON run usable when
    Fingrid published its day-ahead wind forecast.
    """
    o = to_ns(f["origin"])
    d = to_ns(f["delivery"])
    wind, _ = icon.lookup(o, d, "wind_idx")
    da_time = np.minimum(index["fi_wind_fc_da"].first_usable_at(d), o)
    wind_da, _ = icon.lookup(da_time, d, "wind_idx")
    f["om_icon_wind_idx"] = wind
    f["om_icon_wind_rev"] = wind - wind_da
    ecmwf = weather.lookup(o, d, "wind_idx")[0] if weather is not None else np.nan
    f["om_model_spread"] = np.abs(ecmwf - wind)
    return f


def add_wind_hat(f: pd.DataFrame, index: dict[str, SeriesIndex], wind_map) -> pd.DataFrame:
    """Wind production predicted by the learned point weights (src/models/wind_power.py), its gap
    to Fingrid's day-ahead wind forecast, and its revision since that forecast was published."""
    o = to_ns(f["origin"])
    d = to_ns(f["delivery"])
    hat = wind_map.predict(o, d)
    da_time = np.minimum(index["fi_wind_fc_da"].first_usable_at(d), o)
    f["om_wind_hat"] = hat
    f["om_wind_hat_err"] = hat - f["wind_fc"].to_numpy(dtype=float)
    f["om_wind_hat_rev"] = hat - wind_map.predict(da_time, d)
    return f


def add_towns(f: pd.DataFrame, index: dict[str, SeriesIndex], towns) -> pd.DataFrame:
    """Town weather (src/data/weather.load_towns): solar radiation and temperature, and how much the
    newest usable run revised them since Fingrid published its day-ahead solar and consumption
    forecasts. Same availability rule as add_weather: runs usable at the origin, and the
    day-ahead comparison point is never later than the origin."""
    o = to_ns(f["origin"])
    d = to_ns(f["delivery"])
    rad, _ = towns.lookup(o, d, "rad")
    rad_da, _ = towns.lookup(np.minimum(index["fi_solar_fc_da"].first_usable_at(d), o), d, "rad")
    temp, _ = towns.lookup(o, d, "temp")
    temp_da, _ = towns.lookup(np.minimum(index["fi_consumption_fc_da"].first_usable_at(d), o), d, "temp")
    f["om_rad_rev"] = rad - rad_da
    # Revision scaled to MW with the day-ahead solar forecast; the 50 W/m2 floor keeps dawn and
    # dusk from blowing the ratio up.
    f["om_solar_rev_mw"] = f["solar_fc"].to_numpy(dtype=float) * np.clip(
        (rad - rad_da) / np.fmax(rad_da, 50.0), -1.0, 2.0)
    f["om_temp_town"] = temp
    f["om_temp_rev"] = temp - temp_da
    return f


def build_features(long: pd.DataFrame, origins, index: dict[str, SeriesIndex] | None = None,
                   with_targets: bool = True, weather=None, nordic=None, weather2=None,
                   wind_map=None, towns=None) -> pd.DataFrame:
    """Feature (and optional target) table for the given hourly origins.

    weather: optional WeatherIndex (src/data/weather.py) to add the om_* columns.
    weather2: optional second-model WeatherIndex (ICON-EU) for the om_icon_* / spread columns.
    """
    index = index or build_index(long)
    origins = pd.DatetimeIndex(origins).tz_convert("UTC").as_unit("ns")
    if origins.has_duplicates:
        raise ValueError("duplicate forecast origins")
    g = _grid(origins)
    o_ns = to_ns(g["origin"])
    d_ns = to_ns(g["delivery"])
    origin_ns = to_ns(origins)

    def at(sid: str, offset_quarters: int = 0) -> np.ndarray:
        if sid not in index:
            return np.full(len(g), np.nan)
        return index[sid].value_at(d_ns + offset_quarters * NS_PER_QUARTER, o_ns)

    f = g.copy()

    # --- known in advance for the delivery quarter ---
    for sid, name in DELIVERY_SERIES.items():
        f[name] = at(sid)
    f["spot_prev"] = at(SPOT, -1)
    f["spot_next"] = at(SPOT, +1)
    f["spot_ramp_in"] = f["spot"] - f["spot_prev"]
    f["spot_ramp_out"] = f["spot_next"] - f["spot"]
    f["spot_abs_ramp"] = np.fmax(f["spot_ramp_in"].abs(), f["spot_ramp_out"].abs())
    f["spot_minus_horizon_mean"] = f["spot"] - f.groupby("origin")["spot"].transform("mean")
    f["wind_fc_prev_h"] = at("fi_wind_fc_da", -4)
    f["wind_fc_ramp_1h"] = f["wind_fc"] - f["wind_fc_prev_h"]
    f["wind_share"] = f["wind_fc"] / f["cons_fc"]
    f["residual_load_fc"] = f["cons_fc"] - f["wind_fc"] - f["solar_fc"]
    f["quarter"] = pd.DatetimeIndex(g["delivery"]).minute // 15

    # --- newest usable realised values at the origin (same for every step of an origin) ---
    per_origin = pd.DataFrame(index=origins)
    latest_ts = []
    for sid, name in LATEST_SERIES.items():
        if sid not in index:
            per_origin[name] = np.nan
            continue
        ts, vals = index[sid].latest(origins)
        latest_ts.append(ts)
        per_origin[name] = vals
        if sid == IMBALANCE:
            imb_ts = ts
            # spot at the same quarter as the latest imbalance price (spot is published earlier)
            per_origin["last_gap"] = vals - index[SPOT].value_at(ts, origin_ns)
            per_origin["imb_age_q"] = np.where(ts >= 0, (origin_ns - ts) / NS_PER_QUARTER, np.nan)
        if sid == "fi_consumption":
            per_origin["last_cons_err"] = vals - index["fi_consumption_fc_da"].value_at(ts, origin_ns)
        if sid.endswith("_imbalance_price_long"):
            # neighbour imbalance relative to the Finnish spot of the same quarter
            per_origin[name + "_gap"] = vals - index[SPOT].value_at(ts, origin_ns)

    # Short trailing means of the gap and direction over the newest usable quarters.
    # value_at() applies the availability mask, so a quarter that wasn't published yet is NaN.
    for n in (4, 8, 16):   # 1 h, 2 h and 4 h of the newest usable quarters
        gaps, dirs = [], []
        for j in range(n):
            ts_j = imb_ts - j * NS_PER_QUARTER
            imb_j = index[IMBALANCE].value_at(ts_j, origin_ns)
            spot_j = index[SPOT].value_at(ts_j, origin_ns)
            gaps.append(imb_j - spot_j)
            dirs.append(index[DIRECTION].value_at(ts_j, origin_ns))
        per_origin[f"mean_gap_last{n}"] = np.nanmean(np.vstack(gaps), axis=0)
        per_origin[f"mean_dir_last{n}"] = np.nanmean(np.vstack(dirs), axis=0)
    # --- Fingrid real-time series (only if downloaded; see src/data/fingrid.py) ---
    def latest_pair(sid, ref_sid=None, lags=(0,)):
        """Mean over the newest usable quarters of sid (minus ref_sid at the same quarter)."""
        ts, _ = index[sid].latest(origins)
        latest_ts.append(ts)
        vals = []
        for j in lags:
            t_j = ts - j * NS_PER_QUARTER
            v = index[sid].value_at(t_j, origin_ns)   # availability-masked
            if ref_sid:
                v = v - index[ref_sid].value_at(t_j, origin_ns)
            vals.append(v)
        return np.nanmean(np.vstack(vals), axis=0)

    if "fg_hydro_rt" in index:
        # Level and 1-hour change: balancing shows up as plants and loads moving right now.
        for sid, name in (("fg_hydro_rt", "rt_hydro"), ("fg_boilers_rt", "rt_boilers"),
                          ("fg_netimport_rt", "rt_netimport"), ("fg_flow_se3_rt", "rt_flow_se3"),
                          ("fg_flow_ee_rt", "rt_flow_ee")):
            now = latest_pair(sid)
            per_origin[name] = now
            per_origin[name + "_chg_1h"] = now - latest_pair(sid, lags=(4,))
        chp = latest_pair("fg_chp_dh_rt") + latest_pair("fg_chp_ind_rt")
        chp_1h = latest_pair("fg_chp_dh_rt", lags=(4,)) + latest_pair("fg_chp_ind_rt", lags=(4,))
        per_origin["rt_chp_chg_1h"] = chp - chp_1h

    if "fg_wind_rt" in index:
        per_origin["rt_wind_err"] = latest_pair("fg_wind_rt", "fi_wind_fc_da")
        per_origin["rt_wind_err_last4"] = latest_pair("fg_wind_rt", "fi_wind_fc_da", range(4))
        per_origin["rt_cons_err"] = latest_pair("fg_cons_rt", "fi_consumption_fc_da")
        per_origin["rt_freq_dev"] = latest_pair("fg_freq_rt") - 50.0
        per_origin["rt_freq_dev_last4"] = latest_pair("fg_freq_rt", lags=range(4)) - 50.0
        nuc = latest_pair("fg_nuclear_rt")
        nuc_6h = latest_pair("fg_nuclear_rt", lags=range(24, 28))
        per_origin["rt_nuclear"] = nuc
        per_origin["rt_nuclear_change_6h"] = nuc - nuc_6h

    # data_cutoff_utc: the newest *measured* quarter used (never a day-ahead or calendar row,
    # whose timestamps are in the future). Always < origin.
    newest = np.max(np.vstack(latest_ts), axis=0)
    per_origin["data_cutoff"] = pd.to_datetime(np.where(newest >= 0, newest, np.iinfo(np.int64).min),
                                               utc=True)

    f = f.merge(per_origin, left_on="origin", right_index=True, how="left")
    f["age_q"] = f["imb_age_q"] + f["step"] - 1   # quarters between latest known gap and delivery

    if weather is not None:
        f = add_weather(f, index, weather)
    if nordic is not None:
        f = add_weather_nordic(f, index, nordic)
    if weather2 is not None:
        f = add_weather2(f, index, weather, weather2)
    if wind_map is not None:
        f = add_wind_hat(f, index, wind_map)
    if towns is not None:
        f = add_towns(f, index, towns)
    if with_targets:
        f = add_targets(f, index)
    return f


def add_targets(f: pd.DataFrame, index: dict[str, SeriesIndex]) -> pd.DataFrame:
    """Targets at the delivery quarter, with when they became known (for honest training cuts).

    Uses the raw series (no availability mask): targets are never model inputs.
    """
    d = to_ns(f["delivery"])
    far_future = np.full(len(f), np.iinfo(np.int64).max)

    def raw(sid):
        return index[sid].value_at(d, far_future)

    def fu(sid):
        s = index[sid]
        pos = np.clip(np.searchsorted(s.ts, d), 0, len(s.ts) - 1)
        return np.where(s.ts[pos] == d, s.fu[pos], np.iinfo(np.int64).max)

    price, spot, direction = raw(IMBALANCE), raw(SPOT), raw(DIRECTION)
    f = f.copy()
    f["y_price"] = price
    f["y_gap"] = price - spot
    f["y_dir"] = direction
    f["y_spike_high"] = np.where(np.isnan(price), np.nan, (price > spot + SPIKE_MARGIN).astype(float))
    f["y_spike_low"] = np.where(np.isnan(price), np.nan, (price < spot - SPIKE_MARGIN).astype(float))
    f["y_first_usable"] = pd.to_datetime(np.maximum.reduce([fu(IMBALANCE), fu(SPOT), fu(DIRECTION)]),
                                         utc=True)
    return f


FEATURE_COLUMNS = [
    "step", "spot", "spot_ramp_in", "spot_ramp_out", "spot_abs_ramp", "spot_minus_horizon_mean",
    "wind_fc", "wind_fc_ramp_1h", "wind_share", "cons_fc", "solar_fc", "residual_load_fc",
    "cap_fi_ee", "cap_ee_fi", "hour", "weekday", "holiday", "dst", "quarter",
    "last_gap", "mean_gap_last4", "mean_gap_last8", "last_dir", "mean_dir_last4", "mean_dir_last8",
    "last_mfrr_up_mw", "last_mfrr_down_mw", "last_cons_err",
    "last_flow_se1", "last_flow_se3", "last_flow_no4", "last_flow_ee",
    "last_se1_imb_gap", "last_se3_imb_gap", "last_ee_imb_gap", "age_q",
]

FINGRID_RT_COLUMNS = [
    "rt_wind_err", "rt_wind_err_last4", "rt_cons_err", "rt_freq_dev", "rt_freq_dev_last4",
    "rt_nuclear", "rt_nuclear_change_6h",
]

FINGRID_RT2_COLUMNS = [
    "rt_hydro", "rt_hydro_chg_1h", "rt_boilers", "rt_boilers_chg_1h", "rt_netimport",
    "rt_netimport_chg_1h", "rt_flow_se3", "rt_flow_se3_chg_1h", "rt_flow_ee", "rt_flow_ee_chg_1h",
    "rt_chp_chg_1h",
]

# Longer memory: 4-hour averages beat the newest quarter at every horizon (training data, 7 Nov).
MEMORY_COLUMNS = ["mean_gap_last16", "mean_dir_last16"]

NORDIC_COLUMNS = [f"om_{a}_wind_{k}" for a in NORDIC_AREAS for k in ("idx", "rev")] + ["om_nordic_wind_rev"]

# Second weather model (ICON-EU) and ECMWF-vs-ICON disagreement (Pavlo's split_all_icon).
WEATHER2_COLUMNS = ["om_icon_wind_idx", "om_icon_wind_rev", "om_model_spread"]

# Learned wind production (MW) from the weather points (src/models/wind_power.py).
WINDHAT_COLUMNS = ["om_wind_hat", "om_wind_hat_err", "om_wind_hat_rev"]

# Town weather: solar revision and temperature (heating demand) revision since the day-ahead forecasts.
TOWN_SOLAR_COLUMNS = ["om_rad_rev", "om_solar_rev_mw"]
TOWN_TEMP_COLUMNS = ["om_temp_town", "om_temp_rev"]

WEATHER_COLUMNS = [
    "om_wind_idx", "om_wind_idx_da", "om_wind_rev", "om_wind_rev_mw", "om_wind_speed",
    "om_temp", "om_icing", "om_lead_h",
]
