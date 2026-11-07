"""Calibration module for quantile pinball loss and probability Brier scores."""

from typing import Dict, Tuple
import numpy as np
import pandas as pd


def compute_pinball_corrections(
    y_true: np.ndarray,
    pred_p10: np.ndarray,
    pred_p90: np.ndarray,
    steps: np.ndarray,
    step_bands: Tuple[Tuple[int, int], ...] = ((1, 4), (5, 12), (13, 24), (25, 40)),
    shrinkage: float = 0.5,
) -> Dict[str, dict]:
    """Compute pinball-optimal quantile shifts per step band with shrinkage.

    For quantile q, the shift c_q that minimizes pinball loss sum(rho_q(y - (y_hat + c_q)))
    is the empirical q-quantile of the residual (y - y_hat).
    """
    res_p10 = y_true - pred_p10
    res_p90 = y_true - pred_p90

    # Global corrections
    global_c10 = float(np.nanquantile(res_p10, 0.10))
    global_c90 = float(np.nanquantile(res_p90, 0.90))

    band_corrections_p10 = {}
    band_corrections_p90 = {}

    for low_step, high_step in step_bands:
        mask = (steps >= low_step) & (steps <= high_step)
        if np.sum(mask) > 0:
            c10_band = float(np.nanquantile(res_p10[mask], 0.10))
            c90_band = float(np.nanquantile(res_p90[mask], 0.90))

            # Shrink toward global
            shrunk_c10 = (1.0 - shrinkage) * c10_band + shrinkage * global_c10
            shrunk_c90 = (1.0 - shrinkage) * c90_band + shrinkage * global_c90

            band_corrections_p10[(low_step, high_step)] = shrunk_c10
            band_corrections_p90[(low_step, high_step)] = shrunk_c90
        else:
            band_corrections_p10[(low_step, high_step)] = global_c10
            band_corrections_p90[(low_step, high_step)] = global_c90

    return {
        "p10": band_corrections_p10,
        "p90": band_corrections_p90,
        "global_p10": global_c10,
        "global_p90": global_c90,
    }


def apply_pinball_corrections(
    p10: np.ndarray,
    p50: np.ndarray,
    p90: np.ndarray,
    steps: np.ndarray,
    corrections: dict,
) -> Tuple[np.ndarray, np.ndarray]:
    """Apply the step-band shifts to p10 and p90 and enforce monotonicity."""
    p10_adj = p10.copy()
    p90_adj = p90.copy()

    for (low_step, high_step), shift in corrections["p10"].items():
        mask = (steps >= low_step) & (steps <= high_step)
        p10_adj[mask] += shift

    for (low_step, high_step), shift in corrections["p90"].items():
        mask = (steps >= low_step) & (steps <= high_step)
        p90_adj[mask] += shift

    # Enforce monotonicity: p10 <= p50 <= p90
    p10_final = np.minimum(p10_adj, p50)
    p90_final = np.maximum(p90_adj, p50)

    return p10_final, p90_final


def calibrate_probabilities(
    prob_up: np.ndarray,
    prob_spike_h: np.ndarray,
    prob_spike_l: np.ndarray,
    p_none: float = 0.0017,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Scale and regularize probabilities to ensure strict competition bounds."""
    # Scale direction probabilities
    p_up = prob_up * (1.0 - p_none)
    p_down = (1.0 - prob_up) * (1.0 - p_none)
    p_none_arr = np.full_like(p_up, p_none)

    # Normalize sum strictly to 1.0
    tot = p_up + p_down + p_none_arr
    p_up = p_up / tot * (1.0 - p_none)
    p_down = p_down / tot * (1.0 - p_none)

    # Enforce spike condition: p_spike_high + p_spike_low <= 1.0
    p_spike_h = np.clip(prob_spike_h, 0.0001, 0.999)
    p_spike_l = np.clip(prob_spike_l, 0.0001, 0.999)
    spike_sum = p_spike_h + p_spike_l
    over = spike_sum > 0.998
    if np.any(over):
        p_spike_h[over] = p_spike_h[over] / spike_sum[over] * 0.998
        p_spike_l[over] = p_spike_l[over] / spike_sum[over] * 0.998

    return p_up, p_down, p_none_arr, p_spike_h, p_spike_l

