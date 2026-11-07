"""Generate the official final test-period submission: forecast_backtest.csv.

Trains on all data up to 4 October 2026 (the official training cut-off).
Forecasts all 673 test origins (26,920 rows) for 5 Oct - 1 Nov 2026.
Uses Composite Architecture: Direction-Mixture Model + Direct Classifier + TreeSHAP drivers.
Runs validate_submission.py to guarantee submission compliance.
"""

import subprocess
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from src.data.loader import DATA_DIR, STARTER_DIR, load_inputs, load_spot
from src.features.build_features import build_features_for_origins, FEATURE_COLS
from src.models.train_direct import prepare_training_dataset, train_models
from src.models.mixture import DirectionMixtureModel
from src.explain.shap_drivers import ShapDriverExplainer

# Official test-period files
TEST_ORIGINS_FILE = STARTER_DIR / "forecast_origins.csv"
TEST_TEMPLATE_FILE = STARTER_DIR / "sample_submission.csv"
FINAL_SUBMISSION_PATH = WORKSPACE_DIR / "forecast_backtest.csv"
OFFICIAL_TRAIN_CUTOFF = pd.Timestamp("2026-10-04T20:00:00Z")


def generate_official_submission(output_path: Path = FINAL_SUBMISSION_PATH):
    print("=" * 60)
    print("GENERATING OFFICIAL TEST SUBMISSION: forecast_backtest.csv")
    print(f"Official training cutoff: {OFFICIAL_TRAIN_CUTOFF}")
    print("=" * 60)

    print("\n1. Loading input data and spot prices...")
    inputs = load_inputs()
    spot = load_spot()

    print("\n2. Building full training dataset up to 4 October 2026...")
    df_train = prepare_training_dataset(inputs, spot, train_end_origin=OFFICIAL_TRAIN_CUTOFF)

    print("\n3. Training models...")
    print("3a. Training Direct LightGBM Classifier (for directions)...")
    direct_models = train_models(df_train)

    print("3b. Training Direction-Mixture CDF Model (for quantiles & spikes)...")
    mixture_model = DirectionMixtureModel()
    mixture_model.fit(df_train)

    print("3c. Training CatBoost Regressor (for optimal L1 ensemble blending)...")
    cb_model = CatBoostRegressor(
        loss_function="MAE",
        iterations=250,
        learning_rate=0.08,
        depth=6,
        random_seed=42,
        verbose=0,
    )
    cb_model.fit(df_train[FEATURE_COLS], df_train["target_gap"])

    print("\n4. Loading test origins (673 origins)...")
    test_origins = pd.to_datetime(pd.read_csv(TEST_ORIGINS_FILE)["forecast_origin_utc"], utc=True)
    assert len(test_origins) == 673, f"Expected 673 test origins, found {len(test_origins)}"

    print("5. Extracting features for test origins (26,920 rows)...")
    df_test = build_features_for_origins(test_origins, inputs=inputs, spot=spot)
    assert len(df_test) == 26920, f"Expected 26,920 rows, found {len(df_test)}"

    print("\n6. Generating predictions...")
    print("6a. Inverting Mixture CDF for quantiles and spikes...")
    df_mix_out = mixture_model.predict(df_test)

    print("6b. Predicting CatBoost P50 and blending with Mixture (0.60 Mixture + 0.40 CatBoost)...")
    X_test = df_test[FEATURE_COLS]
    spots_test = df_test["spot_price"].values
    pred_cb_gap = cb_model.predict(X_test)
    pred_cb_p50 = spots_test + pred_cb_gap

    # Optimal ensemble blend
    p50_blend = np.round(0.60 * df_mix_out["p50"].values + 0.40 * pred_cb_p50, 4)
    # Maintain monotonicity: p10 <= p50 <= p90
    p10_clean = np.minimum(df_mix_out["p10"].values, p50_blend)
    p90_clean = np.maximum(df_mix_out["p90"].values, p50_blend)

    print("6c. Predicting direction probabilities from Direct Classifier...")
    prob_up = direct_models["dir"].predict_proba(X_test)[:, 1]
    p_none = 0.0017
    p_up_scaled = prob_up * (1.0 - p_none)
    p_down_scaled = (1.0 - prob_up) * (1.0 - p_none)

    print("6d. Computing TreeSHAP top drivers for all 26,920 rows...")
    explainer = ShapDriverExplainer(mixture_model.up_models[0.50])
    top_drivers = explainer.get_top_drivers_column(X_test, top_k=3)

    # Assemble final submission dataframe
    df_final = df_mix_out.copy()
    df_final["p10"] = np.round(p10_clean, 4)
    df_final["p50"] = np.round(p50_blend, 4)
    df_final["p90"] = np.round(p90_clean, 4)
    df_final["p_up"] = np.round(p_up_scaled, 6)
    df_final["p_down"] = np.round(p_down_scaled, 6)
    df_final["p_none"] = np.round(p_none, 6)
    df_final["top_drivers"] = top_drivers

    # Adjust rounding for directions strictly to 1.0
    diff = 1.0 - (df_final["p_up"] + df_final["p_down"] + df_final["p_none"])
    df_final["p_down"] = np.round(df_final["p_down"] + diff, 6)

    # Enforce template column order
    template_cols = pd.read_csv(TEST_TEMPLATE_FILE, nrows=0).columns.tolist()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_final[template_cols].to_csv(output_path, index=False, float_format="%.6f", lineterminator="\n")
    print(f"\nWrote official submission to {output_path} ({len(df_final)} rows)")

    # Validate with official validator
    print("\n7. Validating with validate_submission.py...")
    cmd_val = [
        sys.executable,
        str(STARTER_DIR / "validate_submission.py"),
        "--backtest", str(output_path),
        "--origins", str(TEST_ORIGINS_FILE),
    ]
    res_val = subprocess.run(cmd_val, capture_output=True, text=True)
    print(res_val.stdout)
    assert res_val.returncode == 0, f"Validation FAILED: {res_val.stderr}"
    print("=" * 60)
    print("OFFICIAL VALIDATION PASSED — READY FOR PLATFORM SUBMISSION")
    print("=" * 60)


if __name__ == "__main__":
    generate_official_submission()

