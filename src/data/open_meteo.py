"""Download historical weather model runs from the Open-Meteo Single Runs API.

Each run is a forecast exactly as it was issued at its initialisation time, so it can be used
in a backtest if we also respect when it became *available*:

    first_usable_origin_utc = ceil_to_hour(run_init + PUBLICATION_DELAY[model])

The delays are conservative assumptions (Open-Meteo: a 00 UTC run is generally accessible from
around 04-06 UTC). They're documented in SOURCES.md. The Historical Forecast API is NOT used: it
stitches runs together and leaks future information.

    python -m src.data.open_meteo --model ecmwf_ifs025 --start 2026-05-29 --end 2026-11-02

Data: Open-Meteo.com, CC BY 4.0. Raw responses are cached per run in
external_data/open_meteo/raw/ (git-ignored); the tidy table goes to
external_data/open_meteo/<model>.parquet.
"""
from __future__ import annotations

import argparse
import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import pandas as pd

from src.config import REPO_ROOT

API = "https://single-runs-api.open-meteo.com/v1/forecast"
OUT_DIR = REPO_ROOT / "external_data" / "open_meteo"

# Conservative publication delays after run initialisation (assumptions, see module docstring).
PUBLICATION_DELAY = {
    "ecmwf_ifs025": pd.Timedelta(hours=8),
    "icon_eu": pd.Timedelta(hours=5),
    "metno_nordic": pd.Timedelta(hours=3),
}
RUN_HOURS = {"ecmwf_ifs025": (0, 6, 12, 18), "icon_eu": (0, 6, 12, 18), "metno_nordic": (0, 6, 12, 18)}

# Points across Finland's main wind clusters, mostly the west coast (Ostrobothnia) and the
# Bothnian Bay. Approximate cluster centres, equal weights for now.
POINTS = {
    "pori": (61.65, 21.55),
    "kristinestad": (62.27, 21.38),
    "kauhava_lapua": (63.10, 23.10),
    "vaasa_coast": (63.10, 21.60),
    "kokkola_kalajoki": (64.00, 23.80),
    "raahe_pyhajoki": (64.50, 24.30),
    "oulu_hailuoto": (65.00, 24.90),
    "simo_tornio": (65.70, 24.90),
}
# Second set, added after mapping OpenStreetMap turbines: clusters the first 8 points missed.
POINTS_EXTRA = {
    "kurikka_teuva": (62.50, 22.30),
    "loimaa_sw": (60.80, 23.00),
    "kotka_hamina": (60.55, 27.20),
    "central_pyhajarvi": (63.65, 25.90),
    "kainuu_kajaani": (64.20, 27.70),
    "lapland_pello": (66.70, 24.30),
}
POINT_SETS = {"main": POINTS, "extra": POINTS_EXTRA}
VARIABLES = ["wind_speed_100m", "temperature_2m", "relative_humidity_2m"]
FORECAST_DAYS = 3


def _url(model: str, run: pd.Timestamp, points: dict) -> str:
    lats = ",".join(str(p[0]) for p in points.values())
    lons = ",".join(str(p[1]) for p in points.values())
    q = {
        "latitude": lats, "longitude": lons, "hourly": ",".join(VARIABLES), "models": model,
        "run": run.strftime("%Y-%m-%dT%H:%M"), "forecast_days": FORECAST_DAYS,
        "wind_speed_unit": "ms", "timezone": "GMT",
    }
    return API + "?" + urllib.parse.urlencode(q)


def fetch_run(model: str, run: pd.Timestamp, raw_dir: Path, pause: float = 1.0,
              point_set: str = "main") -> list | None:
    sub = model if point_set == "main" else f"{model}_{point_set}"
    path = raw_dir / sub / f"{run:%Y%m%dT%H}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    req = urllib.request.Request(_url(model, run, POINT_SETS[point_set]), headers={"User-Agent": "sinceai-imbalance-forecast"})
    for attempt in range(6):
        try:
            data = json.load(urllib.request.urlopen(req, timeout=60))
            break
        except urllib.error.HTTPError as e:
            body = e.read().decode(errors="replace")[:200]
            if e.code == 400 and "not available" in body:
                print(f"  {model} {run:%Y-%m-%dT%H} not available")
                return None
            wait = 60 * (attempt + 1) if e.code == 429 else 5 * (attempt + 1)
            print(f"  HTTP {e.code} for {run:%Y-%m-%dT%H}, retry in {wait}s: {body}")
            time.sleep(wait)
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException) as e:
            wait = 10 * (attempt + 1)
            print(f"  {type(e).__name__} for {run:%Y-%m-%dT%H}, retry in {wait}s")
            time.sleep(wait)
    else:
        raise RuntimeError(f"giving up on {model} {run}")
    data = data if isinstance(data, list) else [data]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    time.sleep(pause)
    return data


def to_frame(model: str, run: pd.Timestamp, data: list, point_set: str = "main") -> pd.DataFrame:
    parts = []
    for name, loc in zip(POINT_SETS[point_set], data):
        h = loc["hourly"]
        df = pd.DataFrame({v: h[v] for v in VARIABLES})
        df["valid_time"] = pd.to_datetime(h["time"], utc=True)
        df["point"] = name
        parts.append(df)
    out = pd.concat(parts, ignore_index=True)
    out["model"] = model
    out["run_init"] = run
    out["first_usable_origin_utc"] = (run + PUBLICATION_DELAY[model]).ceil("h")
    return out


def download(model: str, start: str, end: str, pause: float = 1.0, point_set: str = "main") -> Path:
    raw_dir = OUT_DIR / "raw"
    runs = [pd.Timestamp(d, tz="UTC") + pd.Timedelta(hours=h)
            for d in pd.date_range(start, end, freq="D") for h in RUN_HOURS[model]]
    frames, missing = [], []
    for i, run in enumerate(runs, 1):
        data = fetch_run(model, run, raw_dir, pause, point_set)
        if data is None:
            missing.append(run)
            continue
        frames.append(to_frame(model, run, data, point_set))
        if i % 40 == 0:
            print(f"  {i}/{len(runs)} runs ({run:%Y-%m-%d})", flush=True)
    table = pd.concat(frames, ignore_index=True)
    out = OUT_DIR / (f"{model}.parquet" if point_set == "main" else f"{model}_{point_set}.parquet")
    out.parent.mkdir(parents=True, exist_ok=True)
    table.to_parquet(out, index=False)
    print(f"wrote {out.relative_to(REPO_ROOT)}: {len(frames)} runs, {len(table)} rows; "
          f"missing runs: {len(missing)}")
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="ecmwf_ifs025", choices=sorted(PUBLICATION_DELAY))
    ap.add_argument("--start", default="2026-05-29")
    ap.add_argument("--end", default="2026-11-02")
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--points", choices=sorted(POINT_SETS), default="main")
    args = ap.parse_args(argv)
    download(args.model, args.start, args.end, args.pause, args.points)


if __name__ == "__main__":
    main()
