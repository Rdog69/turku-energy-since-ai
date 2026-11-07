#!/usr/bin/env python3
"""Generate 3 figures for the forecasting pipeline slides."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))   # repo root, for `src`

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.config import VALIDATION_FIRST_ORIGIN
from src.data.load import load_long
from src.data.availability import build_index
from src.features.build import build_features

FIGSIZE = (1600 / 160, 900 / 160)
DPI = 160
GRID_COLOR = "#e0e0e0"
CB_COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd", "#8c564b", "#e377c2", "#7f7f7f"]

OUTPUT_DIR = Path("reports/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def training_rows() -> pd.DataFrame:
    """Training data only: hourly origins before the validation period, step 1 (one row per
    delivery quarter), targets published before the validation cut-off."""
    long = load_long()
    index = build_index(long)
    origins = pd.date_range(pd.Timestamp("2026-06-02T00:00Z"), VALIDATION_FIRST_ORIGIN, freq="h",
                            inclusive="left")
    f = build_features(long, origins, index=index)
    f = f[(f["step"] == 1) & (f["y_first_usable"] <= VALIDATION_FIRST_ORIGIN)]
    return f.dropna(subset=["y_gap", "y_dir"])


def figure_1(f):
    """Figure 1: gap by wind quintile."""
    f = f.copy()

    bins = np.percentile(f["wind_fc"], np.linspace(0, 100, 6))
    f["wind_bin"] = pd.cut(f["wind_fc"], bins, include_lowest=True)
    grouped = f.groupby("wind_bin", observed=True)["y_gap"]

    medians = grouped.median()
    q25 = grouped.quantile(0.25)
    q75 = grouped.quantile(0.75)
    up_share = (f["y_dir"] == 1).groupby(f["wind_bin"], observed=True).mean()

    fig, ax1 = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    x = np.arange(len(medians))
    ax1.plot(x, medians, marker="o", color=CB_COLORS[0], label="Median gap")
    ax1.fill_between(x, q25, q75, color=CB_COLORS[0], alpha=0.2, label="Middle 50 % of gaps")
    ax1.set_xticks(x, [f"Q{i + 1}\n{iv.left:,.0f}–{iv.right:,.0f}" for i, iv in enumerate(medians.index)])
    ax1.axhline(0, color="gray", linewidth=0.8)
    ax1.set_xlabel("Day-ahead wind forecast quintile (MW)")
    ax1.set_ylabel("Gap to spot (EUR/MWh)", color=CB_COLORS[0])
    ax1.tick_params(axis='y', labelcolor=CB_COLORS[0])
    ax1.grid(True, color=GRID_COLOR)

    ax2 = ax1.twinx()
    ax2.plot(x, up_share, marker="s", color=CB_COLORS[1], label="Up-regulation share")
    ax2.set_ylabel("Up-regulation share", color=CB_COLORS[1])
    ax2.set_ylim(0, 0.6)
    ax2.tick_params(axis='y', labelcolor=CB_COLORS[1])

    ax1.set_title("Low wind: wider jumps and more up-regulation (training data, Jun – 6 Sep)")
    fig.tight_layout()
    path = OUTPUT_DIR / "gap_by_wind_quintile.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(path)


def figure_2(f):
    """Figure 2: gap magnitude by local hour."""
    f = f.copy()

    grouped = f["y_gap"].abs().groupby(f["hour"])
    medians = grouped.median()
    q25 = grouped.quantile(0.25)
    q75 = grouped.quantile(0.75)

    fig, ax = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    x = medians.index
    ax.plot(x, medians, marker="o", color=CB_COLORS[0], label="Median |gap|")
    ax.fill_between(x, q25, q75, color=CB_COLORS[0], alpha=0.2, label="IQR")
    ax.set_xlabel("Local hour")
    ax.set_ylabel("|Gap| to spot (EUR/MWh)")
    ax.set_title("The evening peak is where the jumps are (training data, Jun – 6 Sep)")
    ax.grid(True, color=GRID_COLOR)
    fig.tight_layout()
    path = OUTPUT_DIR / "gap_by_local_hour.png"
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    print(path)


def figure_3():
    """Figure 3: error by horizon."""
    path = Path("results/split_all/validation/score/score_by_horizon.csv")
    if not path.exists():
        print("Note: Skipping figure 3 (score_by_horizon.csv not found)")
        return

    df = pd.read_csv(path)
    df = df[df["horizon_hour"].between(1, 10)]

    fig, ax1 = plt.subplots(figsize=FIGSIZE, dpi=DPI)
    x = df["horizon_hour"]
    ax1.plot(x, df["mae_p50"], marker="o", color=CB_COLORS[0], label="MAE")
    ax1.plot(x, df["calibration_pinball_mean"], marker="s", color=CB_COLORS[1],
             label="Mean pinball loss")
    ax1.set_xlabel("Forecast hour")
    ax1.set_ylabel("Error (EUR/MWh)")
    ax1.legend(loc="upper left")
    ax1.grid(True, color=GRID_COLOR)

    ax2 = ax1.twinx()
    ax2.plot(x, df["coverage_p10_p90"], marker="^", linestyle="--", color=CB_COLORS[2],
             label="Coverage (p10-p90)")
    ax2.axhline(0.80, color="gray", linestyle=":", linewidth=1, label="Reference: 0.80")
    ax2.set_ylabel("P10–P90 coverage")
    ax2.set_ylim(0.6, 0.9)
    ax2.legend(loc="upper right")

    ax1.set_title("Accuracy by forecast hour (validation, 7 Sep – 4 Oct)")
    fig.tight_layout()
    out_path = OUTPUT_DIR / "error_by_horizon.png"
    fig.savefig(out_path, dpi=DPI)
    plt.close(fig)
    print(out_path)


if __name__ == "__main__":
    rows = training_rows()
    figure_1(rows)
    figure_2(rows)
    figure_3()

