"""Agent `structure`: model structure / training setup on PACKAGE FEATURES ONLY.

    OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_structure screen
    OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_structure run <name>

`screen` = cheap p50-only screen (one quantile-0.5 HGB per fold, no calibration; calibration never
touches p50, so the MAE is exactly what the direct model would get). Not written to the leaderboard.
`run <name>` = full run_experiment rows (both folds, calibrated) for the configurations in RUNS.
"""
from __future__ import annotations

import sys
import time

from experiments.lab.data import threads

threads(2)

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor as HGR

from experiments.lab.data import Data, build_base
from experiments.lab.features.package import package_features
from experiments.lab.features.structure import band_post, blend_post, causal_post, chain, ramp, recency, save_post
from experiments.lab.models import HGB
from experiments.lab.run import features, run_experiment

AGENT = "structure"


# ----------------------------------------------------------------------------- p50 screen
def _fit_p50(Xtr, ytr, Xva, hgb, w=None, q=0.5):
    return HGR(loss="quantile", quantile=q, **{**HGB, **hgb}).fit(Xtr, ytr, sample_weight=w).predict(Xva)


def screen(configs: dict, quantiles=(0.5,)):
    base, data = build_base(), Data()
    X = features([package_features], base, data)
    res, preds = [], {}
    for f in ("A", "B"):
        role = base[f"fold{f}"]
        tr, va = base[role == "train"], base[role == "val"]
        tr = tr[tr.gap.notna()]
        y_ok = va.imb.notna() & va.spot.notna()
        for name, c in configs.items():
            t0 = time.time()
            tgt = c.get("target", "price")
            ytr = (tr.imb if tgt == "price" else tr.gap).to_numpy()
            add = 0 if tgt == "price" else va.spot.to_numpy()
            w = c["w"](tr) if c.get("w") else None
            out = {}
            for q in c.get("qs", quantiles):
                if c.get("bands"):
                    full = c.get("pooled", False)
                    p = (_fit_p50(X.loc[tr.index], ytr, X.loc[va.index], c.get("hgb", {}), w, q) if full
                         else np.full(len(va), np.nan))
                    for a, b in c["bands"]:
                        mt, mv = tr.step.between(a, b).to_numpy(), va.step.between(a, b).to_numpy()
                        p[mv] = _fit_p50(X.loc[tr.index][mt], ytr[mt], X.loc[va.index][mv], c.get("band_hgb", c.get("hgb", {})),
                                         None if w is None else w[mt], q)
                else:
                    p = _fit_p50(X.loc[tr.index], ytr, X.loc[va.index], c.get("hgb", {}), w, q)
                out[q] = p + add
            preds[(f, name)] = out
            y, st = va.imb.to_numpy(), va.step.to_numpy()
            m = y_ok.to_numpy()
            r = dict(fold=f, cfg=name, MAE=np.mean(np.abs(y[m] - out[0.5][m])))
            for a, b in [(1, 4), (5, 12), (13, 40)]:
                mm = m & (st >= a) & (st <= b)
                r[f"s{a}_{b}"] = np.mean(np.abs(y[mm] - out[0.5][mm]))
            if 0.1 in out and 0.9 in out:
                pin = lambda qq, p: np.mean(np.maximum(qq * (y[m] - p[m]), (qq - 1) * (y[m] - p[m])))
                r["pin_raw"] = (pin(.1, out[0.1]) + pin(.9, out[0.9])) / 2
            r["secs"] = round(time.time() - t0)
            res.append(r)
            print({k: (round(v, 3) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    return pd.DataFrame(res), preds


SCREEN = {
    "gap": dict(target="gap"),
    "price": dict(),
    "price_lr03_i500": dict(hgb=dict(learning_rate=0.03, max_iter=500)),
    "price_i500": dict(hgb=dict(max_iter=500)),
    "price_i150": dict(hgb=dict(max_iter=150)),
    "price_leaf15_msl400": dict(hgb=dict(max_leaf_nodes=15, min_samples_leaf=400)),
    "price_leaf63_msl100": dict(hgb=dict(max_leaf_nodes=63, min_samples_leaf=100)),
    "price_msl1000_l2_5": dict(hgb=dict(min_samples_leaf=1000, l2_regularization=5.0)),
    "price_mf05": dict(hgb=dict(max_features=0.5)),
    "price_hl60": dict(w=recency(60)),
    "price_hl90": dict(w=recency(90)),
    "price_hl120": dict(w=recency(120)),
    "price_bands8": dict(bands=[(1, 8), (9, 40)]),
}


L15 = dict(max_leaf_nodes=15, min_samples_leaf=400)
SCREEN2 = {
    "gap_L15": dict(target="gap", hgb=L15),
    "price_L15": dict(hgb=L15),
    "gap_L7": dict(target="gap", hgb=dict(max_leaf_nodes=7, min_samples_leaf=400)),
    "gap_L15_msl800": dict(target="gap", hgb=dict(max_leaf_nodes=15, min_samples_leaf=800)),
    "gap_L15_l2_5": dict(target="gap", hgb={**L15, "l2_regularization": 5.0}),
    "gap_L15_i150": dict(target="gap", hgb={**L15, "max_iter": 150}),
    "gap_L15_i400_lr03": dict(target="gap", hgb={**L15, "max_iter": 400, "learning_rate": 0.03}),
    "gap_L7_msl1000_i400": dict(target="gap", hgb=dict(max_leaf_nodes=7, min_samples_leaf=1000, max_iter=400)),
    "gap_L15_hl60": dict(target="gap", hgb=L15, w=recency(60)),
    "gap_L15_hyb8": dict(target="gap", hgb=L15, bands=[(1, 8)], pooled=True),
    "gap_L15_hyb4": dict(target="gap", hgb=L15, bands=[(1, 4)], pooled=True),
    "gap_L15_hyb4_12": dict(target="gap", hgb=L15, bands=[(1, 4), (5, 12)], pooled=True),
    "price_L15_hyb8": dict(hgb=L15, bands=[(1, 8)], pooled=True),
}

G = dict(max_leaf_nodes=15, min_samples_leaf=400, max_iter=150)
Q3 = (0.1, 0.5, 0.9)
SCREEN3 = {
    "gap_default_q3": dict(target="gap", qs=Q3),
    "gap_G_q3": dict(target="gap", hgb=G, qs=Q3),
    "gap_L15_i100": dict(target="gap", hgb={**G, "max_iter": 100}),
    "gap_G_msl800": dict(target="gap", hgb={**G, "min_samples_leaf": 800}),
    "gap_L7_i150": dict(target="gap", hgb={**G, "max_leaf_nodes": 7}),
    "gap_L15_lr03_i300": dict(target="gap", hgb={**G, "max_iter": 300, "learning_rate": 0.03}),
    "gap_L31_msl400_i150": dict(target="gap", hgb={**G, "max_leaf_nodes": 31}),
    "gap_G_hyb4_12": dict(target="gap", hgb=G, bands=[(1, 4), (5, 12)], pooled=True),
    "gap_G_hyb4_12_bmsl200": dict(target="gap", hgb=G, bands=[(1, 4), (5, 12)], pooled=True, band_hgb={**G, "min_samples_leaf": 200}),
    "gap_G_hyb4_12_bi250": dict(target="gap", hgb=G, bands=[(1, 4), (5, 12)], pooled=True, band_hgb={**G, "max_iter": 250}),
    "gap_G_hyb4_12_q3": dict(target="gap", hgb=G, bands=[(1, 4), (5, 12)], pooled=True, qs=Q3),
}

SCREEN4 = {
    "gap_G_hl60": dict(target="gap", hgb=G, w=recency(60)),
    "gap_G_hl90": dict(target="gap", hgb=G, w=recency(90)),
    "gap_G_hl120": dict(target="gap", hgb=G, w=recency(120)),
    "gap_G_hyb2_4_12": dict(target="gap", hgb=G, bands=[(1, 2), (3, 4), (5, 12)], pooled=True),
    "gap_G_hyb4_8_16": dict(target="gap", hgb=G, bands=[(1, 4), (5, 8), (9, 16)], pooled=True),
    "gap_G_hyb4_12_24": dict(target="gap", hgb=G, bands=[(1, 4), (5, 12), (13, 24)], pooled=True),
}

# ----------------------------------------------------------------------------- full runs
PF = [package_features]


BANDS = [(1, 4), (5, 8), (9, 16)]          # separate models; steps 17-40 stay with the pooled model


def RUNS(name):
    R = {
        "S direct gap G": lambda: run_experiment(
            "S direct gap G", AGENT, PF, model="direct", target="gap", hgb=G,
            notes="REF direct + HGB G (leaf15, msl400, iter150)"),
        "S direct price G": lambda: run_experiment(
            "S direct price G", AGENT, PF, model="direct", target="price", hgb=G,
            notes="target=price with HGB G (vs S direct gap G)"),
        "S direct gap G bands": lambda: run_experiment(
            "S direct gap G bands", AGENT, PF, model="direct", target="gap", hgb=G,
            post=band_post(BANDS, "direct", "gap", G),
            notes="S direct gap G + separate calibrated direct models for steps 1-4, 5-8, 9-16 (all heads)"),
        "S mixture gap G": lambda: run_experiment(
            "S mixture gap G", AGENT, PF, model="mixture", target="gap", hgb=G,
            notes="REF mixture + HGB G (leaf15, msl400, iter150)"),
        "S mixture gap G bands": lambda: run_experiment(
            "S mixture gap G bands", AGENT, PF, model="mixture", target="gap", hgb=G,
            post=chain(save_post("S mixture gap G raw"), band_post(BANDS, "mixture", "gap", G)),
            notes="mixture + HGB G + separate calibrated mixture models for steps 1-4, 5-8, 9-16; "
                  "pooled-only preds saved as structure__S_mixture_gap_G_raw"),
        "S final": lambda: run_experiment(
            "S final", AGENT, PF, model="mixture", target="gap", hgb=G,
            post=chain(band_post(BANDS, "mixture", "gap", G),
                       blend_weights_post("structure__S_direct_gap_G_bands", W_FINAL),
                       causal_post({1: ramp(0.2, 4, 16), 2: ramp(0.15, 8, 24)})),
            notes="S mixture gap G bands, convex blend with S direct gap G bands (weights fitted on fold B), "
                  "causal average with forecasts from o-1h (w<=0.2) and o-2h (w<=0.15)"),
    }
    return R[name]()


# weight of the mixture model per column group, fitted on fold B (analyze mixture_bands vs direct_bands)
W_FINAL = {"p50": {(1, 40): 0.6}, "q": {(1, 40): 0.9}, "spike": {(1, 40): 0.6}, "dir": {(1, 40): 0.2}}


# ----------------------------------------------------------------------------- classifier-head screen
def screen_clf(configs: dict):
    """Raw (uncalibrated) direction Brier and spike Brier of the HGB classifier heads per hyperparameter set."""
    from sklearn.ensemble import HistGradientBoostingClassifier as HGC
    base, data = build_base(), Data()
    X = features([package_features], base, data)
    for f in ("A", "B"):
        role = base[f"fold{f}"]
        tr, va = base[role == "train"], base[role == "val"]
        tr = tr[tr.gap.notna()]
        ok = (va.imb.notna() & va.spot.notna()).to_numpy()
        d, dv, gv = tr.dir.to_numpy(), va.dir.to_numpy(), va.gap.to_numpy()
        pn = float(np.mean(d == 0)); nn = d != 0
        for name, c in configs.items():
            hp = {**HGB, **c}
            pu = HGC(**hp).fit(X.loc[tr.index][nn], (d[nn] == 1).astype(int)).predict_proba(X.loc[va.index])[:, 1]
            pu, pdn = (1 - pn) * pu, (1 - pn) * (1 - pu)
            bd = ((pu - (dv == 1)) ** 2 + (pdn - (dv == -1)) ** 2 + (pn - (dv == 0)) ** 2)[ok].mean()
            g = tr.gap.to_numpy()
            sh = HGC(**hp).fit(X.loc[tr.index], (g > 50).astype(int)).predict_proba(X.loc[va.index])[:, 1]
            sl = HGC(**hp).fit(X.loc[tr.index], (g < -50).astype(int)).predict_proba(X.loc[va.index])[:, 1]
            sp = (np.mean((sh - (gv > 50))[ok] ** 2) + np.mean((sl - (gv < -50))[ok] ** 2)) / 2
            print(dict(fold=f, cfg=name, brier_dir_raw=round(bd, 4), brier_spike_raw=round(sp, 4)), flush=True)


CLF = {
    "default": {},
    "G": G,
    "G_msl800": {**G, "min_samples_leaf": 800},
    "G_L7": {**G, "max_leaf_nodes": 7},
    "G_i80": {**G, "max_iter": 80},
    "G_lr03": {**G, "learning_rate": 0.03},
    "G_L7_msl800_i100": {**G, "max_leaf_nodes": 7, "min_samples_leaf": 800, "max_iter": 100},
}


# ----------------------------------------------------------------------------- offline blend / causal fitting
GROUPS = {"p50": (("p50",), "MAE"), "q": (("p10", "p90"), "pinball"), "spike": (("p_hi", "p_lo"), "brier_spike"),
          "dir": (("p_up", "p_down", "p_none"), "brier_dir")}
SBANDS = [(1, 4), (5, 8), (9, 16), (17, 40)]


def _sub(p, m):
    return {k: np.asarray(v)[m] for k, v in p.items()}


def _metric(p, va, name):
    from experiments.lab.models import metrics
    return metrics(p, va.imb, va.spot, va.dir)[name]


def analyze(tag_a: str, tag_b: str, per_band: bool = False, grid=np.round(np.arange(0, 1.01, 0.1), 2)):
    """Convex blend w*a + (1-w)*b per column group (optionally per step band), w fitted on fold B
    (the earlier fold) and applied unchanged to fold A. Returns {group: {band: w}}."""
    from experiments.lab.features.structure import load_pred
    base = build_base()
    P = {}
    for f in "AB":
        va = base[base[f"fold{f}"] == "val"]
        P[f] = (va, load_pred(tag_a, f, va), load_pred(tag_b, f, va))
    bands = SBANDS if per_band else [(1, 40)]
    W = {}
    for g, (keys, mname) in GROUPS.items():
        W[g] = {}
        for (a, b) in bands:
            va, pa, pb = P["B"]
            m = va.step.between(a, b).to_numpy()
            sc = []
            for w in grid:
                p = {k: (w * pa[k] + (1 - w) * pb[k]) if k in keys else pa[k] for k in pa}
                sc.append(_metric(_sub(p, m), va[m], mname))
            W[g][(a, b)] = float(grid[int(np.argmin(sc))])
    rows = []
    for f in "AB":
        va, pa, pb = P[f]
        st = va.step.to_numpy()
        pbl = {k: np.array(pa[k], float) for k in pa}
        for g, (keys, _) in GROUPS.items():
            for (a, b), w in W[g].items():
                m = (st >= a) & (st <= b)
                for k in keys:
                    pbl[k][m] = w * pa[k][m] + (1 - w) * pb[k][m]
        for nm, p in (("A=" + tag_a, pa), ("B=" + tag_b, pb), ("blend", pbl)):
            from experiments.lab.models import metrics
            mm = metrics(p, va.imb, va.spot, va.dir, va.step)
            rows.append(dict(fold=f, which=nm, **{k: round(mm[k], 4) for k in ("MAE", "pinball", "brier_spike", "brier_dir",
                                                                             "MAE_s1_4", "MAE_s13_40")}))
    print("weights (fitted on B, weight of A):", W)
    print(pd.DataFrame(rows).to_string(index=False))
    return W


def blend_weights_post(tag_other: str, W: dict):
    """post: pred <- w*pred + (1-w)*other per column group / step band, w from analyze() (fitted on fold B)."""
    from experiments.lab.features.structure import _fix, fold_of, load_pred

    def post(pred, va, X_va):
        o = load_pred(tag_other, fold_of(va), va)
        st = va["step"].to_numpy()
        out = {k: np.array(v, float) for k, v in pred.items()}
        for g, (keys, _) in GROUPS.items():
            for (a, b), w in W[g].items():
                m = (st >= a) & (st <= b)
                for k in keys:
                    out[k][m] = w * np.asarray(pred[k], float)[m] + (1 - w) * o[k][m]
        return _fix(out)
    return post


def analyze_causal(tag: str):
    """Fit causal-average weights on fold B (lag-1 ramp from step 4 to 16, optional lag 2), check on fold A."""
    from experiments.lab.features.structure import load_pred
    from experiments.lab.models import metrics
    base = build_base()
    P = {f: (base[base[f"fold{f}"] == "val"],) for f in "AB"}
    P = {f: (P[f][0], load_pred(tag, f, P[f][0])) for f in "AB"}
    cfgs = [(w1, w2) for w1 in (0.0, 0.2, 0.3, 0.4, 0.5) for w2 in (0.0, 0.15, 0.25)]
    res = []
    for w1, w2 in cfgs:
        cp = causal_post({1: ramp(w1, 4, 16), 2: ramp(w2, 8, 24)})
        r = dict(w1=w1, w2=w2)
        for f in "AB":
            va, p = P[f]
            q = cp(p, va[["origin", "step", "delivery"]], None)
            mm = metrics(q, va.imb, va.spot, va.dir, va.step)
            r.update({f"{f}_{k}": round(mm[k], 4) for k in ("MAE", "pinball", "brier_spike", "brier_dir")})
        res.append(r)
    df = pd.DataFrame(res)
    df["B_score"] = sum(df[f"B_{k}"] / df[f"B_{k}"].iloc[0] for k in ("MAE", "pinball", "brier_spike", "brier_dir"))
    print(df.to_string(index=False))
    best = df.sort_values("B_score").iloc[0]
    print("best on B:", dict(best[["w1", "w2"]]))
    return float(best.w1), float(best.w2)


if __name__ == "__main__":
    mode = sys.argv[1]
    if mode == "screen":
        ALL = {**SCREEN, **SCREEN2, **SCREEN3, **SCREEN4}
        which = sys.argv[2:] or list(SCREEN)
        if which == ["2"]:
            which = list(SCREEN2)
        if which == ["3"]:
            which = list(SCREEN3)
        if which == ["4"]:
            which = list(SCREEN4)
        qs = (0.5,)
        df, _ = screen({k: ALL[k] for k in which}, qs)
        piv = df.pivot(index="cfg", columns="fold", values="MAE").reindex(which)
        print(piv.round(3).to_string())
    elif mode == "run":
        for nm in " ".join(sys.argv[2:]).split(","):
            RUNS(nm.strip())
    elif mode == "analyze":            # analyze <tag_a> <tag_b> [band]
        analyze(sys.argv[2], sys.argv[3], per_band=len(sys.argv) > 4)
    elif mode == "clf":
        screen_clf(CLF)
    elif mode == "causal":             # causal <tag>
        analyze_causal(sys.argv[2])
