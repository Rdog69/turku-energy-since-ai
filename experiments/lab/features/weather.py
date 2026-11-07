"""Weather-model features (agent `weather`): wind-forecast revisions since the day-ahead forecast,
run-to-run spread, FMI nowcast error, Helsinki temperature and an icing proxy.

Power curve: CF = sum_i w_i * sigmoid((v100_i - a) / b) over the 7 wind-cluster points, CF = fg75 / fg268.
Fitted ONCE (scratch script, scipy least_squares) on deliveries < CUT only, using the IFS short-lead
forecast (lead 8-20 h, i.e. what the newest usable run looks like) as input: last autumn 2025 + 25 May - 31 Jul 2026.
The parameters are hard-coded below so the feature functions never fit anything on the data they receive.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import U, Data, asof, at_delivery, nwp_latest, per_origin

CUT = pd.Timestamp("2026-07-31T21:00Z")          # every mapping below was fitted on deliveries before this
PTS = ["kristiinankaupunki", "vaasa", "kokkola", "lestijarvi", "kalajoki", "raahe_pyhajoki", "ii_simo"]
# IFS-input fit (lead 8-20 h), deliveries < CUT. ERA5-input fit was ~identical (a=7.13, b=1.39).
PC_A, PC_B = 7.003, 1.3895
PC_W = np.array([0.1509, 0.0167, 0.0108, 0.2219, 0.1316, 0.0212, 0.0955])
# FMI station -> nearest NWP point (10 m wind)
FMI_MAP = {"Pori": "kristiinankaupunki", "Vaasa": "vaasa", "Kokkola": "kokkola", "Kalajoki": "kalajoki",
           "Raahe": "raahe_pyhajoki", "Oulunsalo": "raahe_pyhajoki", "Kemi": "ii_simo"}
H = pd.Timedelta("1h")
S = lambda d, src, sid: d.series(src, sid)


def _sig(v):
    return 1.0 / (1.0 + np.exp(-(v - PC_A) / PC_B))


def cf_nwp(nwp: pd.DataFrame, b: pd.DataFrame, nth: int = 0) -> pd.Series:
    """Capacity factor from the power curve, newest usable run (nth=1: the one before) at b.delivery."""
    out = np.zeros(len(b))
    for p, w in zip(PTS, PC_W):
        out = out + w * _sig(nwp_latest(nwp, b, "wind_speed_100m", point=p, nth=nth).to_numpy())
    return pd.Series(out, index=b.index)


def _cap_at(data: Data, origins: pd.Series) -> np.ndarray:
    a = asof(S(data, "fg_extra", "fg268_wind_capacity"), origins, lags=(0,))
    c = a["lag0"].to_numpy()
    return np.where(np.isnan(c), 9400.0, c)


def _uo(base):
    return base["origin"].drop_duplicates().sort_values().reset_index(drop=True)


def _syn(times: pd.DatetimeIndex) -> pd.DataFrame:
    """Synthetic base: one row per hour t with origin = delivery = t."""
    t = U(pd.Series(times))
    return pd.DataFrame({"origin": t, "delivery": t, "step": 1})


def _da_origin(data: Data, base: pd.DataFrame) -> pd.DataFrame:
    """base with origin replaced by the publication time (fu) of fi_wind_fc_da at the delivery quarter."""
    s = S(data, "pkg", "fi_wind_fc_da")
    s = s.assign(value=s["fu"].astype("int64").astype(float))
    fu_ns = at_delivery(s, base)
    o = pd.to_datetime(fu_ns, utc=True).dt.as_unit("ns")
    o = o.where(o.notna(), base["origin"])
    return base.assign(origin=o)


# ----------------------------------------------------------------------------- 1-2. wind revision
def wind_rev_features(base: pd.DataFrame, data: Data, model: str = "ifs") -> pd.DataFrame:
    nwp = data[model]
    pre = model
    o = _uo(base)
    cap_o = pd.Series(_cap_at(data, o), index=U(o))
    cap = cap_o.reindex(U(base["origin"])).to_numpy()
    fc = at_delivery(S(data, "pkg", "fi_wind_fc_da"), base).to_numpy()
    cf0 = cf_nwp(nwp, base, 0).to_numpy()
    cf1 = cf_nwp(nwp, base, 1).to_numpy()
    cfd = cf_nwp(nwp, _da_origin(data, base), 0).to_numpy()
    f = pd.DataFrame(index=base.index)
    f[f"{pre}_mw"] = cf0 * cap
    f[f"{pre}_rev"] = cf0 * cap - fc
    f[f"{pre}_runchg"] = (cf0 - cf1) * cap
    f[f"{pre}_rev_da"] = (cf0 - cfd) * cap
    # trailing 7-day mean of (newest-run MW - fc_da) at hourly t <= origin: removes the seasonal
    # offset between our curve and Fingrid's (summer +, October -)
    t0 = o.min().floor("h") - pd.Timedelta(days=7)
    hrs = pd.date_range(t0, o.max(), freq="h")
    sb = _syn(hrs)
    s_mw = cf_nwp(nwp, sb, 0).to_numpy() * _cap_at(data, sb["origin"])
    s_fc = at_delivery(S(data, "pkg", "fi_wind_fc_da"), sb).to_numpy()
    D = pd.Series(s_mw - s_fc, index=U(hrs))
    Dm = D.rolling("7D", min_periods=48).mean()
    f[f"{pre}_rev_dc"] = f[f"{pre}_rev"].to_numpy() - Dm.reindex(U(base["origin"])).to_numpy()
    return f


def ifs_rev(base, data):
    return wind_rev_features(base, data, "ifs")


def icon_rev(base, data):
    return wind_rev_features(base, data, "icon")


# ----------------------------------------------------------------------------- measured wind now vs forecasts
def _wind_now(base: pd.DataFrame, data: Data, with_ifs: bool) -> pd.DataFrame:
    o = _uo(base)
    w = S(data, "fg_rt", "fg181_wind_rt")
    a = asof(w, o, lags=(0, 1, 2, 3))
    a.index = U(o)
    oi = pd.DatetimeIndex(U(o))
    t_last = oi - pd.to_timedelta(a["age_q"].to_numpy() * 15, unit="min")
    nb = pd.DataFrame({"origin": oi, "delivery": t_last, "step": 1})
    fcs = S(data, "pkg", "fi_wind_fc_da")
    fc_now = at_delivery(fcs, nb).to_numpy()
    fc_prev = np.nanmean(np.stack([at_delivery(fcs, nb.assign(delivery=nb.delivery - k * pd.Timedelta(minutes=15))).to_numpy()
                                   for k in range(4)], axis=1), axis=1)
    rs = pd.DataFrame(index=oi)
    with np.errstate(all="ignore"):
        m4 = np.nanmean(a[["lag0", "lag1", "lag2", "lag3"]].to_numpy(), axis=1)
    if not with_ifs:
        rs["wind_rt"] = a["lag0"].to_numpy()
        rs["wind_err_now"] = a["lag0"].to_numpy() - fc_now
        rs["wind_err_now4"] = m4 - fc_prev
        rs["wind_rt_d4"] = a["lag0"].to_numpy() - a["lag3"].to_numpy()
        return per_origin(base, rs)
    cap = _cap_at(data, o)
    s_now = cf_nwp(data["ifs"], nb, 0).to_numpy() * cap
    rs["ifs_err_now"] = a["lag0"].to_numpy() - s_now
    f = per_origin(base, rs)
    # IFS forecast at delivery corrected by the current IFS error (persistence of the model error)
    fc_del = at_delivery(fcs, base).to_numpy()
    ifs_mw = cf_nwp(data["ifs"], base, 0).to_numpy() * pd.Series(cap, index=oi).reindex(U(base["origin"])).to_numpy()
    f["ifs_corr_rev"] = ifs_mw + f["ifs_err_now"].to_numpy() - fc_del
    return f


def wind_err_features(base, data):
    """fg181 real-time wind vs fi_wind_fc_da now (no NWP)."""
    return _wind_now(base, data, with_ifs=False)


def ifs_now_features(base, data):
    """fg181 real-time wind vs the newest IFS run now, and the IFS forecast corrected by that error."""
    return _wind_now(base, data, with_ifs=True)


# ----------------------------------------------------------------------------- 3. FMI nowcast
def fmi_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Observed 10-min wind at coastal stations (last usable hour) vs the newest IFS run's 10 m wind."""
    o = _uo(base)
    # hourly grid of origins incl. 3 days before the first one (for the trailing bias), independent of base
    oi = pd.DatetimeIndex(U(pd.Series(pd.date_range(o.min().floor("h") - pd.Timedelta(days=3), o.max(), freq="h"))))
    fmi = data["fmi"]
    fmi = fmi[fmi.station.isin(list(FMI_MAP))]
    ws = fmi.pivot_table(index="time_utc", columns="station", values="ws_10min")
    fu_t = fmi.groupby("time_utc")["fu"].max().sort_index()
    by_fu = pd.DataFrame({"fu": U(pd.Series(fu_t.to_numpy())).to_numpy(), "t": U(pd.Series(fu_t.index)).to_numpy()})
    by_fu["fu"], by_fu["t"] = U(by_fu["fu"]), U(by_fu["t"])
    by_fu = by_fu.sort_values("fu")
    by_fu["tmax"] = by_fu["t"].cummax()
    m = pd.merge_asof(pd.DataFrame({"origin": oi}), by_fu[["fu", "tmax"]], left_on="origin", right_on="fu",
                      direction="backward")
    t_new = pd.DatetimeIndex(U(m["tmax"]))
    ws.index = U(ws.index)
    fu_t.index = U(fu_t.index)
    nwp = data["ifs"]
    errs, obs_l, trend = [], [], []
    for st, pt in FMI_MAP.items():
        if st not in ws:
            continue
        vals = []
        for k in range(9):           # 90 min of 10-min obs ending at the newest usable time
            t = t_new - k * pd.Timedelta(minutes=10)
            v = ws[st].reindex(t).to_numpy()
            fu = U(fu_t.reindex(t).to_numpy())
            ok = pd.notna(fu) & (fu <= oi)
            vals.append(np.where(ok, v, np.nan))
        V = np.stack(vals, axis=1)
        with np.errstate(all="ignore"):
            obs = np.nanmean(V[:, :6], axis=1)
            tr = np.nanmean(V[:, :3], axis=1) - np.nanmean(V[:, 6:9], axis=1)
        nb = pd.DataFrame({"origin": oi, "delivery": t_new - pd.Timedelta(minutes=25), "step": 1})
        pred = nwp_latest(nwp, nb, "wind_speed_10m", point=pt).to_numpy()
        errs.append(obs - pred); obs_l.append(obs); trend.append(tr)
    with np.errstate(all="ignore"):
        rs = pd.DataFrame(index=oi)
        rs["fmi_ws"] = np.nanmean(np.stack(obs_l, 1), axis=1)
        rs["fmi_err"] = np.nanmean(np.stack(errs, 1), axis=1)
        rs["fmi_trend"] = np.nanmean(np.stack(trend, 1), axis=1)
    # station exposure bias: subtract the trailing 3-day mean of the error (only past origins)
    e = rs["fmi_err"]
    rs["fmi_err_dc"] = e - e.rolling("3D", min_periods=12).mean()
    return per_origin(base, rs.reindex(pd.DatetimeIndex(U(o))))


# ----------------------------------------------------------------------------- 4. temperature and icing
def temp_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    nwp = data["ifs"]
    f = pd.DataFrame(index=base.index)
    t = nwp_latest(nwp, base, "temperature_2m", point="helsinki").to_numpy()
    tda = nwp_latest(nwp, _da_origin(data, base), "temperature_2m", point="helsinki").to_numpy()
    f["t_hel"] = t
    f["t_hel_rev"] = t - tda
    ice = np.zeros(len(base))
    for p in PTS:
        tp = nwp_latest(nwp, base, "temperature_2m", point=p).to_numpy()
        rh = nwp_latest(nwp, base, "relative_humidity_2m", point=p).to_numpy()
        ice += ((tp >= -6) & (tp <= 2) & (rh >= 90)).astype(float)
    f["icing_frac"] = ice / len(PTS)
    return f


# ----------------------------------------------------------------------------- combined expected DA wind error
# OLS of (fg75 - fi_wind_fc_da) at delivery on [wind_err_now, ifs_rev_dc, ifs_corr_rev, ifs_runchg] per step band,
# fitted on deliveries 2 Jun - 31 Jul 2026 (< CUT) only; intercept dropped. OOS (fit June, test July) R2:
# 0.75 / 0.49 / 0.30 / 0.17 vs best single feature 0.71 / 0.39 / 0.24 / 0.14.
HAT_COEF = {(1, 4): [0.54, 0.099, 0.298, -0.079], (5, 12): [0.411, 0.23, 0.193, -0.092],
            (13, 24): [0.255, 0.309, 0.156, -0.151], (25, 40): [0.134, 0.35, 0.104, -0.165]}


def wind_hat_features(base, data):
    X = pd.concat([ifs_rev(base, data), wind_err_features(base, data), ifs_now_features(base, data)], axis=1)
    A = X[["wind_err_now", "ifs_rev_dc", "ifs_corr_rev", "ifs_runchg"]].to_numpy(float)
    st = base["step"].to_numpy()
    out = np.full(len(base), np.nan)
    for (lo, hi), c in HAT_COEF.items():
        m = (st >= lo) & (st <= hi)
        out[m] = np.nan_to_num(A[m]) @ np.asarray(c)
    return pd.DataFrame({"wind_err_hat": out}, index=base.index)
