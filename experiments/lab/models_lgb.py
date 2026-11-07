"""LightGBM drop-in for models.fit_predict (direct + mixture), with bagging and seed averaging.

Reuses models.fit_predict's direct/mixture logic by swapping its two learners (_reg, _clf) for LightGBM ones
for the duration of the call (models.py itself is untouched).
"""
from __future__ import annotations

import numpy as np
from lightgbm import LGBMClassifier, LGBMRegressor

from experiments.lab import models as M

LGB = dict(num_leaves=15, min_child_samples=400, n_estimators=150, learning_rate=0.05, subsample=0.8,
           subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, n_jobs=2, verbose=-1)
CFG = dict(LGB)
CFG["n_seeds"] = 1


def configure(**kw):
    CFG.clear(); CFG.update(LGB); CFG["n_seeds"] = 1; CFG.update(kw)


def _params():
    p = {k: v for k, v in CFG.items() if k != "n_seeds"}
    return p, int(CFG["n_seeds"])


def _reg(q, X, y, w, hgb=None):
    p, ns = _params()
    ms = [LGBMRegressor(objective="quantile", alpha=q, random_state=s, **p).fit(X, y, sample_weight=w) for s in range(ns)]

    class Avg:
        def predict(self, Xn):
            return np.mean([m.predict(Xn) for m in ms], axis=0)
    return Avg()


def _clf(X, y, w, hgb=None):
    p, ns = _params()
    ms = [LGBMClassifier(random_state=s, **p).fit(X, y, sample_weight=w) for s in range(ns)]

    class Avg:
        def predict_proba(self, Xn):
            return np.mean([m.predict_proba(Xn) for m in ms], axis=0)
    return Avg()


def fit_predict_lgb(Xtr, tr, Xva, va, model="mixture", target="gap", hgb=None, w=None):
    """Same signature/outputs as models.fit_predict; hgb is ignored (use configure())."""
    old = M._reg, M._clf
    M._reg, M._clf = _reg, _clf
    try:
        return _orig(Xtr, tr, Xva, va, model=model, target=target, hgb=hgb, w=w)
    finally:
        M._reg, M._clf = old


_orig = M.fit_predict
