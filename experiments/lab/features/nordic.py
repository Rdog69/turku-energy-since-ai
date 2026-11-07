"""Nordic/Baltic wind (Frank's 12 IFS points in SE/NO/DK/EE, his Open-Meteo runs, IFS +8 h delay).

The Nordic mFRR energy market is shared since 2025, so a wind miss in Sweden/Norway can tip Finland's direction.
Per area: wind index (generic power curve, no fit) from the newest usable run, and its revision since the run that
was newest when the Finnish day-ahead wind forecast was published (what the day-ahead market didn't know).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import Data, nwp_latest
from .weather import _da_origin, _sig

AREAS = {"se": ["se1_norrbotten", "se2_jamtland", "se2_vasternorrland", "se3_vastra_gotaland", "se3_gotland", "se4_skane"],
         "no": ["no3_fosen", "no2_rogaland", "no4_finnmark"], "dk": ["dk1_jutland", "dk2_offshore"], "ee": ["ee_west"]}


def _idx(fw, b, pts, nth=0):
    return np.nanmean(np.stack([_sig(nwp_latest(fw, b, "wind_speed_100m", point="nord_" + p, nth=nth).to_numpy())
                                for p in pts]), axis=0)


def nordic_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    fw = data["fw"]
    bda = _da_origin(data, base)
    f = pd.DataFrame(index=base.index)
    tot_now = tot_da = 0
    for a, pts in AREAS.items():
        now, da = _idx(fw, base, pts), _idx(fw, bda, pts)
        f[f"nw_{a}"] = now
        f[f"nw_{a}_rev"] = now - da
        wgt = len(pts)
        tot_now, tot_da = tot_now + wgt * now, tot_da + wgt * da
    n = sum(len(p) for p in AREAS.values())
    f["nw_all_rev"] = (tot_now - tot_da) / n
    f["nw_all_runchg"] = np.nanmean(np.stack([_idx(fw, base, p) - _idx(fw, base, p, 1) for p in AREAS.values()]), 0)
    return f


def nordic_rev(base, data):
    """Revisions only (the part with new information)."""
    f = nordic_features(base, data)
    return f[[c for c in f.columns if c.endswith("_rev") or c.endswith("runchg")]]
