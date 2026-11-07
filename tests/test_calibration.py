"""Pooled calibration: windows end at the cutoff and inner models never see unpublished targets."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.features.build import FEATURE_COLUMNS
from src.models.calibration import fit_maps, pooled_windows
from src.models.gbm import GBMModel

CUTOFF = pd.Timestamp("2026-08-01T00:00:00Z")


def test_pooled_windows_end_at_cutoff():
    w = pooled_windows(CUTOFF, 3, 14)
    assert w[-1][1] == CUTOFF
    assert [b - a for a, b in w] == [pd.Timedelta(days=14)] * 3
    assert all(w[i][1] == w[i + 1][0] for i in range(2))     # contiguous, no overlap
    assert w[0][0] == CUTOFF - pd.Timedelta(days=42)


class _Probe(GBMModel):
    """Records what each inner fit was allowed to see; predictions are random but well-formed."""
    seen: list = []

    def _fit_all(self, df, ref):
        self.seen.append((df["y_first_usable"].max(), ref))
        return {}

    def _raw(self, m, X):
        n = len(X)
        rng = np.random.default_rng(len(self.seen))
        u = rng.uniform(0.05, 0.95, n)
        t = rng.uniform(0.01, 0.3, n)
        return {"p10": rng.normal(-20, 5, n), "p50": rng.normal(0, 5, n), "p90": rng.normal(30, 5, n),
                "up": u, "high_tail": t, "low_tail": t, "high": u * t, "low": (1 - u) * t}


def _train(n_days=70, steps=(1, 8)):
    rng = np.random.default_rng(1)
    origins = pd.date_range(CUTOFF - pd.Timedelta(days=n_days), CUTOFF, freq="h", inclusive="left")
    rows = []
    for s in range(steps[0], steps[1] + 1):
        d = pd.DataFrame({"origin": origins, "step": s})
        d["delivery"] = d["origin"] + pd.Timedelta(minutes=15 * (s - 1))
        d["y_first_usable"] = d["delivery"].dt.ceil("h") + pd.Timedelta(hours=1)   # published after delivery
        rows.append(d)
    df = pd.concat(rows, ignore_index=True)
    df = df.loc[df["y_first_usable"] <= CUTOFF].reset_index(drop=True)
    n = len(df)
    df["y_gap"] = rng.normal(0, 20, n)
    df["y_dir"] = rng.choice([-1, 0, 1], n, p=[0.5, 0.02, 0.48])
    df["y_spike_high"] = (rng.uniform(size=n) < 0.1).astype(int)
    df["y_spike_low"] = (rng.uniform(size=n) < 0.1).astype(int)
    for c in [c for c in FEATURE_COLUMNS if c not in df.columns]:
        df[c] = 0.0
    return df


def test_pooled_inner_fits_only_see_published_targets_and_short_model_skips_bands():
    m = _Probe(calibrate=True, spike_mode="product", calib_mode="pooled", calib_folds=3, holdout_days=14)
    m.seen = []
    train = _train(steps=(1, 8))                       # like the short model: steps 1-8 only
    m._calibrate(train, CUTOFF)
    starts = [CUTOFF - pd.Timedelta(days=d) for d in (42, 28, 14)]
    assert [ref for _, ref in m.seen] == starts
    assert all(max_fu <= ref for max_fu, ref in m.seen)          # y_first_usable <= holdout start
    assert sorted(m.pool["fold"].unique()) == [0, 1, 2]
    assert ("p90", 1) in m.offsets and ("p90", 9) not in m.offsets   # no rows in later bands: skipped
    for col in ("up", "high", "low"):
        assert col in m.platt or col in m.spike_cal


def test_spike_calibration_modes_return_probabilities():
    m = _Probe(calibrate=True, spike_mode="product", calib_mode="pooled")
    m.seen = []
    m._calibrate(_train(), CUTOFF)
    raw = m._raw({}, pd.DataFrame(index=range(50)))
    for mode in ("product", "parts", "product2"):
        platt, spike_cal, _ = fit_maps(m.pool, "product", mode)
        for col in ("high", "low"):
            p = spike_cal[col](raw) if col in spike_cal else platt[col](raw[col])
            assert p.shape == (50,) and np.all((p >= 0) & (p <= 1))
