"""Experiment Phase 3: Smooth Horizon-Aware Blending.

Tests whether a single slope parameter b in [-0.10, +0.10] for horizon-dependent blending:
w_abdo(step) = 0.5 + b * (1 - 2 * (step - 1) / 39)
can improve performance over fixed 50/50 without overfitting.

Evaluates:
- Full official 4 metrics via score.py
- Minimal displacement projection for valid quantiles
- Paired block bootstrap (1,000 replications over 28 calendar days)
"""
from __future__ import annotations

import io
import subprocess
import sys
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.backtest.postprocess import postprocess_forecasts
from src.backtest.temporal_validation import (
    evaluate_predictions,
    paired_block_bootstrap,
    BASELINE_REF_VAL,
    WEIGHTS,
)

PKG_DIR = REPO_ROOT / "Dataset" / "starter_package_v1"
ACTUALS_VAL = PKG_DIR / "data" / "actuals_validation.csv"
FRANK_VAL = REPO_ROOT / "results" / "v4_n50" / "validation" / "forecast_backtest.csv"


def run_experiment():
    print("=" * 80)
    print("PHASE 3: SMOOTH HORIZON-AWARE BLENDING EXPERIMENT")
    print("=" * 80)

    df_frank = pd.read_csv(FRANK_VAL)
    res = subprocess.run(
        ["git", "show", "20b414d8c8790ba4e8fc5a491d0dbdab56f1c33c:submissions/validation_team5050.csv"],
        capture_output=True, text=True, check=True
    )
    df_team = pd.read_csv(io.StringIO(res.stdout))

    # Isolated Abdo predictions
    p50_frank = df_frank["p50"].values
    p50_abdo = 2.0 * df_team["p50"].values - df_frank["p50"].values
    step = df_team["step"].values

    # Baseline postprocessed
    df_base = df_team.copy()
    df_base["top_drivers"] = df_frank["top_drivers"].fillna("spot;wind_fc;cons_fc").values
    df_base_clean = postprocess_forecasts(df_base, mode="validation", expected_rows=len(df_base))

    base_eval = evaluate_predictions(df_base_clean, ACTUALS_VAL, period_name="validation")
    base_mae = base_eval["overall"]["mae_p50"]
    base_pb = base_eval["overall"]["pinball_mean"]
    base_pts = base_eval["points"]

    print("\n--- BASELINE REFERENCE (team5050 50/50, b=0.0) ---")
    print(f"MAE: {base_mae:.4f} EUR/MWh | Pinball: {base_pb:.4f} | Coverage: {base_eval['overall']['coverage']:.1f}% | Points: {base_pts:+.3f}")

    b_grid = [-0.10, -0.05, -0.02, 0.0, +0.02, +0.05, +0.10]
    results = []

    best_pts = -999.0
    best_b = 0.0
    best_df = None

    for b in b_grid:
        decay = 1.0 - 2.0 * (step - 1) / 39.0
        w_abdo = np.clip(0.5 + b * decay, 0.0, 1.0)
        w_frank = 1.0 - w_abdo

        cand = df_team.copy()
        cand["p50"] = w_abdo * p50_abdo + w_frank * p50_frank
        cand["top_drivers"] = df_frank["top_drivers"].fillna("spot;wind_fc;cons_fc").values

        cand_clean = postprocess_forecasts(cand, mode="validation", expected_rows=len(cand))
        sc = evaluate_predictions(cand_clean, ACTUALS_VAL, period_name="validation")

        mae = sc["overall"]["mae_p50"]
        pb = sc["overall"]["pinball_mean"]
        cov = sc["overall"]["coverage"]
        spk = sc["overall"]["brier_spike_mean"]
        dir_b = sc["overall"]["brier_direction"]
        pts = sc["points"]

        d_mae = base_mae - mae
        d_pts = pts - base_pts

        results.append({
            "b": b,
            "mae": mae,
            "pinball": pb,
            "coverage": cov,
            "spike_brier": spk,
            "dir_brier": dir_b,
            "points": pts,
            "d_mae": d_mae,
            "d_pts": d_pts,
        })

        print(f"b={b:+.2f} | MAE: {mae:.4f} (Δ={d_mae:+.4f}) | Pinball: {pb:.4f} | Cov: {cov:.1f}% | Points: {pts:+.3f} (Δ={d_pts:+.4f})")

        if pts > best_pts:
            best_pts = pts
            best_b = b
            best_df = cand_clean

    df_res = pd.DataFrame(results)
    print("\n" + "=" * 80)
    print(f"BEST CANDIDATE: b = {best_b:+.2f} with Points Δ = {best_pts - base_pts:+.4f} pts")

    if best_b != 0.0:
        print("\nRunning Paired Block Bootstrap (1,000 calendar day blocks) on best candidate...")
        boot = paired_block_bootstrap(
            df_base=df_base_clean,
            df_cand=best_df,
            actuals_path=ACTUALS_VAL,
            n_boot=1000,
            seed=42
        )

        ci_mae = boot["delta_mae_95ci"]
        p_win = boot["prob_mae_improves"]
        print(f"Bootstrap Mean ΔMAE:     {boot['delta_mae_mean']:+.4f} EUR/MWh")
        print(f"Bootstrap 95% CI on ΔMAE: [{ci_mae[0]:+.4f}, {ci_mae[1]:+.4f}]")
        print(f"Probability Candidate Beats Baseline: {p_win * 100:.1f}%")

        if ci_mae[0] > 0.0:
            print("\nACCEPTANCE DECISION: ACCEPT (Statistically significant improvement on September).")
            print("Note: Must verify on Fold B before production deployment!")
        else:
            print("\nACCEPTANCE DECISION: REJECT (95% CI crosses zero; not statistically distinguishable from noise).")
            print("Retaining b = 0.0 (fixed 50/50 equal blend) per Clemen's Equal-Weight Theorem.")
    else:
        print("\nACCEPTANCE DECISION: REJECT (Baseline b=0.0 is optimal).")
    print("=" * 80)


if __name__ == "__main__":
    run_experiment()
