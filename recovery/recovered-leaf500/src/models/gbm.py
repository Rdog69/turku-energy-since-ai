"""LightGBM models for every output column.

* Price: quantile regression on the gap to spot (q = 0.1, 0.5, 0.9), then add spot back.
* Direction: binary "up" classifier; p_none is the tiny training share (finding 8).
* Spikes: either direct binary classifiers ("direct") or P(direction) x P(tail | direction)
  ("product", finding 11).

Options that target the season drift (PLAN finding 9):
* tau_days: exponential recency weights on training rows (half the weight every tau*ln2 days).
* calibrate: hold out the last `holdout_days` of the training window, fit inner models on the rest,
  learn calibration maps on the holdout (Platt scaling for probabilities, conformal-style offsets for
  quantiles), then refit on the whole window and apply the maps. Only training-window data is used,
  so validation stays an honest out-of-time test.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from src.features.build import FEATURE_COLUMNS

QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}
STEP_BANDS = [(1, 8), (9, 20), (21, 40)]

BASE_PARAMS = dict(
    learning_rate=0.05,
    n_estimators=400,
    num_leaves=31,
    min_child_samples=500,     # increased from 300 to reduce probability overconfidence
    subsample=0.8,
    subsample_freq=1,
    colsample_bytree=0.8,
    reg_lambda=1.0,
    verbose=-1,
)


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


class _Platt:
    """Monotone recalibration p -> sigmoid(a * logit(p) + b), fitted on a holdout."""

    def __init__(self):
        self.lr = None

    def fit(self, p, y):
        if len(np.unique(y)) < 2:
            return self
        self.lr = LogisticRegression(C=100.0).fit(_logit(p).reshape(-1, 1), y)
        return self

    def __call__(self, p):
        if self.lr is None:
            return p
        return self.lr.predict_proba(_logit(p).reshape(-1, 1))[:, 1]


@dataclass
class GBMModel:
    tau_days: float | None = None
    calibrate: bool = False
    spike_mode: str = "direct"           # "direct" or "product"
    holdout_days: int = 14
    name: str = "gbm"
    params: dict = field(default_factory=lambda: dict(BASE_PARAMS))

    # fitted state
    models: dict = field(default_factory=dict, repr=False)
    platt: dict = field(default_factory=dict, repr=False)
    offsets: dict = field(default_factory=dict, repr=False)
    p_none: float = 0.0
    log: list = field(default_factory=list, repr=False)

    # ------------------------------------------------------------------ fitting
    def _weights(self, df, ref):
        if not self.tau_days:
            return None
        age_days = (ref - df["delivery"]).dt.total_seconds().to_numpy() / 86400
        return np.exp(-np.clip(age_days, 0, None) / self.tau_days)

    def _fit_all(self, df: pd.DataFrame, ref: pd.Timestamp) -> dict:
        X = df[FEATURE_COLUMNS]
        w = self._weights(df, ref)
        m = {}
        for col, q in QUANTILES.items():
            m[col] = lgb.LGBMRegressor(objective="quantile", alpha=q, **self.params).fit(
                X, df["y_gap"], sample_weight=w)
        m["up"] = lgb.LGBMClassifier(**self.params).fit(X, (df["y_dir"] == 1).astype(int), sample_weight=w)
        if self.spike_mode == "direct":
            for col in ("high", "low"):
                m[col] = lgb.LGBMClassifier(**self.params).fit(
                    X, df[f"y_spike_{col}"].astype(int), sample_weight=w)
        else:
            for col, direction in (("high", 1), ("low", -1)):
                sub = df["y_dir"] == direction
                ws = None if w is None else w[sub.to_numpy()]
                m[col] = lgb.LGBMClassifier(**self.params).fit(
                    X[sub], df.loc[sub, f"y_spike_{col}"].astype(int), sample_weight=ws)
        return m

    def _raw(self, m: dict, X: pd.DataFrame) -> dict:
        out = {col: m[col].predict(X) for col in QUANTILES}
        out["up"] = m["up"].predict_proba(X)[:, 1]
        out["high"] = m["high"].predict_proba(X)[:, 1]
        out["low"] = m["low"].predict_proba(X)[:, 1]
        if self.spike_mode == "product":
            out["high"] = out["up"] * out["high"]
            out["low"] = (1 - out["up"]) * out["low"]
        return out

    def fit(self, train: pd.DataFrame, cutoff: pd.Timestamp) -> "GBMModel":
        train = train.dropna(subset=["y_gap", "y_dir"]).reset_index(drop=True)
        self.p_none = float((train.drop_duplicates("delivery")["y_dir"] == 0).mean())

        if self.calibrate:
            split = cutoff - pd.Timedelta(days=self.holdout_days)
            inner = train.loc[train["y_first_usable"] <= split]
            hold = train.loc[train["origin"] >= split]
            m_inner = self._fit_all(inner, split)
            raw = self._raw(m_inner, hold[FEATURE_COLUMNS])
            for col in ("up", "high", "low"):
                y = {"up": hold["y_dir"] == 1, "high": hold["y_spike_high"] == 1,
                     "low": hold["y_spike_low"] == 1}[col].astype(int).to_numpy()
                self.platt[col] = _Platt().fit(raw[col], y)
            for col, q in QUANTILES.items():
                resid = hold["y_gap"].to_numpy() - raw[col]
                for lo, hi in STEP_BANDS:
                    band = hold["step"].between(lo, hi).to_numpy()
                    self.offsets[(col, lo)] = float(np.quantile(resid[band], q))
            self.log.append(f"calibration holdout: {len(hold)} rows from {split:%Y-%m-%d}; "
                            + ", ".join(f"{c}@{lo}={v:+.1f}" for (c, lo), v in self.offsets.items()))

        self.models = self._fit_all(train, cutoff)
        return self

    # --------------------------------------------------------------- prediction
    def predict(self, feats: pd.DataFrame, with_drivers: bool = True) -> pd.DataFrame:
        X = feats[FEATURE_COLUMNS]
        raw = self._raw(self.models, X)
        if self.calibrate:
            for col in ("up", "high", "low"):
                raw[col] = self.platt[col](raw[col])
            steps = feats["step"].to_numpy()
            for col in QUANTILES:
                for lo, hi in STEP_BANDS:
                    band = (steps >= lo) & (steps <= hi)
                    raw[col][band] = raw[col][band] + self.offsets[(col, lo)]

        spot = feats["spot"].to_numpy()
        p_up = np.clip(raw["up"], 0, 1) * (1 - self.p_none)
        out = pd.DataFrame({
            "p10": spot + raw["p10"], "p50": spot + raw["p50"], "p90": spot + raw["p90"],
            "p_up": p_up, "p_down": 1 - self.p_none - p_up, "p_none": self.p_none,
            "p_spike_high": np.clip(raw["high"], 0, 1), "p_spike_low": np.clip(raw["low"], 0, 1),
        }, index=feats.index)
        out["top_drivers"] = self.top_drivers(X) if with_drivers else ""
        return out

    def top_drivers(self, X: pd.DataFrame, k: int = 3) -> list[str]:
        """Top-k features by |SHAP| of the p50 model, per row (LightGBM's built-in TreeSHAP)."""
        contrib = self.models["p50"].predict(X, pred_contrib=True)[:, :-1]  # drop bias column
        order = np.argsort(-np.abs(contrib), axis=1)[:, :k]
        names = np.array(FEATURE_COLUMNS)
        return [";".join(row) for row in names[order]]

    def describe(self) -> str:
        bits = [f"{self.name}: tau_days={self.tau_days}, calibrate={self.calibrate}, "
                f"spikes={self.spike_mode}, p_none={self.p_none:.4f}"]
        return "\n".join(bits + self.log)
