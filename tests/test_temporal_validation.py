"""Unit tests for temporal validation framework."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.backtest.temporal_validation import (
    compute_pinball,
    compute_brier_2class,
    compute_brier_3class,
    evaluate_predictions,
    HORIZON_BANDS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
ACTUALS_VAL = REPO_ROOT / "Dataset" / "starter_package_v1" / "data" / "actuals_validation.csv"
SAMPLE_VAL_SUB = REPO_ROOT / "results" / "validation" / "forecast_backtest.csv"


def test_pinball_loss_exact():
    y = np.array([10.0, 20.0])
    yhat = np.array([12.0, 15.0])
    # diff: [-2.0, 5.0]
    # q=0.5: 0.5*max(d, -d) = 0.5*(2 + 5)/2 = 1.75
    pb = compute_pinball(y, yhat, 0.50)
    assert np.isclose(pb, 1.75)


def test_brier_exact():
    p = np.array([0.8, 0.1])
    o = np.array([1.0, 0.0])
    b = compute_brier_2class(p, o)
    # (0.8 - 1)^2 = 0.04; (0.1 - 0)^2 = 0.01; mean = 0.025
    assert np.isclose(b, 0.025)


def test_horizon_bands_coverage():
    steps = set()
    for s0, s1 in HORIZON_BANDS.values():
        steps.update(range(s0, s1 + 1))
    assert steps == set(range(1, 41)), "Horizon bands must span exactly steps 1-40 without gaps"


@pytest.mark.skipif(not SAMPLE_VAL_SUB.exists(), reason="Validation file not present")
def test_evaluate_predictions_runs():
    df_pred = pd.read_csv(SAMPLE_VAL_SUB)
    res = evaluate_predictions(df_pred, ACTUALS_VAL, period_name="validation")
    assert "overall" in res
    assert "horizons" in res
    assert "weekly" in res
    assert "points" in res
    assert res["overall"]["mae_p50"] > 0
    assert 78.0 <= res["overall"]["coverage"] <= 82.0
