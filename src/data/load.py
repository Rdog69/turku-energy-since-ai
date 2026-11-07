"""Load the starter package's long-format data.

Never print rows of the spot price data (Nord Pool licence): summaries only.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.config import package_dir

LONG_COLUMNS = ["series_id", "source", "dataset_id", "timestamp_utc", "value", "unit",
                "first_usable_origin_utc"]

IMBALANCE = "fi_imbalance_price"
DIRECTION = "fi_mfrr_direction"
SPOT = "fi_spot_price"


def _read_long(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, dtype={"dataset_id": str})
    for col in ("timestamp_utc", "first_usable_origin_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df[LONG_COLUMNS]


@lru_cache(maxsize=2)
def load_long(pkg: str | None = None) -> pd.DataFrame:
    """All input series plus the spot price, long format, UTC timestamps.

    One row per (series_id, timestamp_utc), with first_usable_origin_utc on every row.
    """
    root = Path(pkg) if pkg else package_dir()
    data = root / "data"
    try:
        inputs = _read_long(data / "inputs.parquet")
    except (ImportError, FileNotFoundError, ValueError):
        inputs = _read_long(data / "inputs.csv")
    parts = [inputs]
    spot_path = data / "spot_nordpool.csv"
    if spot_path.exists():
        parts.append(_read_long(spot_path))
    long = pd.concat(parts, ignore_index=True)
    dupes = long.duplicated(["series_id", "timestamp_utc"]).sum()
    if dupes:
        raise ValueError(f"{dupes} duplicate (series_id, timestamp_utc) rows")
    return long


def load_long_all(pkg: str | None = None) -> pd.DataFrame:
    """Package data plus downloaded external series in the same long format (if present).

    Currently: Fingrid real-time series (src/data/fingrid.py), each with its own
    first_usable_origin_utc, so every availability rule and test applies unchanged.
    """
    from src.data.fingrid import load_long_extra
    base = load_long(pkg)
    extra = load_long_extra()
    if extra is None:
        return base
    overlap = set(extra["series_id"]) & set(base["series_id"])
    if overlap:
        raise ValueError(f"external series clash with package series: {overlap}")
    return pd.concat([base, extra[LONG_COLUMNS]], ignore_index=True)


def load_actuals_validation(pkg: str | None = None) -> pd.DataFrame:
    root = Path(pkg) if pkg else package_dir()
    df = pd.read_csv(root / "data" / "actuals_validation.csv")
    for col in ("delivery_start_utc", "first_usable_origin_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df
