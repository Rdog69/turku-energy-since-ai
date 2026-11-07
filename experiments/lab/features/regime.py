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
