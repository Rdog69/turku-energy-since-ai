"""Market-regime flags, so a model trained on Mar 2025 - Oct 2026 can tell the eras apart (history mode).
Calendar facts only (known in advance), so leak-free:
  * da15     : 15-minute day-ahead products (from 1 Oct 2025; before, spot was hourly)
  * newrule  : 1 Jun 2026 imbalance-price rule (history targets are already recomputed with it; flag kept
               because bidding behaviour may have changed with it)
(no time-trend feature on purpose: it would let the trees memorise periods)
"""
from __future__ import annotations

import pandas as pd

from ..data import Data


def regime_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    d = base["delivery"]
    return pd.DataFrame({"da15": (d >= pd.Timestamp("2025-09-30T21:00Z")).astype(float),
                         "newrule": (d >= pd.Timestamp("2026-05-31T21:00Z")).astype(float)},
                        index=base.index)


# ----------------------------------------------------------------------------- realised-volatility regime
WINDOWS = {"3d": 288, "7d": 672, "28d": 2688}     # quarters


def _grid_series(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """value and fu on a regular 15-min grid (missing quarters stay NaN / NaT)."""
    from ..data import U
    s = df.dropna(subset=["value"]).drop_duplicates("ts").set_index("ts").sort_index()
    grid = pd.date_range(s.index.min(), s.index.max(), freq="15min")
    return s["value"].reindex(grid), U(s["fu"].reindex(grid))


def _rolled(val: pd.Series, fu: pd.Series, n: int, how) -> pd.DataFrame:
    """Rolling statistic over the last n quarters, stamped at each quarter with that quarter's own fu.
    fu is monotone in ts for these series (fixed publication delay), so every quarter inside the window is
    usable whenever the newest one is; leakcheck verifies it."""
    r = how(val.rolling(n, min_periods=n // 2))
    out = pd.DataFrame({"ts": val.index, "value": r.to_numpy(), "fu": fu.to_numpy()})
    return out.dropna(subset=["fu"])


def vol_regime_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """How calm or wild the balancing market has been over the last 3 / 7 / 28 days, known at the origin:
    mean |gap|, gap std, high/low spike shares, up-regulation share, plus the 3-day/28-day |gap| ratio.
    Motivation: in a calm month (Oct 2026) the models' p10-p90 bands over-cover (~92 % vs 80 %); with 19 months of
    calm and wild periods in training, these let the trees narrow or widen the bands by regime."""
    import numpy as np
    from ..data import U, asof, per_origin
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    imb = data.series("pkg", "fi_imbalance_price")
    spot = data.series("pkg", "fi_spot_price").drop_duplicates("ts").set_index("ts")["value"]
    v_imb, fu_imb = _grid_series(imb)
    gap = v_imb - spot.reindex(v_imb.index).to_numpy()
    v_dir, fu_dir = _grid_series(data.series("pkg", "fi_mfrr_direction"))
    up = (v_dir == 1).astype(float).where(v_dir.notna())
    stats = {
        "absgap": (gap.abs(), fu_imb, lambda r: r.mean()),
        "gapsd": (gap, fu_imb, lambda r: r.std()),
        "spkhi": ((gap > 50).astype(float).where(gap.notna()), fu_imb, lambda r: r.mean()),
        "spklo": ((gap < -50).astype(float).where(gap.notna()), fu_imb, lambda r: r.mean()),
        "upsh": (up, fu_dir, lambda r: r.mean()),
    }
    rs = pd.DataFrame(index=U(o))
    for name, (val, fu, how) in stats.items():
        for wn, n in WINDOWS.items():
            rs[f"vr_{name}_{wn}"] = asof(_rolled(val, fu, n, how), o, lags=(0,))["lag0"].to_numpy()
    with np.errstate(all="ignore"):
        rs["vr_absgap_ratio"] = rs["vr_absgap_3d"] / rs["vr_absgap_28d"]
    return per_origin(base, rs)
