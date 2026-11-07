"""Empirical-Bayes calibration (probs agent's BEST recipe): spike Platt shrunk to identity by s = m/(m+m0)
(m = distinct delivery quarters with an event in the window) + multiplicative p10/p90 width per step band."""
from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression


def _lg(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _sg(x):
    return 1 / (1 + np.exp(-x))


def platt_eb(p_fit, y, deliv, p_app, m0=50):
    if y.min() == y.max():
        return p_app
    m = LogisticRegression(C=1e6).fit(_lg(p_fit)[:, None], y)
    A, B = float(m.intercept_[0]), float(m.coef_[0, 0])
    mm = len(np.unique(deliv[y == 1]))
    s = mm / (mm + m0)
    return _sg(s * A + (1 + s * (B - 1)) * _lg(p_app))


def calibrate_eb(pred_cal: dict, cal, pred_app: dict, app, m0: int = 50) -> dict:
    out = dict(pred_app)
    band = lambda st: np.select([st <= 4, st <= 12, st <= 24], [0, 1, 2], 3)
    bc, ba = band(cal["step"].to_numpy()), band(app["step"].to_numpy())
    y = cal["imb"].to_numpy()
    ks = np.arange(0.5, 2.505, 0.01)
    for k, tau in (("p10", .1), ("p90", .9)):
        adj = out[k].copy()
        for b in range(4):
            m = (bc == b) & ~np.isnan(y)
            if m.sum() > 50 and (ba == b).any():
                r = y[m] - pred_cal["p50"][m]
                w = pred_cal[k][m] - pred_cal["p50"][m]
                L = [np.mean(np.maximum(tau * (r - kk * w), (tau - 1) * (r - kk * w))) for kk in ks]
                kk = ks[int(np.argmin(L))]
                sel = ba == b
                adj[sel] = out["p50"][sel] + kk * (out[k][sel] - out["p50"][sel]) + np.quantile(r - kk * w, tau)
        out[k] = adj
    g = cal["gap"].to_numpy(); ok = ~np.isnan(g)
    dv = cal["delivery"].to_numpy().astype("datetime64[ns]").astype(np.int64)[ok]
    hi = platt_eb(pred_cal["p_hi"][ok], (g[ok] > 50).astype(int), dv, out["p_hi"], m0)
    lo = platt_eb(pred_cal["p_lo"][ok], (g[ok] < -50).astype(int), dv, out["p_lo"], m0)
    s = np.maximum(hi + lo, 1); out["p_hi"], out["p_lo"] = hi / s, lo / s
    from .models import _platt
    d = cal["dir"].to_numpy(); nn = ok & (d != 0)
    pc = pred_cal["p_up"] / (pred_cal["p_up"] + pred_cal["p_down"])
    pa = out["p_up"] / (out["p_up"] + out["p_down"])
    cu = _platt(pc[nn], (d[nn] == 1).astype(int), pa)
    out["p_up"], out["p_down"] = (1 - out["p_none"]) * cu, (1 - out["p_none"]) * (1 - cu)
    out["p10"] = np.minimum(out["p10"], out["p50"]); out["p90"] = np.maximum(out["p90"], out["p50"])
    return out
