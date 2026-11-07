"""Direct LightGBM model forecasting gap-to-spot quantiles, directions, and spikes."""

from pathlib import Path
import lightgbm as lgb
import numpy as np
import pandas as pd

from src.data.loader import (
    DATA_DIR,
    STARTER_DIR,
    WORKSPACE_DIR,
    load_inputs,
    load_spot,
    load_validation_actuals,
    to_utc,
)
from src.features.build_features import build_features_for_origins, FEATURE_COLS
from src.models.calibrate import (
    compute_pinball_corrections,
    apply_pinball_corrections,
    calibrate_probabilities,
)


def prepare_training_dataset(inputs: pd.DataFrame, spot: pd.DataFrame, train_end_origin: pd.Timestamp):
    """Build feature table and ground truth labels for all historical training origins."""
    # Find all full-hour origins from start of data up to train_end_origin
    first_hour = pd.Timestamp("2026-06-02T00:00:00Z")
    origins = pd.date_range(first_hour, train_end_origin, freq="h")

    # Construct ground truth delivery quarter table
    imb_s = inputs[inputs["series_id"] == "fi_imbalance_price"][["timestamp_utc", "value"]].rename(
        columns={"value": "imbalance_price"}
    )
    spot_s = spot[["timestamp_utc", "value"]].rename(columns={"value": "spot_price"})
    dir_s = inputs[inputs["series_id"] == "fi_mfrr_direction"][["timestamp_utc", "value"]].rename(
        columns={"value": "direction"}
    )
    # Map direction value -1, 0, 1 to string 'down', 'none', 'up'
    dir_map = {-1.0: "down", 0.0: "none", 1.0: "up"}
    dir_s["direction"] = dir_s["direction"].map(dir_map)

    actuals = pd.merge(imb_s, spot_s, on="timestamp_utc")
    actuals = pd.merge(actuals, dir_s, on="timestamp_utc", how="left")
    actuals = actuals.rename(columns={"timestamp_utc": "delivery_start_utc"})

    print(f"Building features for {len(origins)} training origins...")
    df_train = build_features_for_origins(origins, inputs=inputs, spot=spot, actuals=actuals)

    # Filter out rows where target_gap is missing
    df_train = df_train.dropna(subset=["target_gap"]).reset_index(drop=True)
    print(f"Total valid training samples: {len(df_train)}")
    return df_train


def train_models(df_train: pd.DataFrame):
    """Train quantile, direction, and spike models on feature matrix."""
    X = df_train[FEATURE_COLS]
    y_gap = df_train["target_gap"]

    print("Training LightGBM P50 (median / L1 loss)...")
    model_p50 = lgb.LGBMRegressor(
        objective="regression_l1",
        n_estimators=150,
        learning_rate=0.08,
        num_leaves=31,
        random_state=42,
        verbose=-1,
    )
    model_p50.fit(X, y_gap)

    print("Training LightGBM P10 (quantile 0.10)...")
    model_p10 = lgb.LGBMRegressor(
        objective="quantile",
        alpha=0.10,
        n_estimators=150,
        learning_rate=0.08,
        num_leaves=31,
        random_state=42,
        verbose=-1,
    )
    model_p10.fit(X, y_gap)

    print("Training LightGBM P90 (quantile 0.90)...")
    model_p90 = lgb.LGBMRegressor(
        objective="quantile",
        alpha=0.90,
        n_estimators=150,
        learning_rate=0.08,
        num_leaves=31,
        random_state=42,
        verbose=-1,
    )
    model_p90.fit(X, y_gap)

    # Direction model (Up vs Down)
    print("Training LightGBM Direction Classifier...")
    # target_direction: up -> 1, down -> 0, none -> ignore or map to down
    y_dir = (df_train["target_direction"] == "up").astype(int)
    model_dir = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=100,
        learning_rate=0.08,
        num_leaves=31,
        random_state=42,
        verbose=-1,
    )
    model_dir.fit(X, y_dir)

    # Spike models
    print("Training LightGBM Spike Classifiers...")
    y_spike_h = df_train["target_spike_high"].astype(int)
    model_spike_h = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=80,
        learning_rate=0.08,
        num_leaves=20,
        random_state=42,
        verbose=-1,
    )
    model_spike_h.fit(X, y_spike_h)

    y_spike_l = df_train["target_spike_low"].astype(int)
    model_spike_l = lgb.LGBMClassifier(
        objective="binary",
        n_estimators=80,
        learning_rate=0.08,
        num_leaves=20,
        random_state=42,
        verbose=-1,
    )
    model_spike_l.fit(X, y_spike_l)

    # Compute step-band pinball corrections on training set
    print("Computing pinball-optimal quantile calibration...")
    pred_p10_train = model_p10.predict(X)
    pred_p90_train = model_p90.predict(X)
    corrections = compute_pinball_corrections(
        y_true=y_gap.values,
        pred_p10=pred_p10_train,
        pred_p90=pred_p90_train,
        steps=df_train["step"].values,
        shrinkage=0.5,
    )

    return {
        "p10": model_p10,
        "p50": model_p50,
        "p90": model_p90,
        "dir": model_dir,
        "spike_h": model_spike_h,
        "spike_l": model_spike_l,
        "corrections": corrections,
    }


def predict_submission(models: dict, df_eval: pd.DataFrame, template_path: Path, output_path: Path):
    """Generate forecast predictions, ensure monotonicity and constraints, write CSV."""
    X = df_eval[FEATURE_COLS]
    spots = df_eval["spot_price"].values
    steps = df_eval["step"].values

    # Predict gap quantiles and add spot back
    pred_gap_p50 = models["p50"].predict(X)
    pred_gap_p10 = models["p10"].predict(X)
    pred_gap_p90 = models["p90"].predict(X)

    raw_p50 = spots + pred_gap_p50
    raw_p10 = spots + pred_gap_p10
    raw_p90 = spots + pred_gap_p90

    # Apply pinball calibration shifts per step band
    if "corrections" in models:
        p10, p90 = apply_pinball_corrections(raw_p10, raw_p50, raw_p90, steps, models["corrections"])
    else:
        p10 = np.minimum(raw_p10, raw_p50)
        p90 = np.maximum(raw_p90, raw_p50)
    p50 = raw_p50

    # Probabilities
    raw_prob_up = models["dir"].predict_proba(X)[:, 1]
    raw_spike_h = models["spike_h"].predict_proba(X)[:, 1]
    raw_spike_l = models["spike_l"].predict_proba(X)[:, 1]

    p_up, p_down, p_none, p_spike_h, p_spike_l = calibrate_probabilities(
        prob_up=raw_prob_up,
        prob_spike_h=raw_spike_h,
        prob_spike_l=raw_spike_l,
    )

    out_df = pd.DataFrame({
        "forecast_origin_utc": df_eval["forecast_origin_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "delivery_start_utc": df_eval["delivery_start_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "step": df_eval["step"],
        "p10": np.round(p10, 4),
        "p50": np.round(p50, 4),
        "p90": np.round(p90, 4),
        "p_up": np.round(p_up, 6),
        "p_down": np.round(p_down, 6),
        "p_none": np.round(p_none, 6),
        "p_spike_high": np.round(p_spike_h, 6),
        "p_spike_low": np.round(p_spike_l, 6),
        "data_cutoff_utc": df_eval["data_cutoff_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "top_drivers": "net_load_da;wind_fc_da;shrunk_last_gap",
    })

    # Adjust rounding for probabilities so sum is strictly 1.0
    diff = 1.0 - (out_df["p_up"] + out_df["p_down"] + out_df["p_none"])
    out_df["p_down"] = np.round(out_df["p_down"] + diff, 6)

    template_cols = pd.read_csv(template_path, nrows=0).columns.tolist()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    out_df[template_cols].to_csv(output_path, index=False, float_format="%.6f", lineterminator="\n")
    print(f"Wrote calibrated submission file to {output_path} ({len(out_df)} rows)")
    return out_df

