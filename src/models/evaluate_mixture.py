"""Train and evaluate the Direction-Mixture Model on the validation set."""

import subprocess
import sys
from pathlib import Path
import pandas as pd

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from src.data.loader import DATA_DIR, STARTER_DIR, load_inputs, load_spot
from src.features.build_features import build_features_for_origins
from src.models.train_direct import prepare_training_dataset
from src.models.mixture import DirectionMixtureModel

OUTPUT_DIR = WORKSPACE_DIR / "results" / "mixture"
TRAIN_END_ORIGIN = pd.Timestamp("2026-09-06T20:00:00Z")
VALIDATION_ORIGINS_FILE = WORKSPACE_DIR / "baseline_output" / "validation" / "forecast_origins.csv"
VALIDATION_TEMPLATE_FILE = WORKSPACE_DIR / "baseline_output" / "validation" / "sample_submission.csv"
BASELINE_SUMMARY = WORKSPACE_DIR / "baseline_output" / "validation" / "score" / "score_summary.csv"


def run_mixture_evaluation():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading raw inputs and spot prices...")
    inputs = load_inputs()
    spot = load_spot()

    # 1. Prepare training data
    df_train = prepare_training_dataset(inputs, spot, train_end_origin=TRAIN_END_ORIGIN)

    # 2. Fit Mixture Model
    mixture = DirectionMixtureModel()
    mixture.fit(df_train)

    # 3. Build features for validation origins
    val_origins = pd.to_datetime(pd.read_csv(VALIDATION_ORIGINS_FILE)["forecast_origin_utc"], utc=True)
    print(f"Building features for {len(val_origins)} validation origins...")
    df_val = build_features_for_origins(val_origins, inputs=inputs, spot=spot)

    # 4. Predict
    print("Inverting Mixture CDF for validation origins...")
    out_df = mixture.predict(df_val)

    submission_file = OUTPUT_DIR / "forecast_backtest.csv"
    template_cols = pd.read_csv(VALIDATION_TEMPLATE_FILE, nrows=0).columns.tolist()
    out_df[template_cols].to_csv(submission_file, index=False, float_format="%.6f", lineterminator="\n")
    print(f"Wrote Mixture Model submission to {submission_file}")

    # 5. Validate submission format
    print("\n--- Running validate_submission.py ---")
    cmd_val = [
        sys.executable,
        str(STARTER_DIR / "validate_submission.py"),
        "--backtest", str(submission_file),
        "--origins", str(VALIDATION_ORIGINS_FILE),
    ]
    res_val = subprocess.run(cmd_val, capture_output=True, text=True)
    print(res_val.stdout)
    assert res_val.returncode == 0, f"Validator failed: {res_val.stderr}"

    # 6. Score against validation actuals
    print("--- Running score.py ---")
    score_dir = OUTPUT_DIR / "score"
    cmd_score = [
        sys.executable,
        str(STARTER_DIR / "score.py"),
        "--actuals", str(DATA_DIR / "actuals_validation.csv"),
        "--submission", str(submission_file),
        "--output-dir", str(score_dir),
    ]
    if BASELINE_SUMMARY.exists():
        cmd_score.extend(["--baseline-summary", str(BASELINE_SUMMARY)])

    res_score = subprocess.run(cmd_score, capture_output=True, text=True)
    print(res_score.stdout)


if __name__ == "__main__":
    run_mixture_evaluation()

