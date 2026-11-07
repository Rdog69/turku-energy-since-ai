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

    @property
    def use_weather(self) -> bool:
        return getattr(self.short, "use_weather", False) or getattr(self.long, "use_weather", False)

    @property
    def use_fingrid(self) -> bool:
        return getattr(self.short, "use_fingrid", False) or getattr(self.long, "use_fingrid", False)

    @property
    def use_rt_imbalance(self) -> bool:
        return getattr(self.short, "use_rt_imbalance", False) or getattr(self.long, "use_rt_imbalance", False)

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
