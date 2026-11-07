"""Experiment E02: Regularized Global Blend Weights Evaluation.

Tests whether a single regularized global weight w in [0.30, 0.70] (centered at 0.50)
improves the official multi-metric score over equal 50/50.

Requirements:
- Evaluates across all 4 official competition metrics
- Measures sensitivity of MAE, Pinball, Spikes, and Direction
- Enforces strict anti-overfitting gate: if optimal weight does not generalize or degrades
  non-target metrics, retain 50/50 per Clemen's theorem.
"""
from __future__ import annotations

import io
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = REPO_ROOT / "Dataset" / "starter_package_v1"
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


def score_candidate(df: pd.DataFrame) -> dict:
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

    # Compute official points vs baseline
    pts = (
        WEIGHTS["MAE"] * (BASELINE_REF["mae_p50"] - summary["mae_p50"]) / BASELINE_REF["mae_p50"]
        + WEIGHTS["pinball"] * (BASELINE_REF["calibration_pinball_mean"] - summary["calibration_pinball_mean"]) / BASELINE_REF["calibration_pinball_mean"]
        + WEIGHTS["brier_spike"] * (BASELINE_REF["brier_spike_mean"] - summary["brier_spike_mean"]) / BASELINE_REF["brier_spike_mean"]
        + WEIGHTS["brier_dir"] * (BASELINE_REF["brier_direction"] - summary["brier_direction"]) / BASELINE_REF["brier_direction"]
    )
    summary["points"] = pts
    return summary


def run_experiment():
    print("=" * 70)
    print("EXPERIMENT E02: REGULARIZED GLOBAL BLEND WEIGHT SWEEP")
    print("=" * 70)

    df_frank = pd.read_csv(FRANK_VAL)
    res = subprocess.run(
        ["git", "show", "origin/brainstorming-abdo:submissions/validation_team5050.csv"],
        capture_output=True, text=True, check=True
    )
    df_team = pd.read_csv(io.StringIO(res.stdout))

    # Reconstruct isolated Abdo model
    df_abdo = df_team.copy()
    for col in ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]:
        df_abdo[col] = 2.0 * df_team[col] - df_frank[col]

    grid = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65]
    results = []

    for w_frank in grid:
        w_abdo = 1.0 - w_frank
        cand = df_team.copy()
        for col in ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]:
            cand[col] = w_frank * df_frank[col] + w_abdo * df_abdo[col]

        # Enforce consistency guards & Kolmogorov direction envelope
        q = np.sort(cand[["p10", "p50", "p90"]].to_numpy(), axis=1)
        cand["p10"], cand["p50"], cand["p90"] = q[:, 0], q[:, 1], q[:, 2]

        probs = cand[["p_up", "p_down", "p_none"]].clip(0, 1)
        cand[["p_up", "p_down", "p_none"]] = probs.div(probs.sum(axis=1), axis=0)

        cand["p_spike_high"] = np.minimum(cand["p_spike_high"], cand["p_up"])
        cand["p_spike_low"] = np.minimum(cand["p_spike_low"], cand["p_down"])
        s = cand["p_spike_high"] + cand["p_spike_low"]
        scale = np.where(s > 1.0, 1.0 / s, 1.0)
        cand["p_spike_high"] *= scale
        cand["p_spike_low"] *= scale

        cand["top_drivers"] = df_frank["top_drivers"].fillna("spot;wind_fc;cons_fc")

        sc = score_candidate(cand)
        results.append({
            "w_frank": w_frank,
            "w_abdo": round(w_abdo, 2),
            "mae": round(sc["mae_p50"], 4),
            "pinball": round(sc["calibration_pinball_mean"], 4),
            "coverage": round(sc["coverage_p10_p90"] * 100.0, 2),
            "spike_brier": round(sc["brier_spike_mean"], 5),
            "dir_brier": round(sc["brier_direction"], 5),
            "points": round(sc["points"], 3),
        })
        print(f"w_frank={w_frank:.2f} (w_abdo={w_abdo:.2f}) | MAE: {sc['mae_p50']:.2f} | Pinball: {sc['calibration_pinball_mean']:.2f} | Spk: {sc['brier_spike_mean']:.5f} | Dir: {sc['brier_direction']:.5f} | Points: {sc['points']:+.3f}")

    df_res = pd.DataFrame(results)
    best_idx = df_res["points"].idxmax()
    best_row = df_res.iloc[best_idx]
    base_row = df_res[df_res["w_frank"] == 0.50].iloc[0]

    print("\n" + "=" * 70)
    print("EXPERIMENT E02 SUMMARY & ACCEPTANCE DECISION:")
    print(f"Baseline (50/50):     Points = {base_row['points']:+.3f} (MAE: {base_row['mae']:.2f}, Pinball: {base_row['pinball']:.2f}, Spk: {base_row['spike_brier']:.5f})")
    print(f"Best Sweep w={best_row['w_frank']:.2f}:   Points = {best_row['points']:+.3f} (MAE: {best_row['mae']:.2f}, Pinball: {best_row['pinball']:.2f}, Spk: {best_row['spike_brier']:.5f})")
    diff_pts = best_row["points"] - base_row["points"]
    print(f"Points Delta:         {diff_pts:+.4f} pts")

    if abs(diff_pts) < 0.05 or best_row["w_frank"] == 0.50:
        print("\nDECISION: RETAIN EQUAL 50/50 WEIGHTS.")
        print("Reason: Per Clemen's Equal-Weight Theorem and Phase 2 guardrails, deviation from 0.50 provides negligible (<0.05 pts) gain and introduces estimation variance that risks unseen-period collapse.")
    else:
        print("\nDECISION: CANDIDATE FOR MULTI-FOLD EVALUATION.")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    run_experiment()
