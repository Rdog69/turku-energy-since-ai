"""Weather-run features with the availability rule built in.

A weather model run is usable from its first_usable_origin_utc (run init + a conservative
publication delay, see open_meteo.py). At origin t we use the newest run usable at t.

The key feature is the **wind revision**: how much the newest run's wind differs from the run
that was available when Fingrid published its day-ahead wind forecast (fi_wind_fc_da). The market
planned around the day-ahead forecast; a later revision is information the plan doesn't contain
yet (PLAN section 4, Open-Meteo row).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.availability import to_ns
from src.data.open_meteo import OUT_DIR

HOUR_NS = 3_600_000_000_000


def power_curve(ws: np.ndarray) -> np.ndarray:
    """Generic turbine curve at hub height: 0 below 3 m/s, cubic to rated at 12 m/s, cut-out 25."""
    ws = np.asarray(ws, dtype=float)
    p = np.clip((ws ** 3 - 27.0) / (12.0 ** 3 - 27.0), 0.0, 1.0)
    return np.where(ws >= 25.0, 0.0, p)


def point_weights() -> dict[str, float] | None:
    """Share of Finland's wind capacity nearest to each weather point (OpenStreetMap turbines).

    Turbines without a capacity tag get the median tagged capacity. Returns None if the OSM
    file isn't downloaded (then all points count equally).
    """
    from src.data.open_meteo import POINTS, POINTS_EXTRA
    POINTS = {**POINTS, **POINTS_EXTRA} if (OUT_DIR / "ecmwf_ifs025_extra.parquet").exists() else POINTS
    path = OUT_DIR.parent / "osm" / "turbines.parquet"
    if not path.exists():
        return None
    from src.data.osm_farms import clean_turbine_capacity
    t = pd.read_parquet(path)
    cap = clean_turbine_capacity(t["capacity_mw"])
    cap = cap.fillna(cap.median())
    names = list(POINTS)
    lat = np.array([POINTS[n][0] for n in names])
    lon = np.array([POINTS[n][1] for n in names])
    # equirectangular distance is fine at this scale
    d = (t["lat"].to_numpy()[:, None] - lat) ** 2 + ((t["lon"].to_numpy()[:, None] - lon) * np.cos(np.radians(64))) ** 2
    nearest = np.array(names)[d.argmin(axis=1)]
    w = pd.Series(cap.to_numpy()).groupby(nearest).sum()
    w = w.reindex(names).fillna(0.0)
    return (w / w.sum()).to_dict()


def summarise_runs(raw: pd.DataFrame, weights: dict[str, float] | None = None) -> pd.DataFrame:
    """Per (run, valid hour): wind power index, wind speed, temperature, icing share.

    weights: per-point weights (e.g. installed wind capacity nearest to each point); default equal.
    """
    df = raw.copy()
    df["wind_idx"] = power_curve(df["wind_speed_100m"])
    df["icing"] = (df["temperature_2m"].between(-3.0, 1.0) & (df["relative_humidity_2m"] >= 90)).astype(float)
    df["w"] = df["point"].map(weights).fillna(0.0) if weights else 1.0
    cols = {"wind_idx": "wind_idx", "wind_speed_100m": "wind_speed", "temperature_2m": "temp", "icing": "icing"}
    for src_col in cols:
        df[src_col + "_w"] = df[src_col] * df["w"]
    g = df.groupby(["run_init", "valid_time", "first_usable_origin_utc"])
    wsum = g["w"].sum()
    out = pd.DataFrame({dst: g[src + "_w"].sum() / wsum for src, dst in cols.items()}).reset_index()
    return out


def summarise_towns(raw: pd.DataFrame) -> pd.DataFrame:
    """Per (run, valid hour): town means of solar radiation (W/m2), cloud cover (%) and temperature (C).

    The 8 towns (open_meteo.POINTS_SOLAR) count equally.
    """
    g = raw.groupby(["run_init", "valid_time", "first_usable_origin_utc"])
    return pd.DataFrame({"rad": g["shortwave_radiation"].mean(), "cloud": g["cloud_cover"].mean(),
                         "temp": g["temperature_2m"].mean()}).reset_index()


def load_towns(model: str = "ecmwf_ifs025") -> "WeatherIndex | None":
    """Town weather (radiation, cloud, temperature) as a WeatherIndex with those three variables."""
    path = OUT_DIR / f"{model}_solar.parquet"
    if not path.exists():
        return None
    return TownIndex(summarise_towns(pd.read_parquet(path)))


def load_nordic(model: str = "ecmwf_ifs025") -> dict[str, "WeatherIndex"] | None:
    """One WeatherIndex per neighbouring area (se / no / dk / ee), points weighted equally."""
    from src.data.open_meteo import POINT_AREAS
    path = OUT_DIR / f"{model}_nordic.parquet"
    if not path.exists():
        return None
    raw = pd.read_parquet(path)
    raw["area"] = raw["point"].map(POINT_AREAS)
    return {area: WeatherIndex(summarise_runs(g.drop(columns="area")))
            for area, g in raw.groupby("area")}


class WeatherIndex:
    """Runs x hourly matrix per variable, looked up by (origin, time) with linear interpolation."""

    VARS = ("wind_idx", "wind_speed", "temp", "icing")

    def __init__(self, summary: pd.DataFrame):
        runs = summary[["run_init", "first_usable_origin_utc"]].drop_duplicates().sort_values(
            ["first_usable_origin_utc", "run_init"])
        self.run_init = to_ns(runs["run_init"])
        self.run_fu = to_ns(runs["first_usable_origin_utc"])
        hours = to_ns(summary["valid_time"])
        self.h0 = hours.min()
        n_hours = int((hours.max() - self.h0) // HOUR_NS) + 1
        r_pos = np.searchsorted(self.run_init, to_ns(summary["run_init"]))
        h_pos = ((hours - self.h0) // HOUR_NS).astype(int)
        self.mats = {}
        for v in self.VARS:
            m = np.full((len(self.run_init), n_hours), np.nan, dtype=np.float32)
            m[r_pos, h_pos] = summary[v].to_numpy(dtype=np.float32)
            self.mats[v] = m

    @classmethod
    def load(cls, model: str = "ecmwf_ifs025", path: Path | None = None,
             capacity_weighted: bool = False) -> "WeatherIndex":
        raw = pd.read_parquet(path or OUT_DIR / f"{model}.parquet")
        extra = OUT_DIR / f"{model}_extra.parquet"
        if capacity_weighted and path is None and extra.exists():
            # same runs, same publication rule; only runs present in both sets are kept
            ex = pd.read_parquet(extra)
            both = set(raw["run_init"]) & set(ex["run_init"])
            raw = pd.concat([raw[raw["run_init"].isin(both)], ex[ex["run_init"].isin(both)]], ignore_index=True)
        return cls(summarise_runs(raw, point_weights() if capacity_weighted else None))

    def truncated(self, origin) -> "WeatherIndex":
        """Copy containing only runs usable at `origin` (for leakage tests)."""
        keep = self.run_fu <= to_ns(pd.Timestamp(origin))[0]
        new = object.__new__(WeatherIndex)
        new.run_init, new.run_fu, new.h0 = self.run_init[keep], self.run_fu[keep], self.h0
        new.mats = {v: m[keep] for v, m in self.mats.items()}
        return new

    def lookup(self, origins_ns: np.ndarray, times_ns: np.ndarray, var: str):
        """Value of `var` at `times` from the newest run usable at each origin.

        Returns (values, run_init_ns); NaN / -1 where no run is usable.
        """
        k = np.searchsorted(self.run_fu, origins_ns, side="right") - 1
        ok = k >= 0
        kc = np.clip(k, 0, None)
        pos = (times_ns - self.h0) / HOUR_NS
        lo = np.floor(pos).astype(int)
        w = pos - lo
        m = self.mats[var]
        n = m.shape[1]
        lo_c, hi_c = np.clip(lo, 0, n - 1), np.clip(lo + 1, 0, n - 1)
        v = (1 - w) * m[kc, lo_c] + w * m[kc, hi_c]
        v = np.where(ok & (lo >= 0) & (lo + 1 < n), v, np.nan)
        run = np.where(ok, self.run_init[kc], -1)
        return v.astype(float), run


class TownIndex(WeatherIndex):
    """Same lookups, for the town variables from summarise_towns()."""
    VARS = ("rad", "cloud", "temp")
