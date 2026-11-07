"""Direction- and spike-history features for the probability metrics (agent: probs).

All per-origin state comes from `asof` (newest usable quarter = 5 quarters before the origin);
per-delivery seasonal lags come from `at_delivery` (only if already published at the origin).
Nothing is fitted here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import U, Data, asof, at_delivery, per_origin

S = lambda d, sid: d.series("pkg", sid)
N = 96  # 24 h of quarter-hour history


def dir_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    oi = pd.DatetimeIndex(U(o))
    rs = pd.DataFrame(index=oi)
    # ---- direction history (newest first)
    a = asof(S(data, "fi_mfrr_direction"), o, lags=tuple(range(N)))
    D = a[[f"lag{i}" for i in range(N)]].to_numpy(float)
    same = D == D[:, :1]
    run = np.where(same.all(axis=1), N, np.argmin(same, axis=1)).astype(float)
    run[np.isnan(D[:, 0])] = np.nan
    rs["dir_run"] = run                                   # quarters since the last direction change
    rs["dir_run_signed"] = run * D[:, 0]
    # length of the previous run (how persistent the regime before the switch was)
    prev = np.full(len(D), np.nan)
    for i in range(len(D)):
        r = int(run[i]) if not np.isnan(run[i]) else N
        if r < N:
            seg = D[i, r:]
            sm = seg == seg[0]
            prev[i] = N - r if sm.all() else np.argmin(sm)
    rs["dir_prev_run"] = prev
    with np.errstate(all="ignore"):
        for n in (4, 16, 32, 96):
            v = D[:, :n]
            rs[f"dir_up{n}"] = np.nanmean(np.where(np.isnan(v), np.nan, (v == 1).astype(float)), axis=1)
        ch = (D[:, 1:17] != D[:, :16]) & ~np.isnan(D[:, 1:17]) & ~np.isnan(D[:, :16])
        rs["dir_switch16"] = ch.sum(axis=1).astype(float)
    # ---- spike history from imbalance price - spot of the same (past) quarter
    imb = asof(S(data, "fi_imbalance_price"), o, lags=tuple(range(N)))
    last_ts = oi - pd.to_timedelta(imb["age_q"].to_numpy() * 15, unit="min")
    spot_at = S(data, "fi_spot_price").drop_duplicates("ts").set_index("ts")["value"]
    sp = np.stack([spot_at.reindex(last_ts - i * pd.Timedelta(minutes=15)).to_numpy() for i in range(N)], axis=1)
    G = imb[[f"lag{i}" for i in range(N)]].to_numpy(float) - sp
    with np.errstate(all="ignore"):
        for n in (16, 96):
            v = G[:, :n]
            nan = np.isnan(v)
            rs[f"hi_share{n}"] = np.nanmean(np.where(nan, np.nan, (v > 50).astype(float)), axis=1)
            rs[f"lo_share{n}"] = np.nanmean(np.where(nan, np.nan, (v < -50).astype(float)), axis=1)
        rs["gap_max16"] = np.nanmax(G[:, :16], axis=1)
        rs["gap_min16"] = np.nanmin(G[:, :16], axis=1)
    f = per_origin(base, rs)
    # ---- same quarter on previous days (published long ago)
    dser, iser, sser = S(data, "fi_mfrr_direction"), S(data, "fi_imbalance_price"), S(data, "fi_spot_price")
    dl = np.stack([at_delivery(dser, base, -96 * k).to_numpy() for k in range(1, 8)], axis=1)
    gl = np.stack([(at_delivery(iser, base, -96 * k) - at_delivery(sser, base, -96 * k)).to_numpy() for k in range(1, 8)], axis=1)
    with np.errstate(all="ignore"):
        f["dir_d1"] = dl[:, 0]
        f["dir_up_7d_sameq"] = np.nanmean(np.where(np.isnan(dl), np.nan, (dl == 1).astype(float)), axis=1)
        f["gap_d1"] = gl[:, 0]
        f["hi_7d_sameq"] = np.nanmean(np.where(np.isnan(gl), np.nan, (gl > 50).astype(float)), axis=1)
        f["lo_7d_sameq"] = np.nanmean(np.where(np.isnan(gl), np.nan, (gl < -50).astype(float)), axis=1)
    return f
