"""Spot-anchor model: price = spot + a constant gap distribution.

The floor every other model must beat. It uses no recent state at all: the gap quantiles,
direction shares and spike shares come from training rows only.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass
class SpotAnchor:
    q10: float = 0.0
    q50: float = 0.0
    q90: float = 0.0
    p_up: float = 0.0
    p_down: float = 0.0
    p_none: float = 0.0
    p_spike_high: float = 0.0
    p_spike_low: float = 0.0
    n_train: int = 0

    name = "spot_anchor"

    def fit(self, train: pd.DataFrame, cutoff: pd.Timestamp | None = None) -> "SpotAnchor":
        # one row per delivery quarter: each quarter appears up to 40 times (once per origin)
        rows = train.drop_duplicates("delivery").dropna(subset=["y_gap", "y_dir"])
        gap = rows["y_gap"].to_numpy()
        self.q10, self.q50, self.q90 = np.quantile(gap, [0.1, 0.5, 0.9])
        self.p_up = float((rows["y_dir"] == 1).mean())
        self.p_down = float((rows["y_dir"] == -1).mean())
        self.p_none = 1.0 - self.p_up - self.p_down
        self.p_spike_high = float(rows["y_spike_high"].mean())
        self.p_spike_low = float(rows["y_spike_low"].mean())
        self.n_train = len(rows)
        return self

    def predict(self, feats: pd.DataFrame) -> pd.DataFrame:
        spot = feats["spot"].to_numpy()
        out = pd.DataFrame({
            "p10": spot + self.q10,
            "p50": spot + self.q50,
            "p90": spot + self.q90,
            "p_up": self.p_up,
            "p_down": self.p_down,
            "p_none": self.p_none,
            "p_spike_high": self.p_spike_high,
            "p_spike_low": self.p_spike_low,
            "top_drivers": "spot",
        }, index=feats.index)
        return out

    def describe(self) -> str:
        return (f"{self.name}: {self.n_train} training quarters; gap q10/q50/q90 "
                f"{self.q10:.1f}/{self.q50:.1f}/{self.q90:.1f}; up/down/none "
                f"{self.p_up:.3f}/{self.p_down:.3f}/{self.p_none:.4f}; spikes high/low "
                f"{self.p_spike_high:.3f}/{self.p_spike_low:.3f}")
