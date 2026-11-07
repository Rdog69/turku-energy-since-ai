"""Direction boosts on top of INT2 (agent dir_boost). Posts never read targets."""
from __future__ import annotations
import numpy as np
from .features import history as H
from .features.structure import fold_of

SCR = "/private/tmp/claude-501/-Users-abderahimmojahid-Studies--bo-SINCE-AI-turku-energy-since-ai/ce30b3d5-78fc-4083-a944-60b3e24dbaf1/scratchpad"


def capture_post():
    """Save pre-blend predictions + history logit (no targets) for offline sweeps."""
    def post(pred, va, X_va):
        from .data import Data
        l = H.hist_full_features(va[["origin", "step", "delivery"]], Data())["hfull_lpup"].to_numpy()
        np.savez(f"{SCR}/cap_{fold_of(va)}.npz", idx=va.index.to_numpy(), step=va["step"].to_numpy(), l=l,
                 **{k: np.asarray(v) for k, v in pred.items()})
        return pred
    return post


def blend_band_post(wts, bands=((1, 4), (5, 8), (9, 16)), temp=1.0):
    """Per step-band history blend weight, optional temperature on the blended logit."""
    def post(pred, va, X_va):
        from .data import Data
        l = H.hist_full_features(va[["origin", "step"] + ["delivery"]], Data())["hfull_lpup"].to_numpy()
        st = va["step"].to_numpy()
        w = np.full(len(st), wts[-1], float)
        for (a, b), x in zip(bands, wts):
            w[(st >= a) & (st <= b)] = x
        pu, pdn, pn = pred["p_up"], pred["p_down"], pred["p_none"]
        q = np.clip(pu / np.maximum(pu + pdn, 1e-9), 1e-4, 1 - 1e-4)
        z = temp * (w * l + (1 - w) * np.log(q / (1 - q)))
        p = 1 / (1 + np.exp(-z))
        out = dict(pred)
        out["p_up"], out["p_down"] = (1 - pn) * p, (1 - pn) * (1 - p)
        return out
    return post


# ---- history-model variants (fitted on fg_hist only, i.e. before 2026-06-01 < cutoff) ----
_VCACHE: dict = {}


def hist_variant_fit(tag, weight_fn=None, keep_fn=None, params=None):
    """Fit P(up) on fg_hist like H._fit_hist, but with row weights / row filter by delivery time."""
    from sklearn.ensemble import HistGradientBoostingClassifier as HGC
    from .data import Data
    if tag in _VCACHE:
        return _VCACHE[tag]
    cols = H.DA_COLS + H.OR_COLS
    d = Data()
    h = H.hist_as_pkg(d)
    hd = Data({"pkg": h})
    hb = H._hist_base(h)
    X = H._da_frame(hb, hd).join(H._origin_frame(hb, hd))
    m = hb["y"].notna().to_numpy() & (hb["y"] != 0).to_numpy()
    m &= hb["delivery"].lt(H.CUTOFF).to_numpy()
    if keep_fn is not None:
        m &= keep_fn(hb["delivery"]).to_numpy()
    w = weight_fn(hb["delivery"])[m] if weight_fn else None
    p = dict(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=300, l2_regularization=1.0,
             early_stopping=False, random_state=0)
    p.update(params or {})
    clf = HGC(**p).fit(X.loc[m, cols], (hb.loc[m, "y"] == 1).astype(int), sample_weight=w)
    _VCACHE[tag] = clf
    return clf


def hist_variant_logit(base, tag, **kw):
    from .data import Data
    clf = hist_variant_fit(tag, **kw)
    cols = H.DA_COLS + H.OR_COLS
    X = H._da_frame(base, Data()).join(H._origin_frame(base, Data()))
    return H._logit(clf.predict_proba(X[cols])[:, 1])
