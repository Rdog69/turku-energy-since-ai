"""Rebuild external_data/_frank/open_meteo/runs_frank_points.csv.gz (lab source "fw") from Frank's branch.
    git fetch origin brainstorming-frank && .venv/bin/python tools/convert_frank_weather.py
Points: ifs_* (14 FI), icon_* (8 FI), nord_* (12 SE/NO/DK/EE). Delays as in Frank's fetcher: IFS +8 h, ICON +5 h."""
import io, subprocess
from pathlib import Path
import pandas as pd

OUT = Path("external_data/_frank/open_meteo"); OUT.mkdir(parents=True, exist_ok=True)
FS = {"ifs": ["ecmwf_ifs025", "ecmwf_ifs025_extra"], "icon": ["icon_eu"], "nord": ["ecmwf_ifs025_nordic"]}
iso = lambda s: pd.to_datetime(s, utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
parts = []
for pre, files in FS.items():
    for f in files:
        raw = subprocess.run(["git", "show", f"origin/brainstorming-frank:external_data/open_meteo/{f}.parquet"],
                             capture_output=True, check=True).stdout
        d = pd.read_parquet(io.BytesIO(raw))
        parts.append(pd.DataFrame({"model": d.model, "run_init_utc": iso(d.run_init), "point": pre + "_" + d.point,
                                   "valid_utc": iso(d.valid_time), "wind_speed_100m": d.wind_speed_100m,
                                   "temperature_2m": d.temperature_2m,
                                   "first_usable_origin_utc": iso(d.first_usable_origin_utc)}))
pd.concat(parts).to_csv(OUT / "runs_frank_points.csv.gz", index=False)
print("wrote", OUT / "runs_frank_points.csv.gz")
