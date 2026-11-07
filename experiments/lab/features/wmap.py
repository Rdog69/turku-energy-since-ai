"""Learned wind map (Frank's idea, our implementation): 22 points (14 IFS + 8 ICON-EU, Frank's Open-Meteo runs)
-> capacity factor, non-negative weights fitted ONCE by experiments/lab/fit_wmap.py on deliveries 1 Jun - 31 Jul 2026
(< CUT, before both lab folds) at 5 h lead. Coefficients are hard-coded: nothing is fitted on the data we receive.

Features (MW = CF x fg268 capacity at the origin):
  wm_mw      newest usable runs, combined map
  wm_rev     wm_mw - Fingrid day-ahead wind forecast at delivery (the forecast error we expect)
  wm_rev_dc  wm_rev minus its trailing 7-day mean (removes seasonal offset between map and Fingrid)
  wm_runchg  combined map: newest runs - previous runs
  wm_rev_da  combined map now - combined map at the time the day-ahead wind forecast was published
  wm_dis     ICON-only map - IFS-only map (model disagreement, MW)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import U, Data, at_delivery, nwp_latest
from .weather import S, _cap_at, _da_origin, _sig, _syn, _uo

W_ALL = {'icon_kauhava_lapua': 0.0502, 'icon_kokkola_kalajoki': 0.0442, 'icon_kristinestad': 0.0102,
         'icon_oulu_hailuoto': 0.0137, 'icon_pori': 0.0079, 'icon_raahe_pyhajoki': 0.0172, 'icon_simo_tornio': 0.0267,
         'icon_vaasa_coast': 0.0096, 'ifs_central_pyhajarvi': 0.0939, 'ifs_kainuu_kajaani': 0.0361,
         'ifs_kokkola_kalajoki': 0.0488, 'ifs_kristinestad': 0.0923, 'ifs_kurikka_teuva': 0.0078,
         'ifs_lapland_pello': 0.0242, 'ifs_loimaa_sw': 0.0295, 'ifs_raahe_pyhajoki': 0.0252, 'ifs_simo_tornio': 0.0012,
         'ifs_vaasa_coast': 0.0041, '_b': 0.0}
W_IFS = {'ifs_central_pyhajarvi': 0.1177, 'ifs_kainuu_kajaani': 0.0393, 'ifs_kauhava_lapua': 0.0175,
         'ifs_kokkola_kalajoki': 0.1056, 'ifs_kotka_hamina': 0.0033, 'ifs_kristinestad': 0.1001, 'ifs_kurikka_teuva': 0.015,
         'ifs_lapland_pello': 0.0371, 'ifs_loimaa_sw': 0.0247, 'ifs_oulu_hailuoto': 0.0175, 'ifs_pori': 0.0157,
         'ifs_raahe_pyhajoki': 0.052, 'ifs_simo_tornio': 0.0203, 'ifs_vaasa_coast': 0.0279, '_b': 0.0}
W_ICON = {'icon_kauhava_lapua': 0.1138, 'icon_kokkola_kalajoki': 0.0893, 'icon_kristinestad': 0.0447,
          'icon_oulu_hailuoto': 0.0264, 'icon_pori': 0.0453, 'icon_raahe_pyhajoki': 0.0256, 'icon_simo_tornio': 0.0563,
          'icon_vaasa_coast': 0.0281, '_b': 0.0045}


def cf_map(fw: pd.DataFrame, b: pd.DataFrame, w: dict, nth: int = 0) -> np.ndarray:
    out = np.full(len(b), w["_b"])
    for p, c in w.items():
        if p != "_b":
            out = out + c * _sig(nwp_latest(fw, b, "wind_speed_100m", point=p, nth=nth).to_numpy())
    return out


def wmap_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    fw = data["fw"]
    o = _uo(base)
    cap = pd.Series(_cap_at(data, o), index=U(o)).reindex(U(base["origin"])).to_numpy()
    fc = at_delivery(S(data, "pkg", "fi_wind_fc_da"), base).to_numpy()
    c0 = cf_map(fw, base, W_ALL)
    f = pd.DataFrame(index=base.index)
    f["wm_mw"] = c0 * cap
    f["wm_rev"] = c0 * cap - fc
    f["wm_runchg"] = (c0 - cf_map(fw, base, W_ALL, 1)) * cap
    f["wm_rev_da"] = (c0 - cf_map(fw, _da_origin(data, base), W_ALL)) * cap
    f["wm_dis"] = (cf_map(fw, base, W_ICON) - cf_map(fw, base, W_IFS)) * cap
    t0 = o.min().floor("h") - pd.Timedelta(days=7)
    hrs = pd.date_range(t0, o.max(), freq="h")
    sb = _syn(hrs)
    D = pd.Series(cf_map(fw, sb, W_ALL) * _cap_at(data, sb["origin"]) - at_delivery(S(data, "pkg", "fi_wind_fc_da"), sb).to_numpy(),
                  index=U(hrs))
    Dm = D.rolling("7D", min_periods=48).mean()
    f["wm_rev_dc"] = f["wm_rev"].to_numpy() - Dm.reindex(U(base["origin"])).to_numpy()
    # adaptive scale: trailing 7-day sum(measured fg181) / sum(map MW) over hours whose measurement is usable at
    # the origin (the summer fit saturates in autumn; correlation is fine, the level is not)
    g = S(data, "fg_rt", "fg181_wind_rt")
    g = g[(g.ts >= t0) & (g.ts <= o.max())]
    hy = g.assign(h=g.ts.dt.floor("h")).groupby("h").agg(y=("value", "mean"), fu=("fu", "max"), n=("value", "size"))
    hy = hy[hy.n == 4]
    mm = pd.Series(cf_map(fw, sb, W_ALL) * _cap_at(data, sb["origin"]), index=U(hrs))
    hy["m"] = mm.reindex(U(hy.index)).to_numpy()
    hy = hy.dropna()
    hy["fu"] = U(pd.Series(hy["fu"].to_numpy())).cummax().to_numpy()
    fu_ns = hy["fu"].to_numpy().astype("datetime64[ns]").astype(np.int64)
    h_ns = U(pd.Series(hy.index)).to_numpy().astype("datetime64[ns]").astype(np.int64)
    cy, cm = np.r_[0, np.cumsum(hy.y.to_numpy())], np.r_[0, np.cumsum(hy.m.to_numpy())]
    on = U(o).to_numpy().astype("datetime64[ns]").astype(np.int64)
    hi = np.searchsorted(fu_ns, on, "right")
    lo = np.minimum(np.searchsorted(h_ns, on - 7 * 86400 * 10**9, "left"), hi)
    with np.errstate(all="ignore"):
        k = np.where(hi - lo >= 48, (cy[hi] - cy[lo]) / (cm[hi] - cm[lo]), np.nan)
    k = pd.Series(np.clip(k, 0.5, 2.0), index=U(o)).reindex(U(base["origin"])).to_numpy()
    f["wm_k"] = k
    f["wm_rev_s"] = f["wm_mw"].to_numpy() * k - fc
    return f


def wmap_core(base, data):
    """Smaller set: just the de-biased revision, run change and model disagreement."""
    return wmap_features(base, data)[["wm_rev_dc", "wm_runchg", "wm_dis"]]


def wmap_s(base, data):
    """Scaled revision + run change + disagreement + de-biased revision."""
    return wmap_features(base, data)[["wm_rev_s", "wm_rev_dc", "wm_runchg", "wm_dis"]]
