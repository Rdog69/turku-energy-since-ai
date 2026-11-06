"""Elering (Estonian TSO) open data: Estonian system balance, production, consumption (no key).

`system_balance` is Estonia's real-time imbalance, a neighbour signal fresher than ENTSO-E's
~2 h delay. Since Feb 2025 Estonia is synchronised with Continental Europe, so its frequency is
NOT the Nordic frequency; only balance and flows matter here.
Assumed delay: 60 min after the timestamp (☐ unverified; the dashboard updates near real time).
    first_usable_origin_utc = ceil_hour(timestamp + 60 min)

Usage:  python -m src.data.external.elering
"""
from __future__ import annotations

import pandas as pd

from .common import PERIODS, Http, ceil_hour, json_loads, write

API = "https://dashboard.elering.ee/api/system"
http = Http("elering", min_interval_s=0.5)
DELAY = pd.Timedelta(minutes=60)


def fetch(period: str) -> pd.DataFrame:
    start, end = (pd.Timestamp(x, tz="UTC") for x in PERIODS[period])
    frames = []
    for m0 in pd.date_range(start, end, freq="7D"):
        m1 = min(m0 + pd.Timedelta(days=7), end)
        body = http.get(API, {"start": m0.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "end": m1.strftime("%Y-%m-%dT%H:%M:%S.000Z")},
                        cache_key=f"system_{m0:%Y%m%d}.json")
        d = json_loads(body)
        if d.get("data"):
            frames.append(pd.DataFrame(d["data"]))
    df = pd.concat(frames, ignore_index=True)
    df["timestamp_utc"] = pd.to_datetime(df.pop("timestamp"), unit="s", utc=True)
    df = df.dropna(subset=["system_balance", "production", "consumption"], how="all").drop_duplicates("timestamp_utc")
    df["first_usable_origin_utc"] = ceil_hour(df.timestamp_utc + DELAY)
    return df


def main() -> None:
    for period in PERIODS:
        write(fetch(period), "elering", f"system_{period}")


if __name__ == "__main__":
    main()
