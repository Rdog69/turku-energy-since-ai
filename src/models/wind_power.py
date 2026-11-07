"""Learned wind production from weather-model wind at individual points.

    production(t) ~ b + sum_i w_i * power_curve(wind speed at point i, time t),  w_i >= 0

The weights act as learned installed capacities behind each point (14 ECMWF points, 8 ICON-EU
points). They're fitted to Fingrid's measured wind production (dataset 181, `fg_wind_rt`), which
replaces the generic capacity weighting with weights that match what Finland actually produces.

Availability rules:
* Fitting uses only deliveries before the training cutoff whose measured production was published
  by the cutoff. Each is paired with the newest weather runs usable 5 hours before the delivery
  (a typical lead time within our 10-hour horizon), never a later run.
* Features at origin t use the runs usable at t (WeatherIndex.lookup) and the fixed weights.
  tests/test_availability.py checks both.

Idea from Abdo's lab (`brainstorming-abdo`, wind_hat); this implementation is ours.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from src.data.availability import SeriesIndex, to_ns
from src.data.open_meteo import OUT_DIR
from src.data.weather import WeatherIndex, summarise_runs

HOUR_NS = 3_600_000_000_000
FIT_LEAD = pd.Timedelta(hours=5)
MEASURED = "fg_wind_rt"
SOURCES = (("ecmwf", ("ecmwf_ifs025.parquet", "ecmwf_ifs025_extra.parquet")),
           ("icon", ("icon_eu.parquet",)))


class _WindOnly(WeatherIndex):
    """WeatherIndex holding only the wind power index (a quarter of the memory)."""
    VARS = ("wind_idx",)


def load_points() -> dict[str, WeatherIndex]:
    """One wind-only index per weather point and model."""
    out = {}
    for model, files in SOURCES:
        frames = [pd.read_parquet(OUT_DIR / f) for f in files if (OUT_DIR / f).exists()]
        if not frames:
            continue
        raw = pd.concat(frames, ignore_index=True)
        for point, g in raw.groupby("point"):
            out[f"{model}_{point}"] = _WindOnly(summarise_runs(g))
    return out


class WindPowerMap:
    def __init__(self, points: dict[str, WeatherIndex]):
        self.points = points
        self.names = sorted(points)
        self.coef: np.ndarray | None = None
        self.intercept = 0.0
        self.n_fit = 0
        self.r2 = float("nan")

    def matrix(self, origins_ns, times_ns) -> np.ndarray:
        o, t = np.asarray(origins_ns), np.asarray(times_ns)
        return np.column_stack([self.points[n].lookup(o, t, "wind_idx")[0] for n in self.names])

    def fit(self, index: dict[str, SeriesIndex], cutoff) -> "WindPowerMap":
        s = index[MEASURED]
        c = to_ns(pd.Timestamp(cutoff))[0]
        keep = (s.ts < c) & (s.fu <= c) & ~np.isnan(s.val)
        d, y = s.ts[keep], s.val[keep]
        o = (d - FIT_LEAD.value) // HOUR_NS * HOUR_NS     # newest full hour at least 5 h before
        X = self.matrix(o, d)
        ok = ~np.isnan(X).any(axis=1)
        reg = LinearRegression(positive=True).fit(X[ok], y[ok])
        self.coef, self.intercept = reg.coef_, float(reg.intercept_)
        self.n_fit, self.r2 = int(ok.sum()), float(reg.score(X[ok], y[ok]))
        return self

    def predict(self, origins_ns, times_ns) -> np.ndarray:
        """Production (MW) at each time from the runs usable at each origin; NaN if a point is missing."""
        return self.intercept + self.matrix(origins_ns, times_ns) @ self.coef

    def truncated(self, origin) -> "WindPowerMap":
        """Same weights, but only weather runs usable at `origin` (for leakage tests)."""
        new = WindPowerMap({n: p.truncated(origin) for n, p in self.points.items()})
        new.coef, new.intercept, new.n_fit, new.r2 = self.coef, self.intercept, self.n_fit, self.r2
        return new

    def describe(self) -> str:
        top = sorted(zip(self.names, self.coef), key=lambda x: -x[1])[:5]
        return (f"wind power map: {self.n_fit} quarters, R2 {self.r2:.3f}, intercept {self.intercept:.0f} MW, "
                f"total weight {self.coef.sum():.0f} MW; largest: "
                + ", ".join(f"{n} {w:.0f}" for n, w in top))
