"""Unified Post-Processing & Monotonicity Guards for Imbalance Price Forecasts.

Handles identically for validation, holdout, and test backtest predictions:
1. Minimal-displacement quantile projection: p10 <= p50 <= p90 without shifting p50
2. Direction probability validation & normalization: sum(p_up, p_down, p_none) == 1.0
3. Zero-parameter Kolmogorov physical direction envelope:
   - p_spike_high <= p_up
   - p_spike_low <= p_down
4. Spike sum constraint: p_spike_high + p_spike_low <= 1.0
5. Data cutoff verification: data_cutoff_utc <= forecast_origin_utc
6. Schema and completeness verification (no NaNs, correct row counts, ISO timestamps)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = [
    "forecast_origin_utc",
    "delivery_start_utc",
    "step",
    "p10",
    "p50",
    "p90",
    "p_up",
    "p_down",
    "p_none",
    "p_spike_high",
    "p_spike_low",
]
OPTIONAL_COLUMNS = ["data_cutoff_utc", "top_drivers"]
ALL_STANDARD_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

ISO_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class PostProcessingError(ValueError):
    """Raised when predictions violate fundamental constraints or cannot be projected safely."""


def postprocess_forecasts(
    df: pd.DataFrame,
    mode: Literal["validation", "fold_b", "test"] = "test",
    expected_rows: int | None = None,
) -> pd.DataFrame:
    """Apply unified post-processing pipeline ensuring strict rule compliance."""
    out = df.copy()

    # 1. Schema check
    missing_cols = [c for c in REQUIRED_COLUMNS if c not in out.columns]
    if missing_cols:
        raise PostProcessingError(f"Missing required columns: {missing_cols}")

    if expected_rows is not None and len(out) != expected_rows:
        raise PostProcessingError(f"Row count mismatch: expected {expected_rows}, got {len(out)}")

    # 2. Check for NaNs or Infs in numeric outputs
    num_cols = ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]
    for col in num_cols:
        if out[col].isna().any():
            nan_count = out[col].isna().sum()
            raise PostProcessingError(f"Found {nan_count} NaNs in numeric column '{col}'")
        if np.isinf(out[col]).any():
            raise PostProcessingError(f"Found Infinite values in numeric column '{col}'")

    # 3. Minimal-Displacement Quantile Projection
    # Rather than unconditionally sorting [p10, p50, p90] which can displace the calibrated median p50,
    # we enforce p10 = min(p10, p50) and p90 = max(p90, p50).
    p10 = out["p10"].to_numpy(dtype=float)
    p50 = out["p50"].to_numpy(dtype=float)
    p90 = out["p90"].to_numpy(dtype=float)

    out["p10"] = np.minimum(p10, p50)
    out["p90"] = np.maximum(p90, p50)

    # Secondary check: ensure p10 <= p90
    assert (out["p10"] <= out["p50"]).all(), "p10 > p50 assertion failed"
    assert (out["p50"] <= out["p90"]).all(), "p50 > p90 assertion failed"

    # 4. Direction Probability Validation & Normalization
    p_up = out["p_up"].to_numpy(dtype=float)
    p_down = out["p_down"].to_numpy(dtype=float)
    p_none = out["p_none"].to_numpy(dtype=float)

    # Clip to [0, 1]
    p_up = np.clip(p_up, 0.0, 1.0)
    p_down = np.clip(p_down, 0.0, 1.0)
    p_none = np.clip(p_none, 0.0, 1.0)

    dir_sum = p_up + p_down + p_none
    if (dir_sum <= 1e-6).any():
        raise PostProcessingError("Found direction probabilities with sum near zero")

    out["p_up"] = p_up / dir_sum
    out["p_down"] = p_down / dir_sum
    out["p_none"] = 1.0 - out["p_up"] - out["p_down"]

    # 5. Zero-Parameter Kolmogorov Direction Envelope for Spikes
    # An exceptional positive spike (>+50 EUR/MWh above spot) physically requires mFRR up-regulation.
    # Therefore, P(Spike_High) <= P(Up) and P(Spike_Low) <= P(Down).
    out["p_spike_high"] = np.clip(out["p_spike_high"].to_numpy(dtype=float), 0.0, 1.0)
    out["p_spike_low"] = np.clip(out["p_spike_low"].to_numpy(dtype=float), 0.0, 1.0)

    out["p_spike_high"] = np.minimum(out["p_spike_high"], out["p_up"])
    out["p_spike_low"] = np.minimum(out["p_spike_low"], out["p_down"])

    # 6. Spike Sum Bound: p_spike_high + p_spike_low <= 1.0
    spike_sum = out["p_spike_high"] + out["p_spike_low"]
    scale = np.where(spike_sum > 1.0, 1.0 / spike_sum, 1.0)
    out["p_spike_high"] *= scale
    out["p_spike_low"] *= scale

    # 7. Timestamp Availability Integrity
    if "data_cutoff_utc" in out.columns:
        origin_dt = pd.to_datetime(out["forecast_origin_utc"], utc=True)
        cutoff_dt = pd.to_datetime(out["data_cutoff_utc"], utc=True)
        # Ensure data cutoff never violates causality
        if (cutoff_dt > origin_dt).any():
            violations = (cutoff_dt > origin_dt).sum()
            raise PostProcessingError(f"Causality violation: {violations} rows have data_cutoff_utc > forecast_origin_utc!")
        out["data_cutoff_utc"] = cutoff_dt.dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    # Format timestamps strictly as ISO UTC
    out["forecast_origin_utc"] = pd.to_datetime(out["forecast_origin_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out["delivery_start_utc"] = pd.to_datetime(out["delivery_start_utc"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    out["step"] = out["step"].astype(int)

    # 8. Explainability verification
    if "top_drivers" in out.columns:
        empty_drivers = out["top_drivers"].isna() | out["top_drivers"].astype(str).str.strip().eq("")
        if empty_drivers.any():
            count = empty_drivers.sum()
            raise PostProcessingError(f"Found {count} empty/NaN top_drivers rows! All rows must have valid drivers.")

    # Return formatted columns
    final_cols = [c for c in ALL_STANDARD_COLUMNS if c in out.columns]
    return out[final_cols]

