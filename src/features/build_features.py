"""Feature engineering pipeline for 10-hour Finnish imbalance price forecasting."""

from pathlib import Path
from typing import List, Optional, Union
import numpy as np
import pandas as pd

from src.data.loader import (
    WORKSPACE_DIR,
    load_inputs,
    load_spot,
    load_validation_actuals,
    to_utc,
)
from src.data.available_at import available_at, assert_no_leakage

HORIZON_STEPS = 40
STEP_MINUTES = 15
STEP_OFFSETS = pd.to_timedelta(np.arange(HORIZON_STEPS) * STEP_MINUTES, unit="min")
SPIKE_MARGIN = 50.0

FEATURE_COLS = [
    "step",
    "spot_price",
    "spot_ramp",
    "spot_diff_origin",
    "wind_fc_da",
    "wind_ramp_horizon",
    "wind_low",
    "wind_high",
    "consumption_fc_da",
    "solar_fc_da",
    "net_load_da",
    "net_load_ramp_horizon",
    "wind_share_da",
    "hour_local",
    "weekday_local",
    "is_evening_peak",
    "is_morning_ramp",
    "last_gap",
    "shrunk_last_gap",
    "last_mfrr_direction",
    "last_se1_flow",
    "last_consumption_error",
    "last_ee_imbalance",
]


def extract_pivot_tables(inputs: pd.DataFrame, spot: pd.DataFrame):
    """Pre-pivot series by (timestamp_utc, series_id) for fast vectorized lookups."""
    # Combine inputs and spot
    dfs = [inputs[["series_id", "timestamp_utc", "value", "first_usable_origin_utc"]]]
    if spot is not None and not spot.empty:
        dfs.append(spot[["series_id", "timestamp_utc", "value", "first_usable_origin_utc"]])
    combined = pd.concat(dfs, ignore_index=True)

    # Wide table of values
    wide_values = combined.pivot(index="timestamp_utc", columns="series_id", values="value").sort_index()
    # Wide table of first_usable_origin_utc
    wide_fu = combined.pivot(index="timestamp_utc", columns="series_id", values="first_usable_origin_utc").sort_index()

    return wide_values, wide_fu


def build_features_for_origins(
    origins: Union[List[pd.Timestamp], pd.DatetimeIndex, pd.Series],
    inputs: Optional[pd.DataFrame] = None,
    spot: Optional[pd.DataFrame] = None,
    actuals: Optional[pd.DataFrame] = None,
) -> pd.DataFrame:
    """Build the feature matrix across specified forecast origins.

    Guarantees strict compliance with the data availability rule:
    at origin t, any feature extracted must have first_usable_origin_utc <= t.
    """
    if inputs is None:
        inputs = load_inputs()
    if spot is None:
        spot = load_spot()

    wide_val, wide_fu = extract_pivot_tables(inputs, spot)

    # Map actuals if provided for ground truth target labels
    actuals_map = {}
    if actuals is not None and not actuals.empty:
        actuals_idx = actuals.set_index("delivery_start_utc")
        for col in ("imbalance_price", "spot_price", "direction"):
            if col in actuals_idx.columns:
                actuals_map[col] = actuals_idx[col]

    rows = []
    origins_list = [to_utc(o) for o in origins]

    for origin in origins_list:
        # 1. State usable at origin (historical lags)
        # Latest usable imbalance price is at origin - 1h 15m (5 quarters back)
        imb_target_ts = origin - pd.Timedelta(minutes=75)
        # Check first_usable_origin_utc <= origin
        if (
            imb_target_ts in wide_val.index
            and "fi_imbalance_price" in wide_val.columns
            and wide_fu.loc[imb_target_ts, "fi_imbalance_price"] <= origin
        ):
            last_imb = wide_val.loc[imb_target_ts, "fi_imbalance_price"]
            last_spot = wide_val.loc[imb_target_ts, "fi_spot_price"] if "fi_spot_price" in wide_val.columns else np.nan
            last_dir = wide_val.loc[imb_target_ts, "fi_mfrr_direction"] if "fi_mfrr_direction" in wide_val.columns else np.nan
            last_cutoff = imb_target_ts
        else:
            last_imb = np.nan
            last_spot = np.nan
            last_dir = np.nan
            last_cutoff = origin

        last_gap = last_imb - last_spot if (pd.notna(last_imb) and pd.notna(last_spot)) else np.nan

        # Flow lags (usable at origin - 45m, 3 quarters back)
        flow_target_ts = origin - pd.Timedelta(minutes=45)
        last_se1_flow = wide_val.loc[flow_target_ts, "fi_se1_flow"] if (
            flow_target_ts in wide_val.index
            and "fi_se1_flow" in wide_val.columns
            and wide_fu.loc[flow_target_ts, "fi_se1_flow"] <= origin
        ) else np.nan

        last_cons = wide_val.loc[flow_target_ts, "fi_consumption"] if (
            flow_target_ts in wide_val.index
            and "fi_consumption" in wide_val.columns
            and wide_fu.loc[flow_target_ts, "fi_consumption"] <= origin
        ) else np.nan

        last_cons_da = wide_val.loc[flow_target_ts, "fi_consumption_fc_da"] if (
            flow_target_ts in wide_val.index and "fi_consumption_fc_da" in wide_val.columns
        ) else np.nan
        last_cons_err = last_cons - last_cons_da if (pd.notna(last_cons) and pd.notna(last_cons_da)) else np.nan

        # Neighbour lag (usable at origin - 2h 15m, 9 quarters back)
        nb_target_ts = origin - pd.Timedelta(minutes=135)
        last_ee_imb = wide_val.loc[nb_target_ts, "ee_imbalance_price_long"] if (
            nb_target_ts in wide_val.index
            and "ee_imbalance_price_long" in wide_val.columns
            and wide_fu.loc[nb_target_ts, "ee_imbalance_price_long"] <= origin
        ) else np.nan

        # Origin day-ahead anchors for horizon ramp features
        spot_origin = wide_val.loc[origin, "fi_spot_price"] if (
            origin in wide_val.index and "fi_spot_price" in wide_val.columns and wide_fu.loc[origin, "fi_spot_price"] <= origin
        ) else np.nan
        wind_origin = wide_val.loc[origin, "fi_wind_fc_da"] if (
            origin in wide_val.index and "fi_wind_fc_da" in wide_val.columns and wide_fu.loc[origin, "fi_wind_fc_da"] <= origin
        ) else np.nan
        cons_origin = wide_val.loc[origin, "fi_consumption_fc_da"] if (
            origin in wide_val.index and "fi_consumption_fc_da" in wide_val.columns and wide_fu.loc[origin, "fi_consumption_fc_da"] <= origin
        ) else np.nan
        net_load_origin = cons_origin - wind_origin if (pd.notna(cons_origin) and pd.notna(wind_origin)) else np.nan

        # 2. Loop over 40 steps for this origin
        for step_idx, offset in enumerate(STEP_OFFSETS):
            step = step_idx + 1
            delivery = origin + offset

            # Day-ahead features at delivery time
            spot_delivery = wide_val.loc[delivery, "fi_spot_price"] if (
                delivery in wide_val.index
                and "fi_spot_price" in wide_val.columns
                and wide_fu.loc[delivery, "fi_spot_price"] <= origin
            ) else np.nan

            wind_da = wide_val.loc[delivery, "fi_wind_fc_da"] if (
                delivery in wide_val.index
                and "fi_wind_fc_da" in wide_val.columns
                and wide_fu.loc[delivery, "fi_wind_fc_da"] <= origin
            ) else np.nan

            cons_da = wide_val.loc[delivery, "fi_consumption_fc_da"] if (
                delivery in wide_val.index
                and "fi_consumption_fc_da" in wide_val.columns
                and wide_fu.loc[delivery, "fi_consumption_fc_da"] <= origin
            ) else np.nan

            solar_da = wide_val.loc[delivery, "fi_solar_fc_da"] if (
                delivery in wide_val.index
                and "fi_solar_fc_da" in wide_val.columns
                and wide_fu.loc[delivery, "fi_solar_fc_da"] <= origin
            ) else 0.0

            # Spot changes
            prev_quarter = delivery - pd.Timedelta(minutes=15)
            spot_prev = wide_val.loc[prev_quarter, "fi_spot_price"] if (
                prev_quarter in wide_val.index
                and "fi_spot_price" in wide_val.columns
                and wide_fu.loc[prev_quarter, "fi_spot_price"] <= origin
            ) else spot_delivery

            spot_ramp = spot_delivery - spot_prev if (pd.notna(spot_delivery) and pd.notna(spot_prev)) else 0.0
            spot_diff_origin = spot_delivery - spot_origin if (pd.notna(spot_delivery) and pd.notna(spot_origin)) else 0.0

            # Net position (residual load) and ramps
            net_load = cons_da - wind_da - solar_da if (pd.notna(cons_da) and pd.notna(wind_da)) else np.nan
            net_load_ramp = net_load - net_load_origin if (pd.notna(net_load) and pd.notna(net_load_origin)) else 0.0
            wind_ramp = wind_da - wind_origin if (pd.notna(wind_da) and pd.notna(wind_origin)) else 0.0
            wind_share = wind_da / (cons_da + 1e-3) if (pd.notna(cons_da) and pd.notna(wind_da)) else np.nan
            wind_low = 1.0 if (pd.notna(wind_da) and wind_da < 500.0) else 0.0
            wind_high = 1.0 if (pd.notna(wind_da) and wind_da > 2000.0) else 0.0

            # Time of day interactions
            hour_local = delivery.tz_convert("Europe/Helsinki").hour
            weekday_local = delivery.tz_convert("Europe/Helsinki").weekday()
            is_evening_peak = 1.0 if (17 <= hour_local <= 21) else 0.0
            is_morning_ramp = 1.0 if (6 <= hour_local <= 9) else 0.0

            # Decay factor for recent lag as step grows
            decay = np.exp(-0.15 * (step - 1))
            shrunk_last_gap = last_gap * decay if pd.notna(last_gap) else 0.0

            # Target variables if available
            target_imb = actuals_map["imbalance_price"].get(delivery, np.nan) if "imbalance_price" in actuals_map else np.nan
            target_spot = actuals_map["spot_price"].get(delivery, np.nan) if "spot_price" in actuals_map else spot_delivery
            target_dir = actuals_map["direction"].get(delivery, np.nan) if "direction" in actuals_map else np.nan

            if pd.notna(target_imb) and pd.notna(target_spot):
                target_gap = target_imb - target_spot
                target_spike_high = 1.0 if target_gap > SPIKE_MARGIN else 0.0
                target_spike_low = 1.0 if target_gap < -SPIKE_MARGIN else 0.0
            else:
                target_gap = np.nan
                target_spike_high = np.nan
                target_spike_low = np.nan

            rows.append({
                "forecast_origin_utc": origin,
                "delivery_start_utc": delivery,
                "step": step,
                "data_cutoff_utc": last_cutoff,
                # Day-ahead features
                "spot_price": spot_delivery,
                "spot_ramp": spot_ramp,
                "spot_diff_origin": spot_diff_origin,
                "wind_fc_da": wind_da,
                "wind_ramp_horizon": wind_ramp,
                "wind_low": wind_low,
                "wind_high": wind_high,
                "consumption_fc_da": cons_da,
                "solar_fc_da": solar_da,
                "net_load_da": net_load,
                "net_load_ramp_horizon": net_load_ramp,
                "wind_share_da": wind_share,
                # Calendar features
                "hour_local": hour_local,
                "weekday_local": weekday_local,
                "is_evening_peak": is_evening_peak,
                "is_morning_ramp": is_morning_ramp,
                # Recent state lags & decays
                "last_gap": last_gap,
                "shrunk_last_gap": shrunk_last_gap,
                "last_mfrr_direction": last_dir,
                "last_se1_flow": last_se1_flow,
                "last_consumption_error": last_cons_err,
                "last_ee_imbalance": last_ee_imb,
                # Targets (for training / evaluation)
                "target_imbalance": target_imb,
                "target_spot": target_spot,
                "target_gap": target_gap,
                "target_direction": target_dir,
                "target_spike_high": target_spike_high,
                "target_spike_low": target_spike_low,
            })

    df_features = pd.DataFrame(rows)
    return df_features

