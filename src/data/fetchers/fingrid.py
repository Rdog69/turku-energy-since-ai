"""Fingrid Open Data API fetcher for real-time physical system data.

Datasets:
- 181: Real-time wind power production (3-min series)
- 188: Real-time nuclear power production (3-min series)
- 177: Real-time grid frequency (3-min series)
- 191: Real-time hydro power production (3-min series)

Assumed honest publication delay: 30 minutes after quarter end.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional
import requests
import pandas as pd

FINGRID_API_URL = "https://data.fingrid.fi/api/datasets"


def fetch_fingrid_dataset(
    dataset_id: int,
    start_time_utc: str,
    end_time_utc: str,
    api_key: Optional[str] = None,
) -> pd.DataFrame:
    """Fetch 3-minute timeseries from Fingrid Open Data API."""
    key = api_key or os.environ.get("FINGRID_API_KEY")
    if not key:
        print(f"Notice: FINGRID_API_KEY not set. Skipping live Fingrid API call for dataset {dataset_id}.")
        return pd.DataFrame()

    url = f"{FINGRID_API_URL}/{dataset_id}/data"
    headers = {"x-api-key": key, "Accept": "application/json"}
    params = {
        "startTime": start_time_utc,
        "endTime": end_time_utc,
        "format": "json",
        "pageSize": 10000,
    }

    try:
        response = requests.get(url, headers=headers, params=params, timeout=20)
        response.raise_for_status()
        data = response.json().get("data", [])
        df = pd.DataFrame(data)
        if not df.empty and "startTime" in df.columns:
            df["timestamp_utc"] = pd.to_datetime(df["startTime"], utc=True)
            df["value"] = df["value"].astype(float)
            df = df[["timestamp_utc", "value"]].sort_values("timestamp_utc").reset_index(drop=True)
        return df
    except Exception as e:
        print(f"Warning: Fingrid API request failed for dataset {dataset_id}: {e}")
        return pd.DataFrame()


def resample_to_quarter_hours(
    df: pd.DataFrame,
    delay_minutes: int = 30,
) -> pd.DataFrame:
    """Resample 3-minute readings to 15-minute quarter-hours and attach honest publication delay."""
    if df.empty:
        return pd.DataFrame()

    df = df.set_index("timestamp_utc").resample("15min").mean().dropna().reset_index()

    # Publication delay rule: available delay_minutes after period end, rounded up to next full hour
    period_end = df["timestamp_utc"] + pd.Timedelta(minutes=15)
    published_at = period_end + pd.Timedelta(minutes=delay_minutes)
    df["first_usable_origin_utc"] = published_at.dt.ceil("h")

    return df

