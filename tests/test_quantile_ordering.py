"""Unit tests for unified postprocessing and quantile ordering."""
import numpy as np
import pandas as pd
import pytest

from src.backtest.postprocess import postprocess_forecasts, PostProcessingError


def make_dummy_forecast(n=5):
    origins = [f"2026-10-05T{h:02d}:00:00Z" for h in range(n)]
    deliveries = [f"2026-10-05T{h:02d}:15:00Z" for h in range(n)]
    cutoffs = [f"2026-10-05T{h:02d}:00:00Z" for h in range(n)]
    return pd.DataFrame({
        "forecast_origin_utc": origins,
        "delivery_start_utc": deliveries,
        "step": list(range(1, n + 1)),
        "p10": [20.0, 30.0, 40.0, 50.0, 60.0],
        "p50": [25.0, 35.0, 45.0, 55.0, 65.0],
        "p90": [30.0, 40.0, 50.0, 60.0, 70.0],
        "p_up": [0.6, 0.4, 0.3, 0.8, 0.5],
        "p_down": [0.3, 0.5, 0.6, 0.1, 0.4],
        "p_none": [0.1, 0.1, 0.1, 0.1, 0.1],
        "p_spike_high": [0.1, 0.05, 0.05, 0.2, 0.1],
        "p_spike_low": [0.05, 0.1, 0.1, 0.0, 0.05],
        "data_cutoff_utc": cutoffs,
        "top_drivers": ["spot;wind_fc"] * n,
    })


def test_minimal_displacement_preserves_valid():
    df = make_dummy_forecast()
    out = postprocess_forecasts(df)
    assert np.allclose(out["p10"], df["p10"])
    assert np.allclose(out["p50"], df["p50"])
    assert np.allclose(out["p90"], df["p90"])


def test_quantile_crossing_projection():
    df = make_dummy_forecast()
    # Force p10 > p50 and p90 < p50
    df.loc[0, "p10"] = 30.0  # p50 is 25.0
    df.loc[1, "p90"] = 32.0  # p50 is 35.0
    out = postprocess_forecasts(df)

    # p50 should not move
    assert out.loc[0, "p50"] == 25.0
    assert out.loc[0, "p10"] == 25.0  # clipped to p50

    assert out.loc[1, "p50"] == 35.0
    assert out.loc[1, "p90"] == 35.0  # clipped to p50


def test_kolmogorov_spike_envelope_enforced():
    df = make_dummy_forecast()
    # Violation: p_spike_high > p_up with normalized directions summing to 1.0
    df.loc[0, "p_up"] = 0.10
    df.loc[0, "p_down"] = 0.80
    df.loc[0, "p_none"] = 0.10
    df.loc[0, "p_spike_high"] = 0.25
    out = postprocess_forecasts(df)
    assert np.isclose(out.loc[0, "p_spike_high"], 0.10), "Spike high must be bounded by p_up"


def test_causality_violation_raises():
    df = make_dummy_forecast()
    # Cutoff in the future
    df.loc[0, "data_cutoff_utc"] = "2026-10-05T01:00:00Z"  # origin is 00:00:00Z
    with pytest.raises(PostProcessingError, match="Causality violation"):
        postprocess_forecasts(df)


def test_empty_top_drivers_raises():
    df = make_dummy_forecast()
    df.loc[0, "top_drivers"] = ""
    with pytest.raises(PostProcessingError, match="Found 1 empty/NaN top_drivers"):
        postprocess_forecasts(df)
