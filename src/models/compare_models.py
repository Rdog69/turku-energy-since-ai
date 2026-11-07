"""Comprehensive Model Comparison Framework: LightGBM vs CatBoost vs XGBoost vs Horizon Bridge vs Ensemble.

Evaluates all model families on the official validation dataset (7 Sep - 4 Oct 2026).
"""

from pathlib import Path
import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
from catboost import CatBoostRegressor, CatBoostClassifier
import xgboost as xgb

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from src.data.loader import DATA_DIR, STARTER_DIR, load_inputs, load_spot, load_validation_actuals
from src.features.build_features import build_features_for_origins, FEATURE_COLS
from src.models.train_direct import prepare_training_dataset

TRAIN_END_ORIGIN = pd.Timestamp("2026-09-06T20:00:00Z")
VALIDATION_ORIGINS_FILE = WORKSPACE_DIR / "baseline_output" / "validation" / "forecast_origins.csv"


def train_eval_lightgbm(X_train, y_train, X_val, y_val, spot_val, actual_imb):
    """Evaluate standard LightGBM regressor."""
    model = lgb.LGBMRegressor(
        objective="regression_l1",
        n_estimators=180,
        learning_rate=0.07,
        num_leaves=35,
        random_state=42,
        verbose=-1,
    )
    model.fit(X_train, y_train)
    pred_gap = model.predict(X_val)
    pred_p50 = spot_val + pred_gap
    mae = float(np.mean(np.abs(actual_imb - pred_p50)))
    return mae, pred_p50


def train_eval_catboost(X_train, y_train, X_val, y_val, spot_val, actual_imb):
    """Evaluate CatBoost with symmetric trees and ordered boosting."""
    model = CatBoostRegressor(
        loss_function="MAE",
        iterations=250,
        learning_rate=0.08,
        depth=6,
        random_seed=42,
        verbose=0,
    )
    model.fit(X_train, y_train)
    pred_gap = model.predict(X_val)
    pred_p50 = spot_val + pred_gap
    mae = float(np.mean(np.abs(actual_imb - pred_p50)))
    return mae, pred_p50


def train_eval_xgboost(X_train, y_train, X_val, y_val, spot_val, actual_imb):
    """Evaluate XGBoost regressor."""
    model = xgb.XGBRegressor(
        objective="reg:absoluteerror",
        n_estimators=180,
        learning_rate=0.07,
        max_depth=6,
        random_state=42,
        verbosity=0,
    )
    model.fit(X_train, y_train)
    pred_gap = model.predict(X_val)
    pred_p50 = spot_val + pred_gap
    mae = float(np.mean(np.abs(actual_imb - pred_p50)))
    return mae, pred_p50


def train_eval_horizon_bridge(df_train, df_val, spot_val, actual_imb):
    """Horizon Bridge: separate specialized models for near, mid, and far horizons."""
    bands = [
        ("Near (Steps 1-4)", (1, 4)),
        ("Mid (Steps 5-16)", (5, 16)),
        ("Far (Steps 17-40)", (17, 40)),
    ]
    preds = np.zeros(len(df_val))

    for name, (s_low, s_high) in bands:
        m_train = (df_train["step"] >= s_low) & (df_train["step"] <= s_high)
        m_val = (df_val["step"] >= s_low) & (df_val["step"] <= s_high)

        X_tr = df_train.loc[m_train, FEATURE_COLS]
        y_tr = df_train.loc[m_train, "target_gap"]
        X_v = df_val.loc[m_val, FEATURE_COLS]

        m = lgb.LGBMRegressor(
            objective="regression_l1",
            n_estimators=150,
            learning_rate=0.07,
            num_leaves=31,
            random_state=42,
            verbose=-1,
        )
        m.fit(X_tr, y_tr)
        preds[m_val] = m.predict(X_v)

    pred_p50 = spot_val + preds
    mae = float(np.mean(np.abs(actual_imb - pred_p50)))
    return mae, pred_p50


def run_comparison():
    print("=" * 60)
    print("RUNNING MULTI-MODEL BENCHMARK COMPARISON")
    print("=" * 60)

    inputs = load_inputs()
    spot = load_spot()
    val_actuals = load_validation_actuals()

    # Prepare datasets
    df_train = prepare_training_dataset(inputs, spot, train_end_origin=TRAIN_END_ORIGIN)
    val_origins = pd.to_datetime(pd.read_csv(VALIDATION_ORIGINS_FILE)["forecast_origin_utc"], utc=True)
    df_val = build_features_for_origins(val_origins, inputs=inputs, spot=spot, actuals=val_actuals)

    # Filter to scored rows (rows with valid actual values)
    scored_mask = df_val["target_imbalance"].notna()
    df_val_scored = df_val[scored_mask].reset_index(drop=True)

    X_train = df_train[FEATURE_COLS]
    y_train = df_train["target_gap"]

    X_val = df_val_scored[FEATURE_COLS]
    y_val = df_val_scored["target_gap"]
    spot_val = df_val_scored["spot_price"].values
    actual_imb = df_val_scored["target_imbalance"].values

    results = {}

    print("\n1. Evaluating LightGBM...")
    mae_lgb, pred_lgb = train_eval_lightgbm(X_train, y_train, X_val, y_val, spot_val, actual_imb)
    results["LightGBM"] = {"MAE": mae_lgb, "preds": pred_lgb}
    print(f"   LightGBM MAE: {mae_lgb:.4f} €/MWh")

    print("\n2. Evaluating CatBoost...")
    mae_cb, pred_cb = train_eval_catboost(X_train, y_train, X_val, y_val, spot_val, actual_imb)
    results["CatBoost"] = {"MAE": mae_cb, "preds": pred_cb}
    print(f"   CatBoost MAE: {mae_cb:.4f} €/MWh")

    print("\n3. Evaluating XGBoost...")
    mae_xgb, pred_xgb = train_eval_xgboost(X_train, y_train, X_val, y_val, spot_val, actual_imb)
    results["XGBoost"] = {"MAE": mae_xgb, "preds": pred_xgb}
    print(f"   XGBoost MAE: {mae_xgb:.4f} €/MWh")

    print("\n4. Evaluating Horizon Bridge (Specialized Step-Band Models)...")
    mae_hb, pred_hb = train_eval_horizon_bridge(df_train, df_val_scored, spot_val, actual_imb)
    results["Horizon Bridge"] = {"MAE": mae_hb, "preds": pred_hb}
    print(f"   Horizon Bridge MAE: {mae_hb:.4f} €/MWh")

    print("\n5. Evaluating Blended Ensemble (LightGBM + CatBoost + Horizon Bridge)...")
    pred_ensemble = 0.45 * pred_hb + 0.35 * pred_lgb + 0.20 * pred_cb
    mae_ensemble = float(np.mean(np.abs(actual_imb - pred_ensemble)))
    results["Ensemble Blend"] = {"MAE": mae_ensemble, "preds": pred_ensemble}
    print(f"   Ensemble Blend MAE: {mae_ensemble:.4f} €/MWh")

    # Baseline for reference
    baseline_mae = 66.2033

    print("\n" + "=" * 65)
    print("FINAL MODEL LEADERBOARD (Validation Period: 26,700 rows)")
    print("=" * 65)
    print(f"{'Model Architecture':<25} | {'MAE (€/MWh)':<12} | {'Improvement vs Baseline'}")
    print("-" * 65)
    print(f"{'Official Baseline':<25} | {baseline_mae:<12.4f} | {'Reference (0%)'}")
    for name, res in sorted(results.items(), key=lambda x: x[1]["MAE"]):
        gain = (baseline_mae - res["MAE"]) / baseline_mae * 100
        diff = res["MAE"] - baseline_mae
        print(f"{name:<25} | {res['MAE']:<12.4f} | {diff:+.2f} €/MWh (-{gain:.1f}%)")
    print("=" * 65)


if __name__ == "__main__":
    run_comparison()

