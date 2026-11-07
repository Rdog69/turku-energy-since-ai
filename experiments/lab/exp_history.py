"""Agent `history` experiments. Usage: python -m experiments.lab.exp_history <name> [model]"""
import sys

from experiments.lab.data import threads; threads(2)
from experiments.lab.run import run_experiment
from experiments.lab.features.package import package_features
from experiments.lab.features import history as H

EXPS = {
    "runs": ([package_features, H.runs_features], "direction run length/switches/up shares, spike-regime shares, same-quarter-yesterday dir"),
    "neigh": ([package_features, H.neighbour_features], "Elering system/ac balance + Energinet aFRR DK1/DK2, DK-SE exchange (asof, fu<=origin)"),
    "hda": ([package_features, H.hist_da_features], "P(up | DA net/wind/cons/solar/hour) HGB fitted on fg_hist Mar25-May26"),
    "hfull": ([package_features, H.hist_full_features], "persistence-aware P(up) fitted on fg_hist with simulated origins"),
    "hprior": ([package_features, H.hist_prior_features], "month x hour P(up)/P(none) prior from fg_hist (featherless idea 5)"),
    "hfull2": ([package_features, H.hist_full2_features], "hfull + prev run, up96, mFRR up-down spread, same-quarter previous days; fitted on fg_hist"),
    "hboth": ([package_features, H.hist_both_features], "hda + hfull"),
}

def drift():
    """Direction shares by hour / net position: autumn 2025 (fg_hist) vs summer 2026 (package)."""
    import numpy as np
    import pandas as pd
    from experiments.lab.data import Data
    d = Data()
    h = H.hist_as_pkg(d)
    pk = d["pkg"]

    def wide(df):
        w = df[df.series_id.isin(["fi_mfrr_direction", "fi_imbalance_price", "fi_mfrr_up_price", "fi_mfrr_down_price",
                                  "fi_wind_fc_da", "fi_consumption_fc_da", "fi_solar_fc_da"])]
        w = w.drop_duplicates(["series_id", "ts"]).pivot(index="ts", columns="series_id", values="value")
        w["net"] = w.fi_consumption_fc_da - w.fi_wind_fc_da - w.fi_solar_fc_da
        w["hour"] = w.index.tz_convert(H.TZ).hour
        return w

    wh, wp = wide(h), wide(pk)
    print("hist range", wh.index.min(), wh.index.max(), "| pkg range", wp.index.min(), wp.index.max())
    # sanity: sign convention (dir=1 -> imbalance price == up price)
    for nm, w in (("hist", wh), ("pkg", wp)):
        x = w.dropna(subset=["fi_mfrr_direction", "fi_imbalance_price"])
        for v in (1, -1, 0):
            m = x.fi_mfrr_direction == v
            print(nm, "dir", v, "n", int(m.sum()), "imb==up", round(float(np.isclose(x.fi_imbalance_price[m], x.fi_mfrr_up_price[m]).mean()), 3),
                  "imb==down", round(float(np.isclose(x.fi_imbalance_price[m], x.fi_mfrr_down_price[m]).mean()), 3))
    ov = wh.index.intersection(wp.index)
    if len(ov):
        a, b = wh.loc[ov], wp.loc[ov]
        for c in ("fi_mfrr_direction", "fi_imbalance_price", "fi_wind_fc_da", "fi_consumption_fc_da"):
            print("overlap", c, len(ov), "max abs diff", float(np.nanmax(np.abs(a[c] - b[c]))))
    per = {"aut25 (Sep-Nov 2025)": wh[(wh.index >= "2025-09-01") & (wh.index < "2025-12-01")],
           "oct25 (5 Oct-1 Nov 2025)": wh[(wh.index >= "2025-10-05") & (wh.index < "2025-11-02")],
           "win25 (Dec25-Feb26)": wh[(wh.index >= "2025-12-01") & (wh.index < "2026-03-01")],
           "spr26 (Mar-May 2026)": wh[(wh.index >= "2026-03-01")],
           "sum25 (Jun-Aug 2025)": wh[(wh.index >= "2025-06-01") & (wh.index < "2025-09-01")],
           "sum26 (Jun-Aug 2026)": wp[(wp.index >= "2026-06-01") & (wp.index < "2026-09-01")],
           "sep26 (Sep 2026)": wp[(wp.index >= "2026-09-01") & (wp.index < "2026-10-05")]}
    rows = []
    for k, w in per.items():
        x = w.dropna(subset=["fi_mfrr_direction"])
        dd = x.fi_mfrr_direction
        rows.append(dict(period=k, n=len(x), up=(dd == 1).mean(), down=(dd == -1).mean(), none=(dd == 0).mean(),
                         net_mean=x.net.mean(), wind_mean=x.fi_wind_fc_da.mean(),
                         persist4=(dd.to_numpy()[5:] == dd.to_numpy()[:-5]).mean()))
    print(pd.DataFrame(rows).round(3).to_string(index=False))
    # up share by hour block
    hb = lambda w: pd.cut(w.hour, [-1, 5, 9, 15, 19, 23], labels=["00-05", "06-09", "10-15", "16-19", "20-23"])
    T = pd.DataFrame({k: w.dropna(subset=["fi_mfrr_direction"]).assign(hb=hb).groupby("hb", observed=True).fi_mfrr_direction.apply(lambda s: (s == 1).mean())
                      for k, w in per.items()})
    print("\nP(up) by local hour block"); print(T.round(3).to_string())
    # up share by net-position bin (common bins)
    bins = [-1e9, 4000, 6000, 8000, 10000, 1e9]
    T2 = pd.DataFrame({k: w.dropna(subset=["fi_mfrr_direction", "net"]).assign(nb=lambda z: pd.cut(z.net, bins)).groupby("nb", observed=True).fi_mfrr_direction.apply(lambda s: (s == 1).mean())
                       for k, w in per.items()})
    N2 = pd.DataFrame({k: w.dropna(subset=["fi_mfrr_direction", "net"]).assign(nb=lambda z: pd.cut(z.net, bins)).groupby("nb", observed=True).size() / w.net.notna().sum()
                       for k, w in per.items()})
    print("\nP(up) by DA net position (MW)"); print(T2.round(3).to_string())
    print("\nshare of quarters per net bin"); print(N2.round(3).to_string())
    # within-bin difference: logistic fit of up ~ net (per 1000 MW) per period
    from sklearn.linear_model import LogisticRegression
    print("\nlogit(up) ~ a + b*net/1000 + c*wind/1000")
    for k, w in per.items():
        x = w.dropna(subset=["fi_mfrr_direction", "net", "fi_wind_fc_da"]); x = x[x.fi_mfrr_direction != 0]
        m = LogisticRegression().fit(np.c_[x.net / 1000, x.fi_wind_fc_da / 1000], (x.fi_mfrr_direction == 1).astype(int))
        print(f"  {k:28s} a={m.intercept_[0]:+.2f} b_net={m.coef_[0][0]:+.3f} c_wind={m.coef_[0][1]:+.3f}")


def blend_post(w: float = 0.6):
    """Blend the classifier's P(up | not none) with the history model in logit space.
    The history model is fitted only on fg_hist (< 2026-06-01) and its features go through the
    leak-checked hist_full_features; post functions only see origin/step/delivery."""
    import numpy as np
    from experiments.lab.data import Data, build_base, leakcheck
    from experiments.lab.run import public
    leakcheck(H.hist_full_features, public(build_base()), Data(), n=6)

    def post(pred, va, X_va):
        l = H.hist_full_features(va[["origin", "step", "delivery"]], Data())["hfull_lpup"].to_numpy()
        pu, pdn, pn = pred["p_up"], pred["p_down"], pred["p_none"]
        q = np.clip(pu / np.maximum(pu + pdn, 1e-9), 1e-4, 1 - 1e-4)
        z = w * l + (1 - w) * np.log(q / (1 - q))
        p = 1 / (1 + np.exp(-z))
        out = dict(pred)
        out["p_up"], out["p_down"] = (1 - pn) * p, (1 - pn) * (1 - p)
        return out
    return post


if __name__ == "__main__":
    name = sys.argv[1]
    if name == "drift":
        drift(); sys.exit()
    model = sys.argv[2] if len(sys.argv) > 2 else "direct"
    extra = [e for e in sys.argv[3:] if not e.startswith("blend")]   # e.g. combos: runs hfull
    bl = [float(e[5:]) for e in sys.argv[3:] if e.startswith("blend")]
    fns, notes = EXPS[name]
    for e in extra:
        for fn in EXPS[e][0]:
            if fn not in fns:
                fns = fns + [fn]
        notes += " + " + e
    post = blend_post(bl[0]) if bl else None
    if bl:
        notes += f" | post: logit blend {bl[0]} x hfull history model + {1 - bl[0]:.1f} x classifier for P(up)"
    tag = f"{name}{'+' + '+'.join(extra) if extra else ''}{f' blend{bl[0]}' if bl else ''} {model}"
    run_experiment(tag, agent="history", feature_fns=fns, model=model, target="gap", calibrate=True, notes=notes, post=post)
