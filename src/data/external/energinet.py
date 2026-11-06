"""Energinet Energi Data Service: Danish 1-min system data (no key, open licence with attribution).

Kept small: DK2 is in the Nordic synchronous area and the Nordic mFRR market, so its aFRR
activation and Swedish exchange are a (weak) independent view of Nordic balancing pressure.
1-min values are averaged per quarter-hour. Assumed delay 15 min after quarter end (☐ the
dataset is "right now", updated every minute):
    first_usable_origin_utc = ceil_hour(quarter_end + 15 min)

Usage:  python -m src.data.external.energinet
"""
from __future__ import annotations

import pandas as pd

from .common import PERIODS, Http, ceil_hour, json_loads, write

API = "https://api.energidataservice.dk/dataset/PowerSystemRightNow"
COLS = ["aFRR_ActivatedDK1", "aFRR_ActivatedDK2", "Exchange_DK2_SE", "Exchange_DK1_SE",
        "OnshoreWindPower", "OffshoreWindPower", "ProductionGe100MW"]
http = Http("energinet", min_interval_s=1.0)


def fetch(period: str) -> pd.DataFrame:
    start, end = (pd.Timestamp(x, tz="UTC") for x in PERIODS[period])
    frames = []
    for w0 in pd.date_range(start, end, freq="7D"):
        w1 = min(w0 + pd.Timedelta(days=7), end)
        body = http.get(API, {"start": w0.strftime("%Y-%m-%dT%H:%M"), "end": w1.strftime("%Y-%m-%dT%H:%M"),
                              "timezone": "UTC", "limit": 20000, "columns": ",".join(["Minutes1UTC"] + COLS)},
                        cache_key=f"psrn_{w0:%Y%m%d}.json")
        frames.append(pd.DataFrame(json_loads(body)["records"]))
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = pd.to_datetime(df.pop("Minutes1UTC"), utc=True).dt.floor("15min")
    q = df.groupby("ts")[COLS].mean().reset_index().rename(columns={"ts": "timestamp_utc"})
    q["first_usable_origin_utc"] = ceil_hour(q.timestamp_utc + pd.Timedelta(minutes=30))  # 15 min + 15 min delay
    return q


def main() -> None:
    for period in PERIODS:
        write(fetch(period), "energinet", f"power_system_{period}")


if __name__ == "__main__":
    main()
