"""Model families + score.py metrics + recent-weeks calibration, shared by every agent.

predict() returns a dict with arrays p10, p50, p90, p_up, p_down, p_none, p_hi, p_lo (prices in EUR/MWh).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier as HGC
from sklearn.ensemble import HistGradientBoostingRegressor as HGR
from sklearn.linear_model import LogisticRegression

HGB = dict(max_iter=250, learning_rate=0.06, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0,
           early_stopping=False, random_state=0)
QS = np.array([.02, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, .98])


# ----------------------------------------------------------------------------- metrics (as in score.py)
def metrics(pred: dict, imb, spot, direction, step=None) -> dict:
    y, s, dd = np.asarray(imb, float), np.asarray(spot, float), np.asarray(direction, float)
    ok = ~np.isnan(y) & ~np.isnan(s)
    pin = lambda q, f: np.mean(np.maximum(q * (y[ok] - f[ok]), (q - 1) * (y[ok] - f[ok])))
    hi, lo = (y > s + 50).astype(float), (y < s - 50).astype(float)
    ou, od, on = (dd == 1).astype(float), (dd == -1).astype(float), (dd == 0).astype(float)
    out = dict(MAE=np.mean(np.abs(y[ok] - pred["p50"][ok])),
               pinball=(pin(.1, pred["p10"]) + pin(.9, pred["p90"])) / 2,
               coverage=np.mean((y[ok] >= pred["p10"][ok]) & (y[ok] <= pred["p90"][ok])),
               brier_spike=(np.mean((pred["p_hi"][ok] - hi[ok]) ** 2) + np.mean((pred["p_lo"][ok] - lo[ok]) ** 2)) / 2,
               brier_dir=np.mean(((pred["p_up"] - ou) ** 2 + (pred["p_down"] - od) ** 2 + (pred["p_none"] - on) ** 2)[ok]))
    if step is not None:
        st = np.asarray(step)
        for a, b in [(1, 4), (5, 12), (13, 40)]:
            m = ok & (st >= a) & (st <= b)
            out[f"MAE_s{a}_{b}"] = np.mean(np.abs(y[m] - pred["p50"][m]))
    return out


# ----------------------------------------------------------------------------- model families
def _reg(q, X, y, w, hgb):
    return HGR(loss="quantile", quantile=q, **hgb).fit(X, y, sample_weight=w)


def _clf(X, y, w, hgb):
    return HGC(**hgb).fit(X, y, sample_weight=w)


def _cdf(G, z):
    lo = G[:, :1] - 3 * (G[:, 2:3] - G[:, :1]) - 1
    hi = G[:, -1:] + 3 * (G[:, -1:] - G[:, -3:-2]) + 1
    xs, ps = np.hstack([lo, G, hi]), np.concatenate([[0], QS, [1]])
    return np.stack([np.interp(z, xs[i], ps) for i in range(G.shape[0])])


def fit_predict(Xtr: pd.DataFrame, tr: pd.DataFrame, Xva: pd.DataFrame, va: pd.DataFrame, model: str = "mixture",
                target: str = "gap", hgb: dict | None = None, w: np.ndarray | None = None) -> dict:
    """Train on (Xtr, tr) and predict for (Xva, va). tr/va need columns gap, imb, spot, dir.
    model: 'direct' (3 quantile models + 3 classifiers) or 'mixture' (P(up) x conditional quantile grids).
    target: 'gap' (imb - spot) or 'price' (imb; spot added/removed internally)."""
    hgb = {**HGB, **(hgb or {})}
    y = (tr["gap"] if target == "gap" else tr["imb"]).to_numpy()
    to_gap = (lambda p: p) if target == "gap" else (lambda p: p - va["spot"].to_numpy()[:, None] if p.ndim == 2 else p - va["spot"].to_numpy())
    d = tr["dir"].to_numpy()
    ok = ~np.isnan(y)
    p_none = float(np.mean(d[ok] == 0))
    nn = ok & (d != 0)
    pup = _clf(Xtr[nn], (d[nn] == 1).astype(int), None if w is None else w[nn], hgb).predict_proba(Xva)[:, 1]
    out = dict(p_up=(1 - p_none) * pup, p_down=(1 - p_none) * (1 - pup), p_none=np.full(len(Xva), p_none))
    spot = va["spot"].to_numpy()
    if model == "direct":
        Q = np.sort(np.stack([to_gap(_reg(q, Xtr[ok], y[ok], None if w is None else w[ok], hgb).predict(Xva))
                              for q in (.1, .5, .9)]), axis=0)
        g = tr["gap"].to_numpy()
        sh = _clf(Xtr[ok], (g[ok] > 50).astype(int), None if w is None else w[ok], hgb).predict_proba(Xva)[:, 1]
        sl = _clf(Xtr[ok], (g[ok] < -50).astype(int), None if w is None else w[ok], hgb).predict_proba(Xva)[:, 1]
        s = np.maximum(sh + sl, 1)
        out.update(p10=spot + Q[0], p50=spot + Q[1], p90=spot + Q[2], p_hi=sh / s, p_lo=sl / s)
        return out
    # mixture
    grids = {}
    for side, val in (("up", 1), ("dn", -1)):
        m = ok & (d == val)
        G = np.stack([to_gap(_reg(q, Xtr[m], y[m], None if w is None else w[m], hgb).predict(Xva)) for q in QS], axis=1)
        grids[side] = np.sort(G, axis=1)
    Z = np.arange(-600, 1500.5, 0.5).astype(np.float32)
    i50, im50 = np.searchsorted(Z, 50, side="right") - 1, np.searchsorted(Z, -50, side="left") - 1
    n = len(Xva)
    r = {k: np.empty(n) for k in ("p10", "p50", "p90", "p_hi", "p_lo")}
    pu, pd_, pn = out["p_up"], out["p_down"], out["p_none"]
    for s0 in range(0, n, 3000):
        sl_ = slice(s0, s0 + 3000)
        F = (pn[sl_, None] * (Z[None, :] >= 0) + pu[sl_, None] * _cdf(grids["up"][sl_], Z)
             + pd_[sl_, None] * _cdf(grids["dn"][sl_], Z)).astype(np.float32)
        for k, pr in (("p10", .1), ("p50", .5), ("p90", .9)):
            r[k][sl_] = spot[sl_] + Z[np.minimum((F < pr).sum(axis=1), len(Z) - 1)]
        r["p_hi"][sl_], r["p_lo"][sl_] = 1 - F[:, i50], F[:, im50]
    out.update(r)
    return out


# ----------------------------------------------------------------------------- recent-weeks calibration
def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def _platt(p_fit, o_fit, p_app):
    if o_fit.min() == o_fit.max():
        return p_app
    m = LogisticRegression(C=1e6).fit(_logit(p_fit)[:, None], o_fit)
    return m.predict_proba(_logit(p_app)[:, None])[:, 1]


def calibrate(pred_cal: dict, cal: pd.DataFrame, pred_app: dict, app: pd.DataFrame) -> dict:
    """Fit per-step-band quantile offsets and Platt maps on (pred_cal, cal) — predictions for the
    last weeks of the TRAINING window from a model trained before them — and apply to pred_app."""
    out = dict(pred_app)
    band = lambda st: np.select([st <= 4, st <= 12, st <= 24], [0, 1, 2], 3)
    bc, ba = band(cal["step"].to_numpy()), band(app["step"].to_numpy())
    y = cal["imb"].to_numpy()
    for k, q in (("p10", .1), ("p90", .9)):
        adj = out[k].copy()
        for b in range(4):
            m = (bc == b) & ~np.isnan(y)
            if m.sum() > 50:
                adj[ba == b] += np.quantile(y[m] - pred_cal[k][m], q)
        out[k] = adj
    g = cal["gap"].to_numpy(); ok = ~np.isnan(g)
    hi, lo = _platt(pred_cal["p_hi"][ok], (g[ok] > 50).astype(int), out["p_hi"]), _platt(pred_cal["p_lo"][ok], (g[ok] < -50).astype(int), out["p_lo"])
    s = np.maximum(hi + lo, 1); out["p_hi"], out["p_lo"] = hi / s, lo / s
    d = cal["dir"].to_numpy(); nn = ok & (d != 0)
    pc = pred_cal["p_up"] / (pred_cal["p_up"] + pred_cal["p_down"])
    pa = out["p_up"] / (out["p_up"] + out["p_down"])
    cu = _platt(pc[nn], (d[nn] == 1).astype(int), pa)
    out["p_up"], out["p_down"] = (1 - out["p_none"]) * cu, (1 - out["p_none"]) * (1 - cu)
    out["p10"] = np.minimum(out["p10"], out["p50"]); out["p90"] = np.maximum(out["p90"], out["p50"])
    return out
