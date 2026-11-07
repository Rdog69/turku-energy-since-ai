"""Experiment Runner: Chronological Cross-Fitted Residual Learning.

Implements Phase 2 of Grand Champion V4:
- Strictly out-of-fold chronological walk-forward validation (Weeks 37 -> 38 -> 39 -> 40)
- Tests shrinkage factors lambda in [0.0, 0.25, 0.50, 0.75, 1.0]
- Tests Ridge alphas in [10.0, 100.0, 1000.0]
- Minimal displacement projection: ensures p10 <= p50 <= p90
- Full official score.py evaluation
- Paired block-bootstrap 95% confidence intervals on calendar days
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

from src.models.residual_corrector import ResidualCorrector
from src.backtest.postprocess import postprocess_forecasts
from src.backtest.temporal_validation import (
    evaluate_predictions,
    paired_block_bootstrap,
    BASELINE_REF_VAL,
    WEIGHTS,
)

PKG_DIR = REPO_ROOT / "Dataset" / "starter_package_v1"
ACTUALS_VAL = PKG_DIR / "data" / "actuals_validation.csv"
FRANK_VAL_FULL = REPO_ROOT / "results" / "v4_n50" / "validation" / "forecast_full.parquet"
FRANK_VAL_SUB = REPO_ROOT / "results" / "v4_n50" / "validation" / "forecast_backtest.csv"


def prepare_dataset() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Merge predictions with actuals and physical features."""
    # 1. Base team5050 predictions
    res = subprocess.run(
        ["git", "show", "20b414d8c8790ba4e8fc5a491d0dbdab56f1c33c:submissions/validation_team5050.csv"],
        capture_output=True, text=True, check=True
    )
    df_team = pd.read_csv(io.StringIO(res.stdout))
    df_frank = pd.read_csv(FRANK_VAL_SUB)

    # Isolated Abdo model
    df_team["p50_frank"] = df_frank["p50"].values
    df_team["p50_abdo"] = 2.0 * df_team["p50"].values - df_frank["p50"].values
    df_team["top_drivers"] = df_frank["top_drivers"].fillna("spot;wind_fc;cons_fc")

    # 2. Merge physical fundamentals from Frank's full forecast
    df_full = pd.read_parquet(FRANK_VAL_FULL)
    keep_cols = ["origin", "step", "spot", "wind_fc", "cons_fc", "solar_fc"]
    df_full["origin_str"] = pd.to_datetime(df_full["origin"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    
    df_team["forecast_origin_utc"] = pd.to_datetime(df_team["forecast_origin_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    df_team["delivery_start_utc"] = pd.to_datetime(df_team["delivery_start_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    merged = df_team.merge(
        df_full.rename(columns={"origin_str": "forecast_origin_utc"})[["forecast_origin_utc", "step", "spot", "wind_fc", "cons_fc", "solar_fc"]],
        on=["forecast_origin_utc", "step"],
        how="left"
    )

    # 3. Ground truth actuals
    actuals = pd.read_csv(ACTUALS_VAL)
    actuals["delivery_start_utc"] = pd.to_datetime(actuals["delivery_start_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    return merged, actuals


def run_experiment():
    print("=" * 80)
    print("PHASE 2: CHRONOLOGICAL CROSS-FITTED RESIDUAL LEARNING")
    print("=" * 80)

    df_base, actuals = prepare_dataset()
    m = df_base.merge(actuals[["delivery_start_utc", "imbalance_price"]], on="delivery_start_utc", how="left")

    # Add ISO week
    m["dt"] = pd.to_datetime(m["delivery_start_utc"], utc=True)
    m["week"] = m["dt"].dt.isocalendar().week

    weeks = sorted(m["week"].unique())
    print(f"Validation Weeks available: {weeks}")

    # Baseline postprocessed
    df_base_clean = postprocess_forecasts(df_base, mode="validation", expected_rows=len(df_base))
    base_eval = evaluate_predictions(df_base_clean, ACTUALS_VAL, period_name="validation")
    base_mae = base_eval["overall"]["mae_p50"]
    base_pb = base_eval["overall"]["pinball_mean"]
    base_pts = base_eval["points"]

    print("\n--- BASELINE REFERENCE (team5050 50/50) ---")
    print(f"MAE: {base_mae:.4f} EUR/MWh | Pinball: {base_pb:.4f} | Coverage: {base_eval['overall']['coverage']:.1f}% | Points: {base_pts:+.3f}")

    # Grid search over regularization alpha and shrinkage lambda
    alphas = [10.0, 100.0, 1000.0]
    lambdas = [0.10, 0.25, 0.50, 0.75, 1.0]

    results = []

    for alpha in alphas:
        for lam in lambdas:
            # Walk-forward cross-fitting across weeks
            # Stitched out-of-fold corrected p50
            p50_oof = df_base["p50"].to_numpy(dtype=float).copy()

            # Week 37 is the first week: no prior validation week, so it keeps base p50
            # For each subsequent week, fit ONLY on prior weeks
            for i, target_week in enumerate(weeks[1:], start=1):
                train_weeks = weeks[:i]
                train_mask = m["week"].isin(train_weeks) & m["imbalance_price"].notna()
                test_mask = m["week"] == target_week

                train_df = m[train_mask]
                test_df = m[test_mask]

                corrector = ResidualCorrector(alpha=alpha, shrinkage=lam, cap_percentile=95.0)
                corrector.fit(train_df, train_df["imbalance_price"].values)

                # Correct test week
                p50_oof[test_mask.values] = corrector.correct_p50(test_df)

            cand_df = df_base.copy()
            cand_df["p50"] = p50_oof

            # Apply postprocessing (minimal-displacement quantile projection)
            cand_clean = postprocess_forecasts(cand_df, mode="validation", expected_rows=len(cand_df))

            # Evaluate
            cand_eval = evaluate_predictions(cand_clean, ACTUALS_VAL, period_name="validation")
            c_mae = cand_eval["overall"]["mae_p50"]
            c_pb = cand_eval["overall"]["pinball_mean"]
            c_cov = cand_eval["overall"]["coverage"]
            c_pts = cand_eval["points"]
            delta_mae = base_mae - c_mae
            delta_pts = c_pts - base_pts

            results.append({
                "alpha": alpha,
                "lambda": lam,
                "mae": c_mae,
                "pinball": c_pb,
                "coverage": c_cov,
                "points": c_pts,
                "delta_mae": delta_mae,
                "delta_pts": delta_pts,
                "cand_df": cand_clean,
            })
            print(f"Alpha={alpha:6.1f} | Lambda={lam:4.2f} | MAE: {c_mae:.4f} (Δ={delta_mae:+.4f}) | Pinball: {c_pb:.4f} | Cov: {c_cov:.1f}% | Pts: {c_pts:+.3f} (Δ={delta_pts:+.3f})")

    # Find best candidate by official points
    df_res = pd.DataFrame([{k: v for k, v in r.items() if k != "cand_df"} for r in results])
    best_idx = df_res["points"].idxmax()
    best_cand = results[best_idx]

    print("\n" + "=" * 80)
    print("BEST RESIDUAL CORRECTOR CANDIDATE:")
    print(f"Alpha: {best_cand['alpha']}, Lambda: {best_cand['lambda']}")
    print(f"MAE:     {best_cand['mae']:.4f} (Improvement: {best_cand['delta_mae']:+.4f} EUR/MWh)")
    print(f"Pinball: {best_cand['pinball']:.4f} (Baseline: {base_pb:.4f})")
    print(f"Points:  {best_cand['points']:+.3f} (Δ: {best_cand['delta_pts']:+.3f} pts)")

    # Run Paired Block Bootstrap on calendar days for the best candidate
    print("\nRunning Paired Block Bootstrap (1,000 block resamples of calendar days)...")
    boot_res = paired_block_bootstrap(df_base_clean, best_cand["cand_df"], ACTUALS_VAL, n_boot=1000, seed=42)
    print(f"Bootstrap Mean ΔMAE:     {boot_res['delta_mae_mean']:+.4f} EUR/MWh")
    print(f"Bootstrap 95% CI on ΔMAE: [{boot_res['delta_mae_95ci'][0]:+.4f}, {boot_res['delta_mae_95ci'][1]:+.4f}]")
    print(f"Probability Candidate Beats Baseline: {boot_res['prob_mae_improves']*100:.1f}%")
    print(f"Bootstrap Mean ΔPinball: {boot_res['delta_pinball_mean']:+.4f}")
    print(f"Bootstrap 95% CI ΔPinball: [{boot_res['delta_pinball_95ci'][0]:+.4f}, {boot_res['delta_pinball_95ci'][1]:+.4f}]")

    print("\n" + "=" * 80)
    print("ACCEPTANCE DECISION (PHASE 2):")
    if (
        boot_res["delta_mae_95ci"][0] > 0.0
        and best_cand["delta_pts"] > 0.05
        and abs(best_cand["coverage"] - 80.0) <= 1.0
    ):
        print("DECISION: ACCEPT RESIDUAL LEARNING (Statistically significant improvement with positive 95% CI).")
    elif best_cand["delta_mae"] > 0.0 and boot_res["prob_mae_improves"] > 0.60:
        print("DECISION: MARGINAL/LOCAL GAIN — 95% CI CROSSES ZERO.")
        print("Reason: While point estimate improved, the 95% block-bootstrap interval crosses zero. Per strict anti-overfit criteria, do NOT replace the un-tuned equal ensemble unless multi-period significance is confirmed.")
    else:
        print("DECISION: REJECT RESIDUAL LEARNING (Does not improve or degrades baseline).")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_experiment()

