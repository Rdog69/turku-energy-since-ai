"""Blend test submissions from brainstorming-jim and brainstorming-abdo.

Produces a combined test submission that leverages:
- 60% brainstorming-jim + 40% brainstorming-abdo for Price (MAE: 42.78 EUR/MWh)
- 50% brainstorming-jim + 50% brainstorming-abdo for Quantiles (Pinball: 12.37)
- 60% brainstorming-jim + 40% brainstorming-abdo for Direction (Brier: 0.4180)
- 40% brainstorming-jim + 60% brainstorming-abdo for Spikes (Brier: 0.0923)

Usage:
    python src/models/blend_submissions.py --output forecast_backtest_blend.csv
"""

from __future__ import annotations

import argparse
import io
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description="Blend multi-branch submissions.")
    parser.add_argument("--ours", default=str(ROOT / "forecast_backtest.csv"), help="Our submission file")
    parser.add_argument("--theirs-branch", default="origin/brainstorming-abdo", help="Teammate remote branch")
    parser.add_argument(
        "--theirs-file",
        default="submissions/forecast_backtest_ref_mixture.csv",
        help="Path in teammate branch",
    )
    parser.add_argument("--output", default=str(ROOT / "results" / "forecast_backtest_blend.csv"), help="Output path")
    args = parser.parse_args()

    print(f"Loading our submission from: {args.ours}")
    df_ours = pd.read_csv(args.ours)

    print(f"Loading teammate submission from {args.theirs_branch}:{args.theirs_file}...")
    cmd = ["git", "show", f"{args.theirs_branch}:{args.theirs_file}"]
    out = subprocess.check_output(cmd)
    df_theirs = pd.read_csv(io.BytesIO(out))

    assert len(df_ours) == len(df_theirs), f"Row mismatch: {len(df_ours)} vs {len(df_theirs)}"
    print(f"Merging {len(df_ours)} rows across all 673 origins...")

    df_blend = df_ours.copy()

    # 1. Price p50
    df_blend["p50"] = np.round(0.6 * df_ours["p50"] + 0.4 * df_theirs["p50"], 4)

    # 2. Quantiles p10, p90
    df_blend["p10"] = np.round(0.5 * df_ours["p10"] + 0.5 * df_theirs["p10"], 4)
    df_blend["p90"] = np.round(0.5 * df_ours["p90"] + 0.5 * df_theirs["p90"], 4)

    # Monotonicity enforcement
    df_blend["p10"] = np.minimum(df_blend["p10"], df_blend["p50"])
    df_blend["p90"] = np.maximum(df_blend["p90"], df_blend["p50"])

    # 3. Direction probabilities
    p_up = 0.6 * df_ours["p_up"] + 0.4 * df_theirs["p_up"]
    p_down = 0.6 * df_ours["p_down"] + 0.4 * df_theirs["p_down"]
    p_none = 0.6 * df_ours["p_none"] + 0.4 * df_theirs["p_none"]

    total_p = p_up + p_down + p_none
    df_blend["p_up"] = np.round(p_up / total_p, 6)
    df_blend["p_down"] = np.round(p_down / total_p, 6)
    df_blend["p_none"] = np.round(1.0 - df_blend["p_up"] - df_blend["p_down"], 6)

    # 4. Spikes probabilities
    df_blend["p_spike_high"] = np.clip(
        np.round(0.4 * df_ours["p_spike_high"] + 0.6 * df_theirs["p_spike_high"], 6), 0.0, 1.0
    )
    df_blend["p_spike_low"] = np.clip(
        np.round(0.4 * df_ours["p_spike_low"] + 0.6 * df_theirs["p_spike_low"], 6), 0.0, 1.0
    )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_blend.to_csv(out_path, index=False)
    print(f"\n[OK] Blended submission generated: {out_path} ({len(df_blend)} rows)")


if __name__ == "__main__":
    main()
