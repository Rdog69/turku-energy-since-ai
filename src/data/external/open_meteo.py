"""Open-Meteo: archived NWP model runs (Single Runs API) + ERA5 reanalysis.

Single runs = what the weather model said at each initialisation, i.e. what a forecaster
could have seen. Recommended by the organisers. NEVER use the Historical Forecast API (leaks).

Usable at origin t iff first_usable_origin_utc <= t, where
    first_usable_origin_utc = ceil_hour(run_init + DELAY_H[model])
DELAY_H is a conservative rounding of the measured init->availability delay on Open-Meteo
(measured 6 Nov 2026 from /data/<model>/static/meta.json: ecmwf_ifs 7.1 h, dwd_icon_eu 3.9 h,
metno_nordic_pp 0.8 h).

ERA5 (archive API) is reanalysis = "what actually happened", published ~5 days late.
It is NOT a forecast-time feature; use it only to fit mappings (e.g. wind speed -> wind power).

Usage:  python -m src.data.external.open_meteo [ifs|icon_eu|metno|era5|all]
"""
from __future__ import annotations

import sys

import pandas as pd

from .common import CACHE, PERIODS, POINTS, Http, ceil_hour, json_loads, write

SINGLE = "https://single-runs-api.open-meteo.com/v1/forecast"
ERA5 = "https://archive-api.open-meteo.com/v1/archive"
VARS = ["wind_speed_100m", "wind_direction_100m", "wind_speed_10m", "wind_gusts_10m",
        "temperature_2m", "relative_humidity_2m", "shortwave_radiation", "cloud_cover"]
DELAY_H = {"ecmwf_ifs": 8, "icon_eu": 5, "metno_nordic": 2}
# (model, period, run hours UTC, forecast_hours)
JOBS = {
    "ifs": [("ecmwf_ifs", "last_autumn", (0, 12), 48), ("ecmwf_ifs", "main", (0, 6, 12, 18), 48)],
    "icon_eu": [("icon_eu", "main", (0, 6, 12, 18), 48)],
    "metno": [("metno_nordic", "main", (0, 6, 12, 18), 24)],
}
# 8 locations per call count as 8 calls on the free tier (600/min, 5000/h, 10000/day):
http = Http("open_meteo", min_interval_s=6.5)


def fetch_runs(model: str, period: str, hours, fc_hours: int) -> pd.DataFrame:
    start, end = PERIODS[period]
    runs = [t for t in pd.date_range(start, end, freq="h", tz="UTC", inclusive="left") if t.hour in hours]
    names, lats, lons = list(POINTS), [str(v[0]) for v in POINTS.values()], [str(v[1]) for v in POINTS.values()]
    frames = []
    for i, run in enumerate(runs):
        r = run.strftime("%Y-%m-%dT%H:%M")
        body = http.get(SINGLE, {"latitude": ",".join(lats), "longitude": ",".join(lons), "hourly": ",".join(VARS),
                                 "models": model, "run": r, "forecast_hours": fc_hours, "wind_speed_unit": "ms",
                                 "timezone": "GMT"}, cache_key=f"{model}/{r.replace(':', '')}.json")
        if body is None:
            continue
        try:
            data = json_loads(body)
        except ValueError:            # truncated response got cached: drop it and fetch again once
            (http_cache := CACHE / "open_meteo" / f"{model}/{r.replace(':', '')}.json").unlink(missing_ok=True)
            body = http.get(SINGLE, {"latitude": ",".join(lats), "longitude": ",".join(lons), "hourly": ",".join(VARS),
                                     "models": model, "run": r, "forecast_hours": fc_hours, "wind_speed_unit": "ms",
                                     "timezone": "GMT"}, cache_key=f"{model}/{r.replace(':', '')}.json")
            try:
                data = json_loads(body)
            except (ValueError, TypeError):
                print(f"  {model} {r}: unreadable response twice, skipped"); continue
        data = data if isinstance(data, list) else [data]
        for name, loc in zip(names, data):
            h = pd.DataFrame(loc["hourly"])
            h.insert(0, "point", name)
            h.insert(0, "run_init_utc", run)
            frames.append(h)
        if i % 50 == 0:
            print(f"  {model} {period}: {i + 1}/{len(runs)} runs")
    df = pd.concat(frames, ignore_index=True).rename(columns={"time": "valid_utc"})
    df["valid_utc"] = pd.to_datetime(df.valid_utc, utc=True)
    df["first_usable_origin_utc"] = ceil_hour(df.run_init_utc + pd.Timedelta(hours=DELAY_H[model]))
    df.insert(0, "model", model)
    df = df.dropna(subset=[v for v in VARS if v in df], how="all")
    return df


def fetch_era5(period: str) -> pd.DataFrame:
    start, end = PERIODS[period]
    end_incl = (pd.Timestamp(end) - pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    names, lats, lons = list(POINTS), [str(v[0]) for v in POINTS.values()], [str(v[1]) for v in POINTS.values()]
    body = http.get(ERA5, {"latitude": ",".join(lats), "longitude": ",".join(lons), "hourly": ",".join(VARS),
                           "start_date": start, "end_date": end_incl, "wind_speed_unit": "ms", "timezone": "GMT"},
                    cache_key=f"era5/{period}.json")
    data = json_loads(body)
    data = data if isinstance(data, list) else [data]
    frames = []
    for name, loc in zip(names, data):
        h = pd.DataFrame(loc["hourly"]); h.insert(0, "point", name); frames.append(h)
    df = pd.concat(frames, ignore_index=True).rename(columns={"time": "valid_utc"})
    df["valid_utc"] = pd.to_datetime(df.valid_utc, utc=True)
    # ERA5T appears ~5 days after real time: never a forecast-time feature
    df["first_usable_origin_utc"] = ceil_hour(df.valid_utc + pd.Timedelta(days=6))
    return df


def main(what: str = "all") -> None:
    if what in ("era5", "all"):
        for period in PERIODS:
            write(fetch_era5(period), "open_meteo", f"era5_{period}")
    for key, jobs in JOBS.items():
        if what not in (key, "all"):
            continue
        for model, period, hours, fch in jobs:
            write(fetch_runs(model, period, hours, fch), "open_meteo", f"runs_{model}_{period}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "all")
