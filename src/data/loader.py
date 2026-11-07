"""Data loading utilities for Turku Energia imbalance challenge."""

from pathlib import Path
from typing import Optional, Union
import pandas as pd

# Default paths relative to workspace root
WORKSPACE_DIR = Path(__file__).resolve().parents[2]
STARTER_DIR = WORKSPACE_DIR / "Dataset" / "starter_package_v1"
if not STARTER_DIR.exists():
    STARTER_DIR = WORKSPACE_DIR / "starter_package_v1"
DATA_DIR = STARTER_DIR / "data"


def to_utc(value: Union[str, pd.Timestamp]) -> pd.Timestamp:
    """Ensure timestamp is UTC-aware pandas Timestamp."""
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize("UTC")
    return ts.tz_convert("UTC")


def load_inputs(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load inputs.parquet (or inputs.csv fallback) in long format with UTC timestamps."""
    dir_path = Path(data_dir) if data_dir else DATA_DIR
    parquet_path = dir_path / "inputs.parquet"
    csv_path = dir_path / "inputs.csv"

    if parquet_path.exists():
        df = pd.read_parquet(parquet_path)
    elif csv_path.exists():
        df = pd.read_csv(csv_path, dtype={"dataset_id": str})
    else:
        raise FileNotFoundError(f"Neither inputs.parquet nor inputs.csv found in {dir_path}")

    for col in ("timestamp_utc", "first_usable_origin_utc"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)
    return df


def load_spot(data_dir: Optional[Path] = None) -> Optional[pd.DataFrame]:
    """Load spot_nordpool.csv in long format with UTC timestamps (if available)."""
    dir_path = Path(data_dir) if data_dir else DATA_DIR
    spot_path = dir_path / "spot_nordpool.csv"
    if not spot_path.exists():
        return None

    df = pd.read_csv(spot_path, dtype={"dataset_id": str})
    for col in ("timestamp_utc", "first_usable_origin_utc"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)
    return df


def load_validation_actuals(data_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load actuals_validation.csv."""
    dir_path = Path(data_dir) if data_dir else DATA_DIR
    actuals_path = dir_path / "actuals_validation.csv"
    if not actuals_path.exists():
        raise FileNotFoundError(f"actuals_validation.csv not found in {dir_path}")

    df = pd.read_csv(actuals_path)
    for col in ("delivery_start_utc", "first_usable_origin_utc"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], utc=True)
    return df

