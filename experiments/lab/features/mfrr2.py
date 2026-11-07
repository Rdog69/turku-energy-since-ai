"""Balancing-market internals from Fingrid (fetched with the package's own 60-min rule for mFRR data),
day-ahead reserve prices / transmission capacities, and the real-time calculated imbalance (ACE)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import U, Data, asof, at_delivery, per_origin

LAGGED = [("fg377_mfrr_need", "need"), ("fg373_mfrr_up_bids", "upbid"), ("fg374_mfrr_down_bids", "dnbid"),
          ("fg349_afrr_up_vol", "afup"), ("fg350_afrr_down_vol", "afdn"), ("fg381_mfrr_net_export", "mfx"),
          ("fg385_mfrr_sa_up", "saup"), ("fg386_mfrr_sa_down", "sadn"), ("fg390_mfrr_da_up", "daup"),
          ("fg389_mfrr_da_down", "dadn")]


def _o(base):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    return o, pd.DatetimeIndex(U(o))


def mfrr2_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Recent balancing-market state (newest usable quarter = 5 before step 1, like the package's mFRR data)."""
    o, oi = _o(base)
    out = pd.DataFrame(index=oi)
    for sid, k in LAGGED:
        a = asof(data.series("fg_mfrr2", sid), o, lags=(0, 1, 2, 3, 4, 5, 6, 7))
        out[f"{k}_0"] = a["lag0"].to_numpy()
        out[f"{k}_m4"] = a[[f"lag{i}" for i in range(4)]].mean(axis=1).to_numpy()
        out[f"{k}_m8"] = a[[f"lag{i}" for i in range(8)]].mean(axis=1).to_numpy()
    act_up = asof(data.series("pkg", "fi_mfrr_up_activated"), o, lags=(0, 1, 2, 3))
    act_dn = asof(data.series("pkg", "fi_mfrr_down_activated"), o, lags=(0, 1, 2, 3))
    with np.errstate(all="ignore"):
        out["up_util_m4"] = act_up[[f"lag{i}" for i in range(4)]].mean(axis=1).to_numpy() / np.maximum(out["upbid_m4"], 1)
        out["dn_util_m4"] = act_dn[[f"lag{i}" for i in range(4)]].abs().mean(axis=1).to_numpy() / np.maximum(out["dnbid_m4"].abs(), 1)
        tot = out[["saup_m4", "sadn_m4", "daup_m4", "dadn_m4"]].abs().sum(axis=1)
        out["direct_share_m4"] = (out["daup_m4"].abs() + out["dadn_m4"].abs()) / np.maximum(tot, 1)
    return per_origin(base, out)


def dafcr_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Day-ahead reserve prices (FCR-N/FCR-D, published D-1 22:45) and DA transmission capacity at delivery."""
    f = pd.DataFrame(index=base.index)
    for sid, k in [("fg317_fcrn_price", "fcrn"), ("fg318_fcrd_up_price", "fcrdup"), ("fg283_fcrd_down_price", "fcrddn"),
                   ("fg26_dacap_fi_se1", "cap_fise1"), ("fg27_dacap_fi_se3", "cap_fise3"),
                   ("fg24_dacap_se1_fi", "cap_se1fi"), ("fg25_dacap_se3_fi", "cap_se3fi")]:
        f[k] = at_delivery(data.series("fg_mfrr2", sid), base)
    f["cap_import"] = f[["cap_se1fi", "cap_se3fi"]].sum(axis=1, min_count=1)
    f["cap_export"] = f[["cap_fise1", "cap_fise3"]].sum(axis=1, min_count=1)
    return f


def ace_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Real-time calculated imbalance (ACE open loop, Fingrid 397), 30-min rule like our other real-time data.
    Kept separate: pending the organisers' answer on near-real-time balancing series."""
    o, oi = _o(base)
    a = asof(data.series("fg_mfrr2", "fg397_calc_imbalance_rt"), o, lags=(0, 1, 2, 3, 4, 8))
    out = pd.DataFrame(index=oi)
    out["ace_0"] = a["lag0"].to_numpy()
    out["ace_m4"] = a[["lag0", "lag1", "lag2", "lag3"]].mean(axis=1).to_numpy()
    out["ace_d4"] = (a["lag0"] - a["lag4"]).to_numpy()
    out["ace_d8"] = (a["lag0"] - a["lag8"]).to_numpy()
    return per_origin(base, out)
