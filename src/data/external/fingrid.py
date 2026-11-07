"""Fingrid Open Data: real-time 3-min system data + history of the package series.

Needs FINGRID_API_KEY in .env (free, instant: https://data.fingrid.fi -> sign up).
Rate limit: 1 call / 2 s and 10,000 calls / day (same client settings as the organisers'
build_dataset.py).

Output: the package's long format (series_id, source, dataset_id, timestamp_utc, value, unit,
first_usable_origin_utc), so `available_at()` works unchanged.

Availability rules (☐ = our assumption; confirm with the organisers):
  rt3     3-min real-time data, averaged per quarter-hour. A quarter is usable at
          ceil_hour(quarter_end + RT_DELAY). RT_DELAY defaults to 30 min (the package uses
          30 min for measured data). Override with env FINGRID_RT_DELAY_MIN. ☐
  period  15-min or hourly values: ceil_hour(period_end + delay_min) (as in availability.csv)
  daily   day-ahead series published once a day at a local time on D-1 (as in availability.csv)
  NB Fingrid's continuously updated forecasts (e.g. 245, 241) store only the latest version,
     so their history leaks. They are deliberately NOT in this list.

Usage:
  python -m src.data.external.fingrid check            # print official names of all IDs (1 call each)
  python -m src.data.external.fingrid fetch [group]    # rt | package | extra | all
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass

import pandas as pd

from .common import PERIODS, Http, ceil_hour, json_loads, load_env, write

URL = "https://data.fingrid.fi/api/datasets/{id}/data"
META = "https://data.fingrid.fi/api/datasets/{id}"
TZ = "Europe/Helsinki"


@dataclass(frozen=True)
class DS:
    id: int
    name: str
    kind: str              # rt3 | period | daily
    unit: str
    delay_min: int = 0     # for kind=period
    publish_local: str = ""  # for kind=daily, e.g. "13:00" on D-1
    verified: bool = True  # False = ID inferred, confirm with `check`


RT = [  # real-time 3-min, verified on data.fingrid.fi dataset pages (6 Nov 2026)
    DS(181, "wind_rt", "rt3", "MW"),
    DS(192, "production_rt", "rt3", "MW"),
    DS(193, "consumption_rt", "rt3", "MW"),
    DS(194, "net_import_rt", "rt3", "MW"),
    DS(198, "surplus_deficit_rt", "rt3", "MW"),          # measured net import vs confirmed exchange plan
    DS(186, "surplus_deficit_cum_rt", "rt3", "MW"),
    DS(177, "frequency_rt", "rt3", "Hz"),
    DS(188, "nuclear_rt", "rt3", "MW"),
    DS(191, "hydro_rt", "rt3", "MW"),
    DS(209, "power_system_state_rt", "rt3", "state"),
]
RT2 = [  # second real-time batch (teammate Frank found it helps spikes/direction); same 30-min rule
    DS(371, "boilers_rt", "rt3", "MW"),          # electric boiler consumption: flexible load
    DS(201, "chp_dh_rt", "rt3", "MW"),           # district-heating cogeneration
    DS(202, "chp_ind_rt", "rt3", "MW"),          # industrial cogeneration
    DS(87, "flow_se1_rt", "rt3", "MW"),          # FI-SE1 transmission, real time
    DS(89, "flow_se3_rt", "rt3", "MW"),          # FI-SE3 transmission, real time
    DS(180, "flow_ee_rt", "rt3", "MW"),          # FI-EE transmission, real time
    DS(187, "flow_no_rt", "rt3", "MW"),          # FI-NO transmission, real time
]
PACKAGE = [  # same series as the starter package; delays as in availability.csv
    DS(319, "imbalance_price", "period", "EUR/MWh", 60),
    DS(369, "mfrr_direction", "period", "-1/0/1", 60),
    DS(244, "mfrr_up_price", "period", "EUR/MWh", 60),
    DS(106, "mfrr_down_price", "period", "EUR/MWh", 60),
    DS(375, "mfrr_up_activated", "period", "MW", 60),
    DS(376, "mfrr_down_activated", "period", "MW", 60),
    DS(347, "afrr_up_price", "period", "EUR/MWh", 60),
    DS(348, "afrr_down_price", "period", "EUR/MWh", 60),
    DS(124, "consumption", "period", "MWh/h", 30),
    DS(74, "production", "period", "MWh/h", 30),
    DS(61, "se3_flow", "period", "MW", 30),
    DS(57, "no4_flow", "period", "MW", 30),
    DS(60, "se1_flow", "period", "MW", 30),
    DS(55, "ee_flow", "period", "MW", 30),
    DS(165, "consumption_fc_da", "daily", "MW", publish_local="13:00"),
    DS(246, "wind_fc_da", "daily", "MW", publish_local="13:00"),
    DS(247, "solar_fc_da", "daily", "MW", publish_local="13:00"),
]
EXTRA = [
    DS(75, "wind_15min", "period", "MW", 30),             # measured wind, 15-min averages
    DS(268, "wind_capacity", "period", "MW", 24 * 60),    # capacity used in Fingrid's wind forecast (manual)
    DS(242, "production_plan_da", "daily", "MWh/h", publish_local="18:00"),  # BRP plans, by 18:00 D-1, not revised
    DS(243, "mfrr_up_bids_sum", "period", "MW", 60),      # hour h published at h+2 ("one hour delay")
    DS(22, "mfrr_last_up_bid_price", "period", "EUR/MWh", 60, verified=True),    # ☐ real-time only when FI is separate
    DS(251, "mfrr_last_down_bid_price", "period", "EUR/MWh", 60, verified=True),  # ☐ idem
    DS(176, "imbalance_power_fi_se", "period", "MWh/h", 60),  # ☐ delay unverified
]
GROUPS = {"rt": RT, "rt2": RT2, "package": PACKAGE, "extra": EXTRA}
# Package-series history from the Nordic mFRR market start (Mar 2025) to the package start,
# so the direction/spike models can see last autumn and winter.
HISTORY = ("2025-03-01", "2026-06-01")


def client() -> Http:
    key = load_env().get("FINGRID_API_KEY")
    if not key:
        sys.exit("FINGRID_API_KEY missing: sign up at https://data.fingrid.fi and add it to .env")
    return Http("fingrid", min_interval_s=2.6, headers={"x-api-key": key, "Accept": "application/json"})


def fetch_raw(http: Http, ds: DS, start: str, end: str) -> pd.DataFrame:
    rows = []
    for c0 in pd.date_range(start, end, freq="30D", tz="UTC"):
        c1 = min(c0 + pd.Timedelta(days=30), pd.Timestamp(end, tz="UTC"))
        page = 1
        while True:
            body = http.get(URL.format(id=ds.id), {
                "startTime": c0.strftime("%Y-%m-%dT%H:%M:%SZ"), "endTime": c1.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "format": "json", "pageSize": 20000, "page": page, "sortBy": "startTime", "sortOrder": "asc"},
                cache_key=f"{ds.id}/{c0:%Y%m%d}_{c1:%Y%m%d}_p{page}.json")
            d = json_loads(body)
            rows += d.get("data", [])
            if page >= ((d.get("pagination") or {}).get("lastPage") or 1):
                break
            page += 1
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["start"] = pd.to_datetime(df.startTime, utc=True)
    df["end"] = pd.to_datetime(df.endTime, utc=True)
    return df.dropna(subset=["value"])


def to_long(ds: DS, raw: pd.DataFrame, rt_delay: pd.Timedelta) -> pd.DataFrame:
    if raw.empty:
        return raw
    if ds.kind == "rt3":
        q = raw.assign(ts=raw.start.dt.floor("15min")).groupby("ts").value.mean().reset_index()
        q["fu"] = ceil_hour(q.ts + pd.Timedelta(minutes=15) + rt_delay)
    else:  # repeat longer periods per quarter (like the package); usable from the period end
        parts = []
        for r in raw.itertuples():
            n = max(1, int((r.end - r.start) / pd.Timedelta(minutes=15)))
            for k in range(n):
                parts.append((r.start + k * pd.Timedelta(minutes=15), r.value, r.end))
        q = pd.DataFrame(parts, columns=["ts", "value", "end"])
        if ds.kind == "period":
            q["fu"] = ceil_hour(q.end + pd.Timedelta(minutes=ds.delay_min))
        else:  # daily: published at publish_local on the local day before delivery
            local_day = q.ts.dt.tz_convert(TZ).dt.normalize()
            hh, mm = map(int, ds.publish_local.split(":"))
            pub = (local_day - pd.Timedelta(days=1) + pd.Timedelta(hours=hh, minutes=mm)).dt.tz_convert("UTC")
            q["fu"] = ceil_hour(pub)
        q = q.drop(columns="end")
    return pd.DataFrame({"series_id": f"fg{ds.id}_{ds.name}", "source": "fingrid", "dataset_id": ds.id,
                         "timestamp_utc": q.ts, "value": q.value, "unit": ds.unit,
                         "first_usable_origin_utc": q.fu})


def check() -> None:
    http = client()
    for ds in RT + PACKAGE + EXTRA:
        body = http.get(META.format(id=ds.id), cache_key=f"meta/{ds.id}.json")
        d = json_loads(body)
        print(f"{ds.id:>4} {ds.name:<28} -> {d.get('nameEn') or d.get('name')!r} "
              f"(period {d.get('dataPeriodEn') or d.get('dataPeriod')}, updated {d.get('updateCadenceEn') or ''})")


def fetch(group: str = "all") -> None:
    http = client()
    rt_delay = pd.Timedelta(minutes=int(os.environ.get("FINGRID_RT_DELAY_MIN", load_env().get("FINGRID_RT_DELAY_MIN", 30))))
    for gname, items in GROUPS.items():
        if group not in (gname, "all"):
            continue
        periods = dict(PERIODS)
        if gname == "package":       # package series: continuous history instead of two windows
            periods = {"history": HISTORY}   # already contains last autumn
        for pname, (s, e) in periods.items():
            parts = []
            for ds in items:
                long = to_long(ds, fetch_raw(http, ds, s, e), rt_delay)
                print(f"  fingrid {ds.id} {ds.name} {pname}: {len(long):,} quarter rows")
                parts.append(long)
            write(pd.concat(parts, ignore_index=True), "fingrid", f"{gname}_{pname}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    check() if cmd == "check" else fetch(sys.argv[2] if len(sys.argv) > 2 else "all")
