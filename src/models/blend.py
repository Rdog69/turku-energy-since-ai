"""Horizon split: one model for the first steps, another for the rest.

Fresh real-time signals help the first ~2 hours and hurt later ones (RESULTS.md), so the
short-horizon model gets them and the long-horizon model doesn't.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class HorizonSplit:
    short: object
    long: object
    split_step: int = 8
    name: str = "horizon_split"
    capacity_weighted: bool = False   # weather averaged by OSM wind capacity (src/data/weather.py)

    @property
    def use_weather(self) -> bool:
        return getattr(self.short, "use_weather", False) or getattr(self.long, "use_weather", False)

    @property
    def use_nordic(self) -> bool:
        return getattr(self.short, "use_nordic", False) or getattr(self.long, "use_nordic", False)

    @property
    def use_icon(self) -> bool:
        return getattr(self.short, "use_icon", False) or getattr(self.long, "use_icon", False)

    @property
    def use_wind_hat(self) -> bool:
        return getattr(self.short, "use_wind_hat", False) or getattr(self.long, "use_wind_hat", False)

    @property
    def use_fingrid(self) -> bool:
        return getattr(self.short, "use_fingrid", False) or getattr(self.long, "use_fingrid", False)

    def fit(self, train: pd.DataFrame, cutoff: pd.Timestamp) -> "HorizonSplit":
        # The short model trains on early steps only, so all its capacity goes there.
        self.short.fit(train.loc[train["step"] <= self.split_step].reset_index(drop=True), cutoff)
        self.long.fit(train, cutoff)
        return self

    def predict(self, feats: pd.DataFrame) -> pd.DataFrame:
        early = feats["step"] <= self.split_step
        out = self.long.predict(feats)
        if early.any():
            out.loc[early] = self.short.predict(feats.loc[early]).to_numpy()
        return out

    def describe(self) -> str:
        return (f"{self.name}: steps 1-{self.split_step} from [{self.short.describe()}]\n"
                f"  steps {self.split_step + 1}-40 from [{self.long.describe()}]")


@dataclass
class MedianFrom:
    """P50 (and its drivers) from one model, everything else from another.

    Wind in the neighbouring countries sharpens the median in both September and August, but
    makes the P10-P90 band and the spike probabilities noisier (docs/RESULTS.md). So the final
    model takes only the median from the variant that sees it.
    """
    base: object
    median: object
    name: str = "median_from"

    def _either(self, attr: str) -> bool:
        return getattr(self.base, attr, False) or getattr(self.median, attr, False)

    @property
    def use_weather(self) -> bool:
        return self._either("use_weather")

    @property
    def use_nordic(self) -> bool:
        return self._either("use_nordic")

    @property
    def use_icon(self) -> bool:
        return self._either("use_icon")

    @property
    def use_wind_hat(self) -> bool:
        return self._either("use_wind_hat")

    @property
    def use_fingrid(self) -> bool:
        return self._either("use_fingrid")

    @property
    def capacity_weighted(self) -> bool:
        both = {getattr(self.base, "capacity_weighted", False), getattr(self.median, "capacity_weighted", False)}
        if len(both) != 1:
            raise ValueError("both models must weight the weather points the same way")
        return both.pop()

    def fit(self, train: pd.DataFrame, cutoff: pd.Timestamp) -> "MedianFrom":
        self.base.fit(train, cutoff)
        self.median.fit(train, cutoff)
        return self

    def predict(self, feats: pd.DataFrame) -> pd.DataFrame:
        out = self.base.predict(feats)
        med = self.median.predict(feats)
        out["p50"] = med["p50"].to_numpy()
        if "top_drivers" in med:            # the drivers explain the median
            out["top_drivers"] = med["top_drivers"].to_numpy()
        return out

    def describe(self) -> str:
        return (f"{self.name}: P50 and drivers from [{self.median.describe()}]\n"
                f"  everything else from [{self.base.describe()}]")
