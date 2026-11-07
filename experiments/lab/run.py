"""One call = one experiment on both folds, appended to the shared leaderboard.

    from experiments.lab.run import run_experiment
    run_experiment("my idea", agent="nowcast", feature_fns=[package_features, my_features], model="mixture")

Protocol (identical for everyone, so rows are comparable):
  * fold A: train deliveries < 7 Sep, validate origins 7 Sep - 4 Oct (organisers' window)
  * fold B: train deliveries < 1 Aug, validate origins 1 - 31 Aug
  * calibrate=True: refit on train minus its last 14 days, predict those 14 days, fit
    per-band quantile offsets + Platt maps there, apply to the full model's validation predictions
  * every feature function is leak-checked once per process before it is used
"""
from __future__ import annotations

import fcntl
import os
import json
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .data import FOLDS, HISTORY, SUFFIX, Data, build_base, leakcheck
from .models import calibrate as _calibrate
from .models import fit_predict, metrics

LAB = Path(__file__).resolve().parent
BOARD = Path(os.environ.get("LAB_BOARD", LAB / f"leaderboard{SUFFIX}.csv"))   # LUMI tasks write their own file
PRED = LAB / "_cache" / f"preds{SUFFIX}"
_checked: set = set()
_feat_cache: dict = {}


HIDDEN = ["imb", "gap", "dir", "spot"]   # targets (+ spot) are never visible to feature or post functions


def public(df: pd.DataFrame) -> pd.DataFrame:
    """Rows as feature/post functions may see them: origin, step, delivery, fold labels. No targets."""
    return df.drop(columns=[c for c in HIDDEN if c in df.columns])


FEAT = LAB / "_cache" / f"feat{SUFFIX}"


def _disk_key(fn, base) -> str:
    """Changes whenever any feature/data-layer source file, any external data file, or the row set changes."""
    import hashlib
    h = hashlib.md5()
    for p in sorted(list((LAB / "features").glob("*.py")) + [LAB / "data.py"]):
        h.update(p.read_bytes())
    ext = LAB.parents[1] / "external_data"
    for p in sorted(ext.glob("*/*.csv.gz")) + sorted(ext.glob("*/*/*.csv.gz")):
        h.update(f"{p}:{p.stat().st_mtime_ns}".encode())
    h.update(f"{len(base)}|{base['origin'].iloc[0]}|{base['origin'].iloc[-1]}|{base['step'].sum()}".encode())
    return f"{fn.__module__}.{fn.__name__}.{h.hexdigest()[:16]}.pkl"


def features(fns, base, data, check=True, sources=("pkg",)) -> pd.DataFrame:
    """Feature table; each function's output is cached in memory and on disk (_cache/feat*/), and every function
    is still leak-checked once per process (the truncated recomputations always run)."""
    base = public(base)
    parts = []
    for fn in fns:
        key = fn.__module__ + "." + fn.__name__
        if key not in _feat_cache:
            FEAT.mkdir(parents=True, exist_ok=True)
            dp = FEAT / _disk_key(fn, base)
            if dp.exists() and os.environ.get("LAB_NO_FEAT_CACHE") != "1":
                _feat_cache[key] = pd.read_pickle(dp)
            else:
                _feat_cache[key] = fn(base, data)
                tmp = dp.with_suffix(f".tmp{os.getpid()}")
                _feat_cache[key].to_pickle(tmp)
                tmp.replace(dp)
        if check and key not in _checked:
            leakcheck(fn, base, data, n=6, sources=sources, full=_feat_cache[key])
            _checked.add(key)
        parts.append(_feat_cache[key])
    X = pd.concat(parts, axis=1)
    return X.loc[:, ~X.columns.duplicated()]


def run_experiment(name: str, agent: str, feature_fns, model: str = "mixture", target: str = "gap",
                   calibrate: bool = True, folds=None, hgb: dict | None = None, weight_fn=None,
                   drop: list[str] | None = None, sources=("pkg",), notes: str = "", post=None) -> pd.DataFrame:
    """weight_fn(train_rows) -> sample weights; post(pred, va_rows, X_va) -> pred (optional post-processing)."""
    t0 = time.time()
    folds = folds or tuple(FOLDS)
    base, data = build_base(), Data()
    X = features(feature_fns, base, data, sources=sources)
    if drop:
        X = X.drop(columns=[c for c in drop if c in X])
    rows = []
    for f in folds:
        role = base[f"fold{f}"]
        tr, va = base[role == "train"], base[role == "val"]
        tr = tr[tr.gap.notna()]
        w = weight_fn(tr) if weight_fn else None
        pred = fit_predict(X.loc[tr.index], tr, X.loc[va.index], va, model=model, target=target, hgb=hgb, w=w)
        if calibrate:
            cut = tr.delivery.max() - pd.Timedelta(days=14)
            inner, cal = tr[tr.origin < cut - pd.Timedelta(hours=10)], tr[tr.origin >= cut]
            wi = weight_fn(inner) if weight_fn else None
            pc = fit_predict(X.loc[inner.index], inner, X.loc[cal.index], cal, model=model, target=target, hgb=hgb, w=wi)
            pred = _calibrate(pc, cal, pred, va)
        if post:
            pred = post(pred, public(va), X.loc[va.index])
        m = metrics(pred, va.imb, va.spot, va.dir, va.step)
        PRED.mkdir(parents=True, exist_ok=True)
        tag = f"{agent}__{name}__{f}".replace(" ", "_").replace("/", "-")[:120]
        np.savez_compressed(PRED / f"{tag}.npz", idx=va.index.to_numpy(), **{k: v for k, v in pred.items()})
        rows.append(dict(time=time.strftime("%Y-%m-%d %H:%M"), agent=agent, name=name, fold=f, model=model,
                         target=target, calibrate=calibrate, n_features=X.shape[1],
                         **{k: round(float(v), 5) for k, v in m.items()}, secs=round(time.time() - t0),
                         notes=notes))
    out = pd.DataFrame(rows)
    _append(out)
    print(out[["agent", "name", "fold", "MAE", "pinball", "coverage", "brier_spike", "brier_dir"]].to_string(index=False))
    return out


def _append(df: pd.DataFrame) -> None:
    BOARD.touch(exist_ok=True)
    with open(BOARD, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        fh.seek(0)
        header = fh.read(1) == ""
        df.to_csv(fh, header=header, index=False)
        fcntl.flock(fh, fcntl.LOCK_UN)


def board(fold: str | None = None) -> pd.DataFrame:
    b = pd.read_csv(BOARD)
    return b if fold is None else b[b.fold == fold]
