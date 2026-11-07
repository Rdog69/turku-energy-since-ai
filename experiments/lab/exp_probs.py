"""Agent `probs`: spike / direction probability calibration + pinball width corrections.

Stage `gen` fits the raw components once per (fold, window, feature set) and caches them in
_cache/probs/. window 0 = full model on the fold's train -> validation rows; window W>0 =
inner model on train minus its last W days -> predictions for those W days (the calibration
window, exactly as run.py does for W=14). Components:
  pup            P(up | not none) classifier
  shi, slo       unconditional spike classifiers (as in the 'direct' model)
  chi, clo       conditional spike classifiers: P(gap>50 | up), P(gap<-50 | down)
  Gup, Gdn       13-quantile gap grids per direction (the mixture), only for feature set 'pkg'
Stage `eval` lives in probs_eval.py-style functions below and only post-processes the caches.

    OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_probs gen
"""
from __future__ import annotations

from experiments.lab.data import threads

threads(2)

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from experiments.lab.data import Data, build_base
from experiments.lab.features.package import package_features
from experiments.lab.features.probs import dir_features
from experiments.lab.models import HGB, QS, _cdf, _clf, _reg
from experiments.lab.run import features

LAB = Path(__file__).resolve().parent
PC = LAB / "_cache" / "probs"
PC.mkdir(parents=True, exist_ok=True)


def split(base, fold, win):
    role = base[f"fold{fold}"]
    tr, va = base[role == "train"], base[role == "val"]
    tr = tr[tr.gap.notna()]
    if win == 0:
        return tr, va
    cut = tr.delivery.max() - pd.Timedelta(days=win)
    return tr[tr.origin < cut - pd.Timedelta(hours=10)], tr[tr.origin >= cut]


def pack(Xtr, tr, Xva, grids=True):
    g, d = tr["gap"].to_numpy(), tr["dir"].to_numpy()
    ok = ~np.isnan(g)
    nn, mu, md = ok & (d != 0), ok & (d == 1), ok & (d == -1)
    out = dict(p_none_tr=np.array(float(np.mean(d[ok] == 0))),
               hi_dn_tr=np.array(float(np.mean(g[md] > 50))), lo_up_tr=np.array(float(np.mean(g[mu] < -50))))
    P = lambda m, y: _clf(Xtr[m], y.astype(int), None, HGB).predict_proba(Xva)[:, 1]
    out["pup"] = P(nn, d[nn] == 1)
    out["shi"], out["slo"] = P(ok, g[ok] > 50), P(ok, g[ok] < -50)
    out["chi"], out["clo"] = P(mu, g[mu] > 50), P(md, g[md] < -50)
    if grids:
        for side, m in (("Gup", mu), ("Gdn", md)):
            out[side] = np.sort(np.stack([_reg(q, Xtr[m], g[m], None, HGB).predict(Xva) for q in QS], axis=1), axis=1)
    return out


def mixture(p_up, p_down, p_none, Gup, Gdn, spot):
    """Exactly the mixture assembly of models.fit_predict, given (possibly recalibrated) direction probs."""
    Z = np.arange(-600, 1500.5, 0.5).astype(np.float32)
    i50, im50 = np.searchsorted(Z, 50, side="right") - 1, np.searchsorted(Z, -50, side="left") - 1
    n = len(spot)
    r = {k: np.empty(n) for k in ("p10", "p50", "p90", "p_hi", "p_lo")}
    for s0 in range(0, n, 3000):
        sl_ = slice(s0, s0 + 3000)
        F = (p_none[sl_, None] * (Z[None, :] >= 0) + p_up[sl_, None] * _cdf(Gup[sl_], Z)
             + p_down[sl_, None] * _cdf(Gdn[sl_], Z)).astype(np.float32)
        for k, pr in (("p10", .1), ("p50", .5), ("p90", .9)):
            r[k][sl_] = spot[sl_] + Z[np.minimum((F < pr).sum(axis=1), len(Z) - 1)]
        r["p_hi"][sl_], r["p_lo"][sl_] = 1 - F[:, i50], F[:, im50]
    return r


def tails(Gup, Gdn):
    """Per-direction conditional tail probs of the mixture grids: P(gap>50|up), P(gap<-50|up), same for down."""
    z = np.array([-50.0, 50.0])
    out = {}
    for nm, G in (("up", Gup), ("dn", Gdn)):
        F = np.stack([np.interp(z, *_xs_ps(G[i])) for i in range(G.shape[0])])
        out[f"tlo_{nm}"], out[f"thi_{nm}"] = F[:, 0], 1 - F[:, 1]
    return out


def _xs_ps(g):
    lo = g[0] - 3 * (g[2] - g[0]) - 1
    hi = g[-1] + 3 * (g[-1] - g[-3]) + 1
    return np.concatenate([[lo], g, [hi]]), np.concatenate([[0], QS, [1]])


def gen(jobs):
    base, data = build_base(), Data()
    X = {"pkg": features([package_features], base, data)}
    X["dir"] = features([package_features, dir_features], base, data)
    X["dir"] = X["dir"].loc[:, ~X["dir"].columns.duplicated()]
    for fold, win, fs in jobs:
        f = PC / f"{fold}_w{win}_{fs}.npz"
        if f.exists():
            continue
        t0 = time.time()
        tr, va = split(base, fold, win)
        out = pack(X[fs].loc[tr.index], tr, X[fs].loc[va.index], grids=(fs == "pkg"))
        np.savez_compressed(f, idx=va.index.to_numpy(), **out)
        print(f"{f.name}: {len(tr)} train, {len(va)} pred, {time.time() - t0:.0f}s", flush=True)


JOBS = [("A", 0, "pkg"), ("A", 14, "pkg"), ("B", 0, "pkg"), ("B", 14, "pkg"),
        ("A", 0, "dir"), ("A", 14, "dir"), ("B", 0, "dir"), ("B", 14, "dir"),
        ("A", 28, "pkg"), ("B", 28, "pkg"), ("A", 28, "dir"), ("B", 28, "dir")]

if __name__ == "__main__":
    if sys.argv[1] == "gen":
        gen(JOBS)


# ============================================================================= stage `eval` (post-processing only)
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from scipy.optimize import minimize

from experiments.lab.models import metrics

BANDS = lambda st: np.select([st <= 4, st <= 12, st <= 24], [0, 1, 2], 3)
lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
sg = lambda x: 1 / (1 + np.exp(-x))


def load(fold, win, fs):
    z = np.load(PC / f"{fold}_w{win}_{fs}.npz")
    return {k: z[k] for k in z.files}


def assemble(z, G, spot, pup=None):
    """Raw prediction dict from cached components. z: classifier pack, G: pack holding Gup/Gdn."""
    pn = float(z["p_none_tr"])
    pup = z["pup"] if pup is None else pup
    P = dict(p_up=(1 - pn) * pup, p_down=(1 - pn) * (1 - pup), p_none=np.full(len(pup), pn), pup=pup)
    P.update(mixture(P["p_up"], P["p_down"], P["p_none"], G["Gup"], G["Gdn"], spot))
    P["mhi"], P["mlo"] = P["p_hi"], P["p_lo"]
    s = np.maximum(z["shi"] + z["slo"], 1)
    P["dhi"], P["dlo"] = z["shi"] / s, z["slo"] / s
    P["zchi"], P["zclo"] = z["chi"], z["clo"]
    P["hi_dn"], P["lo_up"] = float(z["hi_dn_tr"]), float(z["lo_up_tr"])
    return P


# ---------------------------------------------------------------- 1-D calibrators: fit(p, y, aux) -> apply(p, aux)
def c_none(p, y, a):
    return lambda q, b: q


def c_platt(p, y, a, C=1e6):
    if y.min() == y.max():
        return lambda q, b: q
    m = LogisticRegression(C=C).fit(lg(p)[:, None], y)
    return lambda q, b: m.predict_proba(lg(q)[:, None])[:, 1]


def c_platt_brier(p, y, a):
    x = lg(p)
    r = minimize(lambda t: np.mean((sg(t[0] + t[1] * x) - y) ** 2), [0.0, 1.0], method="Nelder-Mead").x
    return lambda q, b: sg(r[0] + r[1] * lg(q))


def c_shift(p, y, a):
    x = lg(p)
    r = minimize(lambda t: np.mean((sg(t[0] + x) - y) ** 2), [0.0], method="Nelder-Mead").x
    return lambda q, b: sg(r[0] + lg(q))


def c_temp(p, y, a):
    x = lg(p)
    r = minimize(lambda t: np.mean((sg(t[0] * x) - y) ** 2), [1.0], method="Nelder-Mead").x
    return lambda q, b: sg(r[0] * lg(q))


def c_iso(p, y, a):
    m = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit(p, y)
    return lambda q, b: m.predict(q)


def c_platt_iso(p, y, a):  # average of Platt and isotonic
    f1, f2 = c_platt(p, y, a), c_iso(p, y, a)
    return lambda q, b: (f1(q, b) + f2(q, b)) / 2


def per_band(cal_fn):
    def fit(p, y, a):
        fs = {b: cal_fn(p[a["band"] == b], y[a["band"] == b], None) for b in range(4)}

        def app(q, b):
            out = np.empty_like(q)
            for k, f in fs.items():
                m = b["band"] == k
                out[m] = f(q[m], None)
            return out
        return app
    return fit


SPOT_CUTS = np.array([0.0, 20.0, 50.0, 100.0])


def c_platt_spot(p, y, a, C=1.0):
    """Platt with per-spot-bin intercepts (lightly regularised)."""
    def X(q, b):
        oh = np.eye(len(SPOT_CUTS) + 1)[np.searchsorted(SPOT_CUTS, b["spot"])]
        return np.hstack([lg(q)[:, None], oh[:, 1:]])
    m = LogisticRegression(C=C).fit(X(p, a), y)
    return lambda q, b: m.predict_proba(X(q, b))[:, 1]


def c_stack(cols, C=1.0):
    """Logistic stacking on several logit-probabilities; p is a 2-D array (n, k)."""
    def fit(p, y, a):
        m = LogisticRegression(C=C).fit(lg(p), y)
        return lambda q, b: m.predict_proba(lg(q))[:, 1]
    return fit


def c_shrink_train(p, y, a):
    """p' = (1-alpha) p + alpha * pi, pi = pre-cutoff (full-train) base rate, alpha fitted for Brier on the cal window."""
    pi = a["pi"]
    r = minimize(lambda t: np.mean(((1 - t[0]) * p + t[0] * pi - y) ** 2), [0.1], method="Nelder-Mead").x[0]
    return lambda q, b: (1 - r) * q + r * pi


def c_shrink_recent(p, y, a):
    """Same, but pi = base rate of the calibration window itself (a recent prior)."""
    pi = float(np.mean(y))
    r = minimize(lambda t: np.mean(((1 - t[0]) * p + t[0] * pi - y) ** 2), [0.1], method="Nelder-Mead").x[0]
    return lambda q, b: (1 - r) * q + r * pi


def c_lin_brier(p, y, a):
    """p' = a + b p (probability-space affine), fitted for Brier."""
    r = minimize(lambda t: np.mean((np.clip(t[0] + t[1] * p, 0, 1) - y) ** 2), [0.0, 1.0], method="Nelder-Mead").x
    return lambda q, b: np.clip(r[0] + r[1] * q, 0, 1)


def c_platt_eb(m0=50, fit="logloss", base_fn=None):
    """Empirical-Bayes Platt: fit (a, b) on the calibration window, then shrink towards identity (0, 1)
    by s = m / (m + m0), m = number of DISTINCT delivery quarters with an event in the window.
    Rationale: a 14-day window can contain only a handful of spike episodes (fold B: 3 low spikes)."""
    def fit_(p, y, a):
        x = lg(p)
        if y.min() == y.max():
            A, B = 0.0, 1.0
        elif fit == "logloss":
            m = LogisticRegression(C=1e6).fit(x[:, None], y)
            A, B = float(m.intercept_[0]), float(m.coef_[0, 0])
        else:
            A, B = minimize(lambda t: np.mean((sg(t[0] + t[1] * x) - y) ** 2), [0.0, 1.0], method="Nelder-Mead").x
        mm = len(np.unique(a["deliv"][y == 1])) if a is not None and "deliv" in a else int(y.sum())
        sh = mm / (mm + m0)
        A2, B2 = sh * A, 1 + sh * (B - 1)
        return lambda q, b: sg(A2 + B2 * lg(q))
    return fit_


CAL = dict(shrink_train=c_shrink_train, shrink_recent=c_shrink_recent, lin_brier=c_lin_brier,
           platt_brier_band=None, none=c_none, platt=c_platt, platt_brier=c_platt_brier, shift=c_shift, temp=c_temp, iso=c_iso,
           platt_iso=c_platt_iso, platt_band=per_band(c_platt), shift_band=per_band(c_shift),
           iso_band=per_band(c_iso), platt_spot=c_platt_spot)
CAL["platt_brier_band"] = per_band(c_platt_brier)
for _m0 in (10, 25, 50, 100, 200):
    CAL[f"eb{_m0}"] = c_platt_eb(_m0)
    CAL[f"ebb{_m0}"] = c_platt_eb(_m0, fit="brier")


def aux(rows):
    return dict(band=BANDS(rows["step"].to_numpy()), spot=rows["spot"].to_numpy(),
                deliv=rows["delivery"].to_numpy().astype("datetime64[ns]").astype(np.int64))


def norm_hl(hi, lo):
    s = np.maximum(hi + lo, 1)
    return hi / s, lo / s


def brier_parts(hi, lo, rows):
    g = rows["gap"].to_numpy(); ok = ~np.isnan(g) & ~np.isnan(rows["spot"].to_numpy())
    bh = np.mean((hi[ok] - (g[ok] > 50)) ** 2); bl = np.mean((lo[ok] - (g[ok] < -50)) ** 2)
    return bh, bl


class Fold:
    """Validation rows + calibration windows (7/14/28 days) with raw component predictions."""

    def __init__(self, fold, base, fs_avail=("pkg", "dir"), wins=(14, 28)):
        self.fold, self.base = fold, base
        self.z, self.rows = {}, {}
        for fs in fs_avail:
            for w in (0,) + tuple(wins):
                if (PC / f"{fold}_w{w}_{fs}.npz").exists():
                    self.z[(w, fs)] = load(fold, w, fs)
                    self.rows[w] = base.loc[self.z[(w, fs)]["idx"]]
        self._asm = {}

    def tails(self, w, idx=None):
        ww = 14 if w == 7 else w
        if ("tails", ww) not in self._asm:
            self._asm[("tails", ww)] = tails(self.z[(ww, "pkg")]["Gup"], self.z[(ww, "pkg")]["Gdn"])
        T = self._asm[("tails", ww)]
        if idx is not None:
            sel = np.isin(self.rows[ww].index, idx)
            T = {k: v[sel] for k, v in T.items()}
        return T

    def raw(self, w, fs="pkg", pup=None, tag=""):
        """Assembled raw preds for window w (0 = validation). 7 = last 7 days of the 14-day window."""
        ww = 14 if w == 7 else w
        key = (ww, fs, tag)
        if key not in self._asm:
            z, G = self.z[(ww, fs)], self.z[(ww, "pkg")]
            self._asm[key] = assemble(z, G, self.rows[ww]["spot"].to_numpy(), pup)
        P, rows = self._asm[key], self.rows[ww]
        if w == 7:
            m = (rows.origin >= rows.delivery.max() - pd.Timedelta(days=7)).to_numpy()
            P = {k: (v[m] if isinstance(v, np.ndarray) and v.shape[:1] == (len(m),) else v) for k, v in P.items()}
            rows = rows[m]
        return P, rows


def recipe(F: Fold, w=14, dir_fs="pkg", dir_cal="platt", p_none=None, spike="mix", spike_cal="platt",
           mix_pupcal=False, width="add", spike_fs=None, blend_w=0.5, tail_pupcal=False, q_fs="pkg"):
    """Returns the final validation prediction dict for one calibration recipe."""
    spike_fs = spike_fs or dir_fs
    Pv, va = F.raw(0, dir_fs)
    Pc, ca = F.raw(w, dir_fs)
    av, ac = aux(va), aux(ca)
    out = {}
    # ---------------- direction
    dc = ca["dir"].to_numpy(); nn = (dc != 0) & ~np.isnan(ca["gap"].to_numpy())
    fd = CAL[dir_cal](Pc["pup"][nn], (dc[nn] == 1).astype(int), {k: v[nn] for k, v in ac.items()})
    pup_v, pup_c = fd(Pv["pup"], av), fd(Pc["pup"], ac)
    pn = float(F.z[(0, dir_fs)]["p_none_tr"]) if p_none is None else p_none
    for nm, pu, n in (("v", pup_v, len(va)), ("c", pup_c, len(ca))):
        out[nm] = dict(p_up=(1 - pn) * pu, p_down=(1 - pn) * (1 - pu), p_none=np.full(n, pn))
    # ---------------- mixture quantiles / tail (raw p_up as in REF, or recalibrated p_up)
    if mix_pupcal:
        Mv = mixture(out["v"]["p_up"], out["v"]["p_down"], out["v"]["p_none"], F.z[(0, "pkg")]["Gup"], F.z[(0, "pkg")]["Gdn"], va["spot"].to_numpy())
        ww = 14 if w == 7 else w
        Gc = F.z[(ww, "pkg")]
        sel = np.isin(F.rows[ww].index, ca.index)
        Mc = mixture(out["c"]["p_up"], out["c"]["p_down"], out["c"]["p_none"], Gc["Gup"][sel], Gc["Gdn"][sel], ca["spot"].to_numpy())
    else:
        Pvp, _ = F.raw(0, q_fs); Pcp, _ = F.raw(w, q_fs)
        Mv, Mc = Pvp, Pcp
    Tv, Tc = Mv, Mc
    if tail_pupcal and not mix_pupcal:
        ww = 14 if w == 7 else w
        Gc = F.z[(ww, "pkg")]; sel = np.isin(F.rows[ww].index, ca.index)
        Tv = mixture(out["v"]["p_up"], out["v"]["p_down"], out["v"]["p_none"], F.z[(0, "pkg")]["Gup"], F.z[(0, "pkg")]["Gdn"], va["spot"].to_numpy())
        Tc = mixture(out["c"]["p_up"], out["c"]["p_down"], out["c"]["p_none"], Gc["Gup"][sel], Gc["Gdn"][sel], ca["spot"].to_numpy())
    # ---------------- spike sources (raw)
    Ps_v, _ = F.raw(0, spike_fs); Ps_c, _ = F.raw(w, spike_fs)

    def src(P, M, D):
        cond_hi = D["p_up"] * P["zchi"] + D["p_down"] * P["hi_dn"]
        cond_lo = D["p_down"] * P["zclo"] + D["p_up"] * P["lo_up"]
        S = dict(mix=(M["p_hi"], M["p_lo"]), direct=(P["dhi"], P["dlo"]), cond=(cond_hi, cond_lo))
        return S
    Sv, Sc = src(Ps_v, Tv, out["v"]), src(Ps_c, Tc, out["c"])
    gc = ca["gap"].to_numpy(); okc = ~np.isnan(gc)
    yh, yl = (gc[okc] > 50).astype(int), (gc[okc] < -50).astype(int)
    acs = {k: v[okc] for k, v in ac.items()}
    trr = F.base[F.base[f"fold{F.fold}"] == "train"]["gap"].dropna()
    pis = (float((trr > 50).mean()), float((trr < -50).mean()))
    res = {}
    for j, y in ((0, yh), (1, yl)):
        acs["pi"] = pis[j]
        if spike in Sv:
            pv, pc = Sv[spike][j], Sc[spike][j]
        elif spike.startswith("avg_"):       # e.g. avg_mix_direct: mean of probabilities
            a, b = spike[4:].split("_")
            pv = blend_w * Sv[a][j] + (1 - blend_w) * Sv[b][j]; pc = blend_w * Sc[a][j] + (1 - blend_w) * Sc[b][j]
        elif spike.startswith("lavg_"):      # mean of logits
            a, b = spike[5:].split("_")
            pv = sg(blend_w * lg(Sv[a][j]) + (1 - blend_w) * lg(Sv[b][j])); pc = sg(blend_w * lg(Sc[a][j]) + (1 - blend_w) * lg(Sc[b][j]))
        elif spike in ("fmix", "fcond"):     # factorised: calibrated p_dir x calibrated P(spike | matching dir)
            dv_, dc_ = va["dir"].to_numpy(), ca["dir"].to_numpy()[okc]
            side = 1 if j == 0 else -1
            key = ("thi_up", "thi_dn") if j == 0 else ("tlo_dn", "tlo_up")
            if spike == "fmix":
                cv, cc = F.tails(0), F.tails(w, ca.index)
                mv_, mc_ = cv[key[0]], cc[key[0]][okc]
                ov_, oc_ = cv[key[1]], cc[key[1]][okc]
            else:
                zk = "zchi" if j == 0 else "zclo"
                mv_, mc_ = Ps_v[zk], Ps_c[zk][okc]
                ov_ = np.full(len(va), Ps_v["hi_dn"] if j == 0 else Ps_v["lo_up"]); oc_ = None
            sel_ = dc_ == side
            fcal = CAL[spike_cal](mc_[sel_], y[sel_], {k: (v[sel_] if isinstance(v, np.ndarray) else v) for k, v in acs.items()})
            pm = out["v"]["p_up"] if j == 0 else out["v"]["p_down"]
            po = out["v"]["p_down"] if j == 0 else out["v"]["p_up"]
            res[j] = pm * fcal(mv_, av) + po * ov_
            continue
        elif spike.startswith("stack_"):     # logistic stacking fitted on the calibration window
            ks = spike[6:].split("_")
            Xv = np.stack([Sv[k][j] for k in ks], 1); Xc = np.stack([Sc[k][j] for k in ks], 1)
            f = c_stack(ks)(Xc[okc], y, acs)
            res[j] = f(Xv, av)
            continue
        if spike_cal.startswith("cal_then_avg"):   # calibrate each source separately, then average
            raise NotImplementedError
        f = CAL[spike_cal](pc[okc], y, acs)
        res[j] = f(pv, av)
    out["v"]["p_hi"], out["v"]["p_lo"] = norm_hl(res[0], res[1])
    # ---------------- quantiles
    yv = ca["imb"].to_numpy(); okq = ~np.isnan(yv)
    q = {k: Mv[k].copy() for k in ("p10", "p50", "p90")}
    if width in ("mult", "mult_add"):
        for b in range(4):
            mc, mv = (ac["band"] == b) & okq, av["band"] == b
            for k, tau in (("p10", .1), ("p90", .9)):
                wc = Mc[k][mc] - Mc["p50"][mc]
                ks = np.arange(0.5, 2.505, 0.01)
                L = [np.mean(np.maximum(tau * (yv[mc] - Mc["p50"][mc] - kk * wc), (tau - 1) * (yv[mc] - Mc["p50"][mc] - kk * wc))) for kk in ks]
                kk = ks[int(np.argmin(L))]
                q[k][mv] = q["p50"][mv] + kk * (q[k][mv] - q["p50"][mv])
                if width == "mult_add":
                    adj = np.quantile(yv[mc] - (Mc["p50"][mc] + kk * wc), tau)
                    q[k][mv] += adj
    elif width == "add":
        for b in range(4):
            mc, mv = (ac["band"] == b) & okq, av["band"] == b
            for k, tau in (("p10", .1), ("p90", .9)):
                q[k][mv] += np.quantile(yv[mc] - Mc[k][mc], tau)
    q["p10"] = np.minimum(q["p10"], q["p50"]); q["p90"] = np.maximum(q["p90"], q["p50"])
    out["v"].update(q)
    return out["v"], va


def score(F, **kw):
    P, va = recipe(F, **kw)
    m = metrics(P, va.imb, va.spot, va.dir, va.step)
    bh, bl = brier_parts(P["p_hi"], P["p_lo"], va)
    return dict(MAE=m["MAE"], pinball=m["pinball"], coverage=m["coverage"], brier_spike=m["brier_spike"],
                brier_dir=m["brier_dir"], b_hi=bh, b_lo=bl), P, va


SCR = Path("/private/tmp/claude-501/-Users-abderahimmojahid-Studies--bo-SINCE-AI-turku-energy-since-ai/ce30b3d5-78fc-4083-a944-60b3e24dbaf1/scratchpad")
REF = dict(w=14, dir_fs="pkg", dir_cal="platt", spike="mix", spike_cal="platt", width="add")


def sweep(variants, folds=("A", "B"), out_csv=None, wins=(14, 28)):
    base = build_base()
    Fs = {f: Fold(f, base, wins=wins) for f in folds}
    rows = []
    for name, kw in variants:
        r = {"name": name}
        for f in folds:
            try:
                m, _, _ = score(Fs[f], **{**REF, **kw})
            except KeyError as e:
                m = {}
                print("missing", name, f, e)
            for k, v in m.items():
                r[f"{f}_{k}"] = v
        rows.append(r)
        print(pd.DataFrame([r]).round(5).to_string(index=False, header=len(rows) == 1), flush=True)
    df = pd.DataFrame(rows)
    if out_csv:
        df.to_csv(SCR / out_csv, index=False)
    return df


def day_boot(P1, P2, va, metric="spike", n=500, seed=0):
    """Paired day-block bootstrap of metric(P1) - metric(P2) on validation rows. Returns mean, sd, P(diff<0)."""
    g = va["gap"].to_numpy(); ok = ~np.isnan(g) & ~np.isnan(va["spot"].to_numpy())
    d = va["dir"].to_numpy()
    def per_row(P):
        if metric == "spike":
            return ((P["p_hi"] - (g > 50)) ** 2 + (P["p_lo"] - (g < -50)) ** 2) / 2
        return (P["p_up"] - (d == 1)) ** 2 + (P["p_down"] - (d == -1)) ** 2 + (P["p_none"] - (d == 0)) ** 2
    diff = (per_row(P1) - per_row(P2))[ok]
    day = va["origin"].dt.floor("D").to_numpy()[ok]
    u, inv = np.unique(day, return_inverse=True)
    s, c = np.bincount(inv, diff), np.bincount(inv)
    rng = np.random.default_rng(seed)
    bs = []
    for _ in range(n):
        k = rng.integers(0, len(u), len(u))
        bs.append(s[k].sum() / c[k].sum())
    bs = np.array(bs)
    return diff.mean(), bs.std(), float(np.mean(bs < 0))


def reliability(F, w=0, src=("mhi", "mlo", "dhi", "dlo"), bins=(0, .02, .05, .1, .2, .3, .5, 1.01)):
    P, rows = F.raw(w, "pkg")
    g = rows["gap"].to_numpy(); ok = ~np.isnan(g)
    out = []
    for k in src:
        y = (g > 50) if k.endswith("hi") else (g < -50)
        b = np.digitize(P[k], bins) - 1
        for i in range(len(bins) - 1):
            m = ok & (b == i)
            if m.sum():
                out.append(dict(fold=F.fold, w=w, src=k, bin=f"{bins[i]:.2f}-{bins[i+1]:.2f}", n=int(m.sum()),
                                mean_p=P[k][m].mean(), obs=y[m].mean()))
    return pd.DataFrame(out)
