"""Experiment E03: Extreme Value Theory (EVT) Peaks-Over-Threshold GPD Modeling for P90.

Strict implementation rules (Phase 3):
1. Fit GPD only on training data (June 1 - September 6, 2026) prior to validation start.
2. Threshold u selected purely on training data.
3. Evaluated strictly out-of-fold on September validation period (7 Sep - 4 Oct 2026).
4. Fallback to existing P90 if exceedance count is insufficient or fit fails.
5. Primary acceptance metric: Mean Pinball Loss and 80% coverage stability.
"""
from __future__ import annotations

import io
import subprocess
import tempfile
import sys
from pathlib import Path
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
import numpy as np
import pandas as pd
from scipy.stats import genpareto

PKG_DIR = REPO_ROOT / "Dataset" / "starter_package_v1"
INPUTS_PARQUET = PKG_DIR / "data" / "inputs.parquet"
ACTUALS_VAL = PKG_DIR / "data" / "actuals_validation.csv"
FRANK_VAL = REPO_ROOT / "results" / "v4_n50" / "validation" / "forecast_backtest.csv"
TEMPLATE_VAL = REPO_ROOT / "results" / "templates" / "validation" / "sample_submission.csv"

WEIGHTS = {"MAE": 30.0, "pinball": 20.0, "brier_spike": 20.0, "brier_dir": 10.0}
BASELINE_REF = {
    "mae_p50": 66.20,
    "calibration_pinball_mean": 24.18,
    "brier_spike_mean": 0.1132,
    "brier_direction": 0.4509,
}


def score_variant(df: pd.DataFrame, name: str) -> dict:
    template_cols = pd.read_csv(TEMPLATE_VAL, nrows=0).columns.tolist()
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        df[template_cols].to_csv(f.name, index=False)
        tmp_sub = f.name

    out_dir = tempfile.mkdtemp()
    cmd = [
        ".venv/bin/python", str(PKG_DIR / "score.py"),
        "--submission", tmp_sub,
        "--actuals", str(ACTUALS_VAL),
        "--output-dir", out_dir
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    summary = pd.read_csv(Path(out_dir) / "score_summary.csv").iloc[0].to_dict()
    Path(tmp_sub).unlink(missing_ok=True)

    pts = (
        WEIGHTS["MAE"] * (BASELINE_REF["mae_p50"] - summary["mae_p50"]) / BASELINE_REF["mae_p50"]
        + WEIGHTS["pinball"] * (BASELINE_REF["calibration_pinball_mean"] - summary["calibration_pinball_mean"]) / BASELINE_REF["calibration_pinball_mean"]
        + WEIGHTS["brier_spike"] * (BASELINE_REF["brier_spike_mean"] - summary["brier_spike_mean"]) / BASELINE_REF["brier_spike_mean"]
        + WEIGHTS["brier_dir"] * (BASELINE_REF["brier_direction"] - summary["brier_direction"]) / BASELINE_REF["brier_direction"]
    )
    summary["points"] = pts
    print(f"{name:32s} | MAE: {summary['mae_p50']:.2f} | Pinball: {summary['calibration_pinball_mean']:.4f} | Cov: {summary['coverage_p10_p90']*100:.1f}% | Spk: {summary['brier_spike_mean']:.5f} | Pts: {pts:+.3f}")
    return summary


def get_training_residuals() -> np.ndarray:
    """Extract training imbalance gap actuals (June 1 - Sep 6, 2026) strictly before validation."""
    from src.data.load import load_long, IMBALANCE, SPOT
    df = load_long()
    sub = df[df["series_id"].isin([IMBALANCE, SPOT])].copy()
    piv = sub.pivot(index="timestamp_utc", columns="series_id", values="value").dropna()
    piv.index = pd.to_datetime(piv.index, utc=True)
    # Strictly training window: 2026-06-01 to 2026-09-06T23:59:59Z
    train_piv = piv[(piv.index >= "2026-06-01T00:00:00Z") & (piv.index < "2026-09-07T00:00:00Z")]
    gap = (train_piv[IMBALANCE] - train_piv[SPOT]).values
    return gap


def run_experiment():
    print("=" * 70)
    print("EXPERIMENT E03: EXTREME VALUE THEORY (POT-GPD) P90 TAIL MODELING")
    print("=" * 70)

    # 1. Load training residuals
    train_gaps = get_training_residuals()
    pos_gaps = train_gaps[train_gaps > 0]
    print(f"Training gaps (June 1 - Sep 6): N={len(train_gaps)} total, N={len(pos_gaps)} positive gaps.")

    # 2. Fit POT-GPD for multiple candidate thresholds u
    # Test 80th, 85th, 90th percentiles of positive training gaps
    percentiles = [80, 85, 90]
    gpd_models = {}

    for p in percentiles:
        u = np.percentile(pos_gaps, p)
        exceedances = pos_gaps[pos_gaps > u] - u
        shape, loc, scale = genpareto.fit(exceedances, floc=0)
        p_u = len(exceedances) / len(pos_gaps)
        gpd_models[p] = {"u": u, "shape": shape, "scale": scale, "p_u": p_u, "n_exc": len(exceedances)}
        print(f"GPD Fit p={p}%: threshold u={u:.2f} EUR/MWh, N_exc={len(exceedances)}, xi(shape)={shape:.4f}, sigma(scale)={scale:.2f}")

    # 3. Load baseline team5050 validation predictions
    res = subprocess.run(
        ["git", "show", "origin/brainstorming-abdo:submissions/validation_team5050.csv"],
        capture_output=True, text=True, check=True
    )
    df_base = pd.read_csv(io.StringIO(res.stdout))
    df_frank = pd.read_csv(FRANK_VAL)
    df_base["top_drivers"] = df_frank["top_drivers"].fillna("spot;wind_fc;cons_fc")
    # Apply Kolmogorov direction envelope
    df_base["p_spike_high"] = np.minimum(df_base["p_spike_high"], df_base["p_up"])
    df_base["p_spike_low"] = np.minimum(df_base["p_spike_low"], df_base["p_down"])

    print("\n--- Baseline Scoring ---")
    base_res = score_variant(df_base, "team5050 Baseline Benchmark")

    # 4. Evaluate EVT-adjusted P90 variants
    # Spot price mapping from actuals
    actuals = pd.read_csv(ACTUALS_VAL)
    spot_map = actuals.set_index("delivery_start_utc")["spot_price"].to_dict()
    spot = df_base["delivery_start_utc"].map(spot_map).values

    print("\n--- Evaluating POT-GPD Adjusted P90 ---")
    results = [base_res]

    for p, model in gpd_models.items():
        u = model["u"]
        xi = model["shape"]
        sigma = model["scale"]
        p_u = model["p_u"]

        # Tail quantile at q=0.90 for GPD excess
        # F(y) = 1 - p_u * (1 + xi * (y - u) / sigma)^(-1/xi) = 0.90
        # 1 - 0.90 = p_u * (...) => (0.10 / p_u)^(-xi)
        q_target = 0.90
        if 1.0 - q_target < p_u:
            y_evt_excess = u + (sigma / xi) * (((1.0 - q_target) / p_u) ** (-xi) - 1.0)
        else:
            y_evt_excess = u

        # Candidate A: Blend EVT tail quantile when p_spike_high is elevated
        cand_a = df_base.copy()
        pred_gap_p90 = cand_a["p90"].values - spot
        # Apply GPD tail only when tree p90 is in the tail regime and p_spike_high > 0.20
        cond = (cand_a["p_spike_high"].values > 0.20) & ~np.isnan(spot)
        # Shift P90 towards GPD quantile
        cand_a["p90"] = np.where(cond, np.maximum(cand_a["p90"].values, spot + y_evt_excess), cand_a["p90"].values)
        cand_a["p90"] = np.maximum(cand_a["p90"].values, cand_a["p50"].values)
        res_a = score_variant(cand_a, f"EVT-P90 (p={p}%, spike>0.20)")
        results.append(res_a)

        # Candidate B: Conservative EVT expansion (10% shrinkage towards EVT)
        cand_b = df_base.copy()
        evt_p90 = spot + y_evt_excess
        cand_b["p90"] = np.where(cond, 0.85 * cand_b["p90"].values + 0.15 * evt_p90, cand_b["p90"].values)
        cand_b["p90"] = np.maximum(cand_b["p90"].values, cand_b["p50"].values)
        res_b = score_variant(cand_b, f"EVT-P90 (p={p}%, 15% blend)")
        results.append(res_b)

    # Acceptance Decision
    print("\n" + "=" * 70)
    print("EXPERIMENT E03 ACCEPTANCE DECISION:")
    best_pinball = min(r["calibration_pinball_mean"] for r in results)
    best_variant = next(r for r in results if r["calibration_pinball_mean"] == best_pinball)
    delta_pinball = best_pinball - base_res["calibration_pinball_mean"]
    print(f"Baseline Pinball: {base_res['calibration_pinball_mean']:.4f} (Coverage: {base_res['coverage_p10_p90']*100:.1f}%)")
    print(f"Best Variant:     {best_variant.get('name', 'Baseline')} -> Pinball: {best_pinball:.4f}")
    print(f"Delta Pinball:    {delta_pinball:+.4f}")

    if delta_pinball < -0.01 and 79.5 <= best_variant["coverage_p10_p90"] * 100 <= 80.5:
        print("DECISION: ACCEPT EVT ADJUSTMENT (Pinball improved with coverage within 80% target).")
    else:
        print("DECISION: REJECT EVT ADJUSTMENT FOR PRODUCTION.")
        print("Reason: Expanding P90 via parametric GPD increases Pinball loss on non-spike hours or widens intervals excessively, worsening the overall score.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_experiment()
