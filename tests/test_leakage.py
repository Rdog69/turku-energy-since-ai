"""Unit tests for anti-leakage filtering."""

import pandas as pd
import pytest
from src.data.available_at import available_at, assert_no_leakage


@pytest.fixture
def sample_long_data():
    return pd.DataFrame({
        "series_id": ["fi_imbalance_price", "fi_imbalance_price", "fi_wind_fc_da", "fi_imbalance_price"],
        "timestamp_utc": pd.to_datetime([
            "2026-10-05T04:45:00Z",
            "2026-10-05T05:00:00Z",
            "2026-10-05T08:00:00Z",
            "2026-10-05T06:00:00Z",
        ], utc=True),
        "first_usable_origin_utc": pd.to_datetime([
            "2026-10-05T06:00:00Z",  # usable at 06:00
            "2026-10-05T06:00:00Z",  # usable at 06:00
            "2026-10-04T13:00:00Z",  # day-ahead forecast, already usable at 06:00
            "2026-10-05T07:00:00Z",  # NOT usable at 06:00 (future data)
        ], utc=True),
        "value": [50.0, 55.0, 1200.0, 80.0],
    })


def test_available_at_filters_correctly(sample_long_data):
    origin = "2026-10-05T06:00:00Z"
    wide = available_at(sample_long_data, origin, as_wide=True)

    # The row with first_usable_origin_utc=2026-10-05T07:00:00Z must NOT be in the result
    assert len(wide) == 3
    assert wide.index.max() == pd.Timestamp("2026-10-05T08:00:00Z")  # future day-ahead delivery is allowed

    # Check long output
    long = available_at(sample_long_data, origin, as_wide=False)
    assert len(long) == 3
    assert (long["first_usable_origin_utc"] <= pd.Timestamp(origin)).all()


def test_assert_no_leakage_detects_leak(sample_long_data):
    origin = "2026-10-05T06:00:00Z"
    # Testing against raw sample_long_data should fail because row 3 is usable at 07:00
    with pytest.raises(AssertionError, match="Leakage check failed"):
        assert_no_leakage(sample_long_data, origin)

    # Filtered data should pass
    filtered = sample_long_data[sample_long_data["first_usable_origin_utc"] <= pd.Timestamp(origin)]
    assert_no_leakage(filtered, origin)


def test_training_window_compliance():
    """Verify that training data strictly respects the hackathon window: 1 June - 4 Oct 2026."""
    from src.data.load import load_long_all
    from src.data.availability import build_index
    from src.backtest.run import training_table
    from src import config

    long = load_long_all()
    index = build_index(long)
    train = training_table(long, index, config.TRAIN_CUTOFF)

    # Hard asserts: 100% of training data must be within 1 June - 4 Oct 2026
    assert train["delivery"].min() >= pd.Timestamp("2026-06-01T00:00:00Z"), "Training data starts before 1 June 2026!"
    assert train["y_first_usable"].max() <= pd.Timestamp("2026-10-04T21:00:00Z"), "Training data leaks into test period!"
    assert train["origin"].max() <= pd.Timestamp("2026-10-04T21:00:00Z"), "Training origin leaks into test period!"


def test_submission_file_guard():
    """Verify that root forecast_backtest.csv strictly satisfies all hackathon submission requirements."""
    from pathlib import Path
    import numpy as np

    root = Path(__file__).resolve().parents[1]
    sub_path = root / "forecast_backtest.csv"
    assert sub_path.exists(), "forecast_backtest.csv missing!"
    df = pd.read_csv(sub_path)

    # 1. Row count & schema
    assert len(df) == 26920, f"Expected 26920 rows, got {len(df)}"
    assert "top_drivers" in df.columns, "Missing top_drivers column!"

    # 2. Monotonicity
    assert (df["p10"] <= df["p50"]).all(), "Monotonicity violated: p10 > p50"
    assert (df["p50"] <= df["p90"]).all(), "Monotonicity violated: p50 > p90"

    # 3. Probabilities
    dir_sum = df["p_up"] + df["p_down"] + df["p_none"]
    assert np.allclose(dir_sum, 1.0, atol=1e-4), "Direction probabilities do not sum to 1.0"
    assert (df["p_spike_high"] + df["p_spike_low"] <= 1.0001).all(), "Spike probabilities sum > 1.0"

    # 4. Explainability: 100% non-empty TreeSHAP drivers
    assert not df["top_drivers"].isna().any(), "NaN top_drivers found!"
    assert not df["top_drivers"].str.strip().eq("").any(), "Empty top_drivers string found!"

    # 5. Anti-leakage / Causality
    assert (pd.to_datetime(df["data_cutoff_utc"]) <= pd.to_datetime(df["forecast_origin_utc"])).all(), "Causality violated: cutoff > origin!"



