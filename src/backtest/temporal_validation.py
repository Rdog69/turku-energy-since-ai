"""Robust Multi-Dimensional Temporal Validation Framework.

Implements chronological rolling-origin evaluation per Phase 1 of the implementation plan:
- Official metric computation via score.py
- Horizon-level breakdown:
  * Hour 1 (steps 1-4)
  * Hours 2-4 (steps 5-16)
  * Hours 5-7 (steps 17-28)
  * Hours 8-10 (steps 29-40)
- Weekly breakdown
- Market regime breakdown (calm vs volatile, spot > 100 vs spot <= 100, spot < 0)
- Multi-period evaluation: Fold A (September validation), Fold B (August holdout)
- Machine-readable JSON and DataFrame export
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = REPO_ROOT / "Dataset" / "starter_package_v1"
ACTUALS_DIR = REPO_ROOT / "results" / "actuals"
ACTUALS_VAL = PKG_DIR / "data" / "actuals_validation.csv"
ACTUALS_FOLD_B = ACTUALS_DIR / "actuals_fold_b.csv"
SCORE_SCRIPT = PKG_DIR / "score.py"

REQUIRED_COLS = [
    "forecast_origin_utc", "delivery_start_utc", "step",
    "p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"
]

HORIZON_BANDS = {
    "hour_1": (1, 4),
    "hours_2_4": (5, 16),
    "hours_5_7": (17, 28),
    "hours_8_10": (29, 40),
}

# Points weights from challenge spec
WEIGHTS = {"MAE": 30.0, "pinball": 20.0, "brier_spike": 20.0, "brier_dir": 10.0}

# Baseline reference metrics (organizers' baseline on September validation)
BASELINE_REF_VAL = {
    "mae_p50": 66.20,
    "calibration_pinball_mean": 24.18,
    "brier_spike_mean": 0.1132,
    "brier_direction": 0.4509,
}

# Reference model for Fold B (REF package mixture on August)
BASELINE_REF_FOLD_B = {
    "mae_p50": 29.40231,
    "calibration_pinball_mean": 7.01441,
    "brier_spike_mean": 0.07879,
    "brier_direction": 0.45278,
}


def compute_pinball(y: np.ndarray, yhat: np.ndarray, q: float) -> float:
    diff = y - yhat
    return float(np.mean(np.maximum(q * diff, (q - 1.0) * diff)))


def compute_brier_2class(p: np.ndarray, o: np.ndarray) -> float:
    return float(np.mean((p - o) ** 2))


def compute_brier_3class(p_up: np.ndarray, p_down: np.ndarray, p_none: np.ndarray, direction: pd.Series) -> float:
    o_up = (direction == "up").astype(float).values
    o_down = (direction == "down").astype(float).values
    o_none = (direction == "none").astype(float).values
    return float(np.mean((p_up - o_up) ** 2 + (p_down - o_down) ** 2 + (p_none - o_none) ** 2))


def evaluate_predictions(
    df_pred: pd.DataFrame,
    actuals_path: Path,
    period_name: str = "validation",
    output_dir: Path | None = None
) -> dict[str, Any]:
    """Run full multi-dimensional evaluation on predictions against ground truth actuals."""
    actuals = pd.read_csv(actuals_path)
    actuals["delivery_start_utc"] = pd.to_datetime(actuals["delivery_start_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    # Save temp file for official score.py
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        df_pred[REQUIRED_COLS].to_csv(f.name, index=False)
        tmp_sub = f.name

    tmp_out = Path(tempfile.mkdtemp()) if output_dir is None else output_dir
    tmp_out.mkdir(parents=True, exist_ok=True)

    cmd = [
        ".venv/bin/python", str(SCORE_SCRIPT),
        "--submission", tmp_sub,
        "--actuals", str(actuals_path),
        "--spike-margin", "50",
        "--output-dir", str(tmp_out)
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    os.unlink(tmp_sub)

    # Read official summary
    official_summary = pd.read_csv(tmp_out / "score_summary.csv").iloc[0].to_dict()
    
    # Merge predictions with actuals for fine-grained slicing
    merged = df_pred.merge(actuals, on="delivery_start_utc", how="inner")
    
    # Exclude rows where actuals are missing (same rule as score.py)
    valid_price = merged.dropna(subset=["imbalance_price", "p50", "p10", "p90"])
    valid_spikes = merged.dropna(subset=["imbalance_price", "spot_price", "p_spike_high", "p_spike_low"])
    valid_dir = merged.dropna(subset=["direction", "p_up", "p_down", "p_none"])

    # 1. Horizon breakdown
    horizon_results = {}
    for h_name, (s_min, s_max) in HORIZON_BANDS.items():
        sub_p = valid_price[(valid_price["step"] >= s_min) & (valid_price["step"] <= s_max)]
        sub_s = valid_spikes[(valid_spikes["step"] >= s_min) & (valid_spikes["step"] <= s_max)]
        sub_d = valid_dir[(valid_dir["step"] >= s_min) & (valid_dir["step"] <= s_max)]

        y_p = sub_p["imbalance_price"].values
        p50 = sub_p["p50"].values
        p10 = sub_p["p10"].values
        p90 = sub_p["p90"].values

        mae = float(np.mean(np.abs(y_p - p50))) if len(sub_p) > 0 else np.nan
        pb10 = compute_pinball(y_p, p10, 0.10) if len(sub_p) > 0 else np.nan
        pb90 = compute_pinball(y_p, p90, 0.90) if len(sub_p) > 0 else np.nan
        pinball = 0.5 * (pb10 + pb90)
        cov = float(np.mean((p10 <= y_p) & (y_p <= p90))) * 100.0 if len(sub_p) > 0 else np.nan

        # Spikes
        o_hi = (sub_s["imbalance_price"] > sub_s["spot_price"] + 50.0).astype(float).values
        o_lo = (sub_s["imbalance_price"] < sub_s["spot_price"] - 50.0).astype(float).values
        b_hi = compute_brier_2class(sub_s["p_spike_high"].values, o_hi) if len(sub_s) > 0 else np.nan
        b_lo = compute_brier_2class(sub_s["p_spike_low"].values, o_lo) if len(sub_s) > 0 else np.nan
        spike_brier = 0.5 * (b_hi + b_lo)

        # Direction
        dir_brier = compute_brier_3class(sub_d["p_up"].values, sub_d["p_down"].values, sub_d["p_none"].values, sub_d["direction"]) if len(sub_d) > 0 else np.nan

        horizon_results[h_name] = {
            "steps": f"{s_min}-{s_max}",
            "count": len(sub_p),
            "mae": round(mae, 4),
            "pinball": round(pinball, 4),
            "coverage": round(cov, 2),
            "spike_brier": round(spike_brier, 5),
            "dir_brier": round(dir_brier, 5),
        }

    # 2. Weekly breakdown
    valid_price["dt"] = pd.to_datetime(valid_price["delivery_start_utc"], utc=True)
    valid_price["week"] = valid_price["dt"].dt.isocalendar().week
    weekly_results = {}
    for w, w_df in valid_price.groupby("week"):
        w_p = w_df.dropna(subset=["imbalance_price", "p50", "p10", "p90"])
        y_w = w_p["imbalance_price"].values
        mae_w = float(np.mean(np.abs(y_w - w_p["p50"].values)))
        pb10_w = compute_pinball(y_w, w_p["p10"].values, 0.10)
        pb90_w = compute_pinball(y_w, w_p["p90"].values, 0.90)
        cov_w = float(np.mean((w_p["p10"].values <= y_w) & (y_w <= w_p["p90"].values))) * 100.0
        weekly_results[f"week_{w}"] = {
            "count": len(w_p),
            "mae": round(mae_w, 4),
            "pinball": round(0.5 * (pb10_w + pb90_w), 4),
            "coverage": round(cov_w, 2),
        }

    # 3. Market Regime breakdown
    regimes = {}
    # Volatile (Spot > 100 EUR/MWh) vs Calm (Spot <= 100 EUR/MWh)
    high_spot = valid_price[valid_price["spot_price"] > 100.0]
    low_spot = valid_price[valid_price["spot_price"] <= 100.0]
    neg_spot = valid_price[valid_price["spot_price"] < 0.0]

    for r_name, r_df in [("spot_gt_100_volatile", high_spot), ("spot_lte_100_calm", low_spot), ("spot_negative", neg_spot)]:
        if len(r_df) > 0:
            y_r = r_df["imbalance_price"].values
            mae_r = float(np.mean(np.abs(y_r - r_df["p50"].values)))
            pb_r = 0.5 * (compute_pinball(y_r, r_df["p10"].values, 0.10) + compute_pinball(y_r, r_df["p90"].values, 0.90))
            cov_r = float(np.mean((r_df["p10"].values <= y_r) & (y_r <= r_df["p90"].values))) * 100.0
            regimes[r_name] = {
                "count": len(r_df),
                "mae": round(mae_r, 4),
                "pinball": round(pb_r, 4),
                "coverage": round(cov_r, 2),
            }
        else:
            regimes[r_name] = {"count": 0}

    # 4. Points calculation
    ref = BASELINE_REF_VAL if period_name == "validation" else BASELINE_REF_FOLD_B
    points = (
        WEIGHTS["MAE"] * (ref["mae_p50"] - official_summary["mae_p50"]) / ref["mae_p50"]
        + WEIGHTS["pinball"] * (ref["calibration_pinball_mean"] - official_summary["calibration_pinball_mean"]) / ref["calibration_pinball_mean"]
        + WEIGHTS["brier_spike"] * (ref["brier_spike_mean"] - official_summary["brier_spike_mean"]) / ref["brier_spike_mean"]
        + WEIGHTS["brier_dir"] * (ref["brier_direction"] - official_summary["brier_direction"]) / ref["brier_direction"]
    )

    result = {
        "period": period_name,
        "points": round(points, 3),
        "overall": {
            "mae_p50": round(official_summary["mae_p50"], 4),
            "pinball_mean": round(official_summary["calibration_pinball_mean"], 4),
            "coverage": round(official_summary["coverage_p10_p90"] * 100.0, 2),
            "brier_spike_mean": round(official_summary["brier_spike_mean"], 5),
            "brier_direction": round(official_summary["brier_direction"], 5),
        },
        "horizons": horizon_results,
        "weekly": weekly_results,
        "regimes": regimes,
    }
    return result


def print_evaluation_summary(res: dict[str, Any], title: str = "Evaluation Summary"):
    print(f"\n{'='*25} {title} ({res['period']}) {'='*25}")
    ov = res["overall"]
    print(f"Points Gain:       {res['points']:+.2f} pts")
    print(f"P50 MAE:           {ov['mae_p50']:.2f} EUR/MWh")
    print(f"P10/P90 Pinball:   {ov['pinball_mean']:.2f} (Coverage: {ov['coverage']:.1f}%)")
    print(f"Spike Brier:       {ov['brier_spike_mean']:.5f}")
    print(f"Direction Brier:   {ov['brier_direction']:.5f}")
    print("\nHorizon Breakdown:")
    for h, h_data in res["horizons"].items():
        print(f"  {h:12s} ({h_data['steps']:5s}) | MAE: {h_data['mae']:6.2f} | Pinball: {h_data['pinball']:5.2f} | Cov: {h_data['coverage']:4.1f}% | Spk: {h_data['spike_brier']:.5f} | Dir: {h_data['dir_brier']:.5f}")
    print("\nWeekly MAE & Pinball:")
    for w, w_data in res["weekly"].items():
        print(f"  {w:10s} (N={w_data['count']:4d}) | MAE: {w_data['mae']:6.2f} | Pinball: {w_data['pinball']:5.2f} | Cov: {w_data['coverage']:4.1f}%")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--submission", required=True, help="Path to forecast_backtest.csv to evaluate")
    ap.add_argument("--period", choices=["validation", "fold_b"], default="validation")
    args = ap.parse_args()

    actuals_file = ACTUALS_VAL if args.period == "validation" else ACTUALS_FOLD_B
    df = pd.read_csv(args.submission)
    res = evaluate_predictions(df, actuals_file, period_name=args.period)
    print_evaluation_summary(res, title=f"EVALUATION RESULTS: {Path(args.submission).name}")
