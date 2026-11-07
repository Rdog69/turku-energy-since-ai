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


def load_history(base: pd.DataFrame) -> pd.DataFrame | None:
    """Pre-June history rows (config.HISTORY_PATH) for the series the package also has.

    Only rows before the package starts (config.DATA_START). Publication times are made at least
    as late as the package's own rule: for every measured series, each row gets the largest
    delay the package uses for the same minute of the hour (a row is never usable earlier than
    the package would allow). Day-ahead and calendar rows keep their own times.
    """
    from src.config import DATA_START, HISTORY_PATH
    if HISTORY_PATH.exists():
        h = pd.read_parquet(HISTORY_PATH)
    elif HISTORY_PATH.with_suffix(".csv.gz").exists():    # the file as Abdo's branch has it
        h = pd.read_csv(HISTORY_PATH.with_suffix(".csv.gz"), dtype={"dataset_id": str})
    else:
        return None
    for col in ("timestamp_utc", "first_usable_origin_utc"):
        h[col] = pd.to_datetime(h[col], utc=True)
    h = h.loc[h["series_id"].isin(set(base["series_id"])) & (h["timestamp_utc"] < DATA_START)].copy()
    h["dataset_id"] = h["dataset_id"].astype(str)
    # A few quarters appear twice (mostly mFRR in March 2025, when it was still partly hourly):
    # keep the copy published last.
    h = (h.sort_values("first_usable_origin_utc", kind="stable")
         .drop_duplicates(["series_id", "timestamp_utc"], keep="last"))
    parts = []
    for sid, g in h.groupby("series_id", sort=False):
        p = base.loc[base["series_id"] == sid]
        lag = p["first_usable_origin_utc"] - p["timestamp_utc"]
        if (lag > pd.Timedelta(0)).all():   # measured series: published after the quarter
            by_minute = lag.groupby(p["timestamp_utc"].dt.minute).max()
            delay = g["timestamp_utc"].dt.minute.map(by_minute)
            if delay.isna().any():
                raise ValueError(f"{sid}: history has minutes the package doesn't")
            rule = g["timestamp_utc"] + pd.to_timedelta(delay)
            fu = g["first_usable_origin_utc"]
            g = g.assign(first_usable_origin_utc=fu.where(fu >= rule, rule))
        parts.append(g)
    return pd.concat(parts, ignore_index=True)[LONG_COLUMNS]


def with_history(long: pd.DataFrame) -> pd.DataFrame:
    """long plus the pre-June history rows (see load_history); raises if the file is missing."""
    hist = load_history(long)
    if hist is None:
        raise FileNotFoundError("history missing: external_data/history/pkg_history.parquet")
    out = pd.concat([hist, long], ignore_index=True)
    dupes = out.duplicated(["series_id", "timestamp_utc"]).sum()
    if dupes:
        raise ValueError(f"{dupes} history rows overlap the package")
    return out


def with_rt_history(long: pd.DataFrame) -> pd.DataFrame:
    """long plus the Fingrid real-time series before the main table starts (src.data.fingrid
    load_rt_history), so history rows get real-time features too. Rows already in long win."""
    from src.data.fingrid import load_rt_history
    rt = load_rt_history()
    if rt is None:
        raise FileNotFoundError("real-time history missing: python -m src.data.fingrid --start 2025-03-01 "
                                "--end 2026-05-29 --out fingrid_rt_history.parquet")
    have = pd.MultiIndex.from_frame(long[["series_id", "timestamp_utc"]])
    new = rt.loc[~pd.MultiIndex.from_frame(rt[["series_id", "timestamp_utc"]]).isin(have), LONG_COLUMNS]
    return pd.concat([long, new], ignore_index=True)


def load_actuals_validation(pkg: str | None = None) -> pd.DataFrame:
    root = Path(pkg) if pkg else package_dir()
    df = pd.read_csv(root / "data" / "actuals_validation.csv")
    for col in ("delivery_start_utc", "first_usable_origin_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df
