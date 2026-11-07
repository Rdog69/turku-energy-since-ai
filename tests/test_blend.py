"""MedianFrom must take only P50 and the drivers from the median model."""
from __future__ import annotations

import pandas as pd
import pytest

from src.models.blend import MedianFrom


class Fake:
    def __init__(self, p50, drivers, **flags):
        self.p50, self.drivers, self.fitted = p50, drivers, False
        for k, v in flags.items():
            setattr(self, k, v)

    def fit(self, train, cutoff):
        self.fitted = True
        return self

    def predict(self, feats):
        n = len(feats)
        return pd.DataFrame({"p10": [1.0] * n, "p50": [self.p50] * n, "p90": [9.0] * n,
                             "p_up": [0.3] * n, "p_down": [0.7] * n, "p_none": [0.0] * n,
                             "p_spike_high": [0.1] * n, "p_spike_low": [0.2] * n,
                             "top_drivers": [self.drivers] * n}, index=feats.index)

    def describe(self):
        return "fake"


def test_takes_median_and_drivers_only():
    base = Fake(5.0, "a;b;c", use_weather=True, capacity_weighted=True)
    med = Fake(6.0, "x;y;z", use_weather=True, use_nordic=True, capacity_weighted=True)
    m = MedianFrom(base=base, median=med).fit(pd.DataFrame(), pd.Timestamp("2026-09-06T21:00Z"))
    assert base.fitted and med.fitted
    out = m.predict(pd.DataFrame(index=range(3)))
    assert (out["p50"] == 6.0).all() and (out["top_drivers"] == "x;y;z").all()
    assert (out["p10"] == 1.0).all() and (out["p90"] == 9.0).all() and (out["p_up"] == 0.3).all()
    assert m.use_weather and m.use_nordic and not m.use_icon and m.capacity_weighted


def test_rejects_mixed_weather_weighting():
    m = MedianFrom(base=Fake(5.0, "", capacity_weighted=True), median=Fake(6.0, "", capacity_weighted=False))
    with pytest.raises(ValueError):
        _ = m.capacity_weighted
