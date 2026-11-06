"""Nord Pool UMM (urgent market messages, REMIT): planned and unplanned outages.

Every message version has its own publicationDate. A version is usable at origin t iff
    first_usable_origin_utc = ceil_hour(publicationDate) <= t
Use the newest version per messageId among the usable ones (older versions may be outdated).

One row per (message version x unit x time period). Areas: FI plus the neighbours that
trade with FI (SE1, SE3, EE). Includes generation, production, consumption and
transmission units. ☐ Licence: public REMIT data on the Nord Pool platform; confirm the
use with the organisers (PLAN.md §12).

Usage:  python -m src.data.external.umm
"""
from __future__ import annotations

import pandas as pd

from .common import PERIODS, Http, ceil_hour, json_loads, write

API = "https://ummapi.nordpoolgroup.com/messages"
AREAS = {"FI": "10YFI-1--------U", "SE1": "10Y1001A1001A44P", "SE3": "10Y1001A1001A46L", "EE": "10Y1001A1001A39I"}
http = Http("umm", min_interval_s=0.5)
LIMIT = 500


def fetch(period: str, area: str) -> list[dict]:
    start, end = PERIODS[period]
    items, skip = [], 0
    while True:
        body = http.get(API, {"Areas": AREAS[area], "PublicationStartDate": f"{start}T00:00:00Z",
                              "PublicationStopDate": f"{end}T00:00:00Z", "IncludeOutdated": "true",
                              "Limit": LIMIT, "Skip": skip}, cache_key=f"{area}_{period}_{skip}.json")
        d = json_loads(body)
        items += d["items"]
        skip += LIMIT
        if skip >= d.get("total", 0) or not d["items"]:
            return items


def flatten(items: list[dict], area: str) -> pd.DataFrame:
    rows = []
    for m in items:
        base = {k: m.get(k) for k in ("messageId", "version", "publicationDate", "isOutdated", "messageType",
                                      "unavailabilityType", "eventStatus", "reasonCode", "unavailabilityReason",
                                      "publisherName")}
        base["query_area"] = area
        for kind in ("generationUnits", "productionUnits", "consumptionUnits", "transmissionUnits", "otherUnits"):
            for u in m.get(kind) or []:
                for tp in u.get("timePeriods") or [{}]:
                    rows.append({**base, "unit_kind": kind.replace("Units", ""), "unit_name": u.get("name"),
                                 "unit_eic": u.get("eic"), "area": u.get("areaName"),
                                 "in_area": u.get("inAreaName"), "out_area": u.get("outAreaName"),
                                 "fuel_type": u.get("fuelType"), "installed_mw": u.get("installedCapacity"),
                                 "unavailable_mw": tp.get("unavailableCapacity"),
                                 "available_mw": tp.get("availableCapacity"),
                                 "event_start_utc": tp.get("eventStart"), "event_stop_utc": tp.get("eventStop")})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for c in ("publicationDate", "event_start_utc", "event_stop_utc"):
        df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601")
    df["first_usable_origin_utc"] = ceil_hour(df.publicationDate)
    return df.drop_duplicates()


def main() -> None:
    for period in PERIODS:
        parts = []
        for area in AREAS:
            items = fetch(period, area)
            print(f"  umm {period} {area}: {len(items)} message versions")
            parts.append(flatten(items, area))
        write(pd.concat(parts, ignore_index=True), "umm", f"messages_{period}")


if __name__ == "__main__":
    main()
