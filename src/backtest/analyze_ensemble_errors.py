"""Experiment E01: Multi-Fold Ensemble Error & Complementarity Analysis.

Measures:
1. Individual model performance (Frank v4_n50 vs Abdo P2 INT4+ss lgb7)
2. Error correlation rho(e_Frank, e_Abdo) overall and across horizon bands
3. Variance reduction from equal-weight linear pooling
4. Error correlation during extreme price spikes (|imbalance - spot| > 50)
5. Error correlation during negative price regimes (imbalance < 0 or spot < 0)
6. Head-by-head complementarity (P50, P10/P90, Spikes, Direction)
"""
from __future__ import annotations

import io
import subprocess
from pathlib import Path
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = REPO_ROOT / "Dataset" / "starter_package_v1"
ACTUALS_VAL = PKG_DIR / "data" / "actuals_validation.csv"
FRANK_VAL = REPO_ROOT / "results" / "v4_n50" / "validation" / "forecast_backtest.csv"

HORIZON_BANDS = {
    "Hour 1 (1-4)": (1, 4),
    "Hours 2-4 (5-16)": (5, 16),
    "Hours 5-7 (17-28)": (17, 28),
    "Hours 8-10 (29-40)": (29, 40),
}


def load_data():
    df_frank = pd.read_csv(FRANK_VAL)
    res = subprocess.run(
        ["git", "show", "origin/brainstorming-abdo:submissions/validation_team5050.csv"],
        capture_output=True, text=True, check=True
    )
    df_team = pd.read_csv(io.StringIO(res.stdout))
    actuals = pd.read_csv(ACTUALS_VAL)

    # Reconstruct isolated Abdo model: 2 * team - frank
    df_abdo = df_team.copy()
    for col in ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]:
        df_abdo[col] = 2.0 * df_team[col] - df_frank[col]

    return df_frank, df_abdo, df_team, actuals


def analyze():
    print("=" * 70)
    print("EXPERIMENT E01: ENSEMBLE ERROR & COMPLEMENTARITY ANALYSIS")
    print("=" * 70)

    df_frank, df_abdo, df_team, actuals = load_data()
    m = df_team[["forecast_origin_utc", "delivery_start_utc", "step"]].copy()
    m["p50_frank"] = df_frank["p50"].values
    m["p50_abdo"] = df_abdo["p50"].values
    m["p50_blend"] = df_team["p50"].values

    m = m.merge(actuals, on="delivery_start_utc", how="inner").dropna(subset=["imbalance_price", "spot_price"])

    y = m["imbalance_price"].values
    e_frank = y - m["p50_frank"].values
    e_abdo = y - m["p50_abdo"].values
    e_blend = y - m["p50_blend"].values

    # 1. Overall Error Statistics
    mae_frank = np.mean(np.abs(e_frank))
    mae_abdo = np.mean(np.abs(e_abdo))
    mae_blend = np.mean(np.abs(e_blend))

    var_frank = np.var(e_frank)
    var_abdo = np.var(e_abdo)
    var_blend = np.var(e_blend)
    corr_overall = np.corrcoef(e_frank, e_abdo)[0, 1]

    theoretical_blend_var = 0.25 * var_frank + 0.25 * var_abdo + 0.5 * np.cov(e_frank, e_abdo)[0, 1]

    print("\n1. Overall P50 Accuracy & Variance Reduction:")
    print(f"   Frank v4_n50 MAE:    {mae_frank:.3f} EUR/MWh (Var: {var_frank:.1f})")
    print(f"   Abdo P2 INT4 MAE:    {mae_abdo:.3f} EUR/MWh (Var: {var_abdo:.1f})")
    print(f"   Equal 50/50 MAE:     {mae_blend:.3f} EUR/MWh (Var: {var_blend:.1f})")
    print(f"   Residual Correlation: rho = {corr_overall:.4f}")
    print(f"   Variance Reduction:   -{(1.0 - var_blend / min(var_frank, var_abdo)) * 100:.2f}% vs best individual model")

    # 2. Horizon Breakdown of Error Correlation
    print("\n2. Horizon-by-Horizon Correlation & MAE:")
    print(f"   {'Horizon':18s} | {'Frank MAE':10s} | {'Abdo MAE':10s} | {'Blend MAE':10s} | {'Error Corr (rho)':16s} | {'MAE Gain':8s}")
    print("   " + "-" * 75)
    for h_name, (s_min, s_max) in HORIZON_BANDS.items():
        sub = m[(m["step"] >= s_min) & (m["step"] <= s_max)]
        ef = sub["imbalance_price"].values - sub["p50_frank"].values
        ea = sub["imbalance_price"].values - sub["p50_abdo"].values
        eb = sub["imbalance_price"].values - sub["p50_blend"].values

        mf = np.mean(np.abs(ef))
        ma = np.mean(np.abs(ea))
        mb = np.mean(np.abs(eb))
        rho = np.corrcoef(ef, ea)[0, 1]
        gain = min(mf, ma) - mb
        print(f"   {h_name:18s} | {mf:10.2f} | {ma:10.2f} | {mb:10.2f} | {rho:16.4f} | {gain:+8.2f}")

    # 3. Market Regimes: Spikes vs Normal vs Negative
    print("\n3. Market Regime Diagnostics:")
    # Spike regime: |imbalance - spot| > 50
    m["gap"] = m["imbalance_price"] - m["spot_price"]
    spikes = m[np.abs(m["gap"]) > 50.0]
    normal = m[np.abs(m["gap"]) <= 50.0]
    negative = m[m["imbalance_price"] < 0.0]

    for reg_name, reg_df in [("Spikes (|gap| > 50)", spikes), ("Normal (|gap| <= 50)", normal), ("Negative Prices (< 0)", negative)]:
        if len(reg_df) == 0:
            continue
        ef = reg_df["imbalance_price"].values - reg_df["p50_frank"].values
        ea = reg_df["imbalance_price"].values - reg_df["p50_abdo"].values
        eb = reg_df["imbalance_price"].values - reg_df["p50_blend"].values
        mf = np.mean(np.abs(ef))
        ma = np.mean(np.abs(ea))
        mb = np.mean(np.abs(eb))
        rho = np.corrcoef(ef, ea)[0, 1] if len(reg_df) > 1 else np.nan
        print(f"   {reg_name:25s} (N={len(reg_df):5d}) | Frank: {mf:6.2f} | Abdo: {ma:6.2f} | Blend: {mb:6.2f} | rho: {rho:.4f}")

    # 4. Disagreement as Uncertainty Proxy
    disagreement = np.abs(m["p50_frank"].values - m["p50_abdo"].values)
    m["disagreement"] = disagreement
    corr_disagree_error = np.corrcoef(disagreement, np.abs(e_blend))[0, 1]
    print(f"\n4. Model Disagreement as Uncertainty Indicator:")
    print(f"   Mean Disagreement |p50_frank - p50_abdo|: {np.mean(disagreement):.2f} EUR/MWh")
    print(f"   Correlation between Disagreement and Absolute Blend Error: rho = {corr_disagree_error:.4f}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    analyze()
