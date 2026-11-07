"""Fingrid real-time batch 2 (electric boilers, CHP, real-time border flows), usable 3 quarters before step 1.
Teammate Frank found this batch improved his spike and direction scores."""
from __future__ import annotations

import pandas as pd

from ..data import U, Data, asof, per_origin

SERIES = [("fg371_boilers_rt", "boil"), ("fg201_chp_dh_rt", "chpdh"), ("fg202_chp_ind_rt", "chpind"),
          ("fg87_flow_se1_rt", "fse1"), ("fg89_flow_se3_rt", "fse3"), ("fg180_flow_ee_rt", "fee"),
          ("fg187_flow_no_rt", "fno")]


def rt2_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    out = pd.DataFrame(index=pd.DatetimeIndex(U(o)))
    for sid, short in SERIES:
        a = asof(data.series("fg_rt2", sid), o, lags=(0, 1, 2, 3, 4, 8))
        out[f"{short}_0"] = a["lag0"].to_numpy()
        out[f"{short}_m4"] = a[["lag0", "lag1", "lag2", "lag3"]].mean(axis=1).to_numpy()
        out[f"{short}_d4"] = (a["lag0"] - a["lag4"]).to_numpy()
        out[f"{short}_d8"] = (a["lag0"] - a["lag8"]).to_numpy()
    out["fsum_0"] = out[["fse1_0", "fse3_0", "fee_0", "fno_0"]].sum(axis=1, min_count=1)
    out["fsum_d4"] = out[["fse1_d4", "fse3_d4", "fee_d4", "fno_d4"]].sum(axis=1, min_count=1)
    out["chp_0"] = out[["chpdh_0", "chpind_0"]].sum(axis=1, min_count=1)
    return per_origin(base, out)
