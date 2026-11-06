"""Reference feature set from the starter package only (the 'crowd' baseline + spike threshold features)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import U, Data, asof, asof_window, at_delivery, per_origin

S = lambda d, sid: d.series("pkg", sid)


def package_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    f = pd.DataFrame(index=base.index)
    # --- known for the delivery quarter (published day-ahead)
    spot = at_delivery(S(data, "fi_spot_price"), base)
    f["step"] = base["step"]
    f["hour"] = at_delivery(S(data, "cal_hour_local"), base)
    f["wday"] = at_delivery(S(data, "cal_weekday_local"), base)
    f["hol"] = at_delivery(S(data, "cal_is_holiday_fi"), base)
    f["spot"] = spot
    f["dspot_prev"] = spot - at_delivery(S(data, "fi_spot_price"), base, -1)
    f["dspot_next"] = at_delivery(S(data, "fi_spot_price"), base, +1) - spot
    spot_o = at_delivery(S(data, "fi_spot_price"), base.assign(delivery=base["origin"]))
    f["spot_rel_origin"] = spot - spot_o
    win = pd.DataFrame({"origin": base["origin"], "s": spot}).groupby("origin")["s"].transform("mean")
    f["spot_rel_win"] = spot - win
    wind = at_delivery(S(data, "fi_wind_fc_da"), base)
    cons = at_delivery(S(data, "fi_consumption_fc_da"), base)
    solar = at_delivery(S(data, "fi_solar_fc_da"), base)
    f["wind"], f["cons"], f["solar"] = wind, cons, solar
    f["net"] = cons - wind - solar
    f["dwind4"] = wind - at_delivery(S(data, "fi_wind_fc_da"), base, -4)
    f["dnet4"] = f["net"] - (at_delivery(S(data, "fi_consumption_fc_da"), base, -4)
                             - at_delivery(S(data, "fi_wind_fc_da"), base, -4) - at_delivery(S(data, "fi_solar_fc_da"), base, -4))
    # --- recent state (newest usable rows at the origin)
    imb = asof(S(data, "fi_imbalance_price"), o, lags=(0,))
    imb.index = U(o)
    spot_at = S(data, "fi_spot_price").drop_duplicates("ts").set_index("ts")["value"]
    oi = pd.DatetimeIndex(U(o))
    last_imb_ts = pd.Series(oi - pd.to_timedelta(imb["age_q"].to_numpy() * 15, unit="min"), index=oi)
    rs = pd.DataFrame(index=U(o))
    rs["gap_L"] = imb["lag0"] - spot_at.reindex(last_imb_ts).to_numpy()   # spot of a past quarter is known
    g = asof(S(data, "fi_imbalance_price"), o, lags=tuple(range(16)))
    g.index = U(o)
    sp_hist = np.stack([spot_at.reindex(last_imb_ts - i * pd.Timedelta(minutes=15)).to_numpy() for i in range(16)], axis=1)
    gaps = g[[f"lag{i}" for i in range(16)]].to_numpy() - sp_hist
    with np.errstate(all="ignore"):
        rs["gap_L4"] = np.nanmean(gaps[:, :4], axis=1)
        rs["gap_L16"] = np.nanmean(gaps, axis=1)
    rs["imb_age_q"] = imb["age_q"]
    for sid, name, n in [("fi_mfrr_direction", "dir_L", 1), ("fi_mfrr_direction", "dir_L8", 8),
                         ("fi_mfrr_up_activated", "upmw_L", 1), ("fi_mfrr_down_activated", "dnmw_L", 1),
                         ("fi_mfrr_up_activated", "upmw_L4", 4)]:
        rs[name] = asof_window(S(data, sid), o, n).to_numpy()
    up_last = asof(S(data, "fi_mfrr_up_price"), o)["lag0"].to_numpy()
    dn_last = asof(S(data, "fi_mfrr_down_price"), o)["lag0"].to_numpy()
    rs["up_last"], rs["dn_last"] = up_last, dn_last
    c = asof(S(data, "fi_consumption"), o)
    c.index = U(o)
    c_ts = pd.Series(oi - pd.to_timedelta(c["age_q"].to_numpy() * 15, unit="min"), index=oi)
    cfc = S(data, "fi_consumption_fc_da").drop_duplicates("ts").set_index("ts")["value"]
    rs["conserr_L"] = c["lag0"] - cfc.reindex(c_ts).to_numpy()
    rs["prodcons_L"] = asof(S(data, "fi_production"), o)["lag0"].to_numpy() - c["lag0"].to_numpy()
    for sid, name in [("fi_se1_flow", "se1flow_L"), ("fi_se3_flow", "se3flow_L"), ("fi_ee_flow", "eeflow_L")]:
        rs[name] = asof(S(data, sid), o)["lag0"].to_numpy()
    f = f.join(per_origin(base, rs))
    # --- spike threshold features (round 2: low-spike rate 0.3% -> 58% across spot quintiles)
    f["hi_dist"] = f["up_last"] - (spot + 50)
    f["lo_dist"] = (spot - 50) - f["dn_last"]
    f["up_spread"] = f["up_last"] - spot
    f["dn_spread"] = f["dn_last"] - spot
    return f
