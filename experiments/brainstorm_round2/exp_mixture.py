"""Quick leak-safe experiment: package-only 'crowd proxy' (direct quantiles + classifiers)
vs. direction-mixture CDF, on validation origins 7 Sep - 4 Oct. Metrics as in score.py.
Uses sklearn HistGradientBoosting (LightGBM-family) because libomp is unavailable."""
import sys, time
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor as HGR, HistGradientBoostingClassifier as HGC

P = sys.argv[1]
HL = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0  # recency half-life in days, 0 = off
TAG = sys.argv[3] if len(sys.argv) > 3 else "base"
t0 = time.time()
df = pd.concat([pd.read_parquet(f"{P}/data/inputs.parquet"), pd.read_csv(f"{P}/data/spot_nordpool.csv")])
df["timestamp_utc"] = pd.to_datetime(df.timestamp_utc, utc=True)
df["fu"] = pd.to_datetime(df.first_usable_origin_utc, utc=True)
idx = pd.date_range(df.timestamp_utc.min(), df.timestamp_utc.max(), freq="15min")
W = df.pivot(index="timestamp_utc", columns="series_id", values="value").reindex(idx)
FU = df.pivot(index="timestamp_utc", columns="series_id", values="fu").reindex(idx)
a = {c: W[c].to_numpy(float) for c in W}
gap = a["fi_imbalance_price"] - a["fi_spot_price"]
dirn = a["fi_mfrr_direction"]

VAL = pd.Timestamp("2026-09-06T21:00Z"); END = pd.Timestamp("2026-10-04T21:00Z")
origins = pd.date_range("2026-06-02T00:00Z", "2026-10-04T20:00Z", freq="h")
op = idx.get_indexer(origins)
K = 40
o = np.repeat(op, K); k = np.tile(np.arange(1, K + 1), len(op)); d = o + k - 1
orig_ts = np.repeat(origins.as_unit("s").asi8, K)
L5, L3 = o - 5, o - 3   # newest usable: imbalance family 5 quarters back, measured cons/prod/flows 3 back

def check(series, pos):
    fu = FU[series].to_numpy()[pos]
    fu = pd.DatetimeIndex(pd.to_datetime(fu, utc=True)).as_unit("s").asi8
    ok = (fu <= orig_ts) | np.isnan(a[series][pos])
    assert ok.all(), f"LEAK {series}: {(~ok).sum()} rows"
for s in ["fi_imbalance_price", "fi_mfrr_direction", "fi_mfrr_up_activated", "fi_mfrr_down_activated",
          "fi_mfrr_up_price", "fi_mfrr_down_price"]:
    check(s, L5); check(s, L5 - 7)
for s in ["fi_consumption", "fi_production", "fi_se1_flow", "fi_ee_flow"]:
    check(s, L3)
for s in ["fi_spot_price", "fi_wind_fc_da", "fi_consumption_fc_da", "fi_solar_fc_da", "fi_consumption_fc_da"]:
    check(s, d); check(s, d - 4); check(s, o)
print(f"availability asserts passed ({time.time()-t0:.0f}s)")

net = a["fi_consumption_fc_da"] - a["fi_wind_fc_da"] - a["fi_solar_fc_da"]
roll = lambda x, pos, n: np.nanmean(np.stack([x[pos - j] for j in range(n)]), axis=0)
spot_win = np.nanmean(np.stack([a["fi_spot_price"][o + j] for j in range(K)]), axis=0)
X = pd.DataFrame({
    "step": k, "hour": a["cal_hour_local"][d], "wday": a["cal_weekday_local"][d], "hol": a["cal_is_holiday_fi"][d],
    "spot": a["fi_spot_price"][d], "dspot_prev": a["fi_spot_price"][d] - a["fi_spot_price"][d - 1],
    "spot_rel_win": a["fi_spot_price"][d] - spot_win, "spot_rel_origin": a["fi_spot_price"][d] - a["fi_spot_price"][o],
    "wind": a["fi_wind_fc_da"][d], "cons": a["fi_consumption_fc_da"][d], "solar": a["fi_solar_fc_da"][d],
    "net": net[d], "dwind4": a["fi_wind_fc_da"][d] - a["fi_wind_fc_da"][d - 4], "dnet4": net[d] - net[d - 4],
    "gap_L": gap[L5], "gap_L4": roll(gap, L5, 4), "gap_L16": roll(gap, L5, 16),
    "dir_L": dirn[L5], "dir_L8": roll(dirn, L5, 8),
    "upmw_L": a["fi_mfrr_up_activated"][L5], "dnmw_L": a["fi_mfrr_down_activated"][L5],
    "upspr_L": a["fi_mfrr_up_price"][L5] - a["fi_spot_price"][L5], "dnspr_L": a["fi_mfrr_down_price"][L5] - a["fi_spot_price"][L5],
    "conserr_L": a["fi_consumption"][L3] - a["fi_consumption_fc_da"][L3],
    "prodcons_L": a["fi_production"][L3] - a["fi_consumption"][L3],
    "se1flow_L": a["fi_se1_flow"][L3], "eeflow_L": a["fi_ee_flow"][L3],
    "net_L": net[L3],
})
y, yd, sp, imb = gap[d], dirn[d], a["fi_spot_price"][d], a["fi_imbalance_price"][d]
dts = idx[d]
tr = (dts < VAL) & ~np.isnan(y)
va = (idx[o] >= VAL) & (dts < END) & ~np.isnan(y)
print(f"rows train {tr.sum():,}, val {va.sum():,}; features {X.shape[1]}")
Xtr, Xva = X[tr], X[va]
age_days = ((VAL - dts).total_seconds() / 86400).to_numpy()
WT = np.power(0.5, age_days / HL) if HL > 0 else np.ones(len(dts))

def metrics(p10, p50, p90, pu, pd_, pn, sh, sl, mask=None):
    yy, ss, dd = imb[va], sp[va], yd[va]
    m = np.ones(len(yy), bool) if mask is None else mask
    yy, ss, dd = yy[m], ss[m], dd[m]
    p10, p50, p90, pu, pd_, pn, sh, sl = (v[m] for v in (p10, p50, p90, pu, pd_, pn, sh, sl))
    pin = lambda q, f: np.mean(np.maximum(q * (yy - f), (q - 1) * (yy - f)))
    hi = (yy > ss + 50).astype(float); lo = (yy < ss - 50).astype(float)
    ou, od, on = (dd == 1).astype(float), (dd == -1).astype(float), (dd == 0).astype(float)
    return dict(MAE=np.mean(np.abs(yy - p50)), pinball=(pin(.1, p10) + pin(.9, p90)) / 2,
                cover=np.mean((yy >= p10) & (yy <= p90)),
                brier_spike=(np.mean((sh - hi) ** 2) + np.mean((sl - lo) ** 2)) / 2,
                brier_dir=np.mean((pu - ou) ** 2 + (pd_ - od) ** 2 + (pn - on) ** 2))

HP = dict(max_iter=400, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=200, l2_regularization=1.0, random_state=0)
reg = lambda q, Xa, ya, w=None: HGR(loss="quantile", quantile=q, **HP).fit(Xa, ya, sample_weight=w)
clf = lambda Xa, ya, w=None: HGC(**HP).fit(Xa, ya, sample_weight=w)

res = {}
# --- simple anchors
c = np.nanmedian(y[tr])
p_none = np.mean(yd[tr] == 0); pu0 = np.mean(yd[tr] == 1)
q10c, q90c = np.nanquantile(y[tr], [.1, .9])
n = va.sum(); ones = np.ones(n)
res["anchor: spot+const"] = metrics(sp[va] + q10c, sp[va] + c, sp[va] + q90c, ones * pu0, ones * (1 - pu0 - p_none),
                                    ones * p_none, ones * np.mean(y[tr] > 50), ones * np.mean(y[tr] < -50))

# --- crowd proxy: direct quantiles + classifiers
t1 = time.time()
q = {qq: reg(qq, Xtr, y[tr], WT[tr]).predict(Xva) for qq in (.1, .5, .9)}
D = np.sort(np.stack([q[.1], q[.5], q[.9]]), axis=0)
nn = tr & (yd != 0)
pup = clf(X[nn], (yd[nn] == 1).astype(int), WT[nn]).predict_proba(Xva)[:, 1]
pu, pdn, pn = (1 - p_none) * pup, (1 - p_none) * (1 - pup), ones * p_none
sh = clf(Xtr, (y[tr] > 50).astype(int), WT[tr]).predict_proba(Xva)[:, 1]
sl = clf(Xtr, (y[tr] < -50).astype(int), WT[tr]).predict_proba(Xva)[:, 1]
s = np.maximum(sh + sl, 1); sh, sl = sh / s, sl / s
res["crowd proxy (direct)"] = metrics(sp[va] + D[0], sp[va] + D[1], sp[va] + D[2], pu, pdn, pn, sh, sl)
print(f"direct done ({time.time()-t1:.0f}s)")

# --- mixture: conditional quantile grids per direction
t1 = time.time()
QS = np.array([.02, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, .95, .98])
def grid(mask):
    G = np.stack([reg(qq, X[mask], y[mask], WT[mask]).predict(Xva) for qq in QS], axis=1)
    return np.sort(G, axis=1)
Gu = grid(tr & (yd == 1)); Gd = grid(tr & (yd == -1))
print(f"mixture grids done ({time.time()-t1:.0f}s)")
def cdf(G, z):  # G: (n, nq) sorted quantiles; z: (m,) -> (n, m)
    lo = G[:, :1] - 3 * (G[:, 2:3] - G[:, :1]) - 1; hi = G[:, -1:] + 3 * (G[:, -1:] - G[:, -3:-2]) + 1
    xs = np.hstack([lo, G, hi]); ps = np.concatenate([[0], QS, [1]])
    out = np.empty((G.shape[0], len(z)))
    for i in range(G.shape[0]):
        out[i] = np.interp(z, xs[i], ps)
    return out
Z = np.arange(-600, 1200.5, 0.5).astype(np.float32)
i50, im50 = np.searchsorted(Z, 50, side="right") - 1, np.searchsorted(Z, -50, side="left") - 1  # F(50), F(<-50)
m10, m50, m90, msh, msl = (np.empty(n) for _ in range(5))
for s0 in range(0, n, 3000):
    sl_ = slice(s0, s0 + 3000)
    F = (pn[sl_, None] * (Z[None, :] >= 0) + pu[sl_, None] * cdf(Gu[sl_], Z) + pdn[sl_, None] * cdf(Gd[sl_], Z)).astype(np.float32)
    for arr, pr in ((m10, .1), (m50, .5), (m90, .9)):
        arr[sl_] = Z[np.minimum((F < pr).sum(axis=1), len(Z) - 1)]
    msh[sl_], msl[sl_] = 1 - F[:, i50], F[:, im50]
res["mixture"] = metrics(sp[va] + m10, sp[va] + m50, sp[va] + m90, pu, pdn, pn, msh, msl)
# per-column best-of: mixture quantiles/spikes but direct p50, and the reverse
res["mixture q10/q90+spikes, direct p50"] = metrics(sp[va] + np.minimum(m10, D[1]), sp[va] + D[1], sp[va] + np.maximum(m90, D[1]), pu, pdn, pn, msh, msl)
b50 = (m50 + D[1]) / 2
res["blend p50 (½ mix + ½ direct)"] = metrics(sp[va] + np.minimum(m10, b50), sp[va] + b50, sp[va] + np.maximum(m90, b50), pu, pdn, pn, msh, msl)

B = dict(MAE=66.20, pinball=24.18, cover=0.68, brier_spike=0.1132, brier_dir=0.4509)
out = pd.DataFrame(res).T
out.loc["official baseline (val)"] = B
print("\n=== validation 7 Sep - 4 Oct (all steps) ===")
print(out.round(4).to_string())

steps = k[va]
print("\n=== MAE by step band ===")
for name, p50 in [("direct", D[1]), ("mixture", m50)]:
    print(name, {f"{a_}-{b_}": round(float(np.mean(np.abs(imb[va] - sp[va] - p50)[(steps >= a_) & (steps <= b_)])), 2)
                 for a_, b_ in [(1, 4), (5, 12), (13, 24), (25, 40)]})
np.savez(f"preds_{TAG}.npz", imb=imb[va], sp=sp[va], yd=yd[va], step=k[va], dts=dts[va].asi8, D=D, pu=pu, pdn=pdn, pn=pn, sh=sh, sl=sl, m10=m10, m50=m50, m90=m90, msh=msh, msl=msl)
print(f"\ntotal {time.time()-t0:.0f}s")
