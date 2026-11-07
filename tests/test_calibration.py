"""Shrunk Platt scaling: a huge m0 means no recalibration, a moderate m0 a partial one."""
from __future__ import annotations

import numpy as np

from src.models.gbm import _Platt


def test_shrunk_platt_sits_between_identity_and_full_platt():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.01, 0.5, 4000)
    y = (rng.uniform(size=4000) < p * 0.3).astype(int)      # the raw model over-predicts ~3x
    deliveries = np.arange(4000)
    plain = _Platt().fit(p, y)
    none = _Platt(shrink_m0=10**9).fit(p, y, deliveries)
    partial = _Platt(shrink_m0=50).fit(p, y, deliveries)
    q = np.array([0.05, 0.1, 0.3])
    np.testing.assert_allclose(none(q), q, rtol=1e-3)
    assert 0 < partial.s < 1
    assert np.all(np.abs(partial(q) - q) <= np.abs(plain(q) - q) + 1e-12)
    assert np.all(partial(q) < q)                            # still corrects in the right direction


def test_no_shrink_is_plain_platt():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.01, 0.9, 1000)
    y = (rng.uniform(size=1000) < p).astype(int)
    q = np.linspace(0.02, 0.9, 7)
    np.testing.assert_allclose(_Platt().fit(p, y)(q), _Platt(None).fit(p, y, np.arange(1000))(q))
