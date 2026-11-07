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
* calib_mode="pooled": k rolling out-of-time holdouts ending at the cutoff (calibration.py) instead of
  one; the maps are fitted on the pooled out-of-sample predictions. spike_calib chooses how the
  spike product P(dir) x P(tail | dir) is calibrated ("product" = Platt on the raw product,
  "parts" = calibrated parts, "product2" = logistic map on both logits).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import lightgbm as lgb
import numpy as np
import pandas as pd

from src.features.build import (FEATURE_COLUMNS, FINGRID_RT_COLUMNS, RT_IMBALANCE_COLUMNS, WEATHER_COLUMNS,
                                WEATHER2_COLUMNS, WEATHER2_SPREAD_COLUMNS)
from src.models.calibration import (  # noqa: F401  (re-exported: other code imports these from here)
    QUANTILES, STEP_BANDS, Platt as _Platt, logit as _logit, fit_maps, pooled_windows)

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


@dataclass
class GBMModel:
    tau_days: float | None = None
    calibrate: bool = False
    spike_mode: str = "direct"           # "direct" or "product"
    holdout_days: int = 14
    use_weather: bool = False
    use_icon: bool = False               # needs use_weather; adds ICON-EU + spread columns
    icon_spread_only: bool = False       # only om_model_spread
    name: str = "gbm"
    params: dict = field(default_factory=lambda: dict(BASE_PARAMS))

    # fitted state
    models: dict = field(default_factory=dict, repr=False)
    platt: dict = field(default_factory=dict, repr=False)
    offsets: dict = field(default_factory=dict, repr=False)
    p_none: float = 0.0
    log: list = field(default_factory=list, repr=False)

    use_fingrid: bool = False
    # Real-time signals decay within a few hours (PLAN finding 2). Beyond this step they're set to
    # NaN so the model can't fit noise on them at long horizons. None = use at every step.
    fresh_max_step: int | None = None
    # Live imbalance features (fg198 surplus/deficit etc.); masked beyond fresh_max_step too.
    use_rt_imbalance: bool = False
    rt_imbalance_cols: tuple = tuple(RT_IMBALANCE_COLUMNS)   # subset to use when enabled

    # Calibration of probabilities and quantiles (needs calibrate=True).
    calib_mode: str = "single"           # "single" (last holdout_days) or "pooled" (calib_folds holdouts)
    calib_folds: int = 3
    calib_decay: float = 1.0             # pooled: weight of each older holdout relative to the next one
    spike_calib: str = "product"         # product mode only: "product", "parts" or "product2"
    spike_cal: dict = field(default_factory=dict, repr=False)
    pool: object = field(default=None, repr=False)   # last pool of out-of-sample predictions

    def _mask_fresh(self, X: pd.DataFrame, steps) -> pd.DataFrame:
        if not self.fresh_max_step:
            return X
        cols = (FINGRID_RT_COLUMNS if self.use_fingrid else []) \
            + (list(self.rt_imbalance_cols) if self.use_rt_imbalance else [])
        if not cols:
            return X
        X = X.copy()
        late = np.asarray(steps) > self.fresh_max_step
        X.loc[late, cols] = np.nan
        return X

    @property
    def features(self) -> list[str]:
        return (FEATURE_COLUMNS + (WEATHER_COLUMNS if self.use_weather else [])
                + ((WEATHER2_SPREAD_COLUMNS if self.icon_spread_only else WEATHER2_COLUMNS)
                   if self.use_icon else [])
                + (FINGRID_RT_COLUMNS if self.use_fingrid else [])
                + (list(self.rt_imbalance_cols) if self.use_rt_imbalance else []))

    # ------------------------------------------------------------------ fitting
    def _weights(self, df, ref):
        if not self.tau_days:
            return None
        age_days = (ref - df["delivery"]).dt.total_seconds().to_numpy() / 86400
        return np.exp(-np.clip(age_days, 0, None) / self.tau_days)

    def _fit_all(self, df: pd.DataFrame, ref: pd.Timestamp) -> dict:
        X = self._mask_fresh(df[self.features], df["step"])
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
            out["high_tail"], out["low_tail"] = out["high"], out["low"]
            out["high"] = out["up"] * out["high"]
            out["low"] = (1 - out["up"]) * out["low"]
        return out

    def fit(self, train: pd.DataFrame, cutoff: pd.Timestamp) -> "GBMModel":
        train = train.dropna(subset=["y_gap", "y_dir"]).reset_index(drop=True)
        self.p_none = float((train.drop_duplicates("delivery")["y_dir"] == 0).mean())

        if self.calibrate:
            self._calibrate(train, cutoff)

        self.models = self._fit_all(train, cutoff)
        return self

    def _windows(self, cutoff: pd.Timestamp):
        if self.calib_mode == "single":
            return [(cutoff - pd.Timedelta(days=self.holdout_days), cutoff)]
        if self.calib_mode == "pooled":
            return pooled_windows(cutoff, self.calib_folds, self.holdout_days)
        raise ValueError(f"calib_mode {self.calib_mode!r}")

    def _holdout_pool(self, train: pd.DataFrame, cutoff: pd.Timestamp) -> pd.DataFrame:
        """Out-of-sample predictions for every holdout window ending at the cutoff.

        For window [start, end) the inner model sees only rows whose targets were published by
        `start` (y_first_usable <= start); the holdout rows are the origins in [start, end).
        """
        windows = self._windows(cutoff)
        parts = []
        for i, (start, end) in enumerate(windows):
            inner = train.loc[train["y_first_usable"] <= start]
            hold = train.loc[(train["origin"] >= start) & (train["origin"] < end)]
            if hold.empty or inner.empty:
                self.log.append(f"calibration window {start:%Y-%m-%d}: skipped ({len(inner)} inner, {len(hold)} holdout rows)")
                continue
            raw = self._raw(self._fit_all(inner, start), self._mask_fresh(hold[self.features], hold["step"]))
            part = pd.DataFrame({f"raw_{k}": v for k, v in raw.items()})
            part["step"] = hold["step"].to_numpy()
            part["y_gap"] = hold["y_gap"].to_numpy()
            part["y_dir"] = hold["y_dir"].to_numpy()
            part["y_high"] = hold["y_spike_high"].to_numpy()
            part["y_low"] = hold["y_spike_low"].to_numpy()
            part["fold"] = i
            part["w"] = self.calib_decay ** (len(windows) - 1 - i)
            parts.append(part)
        if not parts:
            raise ValueError("no calibration holdout rows")
        return pd.concat(parts, ignore_index=True)

    def _calibrate(self, train: pd.DataFrame, cutoff: pd.Timestamp) -> None:
        self.pool = self._holdout_pool(train, cutoff)
        self.set_calibration(self.pool)

    def set_calibration(self, pool: pd.DataFrame, spike_calib: str | None = None) -> None:
        """Fit the maps on (a subset of) the pool; also lets experiments re-calibrate cheaply."""
        self.platt, self.spike_cal, self.offsets = fit_maps(pool, self.spike_mode, spike_calib or self.spike_calib)
        label = "holdout" if self.calib_mode == "single" else f"pooled {self.calib_folds}x{self.holdout_days}d"
        folds = []
        if pool["fold"].nunique() > 1:    # per-holdout P90 offsets show how stable the calibration is
            for k, g in pool.groupby("fold"):
                r = g["y_gap"] - g["raw_p90"]
                folds.append(f"fold{k}:p90@1={r[g['step'].between(1, 8)].quantile(0.9):+.1f}")
        self.log.append(f"calibration {label}: {len(pool)} rows; "
                        + ", ".join(f"{c}@{lo}={v:+.1f}" for (c, lo), v in self.offsets.items())
                        + (" | " + " ".join(folds) if folds else ""))

    # --------------------------------------------------------------- prediction
    def predict(self, feats: pd.DataFrame, with_drivers: bool = True) -> pd.DataFrame:
        X = self._mask_fresh(feats[self.features], feats["step"])
        raw = self._raw(self.models, X)
        if self.calibrate:
            plain = dict(raw)                       # uncalibrated parts for the spike maps
            for col in ("up", "high", "low"):
                raw[col] = self.spike_cal[col](plain) if col in self.spike_cal else self.platt[col](raw[col])
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
        contrib = self.models["p50"].predict(X, pred_contrib=True)[:, :-1]  # drop bias column
        order = np.argsort(-np.abs(contrib), axis=1)[:, :k]
        names = np.array(self.features)
        return [";".join(row) for row in names[order]]

    def describe(self) -> str:
        bits = [f"{self.name}: tau_days={self.tau_days}, calibrate={self.calibrate}, "
                f"spikes={self.spike_mode}, calib={self.calib_mode}/{self.spike_calib}, weather={self.use_weather}, "
                f"fingrid_rt={self.use_fingrid}, rt_imbalance={self.use_rt_imbalance}, "
                f"p_none={self.p_none:.4f}"]
        return "\n".join(bits + self.log)
