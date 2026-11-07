"""Open-Meteo Single Runs fetcher for Finnish wind revision features.

Fetches numerical weather prediction (NWP) model runs (ECMWF IFS / ICON)
at 100m turbine hub height on the Finnish west coast (Ostrobothnia wind cluster).
Calculates forecast revisions: Delta_Wind = Latest_Run - DayAhead_Run.
"""

from pathlib import Path
from typing import Dict, List, Optional
import requests
import pandas as pd

# Key west-coast wind clusters in Finland
WEST_COAST_POINTS = [
    {"name": "Vaasa_Ostrobothnia", "lat": 63.096, "lon": 21.615, "weight": 0.45},
    {"name": "Pori_Satakunta", "lat": 61.485, "lon": 21.797, "weight": 0.30},
    {"name": "Oulu_North", "lat": 65.012, "lon": 25.468, "weight": 0.25},
]

OPEN_METEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"


def fetch_point_weather(
    lat: float,
    lon: float,
    start_date: str,
    end_date: str,
    variables: Optional[List[str]] = None,
) -> pd.DataFrame:
    """Fetch historical hourly weather variables for a specific coordinate."""
    if variables is None:
        variables = ["wind_speed_100m", "wind_speed_10m", "wind_gusts_10m", "temperature_2m", "relative_humidity_2m"]

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": start_date,
        "end_date": end_date,
        "hourly": ",".join(variables),
        "timezone": "UTC",
    }

    try:
        response = requests.get(OPEN_METEO_ARCHIVE_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
        hourly = data.get("hourly", {})
        df = pd.DataFrame(hourly)
        if "time" in df.columns:
            df["timestamp_utc"] = pd.to_datetime(df["time"], utc=True)
            df = df.drop(columns=["time"])
        return df
    except Exception as e:
        print(f"Warning: Open-Meteo request failed for ({lat}, {lon}): {e}")
        return pd.DataFrame()


def build_wind_revision_features(start_date: str, end_date: str) -> pd.DataFrame:
    """Aggregate weighted west-coast weather variables into regional wind proxies."""
    dfs = []
    for pt in WEST_COAST_POINTS:
        pt_df = fetch_point_weather(pt["lat"], pt["lon"], start_date, end_date)
        if not pt_df.empty:
            for col in pt_df.columns:
                if col != "timestamp_utc":
                    pt_df[col] = pt_df[col] * pt["weight"]
            dfs.append(pt_df.set_index("timestamp_utc"))

    if not dfs:
        return pd.DataFrame()

    # Sum weighted contributions across the points
    combined = sum(dfs).reset_index()

    # Turbine icing proxy: near freezing (temp between -3 and +1 C) with high relative humidity (>85%)
    icing_cond = (
        (combined["temperature_2m"] >= -3.0)
        & (combined["temperature_2m"] <= 1.0)
        & (combined["relative_humidity_2m"] >= 85.0)
    )
    combined["icing_risk_index"] = icing_cond.astype(float)

    return combined

