"""TreeSHAP feature attribution engine and situational explanation builder."""

from typing import Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
import shap

from src.features.build_features import FEATURE_COLS


class ShapDriverExplainer:
    def __init__(self, model, feature_names: List[str] = FEATURE_COLS):
        self.model = model
        self.feature_names = feature_names
        # LightGBM booster explainer
        booster = model.booster_ if hasattr(model, "booster_") else model
        self.explainer = shap.TreeExplainer(booster)

    def explain(self, X: pd.DataFrame) -> np.ndarray:
        """Compute TreeSHAP values matrix for X."""
        X_vals = X[self.feature_names]
        shap_vals = self.explainer.shap_values(X_vals)
        # For classifiers, shap_values can be a list of arrays per class
        if isinstance(shap_vals, list):
            shap_vals = shap_vals[1] if len(shap_vals) > 1 else shap_vals[0]
        elif hasattr(shap_vals, "values"):
            shap_vals = shap_vals.values
        return shap_vals

    def get_top_drivers_column(self, X: pd.DataFrame, top_k: int = 3) -> List[str]:
        """Compute semicolon-separated top-k feature names by absolute SHAP magnitude."""
        shap_vals = self.explain(X)
        top_drivers_list = []

        abs_shap = np.abs(shap_vals)
        for i in range(len(X)):
            top_indices = np.argsort(abs_shap[i])[::-1][:top_k]
            names = [self.feature_names[idx] for idx in top_indices]
            top_drivers_list.append(";".join(names))

        return top_drivers_list

    def build_origin_explanation_payload(
        self,
        origin_utc: str,
        forecast_df: pd.DataFrame,
        features_df: pd.DataFrame,
    ) -> Dict:
        """Construct structured situational room payload for a single forecast origin."""
        origin_ts = pd.to_datetime(origin_utc, utc=True)
        f_mask = pd.to_datetime(forecast_df["forecast_origin_utc"], utc=True) == origin_ts
        feat_mask = pd.to_datetime(features_df["forecast_origin_utc"], utc=True) == origin_ts

        f_sub = forecast_df.loc[f_mask].sort_values("step").reset_index(drop=True)
        feat_sub = features_df.loc[feat_mask].sort_values("step").reset_index(drop=True)

        if f_sub.empty:
            raise ValueError(f"Origin {origin_utc} not found in forecast data.")

        shap_vals = self.explain(feat_sub)

        steps_payload = []
        high_spike_steps = []
        low_spike_steps = []
        conflicting_signals = []

        for idx, row in f_sub.iterrows():
            step = int(row["step"])
            delivery = row["delivery_start_utc"]
            p50 = float(row["p50"])
            p10 = float(row["p10"])
            p90 = float(row["p90"])
            p_up = float(row["p_up"])
            p_down = float(row["p_down"])
            p_spike_h = float(row["p_spike_high"])
            p_spike_l = float(row["p_spike_low"])
            spot = float(feat_sub.loc[idx, "spot_price"])

            # Top 3 signed drivers for this step
            row_shap = shap_vals[idx]
            top_idxs = np.argsort(np.abs(row_shap))[::-1][:3]
            drivers = [
                {
                    "feature": self.feature_names[j],
                    "contribution_eur_mwh": round(float(row_shap[j]), 2),
                    "feature_value": round(float(feat_sub.loc[idx, self.feature_names[j]]), 2)
                    if pd.notna(feat_sub.loc[idx, self.feature_names[j]]) else None,
                }
                for j in top_idxs
            ]

            # Detect exceptional spike risk
            if p_spike_h >= 0.20:
                high_spike_steps.append({"step": step, "delivery": delivery, "prob": p_spike_h})
            if p_spike_l >= 0.20:
                low_spike_steps.append({"step": step, "delivery": delivery, "prob": p_spike_l})

            # Detect conflicting signals
            # 1. Direction classifier says UP (> 0.60), but P50 is below spot
            if p_up > 0.60 and p50 < spot - 5.0:
                conflicting_signals.append({
                    "step": step,
                    "type": "DIRECTION_PRICE_DIVERGENCE",
                    "description": f"Step {step}: Up-regulation probability is {p_up:.1%}, but P50 forecast ({p50:.1f} €/MWh) is below spot ({spot:.1f} €/MWh).",
                })
            # 2. Unusually wide quantile spread (> 120 EUR/MWh)
            if (p90 - p10) > 120.0:
                conflicting_signals.append({
                    "step": step,
                    "type": "EXTREME_UNCERTAINTY",
                    "description": f"Step {step}: P10–P90 spread is exceptionally wide ({p90 - p10:.1f} €/MWh). Expert review recommended.",
                })

            steps_payload.append({
                "step": step,
                "delivery_start_utc": delivery,
                "spot_price": spot,
                "p10": p10,
                "p50": p50,
                "p90": p90,
                "expected_gap": round(p50 - spot, 2),
                "p_up": p_up,
                "p_down": p_down,
                "p_spike_high": p_spike_h,
                "p_spike_low": p_spike_l,
                "top_drivers": drivers,
            })

        # Operational suggestion for trader / plant manager
        suggestions = []
        if high_spike_steps:
            max_spike = max(high_spike_steps, key=lambda x: x["prob"])
            suggestions.append(
                f"High-spike alert at step {max_spike['step']} ({max_spike['delivery']}) with {max_spike['prob']:.1%} risk. "
                "Review Naantali production plan for upward flexibility; consider holding uncommitted thermal capacity."
            )
        if low_spike_steps:
            max_low = max(low_spike_steps, key=lambda x: x["prob"])
            suggestions.append(
                f"Negative price / down-regulation risk at step {max_low['step']} ({max_low['delivery']}) with {max_low['prob']:.1%} probability. "
                "Review electric boilers / heat pumps to absorb cheap power and avoid downward penalty."
            )

        payload = {
            "forecast_origin_utc": origin_utc,
            "data_cutoff_utc": str(f_sub.loc[0, "data_cutoff_utc"]),
            "summary": {
                "max_p50": round(float(f_sub["p50"].max()), 2),
                "min_p50": round(float(f_sub["p50"].min()), 2),
                "avg_gap_to_spot": round(float((f_sub["p50"] - feat_sub["spot_price"]).mean()), 2),
                "high_spike_count": len(high_spike_steps),
                "low_spike_count": len(low_spike_steps),
            },
            "suggestions_for_review": suggestions,
            "conflicting_signals": conflicting_signals,
            "steps": steps_payload,
        }

        return payload
