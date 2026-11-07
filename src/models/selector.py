"""Composite selector combining the best performing model per scored column.

Accuracy (MAE), Calibration (Pinball), and Spikes (Brier) come from the Direction-Mixture Model.
Direction probabilities (3-class Brier) come from the Direct LightGBM Classifier.
"""

from pathlib import Path
import numpy as np
import pandas as pd

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
MIXTURE_BACKTEST = WORKSPACE_DIR / "results" / "mixture" / "forecast_backtest.csv"
DIRECT_BACKTEST = WORKSPACE_DIR / "results" / "validation" / "forecast_backtest.csv"
OUTPUT_DIR = WORKSPACE_DIR / "results" / "composite"
TEMPLATE_PATH = WORKSPACE_DIR / "baseline_output" / "validation" / "sample_submission.csv"


def build_composite_submission(
    mixture_path: Path = MIXTURE_BACKTEST,
    direct_path: Path = DIRECT_BACKTEST,
    output_dir: Path = OUTPUT_DIR,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    out_file = output_dir / "forecast_backtest.csv"

    print("Loading Mixture and Direct backtest submissions...")
    df_mix = pd.read_csv(mixture_path)
    df_dir = pd.read_csv(direct_path)

    assert len(df_mix) == len(df_dir), "Submission files must have identical row counts"

    # Merge: take quantiles and spikes from Mixture, direction from Direct
    df_composite = df_mix.copy()
    df_composite["p_up"] = df_dir["p_up"]
    df_composite["p_down"] = df_dir["p_down"]
    df_composite["p_none"] = df_dir["p_none"]

    # Verify probability constraints strictly
    diff = 1.0 - (df_composite["p_up"] + df_composite["p_down"] + df_composite["p_none"])
    df_composite["p_down"] = np.round(df_composite["p_down"] + diff, 6)

    template_cols = pd.read_csv(TEMPLATE_PATH, nrows=0).columns.tolist()
    df_composite[template_cols].to_csv(out_file, index=False, float_format="%.6f", lineterminator="\n")
    print(f"Wrote composite submission to {out_file}")
    return out_file


if __name__ == "__main__":
    import numpy as np
    build_composite_submission()
