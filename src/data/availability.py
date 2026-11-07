"""The data availability rule, in one place.

At forecast origin t, a row may be used only if first_usable_origin_utc <= t
(README section 4). Breaking this rule scores 0.

Two implementations:

* `available_at` / `wide_at`: the slow, obviously-correct reference (filter, then pivot),
  equivalent to `rows_available_at()` in the organisers' baseline notebook.
* `SeriesIndex`: fast vectorised lookups for building features over thousands of origins.
  `tests/test_availability.py` checks it against the reference.

Everything that reads data for a forecast must go through one of these.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _utc(ts) -> pd.Timestamp:
    ts = pd.Timestamp(ts)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def available_at(long: pd.DataFrame, origin) -> pd.DataFrame:
    """Long-format rows usable at the origin (reference implementation)."""
    return long.loc[long["first_usable_origin_utc"] <= _utc(origin)]


def wide_at(long: pd.DataFrame, origin) -> pd.DataFrame:
    """Usable rows as a wide table: one row per timestamp_utc, one column per series."""
    usable = available_at(long, origin)
    return usable.pivot(index="timestamp_utc", columns="series_id", values="value").sort_index()


def to_ns(values) -> np.ndarray:
    """Timestamps (Series, Index, scalar) or int64 nanoseconds -> int64 UTC nanoseconds.

    Always converts the unit explicitly: pandas 3 stores parsed timestamps in microseconds,
    so `.asi8` alone would silently mix units.
    """
    if isinstance(values, np.ndarray) and values.dtype == np.int64:
        return values
    if isinstance(values, pd.Timestamp):
        return np.array([_utc(values).as_unit("ns").value], dtype=np.int64)
    idx = pd.DatetimeIndex(values)
    idx = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    return idx.as_unit("ns").asi8


_ns = to_ns


class SeriesIndex:
    """Fast, availability-aware lookups for one series.

    value_at(times, origins): value at each timestamp, or NaN if that row is not usable
        at the matching origin (or doesn't exist).
    latest(origins): for each origin, the newest timestamp_utc whose row is usable, plus its
        value. Correct even if publication delays are not monotonic in time.
    """

    def __init__(self, rows: pd.DataFrame):
        rows = rows.sort_values("timestamp_utc")
        self.ts = _ns(rows["timestamp_utc"])
        if len(self.ts) > 1 and np.any(np.diff(self.ts) == 0):
            # Two rows for one timestamp would make "the value at ts" (and its first_usable time)
            # ambiguous, so refuse instead of silently picking one.
            raise ValueError("duplicate timestamps in series")
        self.fu = _ns(rows["first_usable_origin_utc"])
        self.val = rows["value"].to_numpy(dtype=float)
        # For `latest`: rows sorted by first-usable time, with a running max of timestamp.
        order = np.argsort(self.fu, kind="stable")
        self._fu_sorted = self.fu[order]
        self._ts_cummax = np.maximum.accumulate(self.ts[order])
        # fu non-decreasing in ts means "everything older than the newest usable row is usable
        # too", which makes trailing windows (rolling means) safe.
        self.monotonic = bool(np.all(np.diff(self.fu) >= 0))

    def value_at(self, times, origins) -> np.ndarray:
        t = _ns(times)
        o = np.broadcast_to(_ns(origins), t.shape)
        pos = np.searchsorted(self.ts, t)
        pos_c = np.clip(pos, 0, len(self.ts) - 1)
        hit = (pos < len(self.ts)) & (self.ts[pos_c] == t)
        ok = hit & (self.fu[pos_c] <= o)
        out = np.full(t.shape, np.nan)
        out[ok] = self.val[pos_c[ok]]
        return out

    def first_usable_at(self, times) -> np.ndarray:
        """first_usable_origin_utc (ns) of the row at each timestamp; int64 max if no row."""
        t = _ns(times)
        pos = np.clip(np.searchsorted(self.ts, t), 0, len(self.ts) - 1)
        return np.where(self.ts[pos] == t, self.fu[pos], np.iinfo(np.int64).max)

    def latest(self, origins) -> tuple[np.ndarray, np.ndarray]:
        """(latest usable timestamp in ns or -1, its value or NaN) for each origin."""
        o = _ns(origins)
        k = np.searchsorted(self._fu_sorted, o, side="right") - 1   # last row usable at each origin
        usable = k >= 0                                              # k < 0: nothing usable yet
        latest_ts = np.full(o.shape, -1, dtype=np.int64)
        latest_ts[usable] = self._ts_cummax[k[usable]]
        vals = np.full(o.shape, np.nan)
        pos = np.searchsorted(self.ts, latest_ts)
        pos_c = np.clip(pos, 0, len(self.ts) - 1)
        exact = usable & (pos < len(self.ts)) & (self.ts[pos_c] == latest_ts)
        vals[exact] = self.val[pos_c[exact]]
        return latest_ts, vals


def build_index(long: pd.DataFrame) -> dict[str, SeriesIndex]:
    return {sid: SeriesIndex(rows) for sid, rows in long.groupby("series_id", sort=False)}
