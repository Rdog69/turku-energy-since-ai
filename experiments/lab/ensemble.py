"""Ensemble of saved lab predictions, cross-fitted between fold A and fold B.
Run: OMP_NUM_THREADS=1 .venv/bin/python -W ignore -m experiments.lab.ensemble"""
import sys, itertools, glob, os
import numpy as np, pandas as pd
from scipy.optimize import minimize
sys.path.insert(0, ".")
from experiments.lab.data import build_base
from experiments.lab.models import metrics
from tools.fl_lab import scored_board, W, BOARD

PRED = "experiments/lab/_cache/preds"
base = build_base()
GROUPS = {"p50": ["p50"], "q": ["p10", "p90"], "spike": ["p_hi", "p_lo"], "dir": ["p_up", "p_down", "p_none"]}
METRIC = {"p50": "MAE", "q": "pinball", "spike": "brier_spike", "dir": "brier_dir"}
KEYS = [k for g in GROUPS.values() for k in g]

def load():
    runs = {}
    for f in glob.glob(f"{PRED}/*__A.npz"):
        tag = os.path.basename(f)[:-7]
        fb = f"{PRED}/{tag}__B.npz"
        if not os.path.exists(fb): continue
        d = {}
        for fo, p in (("A", f), ("B", fb)):
            z = np.load(p); d[fo] = {k: z[k] for k in z.files}
        if all(k in d[fo] for fo in "AB" for k in KEYS + ["idx"]): runs[tag] = d
    return runs

def targets(idx):
    b = base.loc[idx]
    return b.imb.to_numpy(float), b.spot.to_numpy(float), b.dir.to_numpy(float), b.step.to_numpy()

def ref_metrics():
    b = pd.read_csv(BOARD); r = b[b.name == "REF package mixture"].drop_duplicates("fold", keep="last").set_index("fold")
    return {f: {m: r.loc[f, m] for m in W} for f in "AB"}
REF = ref_metrics()

def score(mets):  # mets: {fold: {metric: v}}
    return sum(w * (REF[f][m] - mets[f][m]) / REF[f][m] / 2 for f in "AB" for m, w in W.items())

def combine(preds, w, how="mean"):
    """preds: list of dicts (same idx). returns dict of arrays."""
    out = {}
    for g, ks in GROUPS.items():
        for k in ks:
            S = np.stack([p[k] for p in preds])
            if g == "p50" and how == "median": out[k] = np.median(S, 0)
            else: out[k] = np.tensordot(w[g], S, 1)
    return fix(out)

def fix(o):
    lo, md, hi = o["p10"], o["p50"], o["p90"]
    o["p10"], o["p50"], o["p90"] = np.minimum(lo, md), md, np.maximum(hi, md)
    s = np.maximum(o["p_hi"] + o["p_lo"], 1); o["p_hi"], o["p_lo"] = o["p_hi"] / s, o["p_lo"] / s
    d = o["p_up"] + o["p_down"] + o["p_none"]
    for k in ("p_up", "p_down", "p_none"): o[k] = o[k] / d
    return o

def group_loss(g, P, y, s, d, w):
    """loss of group g for weights w; P list of dicts"""
    o = {k: np.tensordot(w, np.stack([p[k] for p in P]), 1) for k in GROUPS[g]}
    if g == "p50": return np.mean(np.abs(y - o["p50"]))
    if g == "q":
        pin = lambda q, f: np.mean(np.maximum(q * (y - f), (q - 1) * (y - f)))
        return (pin(.1, o["p10"]) + pin(.9, o["p90"])) / 2
    hi, lo = (y > s + 50), (y < s - 50)
    if g == "spike": return (np.mean((o["p_hi"] - hi) ** 2) + np.mean((o["p_lo"] - lo) ** 2)) / 2
    return np.mean((o["p_up"] - (d == 1)) ** 2 + (o["p_down"] - (d == -1)) ** 2 + (o["p_none"] - (d == 0)) ** 2)

def fit_w(g, P, y, s, d, maxk=None):
    n = len(P)
    f = lambda w: group_loss(g, P, y, s, d, w)
    if maxk:  # greedy forward selection with replacement (Caruana), maxk picks
        cnt = np.zeros(n); 
        for _ in range(maxk):
            best = min(range(n), key=lambda i: f((cnt + np.eye(n)[i]) / (cnt.sum() + 1)))
            cnt[best] += 1
        return cnt / cnt.sum()
    best = None
    for st in (np.ones(n) / n, np.eye(n)[np.argmin([f(np.eye(n)[i]) for i in range(n)])] * .5 + .5 / n):
        r = minimize(f, st, method="SLSQP", bounds=[(0, 1)] * n, constraints=[{"type": "eq", "fun": lambda w: w.sum() - 1}], options=dict(maxiter=200))
        if best is None or r.fun < best.fun: best = r
    w = np.clip(best.x, 0, None); w[w < 0.02] = 0; return w / w.sum()

def eval_ens(P, ws, how="mean"):
    """P: {fold: list of pred dicts}; ws: {fold: weights dict} -> weights used when predicting that fold"""
    mets = {}
    for fo in "AB":
        y, s, d, st = targets(IDX[fo])
        mets[fo] = metrics(combine(P[fo], ws[fo], how), y, s, d, st)
    return mets

def main(topn=12, verbose=True):
    global IDX
    runs = load()
    tags = list(runs)
    IDX = {fo: runs[tags[0]][fo]["idx"] for fo in "AB"}
    ok = [t for t in tags if all(np.array_equal(runs[t][fo]["idx"], IDX[fo]) for fo in "AB")]
    sb = scored_board(); sb["tag"] = sb.agent + "__" + sb.name.str.replace(",", ";")
    # single-run scores from the saved predictions
    single = {}
    for t in ok:
        m = {}
        for fo in "AB":
            y, s, d, st = targets(IDX[fo]); m[fo] = metrics(fix({k: runs[t][fo][k].copy() for k in KEYS}), y, s, d)
        single[t] = score(m)
    rank = sorted(ok, key=lambda t: -single[t])
    print(f"{len(ok)} runs with both folds; top singles:")
    for t in rank[:8]: print(f"  {single[t]:+.3f}  {t}")
    top = rank[:topn]
    P = {fo: [{k: runs[t][fo][k] for k in KEYS} for t in top] for fo in "AB"}
    N = len(top); res = {}
    res["best single"] = single[rank[0]]
    # 1 equal average top-k
    for k in (2, 3, 5):
        w = {g: np.ones(k) / k for g in GROUPS}
        Pk = {fo: P[fo][:k] for fo in "AB"}
        res[f"equal top{k}"] = score(eval_ens(Pk, {"A": w, "B": w}))
        res[f"equal top{k} median-p50"] = score(eval_ens(Pk, {"A": w, "B": w}, "median")) if k >= 3 else np.nan
    # 2 cross-fitted convex weights (fit on other fold)
    def crossfit(maxk=None, bands=None):
        mets = {}
        wsave = {}
        for fo, other in (("A", "B"), ("B", "A")):
            yo, so, do, sto = targets(IDX[other]); y, s, d, st = targets(IDX[fo])
            o_all = {k: np.zeros(len(y)) for k in KEYS}
            for (a, b) in (bands or [(1, 40)]):
                mo, mv = (sto >= a) & (sto <= b), (st >= a) & (st <= b)
                Po = [{k: p[k][mo] for k in KEYS} for p in P[other]]
                Pv = [{k: p[k][mv] for k in KEYS} for p in P[fo]]
                wb = {g: fit_w(g, Po, yo[mo], so[mo], do[mo], maxk) for g in GROUPS}
                wsave[(fo, a)] = wb
                c = combine(Pv, wb)
                for k in KEYS: o_all[k][mv] = c[k]
            mets[fo] = metrics(fix(o_all), y, s, d, st)
        return score(mets), wsave
    res["crossfit convex (all top%d)" % N], wfull = crossfit()
    for mk in (2, 3):
        res[f"crossfit greedy<= {mk} members/group"], _ = crossfit(mk)
    res["crossfit convex + bands 1-4/5-16/17-40"], _ = crossfit(bands=[(1, 4), (5, 16), (17, 40)])
    res["crossfit greedy3 + bands"], _ = crossfit(3, [(1, 4), (5, 16), (17, 40)])
    print("\nSCORES (cross-fitted unless 'equal'/'best single')")
    for k, v in res.items(): print(f"  {v:+.3f}  {k}")
    print("\nweights fitted on fold B (applied to A), convex all-top:")
    for g, w in wfull[("A", 1)].items(): print(" ", g, {top[i]: round(float(x), 2) for i, x in enumerate(w) if x > 0})
    print("weights fitted on fold A (applied to B):")
    for g, w in wfull[("B", 1)].items(): print(" ", g, {top[i]: round(float(x), 2) for i, x in enumerate(w) if x > 0})
    # final: weights fitted on A+B pooled, greedy 3
    Pp = [{k: np.concatenate([P["A"][i][k], P["B"][i][k]]) for k in KEYS} for i in range(N)]
    t = [targets(IDX[f]) for f in "AB"]; y, s, d = (np.concatenate([x[j] for x in t]) for j in range(3))
    print("\nPooled (A+B) greedy<=3 weights per group (final recipe):")
    for g in GROUPS:
        w = fit_w(g, Pp, y, s, d, 3); print(" ", g, {top[i]: round(float(x), 2) for i, x in enumerate(w) if x > 0})
    # correlation of top-k errors (diversity)
    return res

if __name__ == "__main__":
    main()
