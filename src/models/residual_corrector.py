"""Cross-Fitted Ridge Residual Corrector for Imbalance Price Forecasting.

Implements Phase 2 of Grand Champion V4:
- StandardScaler + Ridge Regression with strong L2 regularization (alpha in [10, 100, 1000])
- Low-dimensional, leakage-safe features available at forecast origin
- Out-of-fold chronological cross-fitting (never in-sample)
- Global shrinkage lambda in [0.0, 0.25, 0.50, 0.75, 1.0]
- Bounded residual clipping based on training fold statistics
"""
from __future__ import annotations

from typing import Any
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler


class ResidualCorrector:
    """Low-complexity Ridge regression model predicting systematic ensemble median residuals."""

    FEATURE_NAMES = [
        "step_norm",
        "step_norm_sq",
        "p50_base",
        "pred_gap",
        "disagreement",
        "net_load",
        "wind_fc",
        "p_spike_high",
        "p_spike_low",
        "quarter_in_hour",
    ]

    def __init__(self, alpha: float = 100.0, shrinkage: float = 0.5, cap_percentile: float = 95.0):
        self.alpha = alpha
        self.shrinkage = shrinkage
        self.cap_percentile = cap_percentile
        self.scaler = StandardScaler()
        self.model = Ridge(alpha=self.alpha, fit_intercept=True)
        self.cap_val = 50.0  # default fallback cap in EUR/MWh
        self.is_fitted = False

    @classmethod
    def extract_features(cls, df: pd.DataFrame) -> np.ndarray:
        """Extract low-dimensional feature matrix from prediction and fundamentals frame."""
        step = df["step"].to_numpy(dtype=float)
        step_norm = step / 40.0
        step_norm_sq = step_norm ** 2
        p50 = df["p50"].to_numpy(dtype=float)
        spot = df["spot"].to_numpy(dtype=float) if "spot" in df.columns else df["spot_price"].to_numpy(dtype=float)
        pred_gap = p50 - spot

        # Disagreement between Frank and Abdo
        if "p50_frank" in df.columns and "p50_abdo" in df.columns:
            disagreement = np.abs(df["p50_frank"].to_numpy(dtype=float) - df["p50_abdo"].to_numpy(dtype=float))
        else:
            disagreement = np.zeros_like(p50)

        # Fundamentals
        cons = df["cons_fc"].to_numpy(dtype=float) if "cons_fc" in df.columns else np.zeros_like(p50)
        wind = df["wind_fc"].to_numpy(dtype=float) if "wind_fc" in df.columns else np.zeros_like(p50)
        solar = df["solar_fc"].to_numpy(dtype=float) if "solar_fc" in df.columns else np.zeros_like(p50)
        net_load = cons - wind - solar

        p_spike_h = df["p_spike_high"].to_numpy(dtype=float)
        p_spike_l = df["p_spike_low"].to_numpy(dtype=float)
        quarter = ((step - 1) % 4).astype(float)

        feats = np.column_stack([
            step_norm,
            step_norm_sq,
            p50,
            pred_gap,
            disagreement,
            net_load,
            wind,
            p_spike_h,
            p_spike_l,
            quarter,
        ])
        # Impute any missing values with 0
        feats = np.nan_to_num(feats, nan=0.0, posinf=0.0, neginf=0.0)
        return feats

    def fit(self, df_train: pd.DataFrame, actual_imbalance: np.ndarray) -> ResidualCorrector:
        """Fit scaler and ridge regressor on out-of-fold training residuals."""
        p50_base = df_train["p50"].to_numpy(dtype=float)
        residual = actual_imbalance - p50_base

        # Calculate robust cap from training fold only
        self.cap_val = float(np.percentile(np.abs(residual), self.cap_percentile))
        self.cap_val = max(self.cap_val, 20.0)  # at least 20 EUR/MWh cap

        X = self.extract_features(df_train)
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, residual)
        self.is_fitted = True
        return self

    def predict_residual(self, df: pd.DataFrame) -> np.ndarray:
        """Predict expected residual with bounded capping."""
        if not self.is_fitted:
            return np.zeros(len(df), dtype=float)
        X = self.extract_features(df)
        X_scaled = self.scaler.transform(X)
        pred_res = self.model.predict(X_scaled)
        # Cap unusually large predictions
        return np.clip(pred_res, -self.cap_val, self.cap_val)

    def correct_p50(self, df: pd.DataFrame) -> np.ndarray:
        """Apply shrinkage residual correction to baseline P50."""
        p50_base = df["p50"].to_numpy(dtype=float)
        if self.shrinkage == 0.0 or not self.is_fitted:
            return p50_base
        pred_res = self.predict_residual(df)
        return p50_base + self.shrinkage * pred_res

