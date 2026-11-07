"""Evaluation helper for zero-parameter physical and mixture identities.

Tests:
1A: Nordic Merit-Order Sign Coherence (p50 vs spot and direction)
1B: Exact 50/50 Mixture Median (Precision-Weighted via inverse spread)
1C: Asymmetric Law of Total Variance (p10 / p90 aleatoric + epistemic spread)
1D: Physical Direction Envelope for Spikes (p_spike_high <= p_up, p_spike_low <= p_down)
Combined: Best zero-parameter combination (1C + 1D)

All evaluated using official score.py.
"""
from __future__ import annotations

import io
import os
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = REPO_ROOT / "Dataset" / "starter_package_v1"
ACTUALS_VAL = PKG_DIR / "data" / "actuals_validation.csv"
TEMPLATE_VAL = REPO_ROOT / "results" / "templates" / "validation" / "sample_submission.csv"


def score_variant(df: pd.DataFrame, name: str) -> dict:
    template_cols = pd.read_csv(TEMPLATE_VAL, nrows=0).columns.tolist()
    with tempfile.NamedTemporaryFile(suffix=".csv", mode="w", delete=False) as f:
        df[template_cols].to_csv(f.name, index=False)
        tmp_path = f.name

    out_dir = tempfile.mkdtemp()
    cmd = [
        ".venv/bin/python", str(PKG_DIR / "score.py"),
        "--submission", tmp_path,
        "--actuals", str(ACTUALS_VAL),
        "--output-dir", out_dir
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    res = pd.read_csv(os.path.join(out_dir, "score_summary.csv")).iloc[0]
    os.unlink(tmp_path)

    metrics = {
        "name": name,
        "mae": res["mae_p50"],
        "pinball": res["calibration_pinball_mean"],
        "coverage": res["coverage_p10_p90"] * 100,
        "spike_brier": res["brier_spike_mean"],
        "dir_brier": res["brier_direction"],
    }
    print(f"{name:38s} | MAE: {metrics['mae']:.2f} | Pinball: {metrics['pinball']:.2f} | Cov: {metrics['coverage']:.1f}% | Spk: {metrics['spike_brier']:.5f} | Dir: {metrics['dir_brier']:.5f}")
    return metrics


def main():
    print("=== ZERO-PARAMETER LAWS EVALUATION (September Validation Set) ===\n")

    # Load base frames
    df_frank = pd.read_csv(REPO_ROOT / "results" / "v4_n50" / "validation" / "forecast_backtest.csv")
    res = subprocess.run(
        ["git", "show", "origin/brainstorming-abdo:submissions/validation_team5050.csv"],
        capture_output=True, text=True, check=True
    )
    df_team = pd.read_csv(io.StringIO(res.stdout))

    # Actuals for spot price
    actuals = pd.read_csv(ACTUALS_VAL)
    spot_map = actuals.set_index("delivery_start_utc")["spot_price"].to_dict()
    spot = df_team["delivery_start_utc"].map(spot_map).values

    # Isolated Abdo model
    df_abdo = df_team.copy()
    for col in ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]:
        df_abdo[col] = 2.0 * df_team[col] - df_frank[col]

    results = []

    # 0. Baseline team5050
    s_base = score_variant(df_team, "team5050 (Baseline Benchmark)")
    results.append(s_base)

    # 1A: Nordic Merit-Order Sign Coherence
    df_1a = df_team.copy()
    p50 = df_1a["p50"].values
    p_up, p_down, p_none = df_1a["p_up"].values, df_1a["p_down"].values, df_1a["p_none"].values
    up_contra = (p_up > 0.50 + p_none) & (p50 < spot) & ~np.isnan(spot)
    down_contra = (p_down > 0.50 + p_none) & (p50 > spot) & ~np.isnan(spot)
    df_1a["p50"] = np.where(up_contra | down_contra, spot, p50)
    q = np.sort(df_1a[["p10", "p50", "p90"]].values, axis=1)
    df_1a["p10"], df_1a["p50"], df_1a["p90"] = q[:, 0], q[:, 1], q[:, 2]
    s_1a = score_variant(df_1a, "1A: Nordic Sign Coherence")
    results.append(s_1a)

    # 1B: Exact 50/50 Mixture Median (Precision-Weighted)
    w_A = np.maximum(df_frank["p90"].values - df_frank["p10"].values, 1.0)
    w_B = np.maximum(df_abdo["p90"].values - df_abdo["p10"].values, 1.0)
    p50_prec = (w_B * df_frank["p50"].values + w_A * df_abdo["p50"].values) / (w_A + w_B)
    df_1b = df_team.copy()
    df_1b["p50"] = p50_prec
    q = np.sort(df_1b[["p10", "p50", "p90"]].values, axis=1)
    df_1b["p10"], df_1b["p50"], df_1b["p90"] = q[:, 0], q[:, 1], q[:, 2]
    s_1b = score_variant(df_1b, "1B: Mixture Median (Precision)")
    results.append(s_1b)

    # 1C: Asymmetric Law of Total Variance
    z90 = 1.28155
    disagree_sq = 0.25 * ((df_frank["p50"].values - df_abdo["p50"].values) ** 2) * (z90 ** 2)
    U_A = np.maximum(df_frank["p90"].values - df_frank["p50"].values, 0.0)
    U_B = np.maximum(df_abdo["p90"].values - df_abdo["p50"].values, 0.0)
    L_A = np.maximum(df_frank["p50"].values - df_frank["p10"].values, 0.0)
    L_B = np.maximum(df_abdo["p50"].values - df_abdo["p10"].values, 0.0)

    U_mix = np.sqrt(0.5 * (U_A ** 2) + 0.5 * (U_B ** 2) + disagree_sq)
    L_mix = np.sqrt(0.5 * (L_A ** 2) + 0.5 * (L_B ** 2) + disagree_sq)

    df_1c = df_team.copy()
    df_1c["p90"] = df_team["p50"].values + U_mix
    df_1c["p10"] = df_team["p50"].values - L_mix
    q = np.sort(df_1c[["p10", "p50", "p90"]].values, axis=1)
    df_1c["p10"], df_1c["p50"], df_1c["p90"] = q[:, 0], q[:, 1], q[:, 2]
    s_1c = score_variant(df_1c, "1C: Law of Total Variance (p10/p90)")
    results.append(s_1c)

    # 1D: Physical Direction Envelope for Spikes
    df_1d = df_team.copy()
    df_1d["p_spike_high"] = np.minimum(df_team["p_spike_high"].values, df_team["p_up"].values)
    df_1d["p_spike_low"] = np.minimum(df_team["p_spike_low"].values, df_team["p_down"].values)
    s_1d = score_variant(df_1d, "1D: Physical Spike Dir Envelope")
    results.append(s_1d)

    # Combined 1C + 1D
    df_comb = df_1c.copy()
    df_comb["p_spike_high"] = np.minimum(df_comb["p_spike_high"].values, df_comb["p_up"].values)
    df_comb["p_spike_low"] = np.minimum(df_comb["p_spike_low"].values, df_comb["p_down"].values)
    s_comb = score_variant(df_comb, "Combined (1C LTV + 1D Envelope)")
    results.append(s_comb)

    print("\n=== SUMMARY TABLE ===")
    summary_df = pd.DataFrame(results)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    main()
