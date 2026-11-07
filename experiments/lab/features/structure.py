"""Agent `structure`: model-structure / training-setup helpers (package features only, no new features).

Everything here plugs into run_experiment's hooks:
  * recency(half_life_days)            -> weight_fn
  * blend_post(tag_or_list, w)         -> post: average with saved predictions of another run (same fold)
  * causal_post(w_by_step)             -> post: average (o, k) with the forecast made at o-1h for the same
                                          delivery (o-1h, k+4); only uses validation predictions made earlier
  * chain(*posts)                      -> post: apply several posts in order
  * band_post(...)                     -> post: refit separate models for a step band and splice them in
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

LAB = Path(__file__).resolve().parents[1]
PRED = LAB / "_cache" / "preds"
KEYS = ("p10", "p50", "p90", "p_up", "p_down", "p_none", "p_hi", "p_lo")


# ----------------------------------------------------------------------------- weights
def recency(half_life_days: float, floor: float = 0.0):
    """Exponential recency weights relative to the newest training delivery (computed per call, so the
    calibration inner fit gets weights relative to its own end)."""
    def fn(tr: pd.DataFrame) -> np.ndarray:
        age = (tr["delivery"].max() - tr["delivery"]) / pd.Timedelta(days=1)
        w = 0.5 ** (age.to_numpy() / half_life_days)
        return np.maximum(w, floor)
    fn.__name__ = f"recency{half_life_days}"
    return fn


# ----------------------------------------------------------------------------- helpers
def fold_of(va: pd.DataFrame) -> str:
    """A (Sep/Oct) or B (Aug) from the validation rows."""
    return "A" if va["origin"].min() >= pd.Timestamp("2026-09-01T00:00Z") else "B"


def load_pred(tag: str, fold: str, va: pd.DataFrame) -> dict:
    """Load saved predictions `<tag>__<fold>.npz`, aligned to va.index."""
    z = np.load(PRED / f"{tag}__{fold}.npz")
    idx = pd.Index(z["idx"])
    pos = idx.get_indexer(va.index)
    assert (pos >= 0).all(), f"{tag} {fold}: saved index does not cover va"
    return {k: z[k][pos] for k in KEYS}


def _fix(p: dict) -> dict:
    p["p10"] = np.minimum(p["p10"], p["p50"])
    p["p90"] = np.maximum(p["p90"], p["p50"])
    s = np.maximum(p["p_hi"] + p["p_lo"], 1)
    p["p_hi"], p["p_lo"] = p["p_hi"] / s, p["p_lo"] / s
    return p


# ----------------------------------------------------------------------------- posts
def blend_post(tags, w: float | None = None, keys=KEYS):
    """Average the current prediction with saved predictions of other runs (equal weights by default;
    w = weight of the current run if a single other tag is given)."""
    tags = [tags] if isinstance(tags, str) else list(tags)

    def post(pred, va, X_va):
        f = fold_of(va)
        others = [load_pred(t, f, va) for t in tags]
        ws = [1.0 / (1 + len(others))] * (1 + len(others)) if w is None else [w] + [(1 - w) / len(others)] * len(others)
        out = dict(pred)
        for k in keys:
            out[k] = ws[0] * np.asarray(pred[k], float) + sum(wi * o[k] for wi, o in zip(ws[1:], others))
        return _fix(out)
    return post


def prev_index(va: pd.DataFrame, lag_h: int = 1) -> np.ndarray:
    """Position in va of the row (origin - lag_h hours, step + 4*lag_h) = same delivery quarter, forecast
    made lag_h hours earlier. -1 if that origin is not among the validation predictions (first origins,
    steps > 40 - 4*lag_h)."""
    key = pd.MultiIndex.from_arrays([va["origin"].to_numpy(), va["step"].to_numpy()])
    pos = pd.Series(np.arange(len(va)), index=key)
    pk = pd.MultiIndex.from_arrays([(va["origin"] - pd.Timedelta(hours=lag_h)).to_numpy(), (va["step"] + 4 * lag_h).to_numpy()])
    return pos.reindex(pk).fillna(-1).astype(int).to_numpy()


def causal_post(w_of_step, keys=KEYS, lags=(1,)):
    """pred(o,k) <- (1 - sum w) * pred(o,k) + sum_l w_l(k) * pred(o - l h, k + 4l).  Causal: the earlier
    forecast is issued at o - l h <= o and only uses information available then.
    w_of_step: callable step -> weight (array in, array out) or dict {lag: callable}."""
    wf = w_of_step if isinstance(w_of_step, dict) else {lags[0]: w_of_step}

    def post(pred, va, X_va):
        st = va["step"].to_numpy()
        out = {k: np.asarray(pred[k], float).copy() for k in KEYS}
        tot = np.zeros(len(va))
        acc = {k: np.zeros(len(va)) for k in keys}
        for L, f in wf.items():
            pi = prev_index(va, L)
            has = pi >= 0
            wl = np.where(has, f(st), 0.0)
            tot += wl
            for k in keys:
                acc[k] += wl * np.where(has, np.asarray(pred[k], float)[np.maximum(pi, 0)], 0.0)
        for k in keys:
            out[k] = (1 - tot) * np.asarray(pred[k], float) + acc[k]
        return _fix(out)
    return post


def save_post(tag: str):
    """Save the incoming (calibrated, pre-post) prediction as structure__<tag>__<fold>.npz; returns it unchanged."""
    def post(pred, va, X_va):
        PRED.mkdir(parents=True, exist_ok=True)
        t = f"structure__{tag}__{fold_of(va)}".replace(" ", "_").replace("/", "-")
        np.savez_compressed(PRED / f"{t}.npz", idx=va.index.to_numpy(), **{k: np.asarray(v) for k, v in pred.items()})
        return pred
    return post


def band_post(bands, model: str = "direct", target: str = "gap", hgb: dict | None = None, calibrate: bool = True,
              keys=KEYS):
    """Refit separate models on the training rows of each step band (same protocol as run_experiment:
    train rows of the fold, inner/cal split for calibration) and splice their predictions into those steps.
    Uses only the training rows' targets (from build_base) and, for validation rows, step + X_va['spot']."""
    def post(pred, va, X_va):
        from ..data import Data, build_base
        from ..models import calibrate as _cal
        from ..models import fit_predict
        from ..run import features
        from .package import package_features
        f = fold_of(va)
        base = build_base()
        X = features([package_features], base, Data())
        tr = base[base[f"fold{f}"] == "train"]
        tr = tr[tr.gap.notna()]
        cut = tr.delivery.max() - pd.Timedelta(days=14)
        inner_all, cal_all = tr[tr.origin < cut - pd.Timedelta(hours=10)], tr[tr.origin >= cut]
        vrows = pd.DataFrame({"step": va["step"].to_numpy(), "spot": X_va["spot"].to_numpy()}, index=va.index)
        out = {k: np.asarray(v, float).copy() for k, v in pred.items()}
        for a, b in bands:
            trb = tr[tr.step.between(a, b)]
            mv = vrows.step.between(a, b).to_numpy()
            vab = vrows[mv]
            pb = fit_predict(X.loc[trb.index], trb, X.loc[vab.index], vab, model=model, target=target, hgb=hgb)
            if calibrate:
                inn, cal = inner_all[inner_all.step.between(a, b)], cal_all[cal_all.step.between(a, b)]
                pc = fit_predict(X.loc[inn.index], inn, X.loc[cal.index], cal, model=model, target=target, hgb=hgb)
                pb = _cal(pc, cal, pb, vab)
            for k in keys:
                out[k][mv] = pb[k]
        return _fix(out)
    return post


def chain(*posts):
    def post(pred, va, X_va):
        for p in posts:
            pred = p(pred, va, X_va)
        return pred
    return post


def ramp(w_max: float, s0: int = 4, s1: int = 16):
    """Weight 0 up to step s0, rising linearly to w_max at step s1 and flat after."""
    return lambda st: w_max * np.clip((np.asarray(st, float) - s0) / (s1 - s0), 0, 1)
