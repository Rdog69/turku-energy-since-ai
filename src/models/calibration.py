"""Calibration helpers: Platt maps, weighted quantile offsets, pooled out-of-time holdouts.

The single-holdout recipe (GBMModel calib_mode="single") fits the calibration maps on the last 14
training days. That window can be unrepresentative (RESULTS.md, "Calibration risk on the test run":
P90 offset +28..+36 for the test run vs +14..+21 for validation). Pooled mode instead uses k rolling
holdouts that end at the cutoff, e.g. [c-42d, c-28d), [c-28d, c-14d), [c-14d, c). For each one an
inner model is fitted on rows whose targets were published by the holdout start
(y_first_usable <= start), so every pooled prediction is out of sample and out of time, then the maps
are fitted on the pool. Only data available at the cutoff is used.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}
STEP_BANDS = [(1, 8), (9, 20), (21, 40)]


def logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


class Platt:
    """Monotone recalibration p -> sigmoid(a * logit(p) + b), fitted on a holdout."""

    def __init__(self):
        self.lr = None

    def fit(self, p, y, w=None):
        if len(np.unique(y)) < 2:
            return self
        self.lr = LogisticRegression(C=100.0).fit(logit(p).reshape(-1, 1), y, sample_weight=w)
        return self

    def __call__(self, p):
        if self.lr is None:
            return p
        return self.lr.predict_proba(logit(p).reshape(-1, 1))[:, 1]


class _Product2:
    """Logistic map on logit P(dir) and logit P(tail | dir): free exponents on the two factors."""

    def __init__(self, col):
        self.col = col
        self.lr = None

    def _x(self, up, tail) -> np.ndarray:
        p_dir = np.asarray(up, dtype=float) if self.col == "high" else 1 - np.asarray(up, dtype=float)
        return np.column_stack([logit(p_dir), logit(np.asarray(tail, dtype=float))])

    def fit(self, up, tail, y, w=None):
        if len(np.unique(y)) >= 2:
            self.lr = LogisticRegression(C=100.0).fit(self._x(up, tail), y, sample_weight=w)
        return self

    def __call__(self, raw) -> np.ndarray:
        if self.lr is None:
            return raw["high"] if self.col == "high" else raw["low"]
        return self.lr.predict_proba(self._x(raw["up"], raw[f"{self.col}_tail"]))[:, 1]


def weighted_quantile(x: np.ndarray, q: float, w: np.ndarray | None = None) -> float:
    if w is None:
        return float(np.quantile(x, q))
    order = np.argsort(x)
    x, w = x[order], w[order]
    cum = (np.cumsum(w) - 0.5 * w) / w.sum()
    return float(np.interp(q, cum, x))


def pooled_windows(cutoff: pd.Timestamp, folds: int, days: int) -> list[tuple[pd.Timestamp, pd.Timestamp]]:
    """Rolling holdouts ending at the cutoff, oldest first: [c-k*d, c-(k-1)*d), ..., [c-d, c)."""
    d = pd.Timedelta(days=days)
    return [(cutoff - (folds - i) * d, cutoff - (folds - i - 1) * d) for i in range(folds)]


def fit_maps(pool: pd.DataFrame, spike_mode: str, spike_calib: str = "product") -> tuple[dict, dict, dict]:
    """Fit Platt maps and per-step-band quantile offsets on a pool of out-of-sample predictions.

    pool columns: raw_{p10,p50,p90,up,high,low}, raw_{high,low}_tail (product mode), step, y_gap,
    y_dir, y_high, y_low and w (row weight). Returns (platt, spike_cal, offsets):
      platt["up"] (and ["high"], ["low"] unless a product spike map is used) are 1-D maps on raw
      probabilities; spike_cal["high"|"low"] are maps on the raw-prediction dict (product mode with
      spike_calib "parts" or "product2"); offsets[(col, band_start)] are additive quantile shifts.
    """
    w = pool["w"].to_numpy()
    wf = None if np.all(w == w[0]) else w          # equal weights: exactly the unweighted fit
    platt, spike_cal, offsets = {}, {}, {}
    y_up = (pool["y_dir"] == 1).astype(int).to_numpy()
    platt["up"] = Platt().fit(pool["raw_up"].to_numpy(), y_up, wf)
    y_spike = {"high": pool["y_high"].astype(int).to_numpy(), "low": pool["y_low"].astype(int).to_numpy()}
    for col in ("high", "low"):
        if spike_mode == "product" and spike_calib == "parts":
            # calibrate the parts: P(dir) with the Platt map above, P(tail | dir) on rows of that direction
            sub = (pool["y_dir"] == (1 if col == "high" else -1)).to_numpy()
            tail = Platt().fit(pool[f"raw_{col}_tail"].to_numpy()[sub], y_spike[col][sub], None if wf is None else wf[sub])
            spike_cal[col] = _PartsProduct(platt["up"], tail, col)
        elif spike_mode == "product" and spike_calib == "product2":
            # one logistic map on both logits: free exponents on P(dir) and P(tail | dir)
            spike_cal[col] = _Product2(col).fit(pool["raw_up"].to_numpy(), pool[f"raw_{col}_tail"].to_numpy(),
                                                y_spike[col], wf)
        else:
            # direct classifiers, or the product of the raw parts mapped as one probability
            platt[col] = Platt().fit(pool[f"raw_{col}"].to_numpy(), y_spike[col], wf)
    for col, q in QUANTILES.items():
        resid = pool["y_gap"].to_numpy() - pool[f"raw_{col}"].to_numpy()
        for lo, hi in STEP_BANDS:
            band = pool["step"].between(lo, hi).to_numpy()
            if band.any():   # a short-horizon model has no rows in later bands
                offsets[(col, lo)] = weighted_quantile(resid[band], q, None if wf is None else wf[band])
    return platt, spike_cal, offsets


class _PartsProduct:
    """Calibrated P(dir) x calibrated P(tail | dir)."""

    def __init__(self, up_map, tail_map, col):
        self.up_map, self.tail_map, self.col = up_map, tail_map, col

    def __call__(self, raw) -> np.ndarray:
        up = np.clip(self.up_map(raw["up"]), 0, 1)
        p_dir = up if self.col == "high" else 1 - up
        return p_dir * self.tail_map(raw[f"{self.col}_tail"])
