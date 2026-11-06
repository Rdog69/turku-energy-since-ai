"""Wind turbines and solar parks in Finland from OpenStreetMap (Overpass API).

    python -m src.data.osm_farms

Writes external_data/osm/turbines.parquet (one row per wind turbine) and
external_data/osm/solar.parquet (one row per solar plant / large solar generator), plus
external_data/osm/farms.json: turbines grouped into farms (operator/name or ~5 km grid cells),
with location, turbine count and capacity where OSM has it.

Static data (installed plants), so no availability issue. Data © OpenStreetMap contributors, ODbL.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from src.config import REPO_ROOT

OUT = REPO_ROOT / "external_data" / "osm"
OVERPASS = "https://overpass-api.de/api/interpreter"

WIND_Q = """
[out:json][timeout:180];
area["ISO3166-1"="FI"][admin_level=2]->.fi;
(node["power"="generator"]["generator:source"="wind"](area.fi);
 way["power"="generator"]["generator:source"="wind"](area.fi););
out center tags;
"""
SOLAR_Q = """
[out:json][timeout:180];
area["ISO3166-1"="FI"][admin_level=2]->.fi;
(nwr["power"="plant"]["plant:source"="solar"](area.fi);
 nwr["power"="generator"]["generator:source"="solar"]["generator:output:electricity"~"MW"](area.fi););
out center tags;
"""


def overpass(query: str) -> list[dict]:
    data = urllib.parse.urlencode({"data": query}).encode()
    for attempt in range(4):
        try:
            req = urllib.request.Request(OVERPASS, data=data, headers={"User-Agent": "sinceai-imbalance-forecast"})
            return json.load(urllib.request.urlopen(req, timeout=240))["elements"]
        except Exception as e:  # Overpass is busy at times
            print(f"  overpass retry {attempt + 1}: {e}")
            time.sleep(20 * (attempt + 1))
    raise RuntimeError("Overpass failed")


def _mw(text) -> float | None:
    """'3.6 MW' / '3600 kW' / '3 MWp' -> MW."""
    if not text:
        return None
    m = re.search(r"([\d.,]+)\s*(k|M|G)?W", str(text))
    if not m:
        return None
    v = float(m.group(1).replace(",", "."))
    return v * {"k": 1e-3, "M": 1.0, "G": 1e3, None: 1e-6}[m.group(2)]


def _rows(elements: list[dict], kind: str) -> pd.DataFrame:
    rows = []
    for e in elements:
        lat = e.get("lat", (e.get("center") or {}).get("lat"))
        lon = e.get("lon", (e.get("center") or {}).get("lon"))
        if lat is None:
            continue
        t = e.get("tags", {})
        cap = _mw(t.get("generator:output:electricity") or t.get("plant:output:electricity"))
        rows.append({"osm_id": f"{e['type']}/{e['id']}", "kind": kind, "lat": lat, "lon": lon,
                     "name": t.get("name") or t.get("operator") or "", "operator": t.get("operator", ""),
                     "capacity_mw": cap})
    return pd.DataFrame(rows)


def clean_turbine_capacity(cap: pd.Series) -> pd.Series:
    """OSM tags are hand-entered. A single turbine is 0.5-8 MW; above 20 MW the tag was almost
    certainly kW without a unit (e.g. '5500' = 5.5 MW); below 0.05 MW it's unusable."""
    cap = cap.where(cap <= 20, cap / 1000)
    return cap.where((cap >= 0.05) & (cap <= 20))


def group_farms(turbines: pd.DataFrame) -> list[dict]:
    """Group turbines into farms on a ~5 km grid (0.05° lat x 0.1° lon)."""
    t = turbines.copy()
    t["capacity_mw"] = clean_turbine_capacity(t["capacity_mw"])
    t["cell"] = (t["lat"] / 0.05).round().astype(int).astype(str) + "_" + (t["lon"] / 0.1).round().astype(int).astype(str)
    farms = []
    for cell, g in t.groupby("cell"):
        names = [n for n in g["name"] if n]
        cap = g["capacity_mw"].sum(min_count=1)
        farms.append({"id": f"wind_{cell}", "kind": "wind", "lat": round(g["lat"].mean(), 4),
                      "lon": round(g["lon"].mean(), 4), "turbines": int(len(g)),
                      "capacity_mw": None if pd.isna(cap) else round(float(cap), 1),
                      "name": max(set(names), key=names.count) if names else ""})
    return sorted(farms, key=lambda f: -f["turbines"])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    turbines = _rows(overpass(WIND_Q), "wind")
    print(f"wind turbines: {len(turbines)} (capacity tagged on {turbines['capacity_mw'].notna().sum()})")
    time.sleep(5)
    solar = _rows(overpass(SOLAR_Q), "solar")
    print(f"solar plants: {len(solar)}")
    turbines.to_parquet(OUT / "turbines.parquet", index=False)
    solar.to_parquet(OUT / "solar.parquet", index=False)
    farms = group_farms(turbines)
    solar_farms = [{"id": f"solar_{r.osm_id.replace('/', '_')}", "kind": "solar", "lat": round(r.lat, 4),
                    "lon": round(r.lon, 4), "capacity_mw": None if pd.isna(r.capacity_mw) else round(r.capacity_mw, 1),
                    "name": r.name} for r in solar.itertuples()]
    (OUT / "farms.json").write_text(json.dumps({"wind": farms, "solar": solar_farms,
                                                "source": "OpenStreetMap contributors, ODbL"}), encoding="utf-8")
    print(f"farms: {len(farms)} wind farms (largest: {farms[0]['turbines']} turbines), {len(solar_farms)} solar")


if __name__ == "__main__":
    main()
