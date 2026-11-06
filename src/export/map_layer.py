"""Map layer for the dashboard: wind/solar farm pins and a per-hour weather overlay.

Adds a `map` block to every origin JSON written by src.export.dashboard, and writes farms.json
next to index.json. Spot-free (weather + OpenStreetMap only), so it's safe for the hosted preview.

Weather at each point comes from the newest ECMWF run *usable at the origin* (same availability
rule as the model). For each point: wind speed for the next 10 hours, the matching capacity
factor from a generic turbine curve, and the share of Finland's wind capacity nearest to it.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.data.availability import to_ns
from src.data.open_meteo import OUT_DIR, POINTS, POINTS_EXTRA
from src.data.weather import point_weights, power_curve

HOURS = 10


def load_points() -> tuple[pd.DataFrame, dict]:
    parts = [pd.read_parquet(OUT_DIR / "ecmwf_ifs025.parquet")]
    pts = dict(POINTS)
    extra = OUT_DIR / "ecmwf_ifs025_extra.parquet"
    if extra.exists():
        parts.append(pd.read_parquet(extra))
        pts.update(POINTS_EXTRA)
    raw = pd.concat(parts, ignore_index=True)
    for c in ("valid_time", "run_init", "first_usable_origin_utc"):
        raw[c] = pd.to_datetime(raw[c], utc=True)
    return raw, pts


def build_map_blocks(origins: list[pd.Timestamp]) -> dict[pd.Timestamp, dict]:
    raw, pts = load_points()
    weights = point_weights() or {p: 1 / len(pts) for p in pts}
    runs = raw[["run_init", "first_usable_origin_utc"]].drop_duplicates().sort_values("first_usable_origin_utc")
    by_run = {r: g.set_index(["point", "valid_time"])["wind_speed_100m"] for r, g in raw.groupby("run_init")}
    out = {}
    fu = to_ns(runs["first_usable_origin_utc"])
    for o in origins:
        k = int(np.searchsorted(fu, to_ns(o)[0], side="right")) - 1   # newest run usable at o
        if k < 0:
            continue
        run = runs["run_init"].iloc[k]
        s = by_run[run]
        hours = [o + pd.Timedelta(hours=h) for h in range(HOURS)]
        points, fleet = [], np.zeros(HOURS)
        for name, (lat, lon) in pts.items():
            ws = np.array([s.get((name, h), np.nan) for h in hours], dtype=float)
            cf = power_curve(ws)
            w = float(weights.get(name, 0.0))
            fleet += np.nan_to_num(cf) * w
            points.append({"name": name, "lat": lat, "lon": lon, "capacity_share": round(w, 3),
                           "wind_ms": [None if np.isnan(v) else round(v, 1) for v in ws],
                           "capacity_factor": [None if np.isnan(v) else round(v, 2) for v in cf]})
        out[o] = {"run_init": run.strftime("%Y-%m-%dT%H:%MZ"),
                  "run_usable_from": runs["first_usable_origin_utc"].iloc[k].strftime("%Y-%m-%dT%H:%MZ"),
                  "hours": [h.strftime("%Y-%m-%dT%H:%MZ") for h in hours],
                  "points": points,
                  "fleet_capacity_factor": [round(float(v), 3) for v in fleet]}
    return out


BORDERS = {  # Fingrid real-time flows; positive = export from Finland (same as the package)
    "SE1": ("fg_flow_se1_rt", (65.85, 24.15), (66.1, 22.6)),
    "SE3": ("fg_flow_se3_rt", (60.9, 21.4), (60.4, 18.4)),
    "NO4": ("fg_flow_no_rt", (69.0, 28.4), (69.6, 29.6)),
    "EE": ("fg_flow_ee_rt", (60.2, 25.0), (59.45, 24.7)),
}


def border_flows(origins: list[pd.Timestamp]) -> dict[pd.Timestamp, list[dict]]:
    """Newest usable real-time flow per border at each origin (availability-masked)."""
    from src.data.availability import build_index
    from src.data.load import load_long_all
    idx = build_index(load_long_all())
    o_ns = to_ns(pd.DatetimeIndex(origins))
    per = {}
    for name, (sid, fi_end, other_end) in BORDERS.items():
        if sid not in idx:
            continue
        ts, vals = idx[sid].latest(o_ns)
        per[name] = (ts, vals, fi_end, other_end)
    out = {}
    for i, o in enumerate(origins):
        rows = []
        for name, (ts, vals, fi_end, other_end) in per.items():
            v = vals[i]
            rows.append({"border": name, "mw": None if np.isnan(v) else round(float(v)),
                         "direction": None if np.isnan(v) else ("export" if v > 0 else "import"),
                         "measured_at": None if ts[i] < 0 else pd.Timestamp(int(ts[i]), tz="UTC").strftime("%Y-%m-%dT%H:%MZ"),
                         "fi_end": fi_end, "other_end": other_end})
        out[o] = rows
    return out


def annotate(root: Path) -> None:
    """Add `map` to every origin JSON under root/origins and write root/farms.json."""
    files = sorted((root / "origins").glob("*.json"))
    origins = [pd.Timestamp(f.stem, tz="UTC") for f in files]
    blocks = build_map_blocks(origins)
    flows = border_flows(origins)
    for o in origins:
        if blocks.get(o) is not None:
            blocks[o]["flows"] = flows.get(o, [])
    for f, o in zip(files, origins):
        doc = json.loads(f.read_text(encoding="utf-8"))
        m = blocks.get(o)
        if m is not None:
            ctx = doc.get("context", {})
            m["measured_vs_dayahead_mw"] = ctx.get("wind_now_vs_forecast_mw")
            m["dayahead_wind_mw"] = ctx.get("wind_fc_mw")
        doc["map"] = m
        f.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    farms = OUT_DIR.parent / "osm" / "farms.json"
    if farms.exists():
        (root / "farms.json").write_text(farms.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"map layer added to {len(files)} origins in {root}")
