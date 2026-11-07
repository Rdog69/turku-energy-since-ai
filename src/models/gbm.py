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

from src.features.build import (FEATURE_COLUMNS, FINGRID_RT2_COLUMNS, FINGRID_RT_COLUMNS, MEMORY_COLUMNS, NORDIC_COLUMNS,
                                WEATHER2_COLUMNS, WEATHER_COLUMNS, WINDHAT_COLUMNS)

QUANTILES = {"p10": 0.1, "p50": 0.5, "p90": 0.9}
STEP_BANDS = [(1, 8), (9, 20), (21, 40)]

BASE_PARAMS = dict(
    learning_rate=0.05,
    n_estimators=400,
    num_leaves=31,
    min_child_samples=300,     # rows are heavily correlated (same quarter, 40 origins)
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
    """Monotone recalibration p -> sigmoid(a + b * logit(p)), fitted on a holdout.

    shrink_m0: shrink the map toward "no recalibration" by s = m / (m + m0), where m is the number
    of distinct delivery quarters with an event in the holdout. A quiet holdout with few spikes
    then can't wipe out the spike probabilities (empirical-Bayes idea from Abdo's lab,
    experiments/lab/calib_eb.py). None = plain Platt scaling.
    """

    def __init__(self, shrink_m0: int | None = None):
        self.lr = None
        self.shrink_m0 = shrink_m0
        self.s = 1.0

    def fit(self, p, y, deliveries=None):
        if len(np.unique(y)) < 2:
            return self
        self.lr = LogisticRegression(C=100.0).fit(_logit(p).reshape(-1, 1), y)
        if self.shrink_m0:
            m = len(np.unique(np.asarray(deliveries)[np.asarray(y) == 1]))
            self.s = m / (m + self.shrink_m0)
        return self

    def __call__(self, p):
        if self.lr is None:
            return p
        if not self.shrink_m0:
            return self.lr.predict_proba(_logit(p).reshape(-1, 1))[:, 1]
        a, b = float(self.lr.intercept_[0]), float(self.lr.coef_[0, 0])
        z = self.s * a + (1 + self.s * (b - 1)) * _logit(p)
        return 1 / (1 + np.exp(-z))


@dataclass
class GBMModel:
    tau_days: float | None = None
    calibrate: bool = False
    spike_mode: str = "direct"           # "direct" or "product"
    holdout_days: int = 14
    use_weather: bool = False
    name: str = "gbm"
    params: dict = field(default_factory=lambda: dict(BASE_PARAMS))

    # fitted state
    models: dict = field(default_factory=dict, repr=False)
    platt: dict = field(default_factory=dict, repr=False)
    offsets: dict = field(default_factory=dict, repr=False)
    p_none: float = 0.0
    log: list = field(default_factory=list, repr=False)

    use_fingrid: bool = False
    use_fingrid2: bool = False      # second batch of real-time series (hydro, boilers, flows, ...)
    n_seeds: int = 1                # >1 = average models trained with different random seeds
    use_nordic: bool = False        # neighbouring areas' wind revision (src/data/weather.load_nordic)
    use_memory: bool = False        # 4-hour averages of the gap and direction
    use_icon: bool = False          # second weather model ICON-EU + ECMWF-vs-ICON spread
    use_wind_hat: bool = False      # learned wind production from the weather points (MW)
    spike_shrink: int | None = None  # m0 for the shrunk spike Platt maps (see _Platt); None = plain
    # Real-time signals decay within a few hours (PLAN finding 2). Beyond this step they're set to
    # NaN so the model can't fit noise on them at long horizons. None = use at every step.
    fresh_max_step: int | None = None

    def _mask_fresh(self, X: pd.DataFrame, steps) -> pd.DataFrame:
        if not (self.use_fingrid and self.fresh_max_step):
            return X
        X = X.copy()
        late = np.asarray(steps) > self.fresh_max_step
        X.loc[late, [c for c in FINGRID_RT_COLUMNS + FINGRID_RT2_COLUMNS if c in X]] = np.nan
        return X

    @property
    def features(self) -> list[str]:
        return (FEATURE_COLUMNS + (WEATHER_COLUMNS if self.use_weather else [])
                + (FINGRID_RT_COLUMNS if self.use_fingrid else [])
                + (FINGRID_RT2_COLUMNS if self.use_fingrid2 else [])
                + (NORDIC_COLUMNS if self.use_nordic else [])
                + (WEATHER2_COLUMNS if self.use_icon else [])
                + (WINDHAT_COLUMNS if self.use_wind_hat else [])
                + (MEMORY_COLUMNS if self.use_memory else []))

    # ------------------------------------------------------------------ fitting
    def _weights(self, df, ref):
        if not self.tau_days:
            return None
        age_days = (ref - df["delivery"]).dt.total_seconds().to_numpy() / 86400
        return np.exp(-np.clip(age_days, 0, None) / self.tau_days)

    def _fit_all(self, df: pd.DataFrame, ref: pd.Timestamp) -> list[dict]:
        return [self._fit_one(df, ref, seed) for seed in range(self.n_seeds)]

    def _fit_one(self, df: pd.DataFrame, ref: pd.Timestamp, seed: int) -> dict:
        X = self._mask_fresh(df[self.features], df["step"])
        w = self._weights(df, ref)
        params = {**self.params, "random_state": seed}
        m = {}
        for col, q in QUANTILES.items():
            m[col] = lgb.LGBMRegressor(objective="quantile", alpha=q, **params).fit(
                X, df["y_gap"], sample_weight=w)
        m["up"] = lgb.LGBMClassifier(**params).fit(X, (df["y_dir"] == 1).astype(int), sample_weight=w)
        if self.spike_mode == "direct":
            for col in ("high", "low"):
                m[col] = lgb.LGBMClassifier(**params).fit(
                    X, df[f"y_spike_{col}"].astype(int), sample_weight=w)
        else:
            for col, direction in (("high", 1), ("low", -1)):
                sub = df["y_dir"] == direction
                ws = None if w is None else w[sub.to_numpy()]
                m[col] = lgb.LGBMClassifier(**params).fit(
                    X[sub], df.loc[sub, f"y_spike_{col}"].astype(int), sample_weight=ws)
        return m

    def _raw(self, ms: list[dict], X: pd.DataFrame) -> dict:
        outs = [self._raw_one(m, X) for m in ms]
        return {k: np.mean([o[k] for o in outs], axis=0) for k in outs[0]}

    def _raw_one(self, m: dict, X: pd.DataFrame) -> dict:
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
            raw = self._raw(m_inner, self._mask_fresh(hold[self.features], hold["step"]))
            for col in ("up", "high", "low"):
                y = {"up": hold["y_dir"] == 1, "high": hold["y_spike_high"] == 1,
                     "low": hold["y_spike_low"] == 1}[col].astype(int).to_numpy()
                m0 = self.spike_shrink if col in ("high", "low") else None
                self.platt[col] = _Platt(m0).fit(raw[col], y, hold["delivery"].to_numpy())
            if self.spike_shrink:
                self.log.append("spike Platt shrink s: " + ", ".join(
                    f"{c}={self.platt[c].s:.2f}" for c in ("high", "low")))
            for col, q in QUANTILES.items():
                resid = hold["y_gap"].to_numpy() - raw[col]
                for lo, hi in STEP_BANDS:
                    band = hold["step"].between(lo, hi).to_numpy()
                    if band.any():   # a short-horizon model has no rows in later bands
                        self.offsets[(col, lo)] = float(np.quantile(resid[band], q))
            self.log.append(f"calibration holdout: {len(hold)} rows from {split:%Y-%m-%d}; "
                            + ", ".join(f"{c}@{lo}={v:+.1f}" for (c, lo), v in self.offsets.items()))

        self.models = self._fit_all(train, cutoff)
        return self

    # --------------------------------------------------------------- prediction
    def predict(self, feats: pd.DataFrame, with_drivers: bool = True) -> pd.DataFrame:
        X = self._mask_fresh(feats[self.features], feats["step"])
        raw = self._raw(self.models, X)
        if self.calibrate:
            for col in ("up", "high", "low"):
                raw[col] = self.platt[col](raw[col])
            steps = feats["step"].to_numpy()
            for col in QUANTILES:
                for lo, hi in STEP_BANDS:
                    band = (steps >= lo) & (steps <= hi)
                    if band.any():
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
        contrib = self.models[0]["p50"].predict(X, pred_contrib=True)[:, :-1]  # drop bias column
        order = np.argsort(-np.abs(contrib), axis=1)[:, :k]
        names = np.array(self.features)
        return [";".join(row) for row in names[order]]

    def describe(self) -> str:
        bits = [f"{self.name}: tau_days={self.tau_days}, calibrate={self.calibrate}, "
                f"spikes={self.spike_mode}, weather={self.use_weather}, fingrid_rt={self.use_fingrid}, "
                f"p_none={self.p_none:.4f}"]
        return "\n".join(bits + self.log)
