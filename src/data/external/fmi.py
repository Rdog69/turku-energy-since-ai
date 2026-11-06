"""FMI open data: 10-minute weather observations at west-coast stations (no key, CC BY 4.0).

Measured wind and temperature, i.e. the *current* weather. Combined with the NWP runs, it shows
whether the forecast is already going wrong.

Timestamps are the end of the 10-min interval. Assumed publication delay: 20 min (☐ FMI publishes
observations within minutes, so 20 min is conservative):
    first_usable_origin_utc = ceil_hour(time + 20 min)

Usage:  python -m src.data.external.fmi
"""
from __future__ import annotations

import re

import pandas as pd

from .common import PERIODS, Http, ceil_hour, write

WFS = "https://opendata.fmi.fi/wfs"
STATIONS = ["Vaasa", "Kokkola", "Kalajoki", "Raahe", "Oulunsalo", "Kemi", "Pori", "Helsinki"]  # place names that return wind (checked 7 Nov)
PARAMS = "ws_10min,wd_10min,wg_10min,t2m,rh"
DELAY = pd.Timedelta(minutes=20)
http = Http("fmi", min_interval_s=0.6)
ROW = re.compile(r"<BsWfs:Time>(.*?)</BsWfs:Time>\s*<BsWfs:ParameterName>(.*?)</BsWfs:ParameterName>\s*"
                 r"<BsWfs:ParameterValue>(.*?)</BsWfs:ParameterValue>", re.S)


def fetch(period: str) -> pd.DataFrame:
    start, end = (pd.Timestamp(x, tz="UTC") for x in PERIODS[period])
    rows = []
    for st in STATIONS:
        t = start
        while t < end:
            t2 = min(t + pd.Timedelta(days=7), end)
            body = http.get(WFS, {"service": "WFS", "version": "2.0.0", "request": "getFeature",
                                  "storedquery_id": "fmi::observations::weather::simple", "place": st,
                                  "starttime": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  "endtime": (t2 - pd.Timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                                  "parameters": PARAMS, "timestep": 10},
                            cache_key=f"{st}_{t:%Y%m%d}.xml")
            if body:
                for ts, p, v in ROW.findall(body.decode("utf-8")):
                    rows.append((st, ts, p, float(v) if v not in ("NaN", "") else None))
            t = t2
        print(f"  fmi {period} {st}: {len(rows):,} rows so far")
    df = pd.DataFrame(rows, columns=["station", "time_utc", "parameter", "value"])
    df["time_utc"] = pd.to_datetime(df.time_utc, utc=True)
    df = df.pivot_table(index=["station", "time_utc"], columns="parameter", values="value").reset_index()
    df["first_usable_origin_utc"] = ceil_hour(df.time_utc + DELAY)
    return df


def main() -> None:
    for period in PERIODS:
        write(fetch(period), "fmi", f"obs_{period}")


if __name__ == "__main__":
    main()
