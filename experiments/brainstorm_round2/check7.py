"""Kill-checks proposed by the round-2 models, on training data (< 4 Oct 21:00Z) only."""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor as HGR
P = "starter_package"
df = pd.concat([pd.read_parquet(f"{P}/data/inputs.parquet"), pd.read_csv(f"{P}/data/spot_nordpool.csv")])
df["timestamp_utc"] = pd.to_datetime(df.timestamp_utc, utc=True)
W = df.pivot(index="timestamp_utc", columns="series_id", values="value").sort_index()
W = W[W.index < pd.Timestamp("2026-10-04T21:00Z")]
sp, ip, d = W.fi_spot_price, W.fi_imbalance_price, W.fi_mfrr_direction
gap = ip - sp; hi = gap > 50; lo = gap < -50; up = d == 1; dn = d == -1

print("== Kimi K3: import saturation -> high spikes (same quarter) ==")
sat = (W.fi_se3_flow < -1170) | (W.fi_se1_flow < -2000)
print(pd.DataFrame({"hi_rate": hi.groupby([sat, up]).mean(), "n": hi.groupby([sat, up]).size()}).rename_axis(["sat_imp", "up"]).round(3))
print("share of quarters saturated:", round(sat.mean(), 3), "| share of high spikes in saturated quarters:", round(sat[hi].mean(), 3))
sat3 = sat.shift(3)  # usable lag-3 saturation vs target quarter
print("lag-3 saturation -> high-spike rate:", hi.groupby(sat3).mean().round(3).to_dict())
for kk in [4, 8, 16, 32]:
    print(f"  saturation persistence P(sat at +{kk} | sat now): {sat.shift(-kk)[sat].mean():.2f}")
print("depeg |FI mFRR up - SE1| median by |gap| decile:",
      (W.fi_mfrr_up_price - W.se1_imbalance_price_long).abs().groupby(pd.qcut(gap.abs().rank(method="first"), 10, labels=False)).median().round(1).to_dict())

print("\n== Kimi K3: bid ladder (atomic prices) ==")
u = ip[up]
print("up-quarter imbalance prices that are whole euros:", round((np.abs(u - u.round()) < 0.005).mean(), 3),
      "| multiples of 5:", round((np.abs(u / 5 - (u / 5).round()) < 0.001).mean(), 3),
      "| up prices > 300 that are multiples of 50:", round((np.abs(u[u > 300] / 50 - (u[u > 300] / 50).round()) < 0.001).mean(), 3), f"(n={int((u > 300).sum())})")

print("\n== DeepSeek: identity prod - cons + exports ==")
res = W.fi_production - W.fi_consumption - (W.fi_se1_flow + W.fi_se3_flow + W.fi_no4_flow + W.fi_ee_flow)
print("residual std MW:", round(res.std(), 1), " mean:", round(res.mean(), 1))

print("\n== DeepSeek: spike rate by spot quintile within direction ==")
q = pd.qcut(sp, 5, labels=False)
print("high-spike rate | up, by spot quintile:", hi[up].groupby(q[up]).mean().round(3).to_dict())
print("low-spike rate | down, by spot quintile:", lo[dn].groupby(q[dn]).mean().round(3).to_dict())
print("corr on down quarters: corr(down price, spot)=%.3f  corr(gap, spot)=%.3f" % (W.fi_mfrr_down_price[dn].corr(sp[dn]), gap[dn].corr(sp[dn])))
print("corr on up quarters:   corr(up price, spot)=%.3f  corr(gap, spot)=%.3f" % (W.fi_mfrr_up_price[up].corr(sp[up]), gap[up].corr(sp[up])))

print("\n== GLM: gap quantiles by month and direction ==")
m = W.index.tz_convert("Europe/Helsinki").month
t = gap.groupby([m, d]).quantile([.1, .5, .9]).unstack().round(1)
print(t.loc[(slice(None), [-1.0, 1.0]), :].to_string())
print("NB month 10 = 1-4 Oct only (n quarters):", int((m == 10).sum()))

print("\n== Kimi K3.1 Pro: effective sample size & blend headroom (saved preds) ==")
z = np.load("preds_base.npz")
yy = z["imb"] - z["sp"]; e1, e2 = yy - z["D"][1], yy - z["m50"]
print("distinct validation delivery quarters:", len(np.unique(z["dts"] + z["step"] * 0)), "rows:", len(yy))
print("corr(direct p50 error, mixture p50 error):", round(np.corrcoef(e1, e2)[0, 1], 3))
A = pd.to_datetime(z["dts"], utc=True) < pd.Timestamp("2026-09-20T21:00Z")
for w in [0, .25, .5, .75, 1]:
    p = w * z["m50"] + (1 - w) * z["D"][1]
    print(f"  w_mix={w:.2f}: MAE fold A {np.mean(np.abs(yy - p)[A]):.2f}  fold B {np.mean(np.abs(yy - p)[~A]):.2f}")
