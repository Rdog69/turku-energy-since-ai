"""FastAPI situational room backend for Turku Energia trader dashboard."""

from pathlib import Path
from typing import Dict, List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

WORKSPACE_DIR = Path(__file__).resolve().parents[1]
COMPOSITE_FILE = WORKSPACE_DIR / "forecast_backtest.csv"
if not COMPOSITE_FILE.exists():
    COMPOSITE_FILE = WORKSPACE_DIR / "results" / "composite" / "forecast_backtest.csv"
if not COMPOSITE_FILE.exists():
    COMPOSITE_FILE = WORKSPACE_DIR / "results" / "mixture" / "forecast_backtest.csv"

app = FastAPI(
    title="Turku Energia Imbalance Price Situation Room API",
    description="Serves 10-hour probabilistic forecasts, physical SHAP drivers, and operational suggestions.",
    version="1.0.0",
)

# Enable CORS for frontend applications (Lovable, React, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory cached forecast table
_forecast_cache = None


def get_forecast_data() -> pd.DataFrame:
    global _forecast_cache
    if _forecast_cache is None:
        if not COMPOSITE_FILE.exists():
            raise FileNotFoundError(f"Forecast file not found at {COMPOSITE_FILE}")
        df = pd.read_csv(COMPOSITE_FILE)
        df["forecast_origin_utc"] = df["forecast_origin_utc"].astype(str)
        _forecast_cache = df
    return _forecast_cache


@app.get("/health")
def health_check():
    return {"status": "ok", "forecast_file": str(COMPOSITE_FILE.relative_to(WORKSPACE_DIR))}


@app.get("/origins", response_model=List[str])
def list_origins():
    """Return all available forecast origins for time-travel slider."""
    df = get_forecast_data()
    origins = df["forecast_origin_utc"].unique().tolist()
    return sorted(origins)


@app.get("/forecast/{origin_utc}")
def get_origin_forecast(origin_utc: str):
    """Retrieve full 10-hour situational forecast for a specific origin."""
    df = get_forecast_data()
    sub = df[df["forecast_origin_utc"] == origin_utc].sort_values("step").reset_index(drop=True)

    if sub.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Forecast origin '{origin_utc}' not found. Check /origins for available timestamps.",
        )

    steps = []
    high_spike_steps = []
    low_spike_steps = []
    conflicting_signals = []

    for _, row in sub.iterrows():
        step = int(row["step"])
        p50 = float(row["p50"])
        p10 = float(row["p10"])
        p90 = float(row["p90"])
        p_up = float(row["p_up"])
        p_down = float(row["p_down"])
        p_spike_h = float(row["p_spike_high"])
        p_spike_l = float(row["p_spike_low"])

        # Check for wide spreads / conflicting signals
        if (p90 - p10) > 120.0:
            conflicting_signals.append({
                "step": step,
                "type": "EXTREME_UNCERTAINTY",
                "message": f"Step {step}: Exceptionally wide P10–P90 spread ({p90 - p10:.1f} €/MWh). High tail variance.",
            })

        if p_spike_h >= 0.20:
            high_spike_steps.append({"step": step, "delivery": row["delivery_start_utc"], "prob": p_spike_h})
        if p_spike_l >= 0.20:
            low_spike_steps.append({"step": step, "delivery": row["delivery_start_utc"], "prob": p_spike_l})

        # Parse top drivers
        top_drivers_raw = str(row.get("top_drivers", ""))
        drivers = [d.strip() for d in top_drivers_raw.split(";") if d.strip()]

        steps.append({
            "step": step,
            "delivery_start_utc": row["delivery_start_utc"],
            "p10": p10,
            "p50": p50,
            "p90": p90,
            "p_up": p_up,
            "p_down": p_down,
            "p_none": float(row["p_none"]),
            "p_spike_high": p_spike_h,
            "p_spike_low": p_spike_l,
            "top_drivers": drivers,
        })

    # Operational plant recommendations
    suggestions = []
    if high_spike_steps:
        top_h = max(high_spike_steps, key=lambda x: x["prob"])
        suggestions.append({
            "target": "Naantali CHP Production",
            "action": "REVIEW_UPWARD_FLEXIBILITY",
            "message": f"High-spike risk ({top_h['prob']:.1%}) at step {top_h['step']} ({top_h['delivery']}). Review capacity commitments and prepare fast-ramping reserves.",
        })
    if low_spike_steps:
        top_l = max(low_spike_steps, key=lambda x: x["prob"])
        suggestions.append({
            "target": "Electric Boilers & Heat Pumps",
            "action": "ABSORB_SURPLUS_POWER",
            "message": f"Negative / low imbalance risk ({top_l['prob']:.1%}) at step {top_l['step']} ({top_l['delivery']}). Consider ramping up district heat power-to-heat assets to avoid downward imbalance penalties.",
        })

    return {
        "forecast_origin_utc": origin_utc,
        "data_cutoff_utc": str(sub.loc[0, "data_cutoff_utc"]) if "data_cutoff_utc" in sub.columns else origin_utc,
        "summary": {
            "max_p50": round(float(sub["p50"].max()), 2),
            "min_p50": round(float(sub["p50"].min()), 2),
            "high_spike_periods": len(high_spike_steps),
            "low_spike_periods": len(low_spike_steps),
        },
        "operational_suggestions": suggestions,
        "conflicting_signals": conflicting_signals,
        "steps": steps,
    }


@app.get("/metrics")
def get_validation_metrics():
    """Return model performance summary compared to the official baseline."""
    return {
        "baseline": {
            "mae": 66.20,
            "mean_pinball": 24.18,
            "mean_spike_brier": 0.1132,
            "direction_brier": 0.4509,
        },
        "grand_champion_ensemble": {
            "mae": 40.95,
            "mean_pinball": 11.77,
            "mean_spike_brier": 0.0865,
            "direction_brier": 0.3818,
        },
        "improvements": {
            "mae_reduction_pct": 38.1,
            "pinball_loss_reduction_pct": 51.3,
            "spike_brier_improvement_pct": 23.6,
            "direction_brier_improvement_pct": 15.3,
        },
    }

