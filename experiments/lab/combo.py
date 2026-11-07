"""Run one experiment from a JSON spec (used by the Featherless loop, tools/fl_lab.py).

    python -m experiments.lab.combo '{"name": "...", "features": ["package", "rt_wind"], "model": "mixture"}'

Spec keys (all optional except name/features):
  features        list of registry names (see REGISTRY)
  model           "mixture" | "direct"
  target          "gap" | "price"
  hgb             HistGradientBoosting overrides, e.g. {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150}
  bands           [[1,4],[5,8],[9,16]]: refit separate models for these step bands (rest: the pooled model)
  hist_blend      0..1: logit blend of P(up) with the history model (fitted on fg_hist only)
  half_life_days  recency weights (null = none)
  causal          0..0.3: average with the forecast for the same delivery from the previous origin, ramped over steps 4-16
  calibrate       true/false (default true)
  short_features  feature sets used ONLY in bands ending at step <= 8 (needs `bands`); pooled model excludes them
  calib           "eb50": probs' EB-shrunk Platt for spikes + multiplicative width (default: models.calibrate)
  cal_days        calibration window in days (default 14; only used with calib)
Everything goes through run_experiment -> leak-checked features, both folds, shared leaderboard.
"""
from __future__ import annotations

import importlib
import json
import sys

from .data import threads

threads(3)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

REGISTRY = {
    # name: (module, function, description)
    "package": ("experiments.lab.features.package", "package_features", "35 starter-package features incl. spike-threshold distances (always include)"),
    "rt_imb": ("experiments.lab.features.nowcast", "rt_imb", "Fingrid real-time surplus/deficit 198/186 (newest, lags, means)"),
    "rt_wind": ("experiments.lab.features.nowcast", "rt_wind", "real-time wind 181 minus day-ahead wind forecast (wind error), lags/trend"),
    "rt_cons": ("experiments.lab.features.nowcast", "rt_cons", "real-time consumption/production-plan errors (helped fold A, hurt B)"),
    "rt2": ("experiments.lab.features.rt2", "rt2_features", "Fingrid real-time batch 2: electric boilers, CHP, real-time border flows (Frank's RT2)"),
    "spot_shape": ("experiments.lab.features.v2", "spot_shape", "spot curve shape: rank in day, distance to day max/min, spread, +-1h ramps (v2 agent: +4.21 with INT5)"),
    "cal2": ("experiments.lab.features.v2", "calendar2", "weekend x hour interaction (+ DST flag)"),
    "mfrr2": ("experiments.lab.features.mfrr2", "mfrr2_features", "balancing-market state: mFRR need, bid volumes, aFRR volumes, mFRR exchange, scheduled vs direct activations, bid-stack use (60-min rule)"),
    "dafcr": ("experiments.lab.features.mfrr2", "dafcr_features", "day-ahead FCR prices + day-ahead transmission capacities at delivery"),
    "ace": ("experiments.lab.features.mfrr2", "ace_features", "real-time calculated imbalance (Fingrid 397), PENDING organiser approval"),
    "rt_misc": ("experiments.lab.features.nowcast", "rt_misc", "frequency, nuclear drop, net import, hydro ramp, fg176"),
    "runs": ("experiments.lab.features.history", "runs_features", "mFRR direction run-length / switch features"),
    "hist_full": ("experiments.lab.features.history", "hist_full_features", "logit P(up) from a model fitted on last year's Fingrid history (as a feature)"),
    "hist_da": ("experiments.lab.features.history", "hist_da_features", "logit P(up | day-ahead inputs) fitted on history"),
    "dir": ("experiments.lab.features.probs", "dir_features", "19 direction-history features (run length, up-share 1-24 h, switches, same quarter previous days)"),
    "umm_trip": ("experiments.lab.features.outages", "umm_trip", "UMM fresh unplanned trip features (did not pass both folds alone)"),
    "ifs_rev": ("experiments.lab.features.weather", "ifs_rev", "newest ECMWF IFS run -> wind MW (power curve) minus Fingrid day-ahead wind forecast (revision)"),
    "wind_err": ("experiments.lab.features.weather", "wind_err_features", "real-time wind error now (weather agent version)"),
    "ifs_now": ("experiments.lab.features.weather", "ifs_now_features", "IFS now-cast vs measured wind"),
    "wind_hat": ("experiments.lab.features.weather", "wind_hat_features", "combined estimate of the day-ahead wind error per step band"),
    "fmi": ("experiments.lab.features.weather", "fmi_features", "FMI coastal station observations"),
    "wmap": ("experiments.lab.features.wmap", "wmap_features", "learned 22-point IFS+ICON wind map (Frank's idea): MW, revision, de-biased/scaled revision, run change, ICON-IFS disagreement"),
    "wmap_core": ("experiments.lab.features.wmap", "wmap_core", "wmap subset: de-biased revision, run change, ICON-IFS disagreement"),
    "wmap_s": ("experiments.lab.features.wmap", "wmap_s", "wmap subset: scaled + de-biased revision, run change, ICON-IFS disagreement"),
    "nordic": ("experiments.lab.features.nordic", "nordic_features", "Nordic/Baltic wind index per area (SE/NO/DK/EE) + revision since day-ahead + run change"),
    "nordic_rev": ("experiments.lab.features.nordic", "nordic_rev", "Nordic wind revisions only (since day-ahead, run change)"),
    "temp": ("experiments.lab.features.weather", "temp_features", "temperature features"),
    "regime": ("experiments.lab.features.regime", "regime_features", "market-era flags (15-min day-ahead, 1 Jun 2026 price rule) for history mode"),
}


def resolve(names):
    fns = []
    for n in names:
        mod, fn, _ = REGISTRY[n]
        fns.append(getattr(importlib.import_module(mod), fn))
    return fns


def band_post(fns, bands, model, target, hgb, calibrate=True, calib=None, cal_days=14, short_fns=(), short_max=8):
    """Like structure.band_post, but with the experiment's own feature set.
    short_fns: extra feature sets used ONLY by bands ending at or before step `short_max` (Frank's finding:
    real-time data helps hours 1-2 and is noise later)."""
    from .data import Data, build_base
    from .models import calibrate as _cal, fit_predict
    if calib == "eb50":
        from .calib_eb import calibrate_eb
        _cal = calibrate_eb
    from .run import features
    from .features.structure import fold_of, _fix, KEYS

    def post(pred, va, X_va):
        f = fold_of(va)
        base = build_base()
        X0 = features(fns, base, Data())
        XS = features(list(fns) + list(short_fns), base, Data()) if short_fns else X0
        tr = base[(base[f"fold{f}"] == "train") & base.gap.notna()]
        cut = tr.delivery.max() - pd.Timedelta(days=cal_days)
        inner_all, cal_all = tr[tr.origin < cut - pd.Timedelta(hours=10)], tr[tr.origin >= cut]
        vrows = pd.DataFrame({"step": va["step"].to_numpy(), "spot": X_va["spot"].to_numpy()}, index=va.index)
        out = {k: np.asarray(v, float).copy() for k, v in pred.items()}
        for a, b in bands:
            trb = tr[tr.step.between(a, b)]
            mv = vrows.step.between(a, b).to_numpy()
            vab = vrows[mv]
            X = XS if (short_fns and b <= short_max) else X0
            pb = fit_predict(X.loc[trb.index], trb, X.loc[vab.index], vab, model=model, target=target, hgb=hgb)
            if calibrate:
                inn, cal = inner_all[inner_all.step.between(a, b)], cal_all[cal_all.step.between(a, b)]
                pc = fit_predict(X.loc[inn.index], inn, X.loc[cal.index], cal, model=model, target=target, hgb=hgb)
                pb = _cal(pc, cal, pb, vab)
            for k in KEYS:
                out[k][mv] = pb[k]
        return _fix(out)
    return post


def pool_post(fns, model, target, hgb, cal_days):
    """EB calibration of the pooled model (replaces run_experiment's built-in calibrate step)."""
    from .data import Data, build_base
    from .calib_eb import calibrate_eb
    from .models import fit_predict
    from .run import features
    from .features.structure import fold_of

    def post(pred, va, X_va):
        f = fold_of(va)
        base = build_base()
        X = features(fns, base, Data())
        tr = base[(base[f"fold{f}"] == "train") & base.gap.notna()]
        cut = tr.delivery.max() - pd.Timedelta(days=cal_days)
        inner, cal = tr[tr.origin < cut - pd.Timedelta(hours=10)], tr[tr.origin >= cut]
        pc = fit_predict(X.loc[inner.index], inner, X.loc[cal.index], cal, model=model, target=target, hgb=hgb)
        vr = pd.DataFrame({"step": va["step"].to_numpy(), "spot": X_va["spot"].to_numpy()}, index=va.index)
        return calibrate_eb(pc, cal, pred, vr)
    return post


def use_lgb(params: dict | None = None):
    """Swap the learners inside models.py for LightGBM ones (bagging + seed averaging), for this process."""
    import os
    from . import models as M
    from . import models_lgb as L
    p = dict(num_leaves=15, min_child_samples=300, n_estimators=250, learning_rate=0.04, n_seeds=3)
    p.update(params or {})
    p.setdefault("n_jobs", int(os.environ.get("OMP_NUM_THREADS", "4")))
    L.configure(**p)
    M._reg, M._clf = L._reg, L._clf


def run_spec(spec: dict):
    from .run import run_experiment
    if spec.get("engine") == "lgb":
        use_lgb(spec.get("lgb"))
    from .features.structure import chain, causal_post, ramp, recency
    names = list(dict.fromkeys(["package"] + list(spec["features"])))
    fns = resolve(names)
    short_fns = resolve([n for n in spec.get("short_features", []) if n not in names])
    model, target = spec.get("model", "mixture"), spec.get("target", "gap")
    hgb, cal = spec.get("hgb") or None, spec.get("calibrate", True)
    calib, cal_days = spec.get("calib"), int(spec.get("cal_days", 14))
    posts = []
    if calib == "eb50" and cal:
        posts.append(pool_post(fns, model, target, hgb, cal_days))
    if spec.get("bands"):
        posts.append(band_post(fns, [tuple(b) for b in spec["bands"]], model, target, hgb, cal, calib, cal_days, short_fns))
    if spec.get("hist_blend"):
        sys.path.insert(0, ".")
        from experiments.lab.exp_history import blend_post
        posts.append(blend_post(float(spec["hist_blend"])))
    if spec.get("causal"):
        posts.append(causal_post(ramp(float(spec["causal"]))))
    hl = spec.get("half_life_days")
    notes = "loop spec: " + json.dumps({k: v for k, v in spec.items() if k not in ("name", "agent")}, sort_keys=True)
    return run_experiment(spec["name"], agent=spec.get("agent", "fl-loop"), feature_fns=fns, model=model, target=target,
                          calibrate=cal and calib != "eb50", hgb=hgb, weight_fn=recency(hl) if hl else None,
                          post=chain(*posts) if posts else None, notes=notes[:900])


if __name__ == "__main__":
    run_spec(json.loads(sys.argv[1]))
