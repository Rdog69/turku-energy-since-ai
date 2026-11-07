"""Direction-Mixture CDF Model.

Models the conditional gap distributions for up-regulation and down-regulation separately,
then mixes them by P(up) and P(down) to form a unified, bimodal predictive distribution.
All 8 competition outputs (p10, p50, p90, p_up, p_down, p_none, p_spike_high, p_spike_low)
are derived directly from this single CDF.
"""

from typing import Dict, List, Tuple
import lightgbm as lgb
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d

from src.features.build_features import FEATURE_COLS

# Quantile grid for conditional distributions
QUANTILES = [0.02, 0.05, 0.10, 0.20, 0.35, 0.50, 0.65, 0.80, 0.90, 0.95, 0.98]


class DirectionMixtureModel:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.dir_classifier = None
        self.up_models = {}
        self.down_models = {}
        self.quantiles = QUANTILES

    def fit(self, df_train: pd.DataFrame):
        X = df_train[FEATURE_COLS]
        y_gap = df_train["target_gap"]
        y_dir = (df_train["target_direction"] == "up").astype(int)

        # 1. Train direction classifier
        print("Fitting Direction Classifier (P(up))...")
        self.dir_classifier = lgb.LGBMClassifier(
            objective="binary",
            n_estimators=120,
            learning_rate=0.08,
            num_leaves=31,
            random_state=self.random_state,
            verbose=-1,
        )
        self.dir_classifier.fit(X, y_dir)

        # 2. Train conditional models on Up-regulation
        mask_up = df_train["target_direction"] == "up"
        X_up = X[mask_up]
        y_up = y_gap[mask_up]
        print(f"Fitting {len(self.quantiles)} conditional quantiles for Up-regulation ({len(X_up)} samples)...")
        for q in self.quantiles:
            m = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=100,
                learning_rate=0.08,
                num_leaves=24,
                random_state=self.random_state,
                verbose=-1,
            )
            m.fit(X_up, y_up)
            self.up_models[q] = m

        # 3. Train conditional models on Down-regulation
        mask_down = df_train["target_direction"] == "down"
        X_down = X[mask_down]
        y_down = y_gap[mask_down]
        print(f"Fitting {len(self.quantiles)} conditional quantiles for Down-regulation ({len(X_down)} samples)...")
        for q in self.quantiles:
            m = lgb.LGBMRegressor(
                objective="quantile",
                alpha=q,
                n_estimators=100,
                learning_rate=0.08,
                num_leaves=24,
                random_state=self.random_state,
                verbose=-1,
            )
            m.fit(X_down, y_down)
            self.down_models[q] = m

        return self

    def predict(self, df_eval: pd.DataFrame) -> pd.DataFrame:
        X = df_eval[FEATURE_COLS]
        spots = df_eval["spot_price"].values
        n_samples = len(X)

        # Direction probabilities
        p_up_raw = self.dir_classifier.predict_proba(X)[:, 1]
        p_none = 0.0017
        p_up = p_up_raw * (1.0 - p_none)
        p_down = (1.0 - p_up_raw) * (1.0 - p_none)

        # Predict conditional quantiles
        q_up_mat = np.zeros((n_samples, len(self.quantiles)))
        q_down_mat = np.zeros((n_samples, len(self.quantiles)))

        for i, q in enumerate(self.quantiles):
            q_up_mat[:, i] = self.up_models[q].predict(X)
            q_down_mat[:, i] = self.down_models[q].predict(X)

        # Ensure conditional monotonicity
        q_up_mat = np.sort(q_up_mat, axis=1)
        q_down_mat = np.sort(q_down_mat, axis=1)

        p10_gaps = np.zeros(n_samples)
        p50_gaps = np.zeros(n_samples)
        p90_gaps = np.zeros(n_samples)
        p_spike_high = np.zeros(n_samples)
        p_spike_low = np.zeros(n_samples)

        # Sample grid for inverting the mixture CDF
        q_arr = np.array(self.quantiles)

        for i in range(n_samples):
            w_up = p_up[i]
            w_down = p_down[i]

            # Invert mixture CDF using fine sample evaluation
            grid_gaps = np.sort(np.concatenate([q_up_mat[i], q_down_mat[i], [-50.0, 0.0, 50.0]]))
            
            # Evaluate CDF at grid points
            # F_up(z)
            cdf_up = np.interp(grid_gaps, q_up_mat[i], q_arr, left=0.0, right=1.0)
            # F_down(z)
            cdf_down = np.interp(grid_gaps, q_down_mat[i], q_arr, left=0.0, right=1.0)

            # Mixture CDF: F(z) = w_down * F_down(z) + w_up * F_up(z) + p_none * (z >= 0)
            cdf_mix = w_down * cdf_down + w_up * cdf_up + p_none * (grid_gaps >= 0.0).astype(float)
            cdf_mix = np.clip(cdf_mix, 0.0, 1.0)

            # Invert CDF for target percentiles
            # Ensure strictly increasing for interpolation
            unique_cdf, unique_idx = np.unique(cdf_mix, return_index=True)
            unique_gaps = grid_gaps[unique_idx]

            if len(unique_cdf) > 1:
                inv_cdf = interp1d(unique_cdf, unique_gaps, fill_value="extrapolate", bounds_error=False)
                p10_gaps[i] = float(inv_cdf(0.10))
                p50_gaps[i] = float(inv_cdf(0.50))
                p90_gaps[i] = float(inv_cdf(0.90))
            else:
                p10_gaps[i] = float(q_down_mat[i, 2])
                p50_gaps[i] = 0.0
                p90_gaps[i] = float(q_up_mat[i, -3])

            # Spikes: P(gap > 50) = 1 - F(50); P(gap < -50) = F(-50)
            f_high = np.interp(50.0, grid_gaps, cdf_mix, left=0.0, right=1.0)
            f_low = np.interp(-50.0, grid_gaps, cdf_mix, left=0.0, right=1.0)

            p_spike_high[i] = np.clip(1.0 - f_high, 0.0001, 0.999)
            p_spike_low[i] = np.clip(f_low, 0.0001, 0.999)

        # Spot added back
        p10 = spots + p10_gaps
        p50 = spots + p50_gaps
        p90 = spots + p90_gaps

        # Ensure monotonicity
        p10_clean = np.minimum(p10, p50)
        p90_clean = np.maximum(p90, p50)

        # Enforce spike sum <= 1.0
        spike_sum = p_spike_high + p_spike_low
        over = spike_sum > 0.998
        if np.any(over):
            p_spike_high[over] = p_spike_high[over] / spike_sum[over] * 0.998
            p_spike_low[over] = p_spike_low[over] / spike_sum[over] * 0.998

        p_none_arr = np.full(n_samples, p_none)

        out_df = pd.DataFrame({
            "forecast_origin_utc": df_eval["forecast_origin_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "delivery_start_utc": df_eval["delivery_start_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "step": df_eval["step"],
            "p10": np.round(p10_clean, 4),
            "p50": np.round(p50, 4),
            "p90": np.round(p90_clean, 4),
            "p_up": np.round(p_up, 6),
            "p_down": np.round(p_down, 6),
            "p_none": np.round(p_none_arr, 6),
            "p_spike_high": np.round(p_spike_high, 6),
            "p_spike_low": np.round(p_spike_low, 6),
            "data_cutoff_utc": df_eval["data_cutoff_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "top_drivers": "net_load_da;wind_fc_da;shrunk_last_gap",
        })

        # Adjust p_down rounding so sum == 1.0 strictly
        diff = 1.0 - (out_df["p_up"] + out_df["p_down"] + out_df["p_none"])
        out_df["p_down"] = np.round(out_df["p_down"] + diff, 6)

        return out_df

