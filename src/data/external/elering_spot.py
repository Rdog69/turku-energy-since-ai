"""Finnish day-ahead (Nord Pool) prices from Elering's open API, to extend spot back to March 2025.

The organisers' spot file starts on 1 Jun 2026. Elering republishes the day-ahead prices for EE/FI/LV/LT.
Hourly until 30 Sep 2025, 15-minute after the switch to 15-min day-ahead products (1 Oct 2025); hourly
values are repeated per quarter. Availability exactly like the package's spot: D-1 14:00 Finnish time.
☐ Licence: the prices originate from Nord Pool; used only inside the team, never redistributed.

    python -m src.data.external.elering_spot
"""
from __future__ import annotations

import pandas as pd

from .common import Http, ceil_hour, json_loads, write

API = "https://dashboard.elering.ee/api/nps/price"
http = Http("elering_nps", min_interval_s=0.5)


def fetch(start="2025-03-01", end="2026-11-03") -> pd.DataFrame:
    rows = []
    for w0 in pd.date_range(start, end, freq="14D", tz="UTC"):
        w1 = min(w0 + pd.Timedelta(days=14), pd.Timestamp(end, tz="UTC"))
        body = http.get(API, {"start": w0.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "end": w1.strftime("%Y-%m-%dT%H:%M:%S.000Z")},
                        cache_key=f"fi_{w0:%Y%m%d}.json")
        rows += json_loads(body)["data"]["fi"]
    df = pd.DataFrame(rows).drop_duplicates("timestamp")
    df["start"] = pd.to_datetime(df.timestamp, unit="s", utc=True)
    df = df.sort_values("start")
    step = df.start.diff().shift(-1).fillna(pd.Timedelta(minutes=15))
    parts = []
    for r, dur in zip(df.itertuples(), step):        # repeat hourly prices for each quarter
        n = 4 if dur >= pd.Timedelta(hours=1) else 1
        for k in range(n):
            parts.append((r.start + k * pd.Timedelta(minutes=15), r.price))
    q = pd.DataFrame(parts, columns=["timestamp_utc", "value"]).drop_duplicates("timestamp_utc")
    local_day = q.timestamp_utc.dt.tz_convert("Europe/Helsinki").dt.normalize()
    pub = (local_day - pd.Timedelta(days=1) + pd.Timedelta(hours=14)).dt.tz_convert("UTC")
    return pd.DataFrame({"series_id": "fi_spot_price", "source": "elering_nps", "dataset_id": "", "timestamp_utc": q.timestamp_utc,
                         "value": q.value, "unit": "EUR/MWh", "first_usable_origin_utc": ceil_hour(pub)})


if __name__ == "__main__":
    write(fetch(), "elering", "fi_spot_history")
