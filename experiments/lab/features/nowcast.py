"""Agent 'nowcast': Fingrid real-time (fg_rt) + extra (fg_extra) features on top of package_features.

Newest fg_rt quarter is 3 quarters before step 1 (package imbalance/mFRR: 5 quarters).
All reads go through asof / asof_window / at_delivery; per-quarter forecast errors pair a real-time
lag with the day-ahead forecast of the SAME past quarter, looked up with at_delivery at the origin.

Groups (tested incrementally):
  rt_imb   - fg198 surplus/deficit (newest, lags, short means, trend) + fg186 cumulative
  rt_wind  - fg181 wind rt minus fi_wind_fc_da at the same quarters, ratio to fg268 capacity
  rt_cons  - fg193 consumption rt minus fi_consumption_fc_da; fg192 production rt minus fg242 BRP plan
  rt_misc  - fg177 frequency, fg188 nuclear drop vs 24 h max, fg194 net import, fg191 hydro ramp,
             fg176 FI-SE imbalance power (hourly constant, 5 q old)
Dropped before testing (no usable coverage in Jun-Oct 2026): fg209 (constant 1), fg243 (all 0),
fg251 (only 14-18 Oct), fg22 (absent).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import Q, U, Data, asof, asof_window, at_delivery, per_origin


def _o(base):
    return base["origin"].drop_duplicates().sort_values().reset_index(drop=True)


def _lags(data: Data, src: str, sid: str, o: pd.Series, n: int) -> pd.DataFrame:
    a = asof(data.series(src, sid), o, lags=tuple(range(n)))
    a.index = U(o)
    return a


def _ts(a: pd.DataFrame, L: int) -> pd.Series:
    """Timestamp of lag L (newest usable quarter minus L quarters)."""
    oi = pd.Series(U(a.index), index=a.index)
    return oi - pd.to_timedelta(a["age_q"].to_numpy() * 15, unit="min") - L * Q


def _at(data: Data, src: str, sid: str, a: pd.DataFrame, L: int) -> np.ndarray:
    """Value of a (day-ahead) series at the timestamp of lag L, only if usable at the origin."""
    b = pd.DataFrame({"origin": pd.Series(U(a.index)), "delivery": _ts(a, L).reset_index(drop=True)})
    b["delivery"] = U(b["delivery"])
    return at_delivery(data.series(src, sid), b).to_numpy()


def _err(data, rt_src, rt_sid, fc_src, fc_sid, o, n):
    """matrix (origins x n) of real-time minus forecast at lags 0..n-1."""
    a = _lags(data, rt_src, rt_sid, o, n)
    E = np.stack([a[f"lag{L}"].to_numpy() - _at(data, fc_src, fc_sid, a, L) for L in range(n)], axis=1)
    return a, E


def _nanmean(M):
    with np.errstate(all="ignore"):
        return np.nanmean(M, axis=1)


# ----------------------------------------------------------------------------- group 1
def rt_imb(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    o = _o(base)
    a = _lags(data, "fg_rt", "fg198_surplus_deficit_rt", o, 16)
    M = a[[f"lag{i}" for i in range(16)]].to_numpy()
    r = pd.DataFrame(index=U(o))
    for L in range(4):
        r[f"i198_{L}"] = M[:, L]
    r["i198_m4"] = _nanmean(M[:, :4])
    r["i198_m8"] = _nanmean(M[:, :8])
    r["i198_m16"] = _nanmean(M)
    r["i198_tr"] = M[:, 0] - M[:, 3]
    with np.errstate(all="ignore"):
        r["i198_absm4"] = np.nanmean(np.abs(M[:, :4]), axis=1)
        r["i198_sd8"] = np.nanstd(M[:, :8], axis=1)
    c = _lags(data, "fg_rt", "fg186_surplus_deficit_cum_rt", o, 5)
    r["i186_0"] = c["lag0"].to_numpy()
    r["i186_d4"] = (c["lag0"] - c["lag4"]).to_numpy()
    return per_origin(base, r)


# ----------------------------------------------------------------------------- group 2
def rt_wind(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    o = _o(base)
    a, E = _err(data, "fg_rt", "fg181_wind_rt", "pkg", "fi_wind_fc_da", o, 8)
    cap = asof(data.series("fg_extra", "fg268_wind_capacity"), o)["lag0"].to_numpy()
    r = pd.DataFrame(index=U(o))
    r["werr_0"] = E[:, 0]
    r["werr_m4"] = _nanmean(E[:, :4])
    r["werr_m8"] = _nanmean(E)
    r["werr_tr"] = E[:, 0] - E[:, 3]
    r["werr_rel"] = E[:, 0] / cap
    r["werr_m4_rel"] = r["werr_m4"].to_numpy() / cap
    r["wind_rt_0"] = a["lag0"].to_numpy()
    f = per_origin(base, r)
    # forecast wind at delivery corrected by the persisting recent error
    wfc = at_delivery(data.series("pkg", "fi_wind_fc_da"), base)
    f["wind_corr_del"] = wfc + f["werr_m4"]
    f["wind_rt_to_del"] = wfc - f["wind_rt_0"]
    return f


# ----------------------------------------------------------------------------- group 3
def rt_cons(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    o = _o(base)
    _, C = _err(data, "fg_rt", "fg193_consumption_rt", "pkg", "fi_consumption_fc_da", o, 4)
    _, P = _err(data, "fg_rt", "fg192_production_rt", "fg_extra", "fg242_production_plan_da", o, 4)
    r = pd.DataFrame(index=U(o))
    r["cerr_0"] = C[:, 0]
    r["cerr_m4"] = _nanmean(C)
    r["cerr_tr"] = C[:, 0] - C[:, 3]
    r["perr_0"] = P[:, 0]
    r["perr_m4"] = _nanmean(P)
    r["perr_tr"] = P[:, 0] - P[:, 3]
    r["nerr_m4"] = r["cerr_m4"] - r["perr_m4"]          # unplanned net import from cons + prod errors
    f = per_origin(base, r)
    plan = at_delivery(data.series("fg_extra", "fg242_production_plan_da"), base)
    cfc = at_delivery(data.series("pkg", "fi_consumption_fc_da"), base)
    f["plan_imp_del"] = cfc - plan                        # planned net import at the delivery quarter
    f["plan_d4"] = plan - at_delivery(data.series("fg_extra", "fg242_production_plan_da"), base, -4)
    return f


# ----------------------------------------------------------------------------- group 4
def rt_misc(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    o = _o(base)
    r = pd.DataFrame(index=U(o))
    fr = _lags(data, "fg_rt", "fg177_frequency_rt", o, 4)
    F = (fr[[f"lag{i}" for i in range(4)]].to_numpy() - 50.0) * 1000.0      # mHz
    r["f177_0"] = F[:, 0]
    r["f177_m4"] = _nanmean(F)
    nuc = data.series("fg_rt", "fg188_nuclear_rt")
    n0 = asof(nuc, o)["lag0"].to_numpy()
    r["nuc_drop"] = n0 - asof_window(nuc, o, 96, how="max").to_numpy()
    r["nuc_d4"] = n0 - asof(nuc, o, lags=(4,))["lag4"].to_numpy()
    im = _lags(data, "fg_rt", "fg194_net_import_rt", o, 5)
    r["imp_0"] = im["lag0"].to_numpy()
    r["imp_d4"] = (im["lag0"] - im["lag4"]).to_numpy()
    hy = _lags(data, "fg_rt", "fg191_hydro_rt", o, 5)
    r["hyd_d4"] = (hy["lag0"] - hy["lag4"]).to_numpy()
    x = _lags(data, "fg_extra", "fg176_imbalance_power_fi_se", o, 5)
    r["x176_0"] = x["lag0"].to_numpy()
    r["x176_d4"] = (x["lag0"] - x["lag4"]).to_numpy()
    return per_origin(base, r)
