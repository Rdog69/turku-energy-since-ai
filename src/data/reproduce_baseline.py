"""Reproduce official baseline forecast on the validation set and verify scoring."""

import subprocess
import sys
from pathlib import Path

# Ensure root workspace is in sys.path
WORKSPACE_DIR = Path(__file__).resolve().parents[2]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

import numpy as np
import pandas as pd

from src.data.loader import (
    DATA_DIR,
    STARTER_DIR,
    load_inputs,
    load_spot,
    to_utc,
)
from src.data.available_at import available_at

OUTPUT_DIR = WORKSPACE_DIR / "baseline_output" / "validation"
HORIZON_STEPS = 40
STEP_OFFSETS = pd.to_timedelta(np.arange(HORIZON_STEPS) * 15, unit="min")
SPIKE_MARGIN = 50.0
VALIDATION_FIRST_ORIGIN = pd.Timestamp("2026-09-06T21:00:00Z")
VALIDATION_START_DATE = "2026-09-07"
VALIDATION_END_DATE = "2026-10-04"

IMBALANCE = "fi_imbalance_price"
DIRECTION = "fi_mfrr_direction"


def persistence_at(imbalance_df: pd.DataFrame, origin: pd.Timestamp):
    """Latest imbalance price legally usable at origin."""
    origin_utc = to_utc(origin)
    ts = imbalance_df["timestamp_utc"]
    hi = ts.searchsorted(origin_utc, side="right")
    part = imbalance_df.iloc[:hi]
    wide = available_at(part, origin_utc, as_wide=True)
    if IMBALANCE in wide.columns and wide[IMBALANCE].notna().any():
        usable = wide[IMBALANCE].dropna()
        return float(usable.iloc[-1]), usable.index[-1]
    return None, None


def calibrate_baseline(inputs: pd.DataFrame, spot: pd.DataFrame, first_origin: pd.Timestamp):
    """Calculate error quantiles and baseline probabilities on pre-validation history."""
    limit = to_utc(first_origin)
    imbalance = inputs.loc[inputs["series_id"] == IMBALANCE].sort_values("timestamp_utc").reset_index(drop=True)
    known = imbalance.loc[imbalance["first_usable_origin_utc"] <= limit]
    target = known.set_index("timestamp_utc")["value"]

    errors = []
    first_hour = imbalance["timestamp_utc"].min().ceil("h")
    for origin in pd.date_range(first_hour, limit, freq="h"):
        val, _ = persistence_at(imbalance, origin)
        if val is None:
            continue
        deliveries = origin + STEP_OFFSETS
        actual = target.reindex(deliveries).to_numpy(dtype=float)
        if np.isnan(actual).all():
            continue
        errors.append(actual - val)

    err = np.vstack(errors)
    q10 = np.nanquantile(err, 0.10, axis=0)
    q90 = np.nanquantile(err, 0.90, axis=0)

    # Direction base rates
    direction = inputs.loc[
        (inputs["series_id"] == DIRECTION)
        & (inputs["first_usable_origin_utc"] <= limit)
        & inputs["value"].notna()
    ]
    p_up = round(float((direction["value"] == 1).mean()), 6)
    p_down = round(float((direction["value"] == -1).mean()), 6)
    p_none = round(1.0 - p_up - p_down, 6)

    # Spike base rates
    if spot is not None and not spot.empty:
        s = spot.loc[spot["first_usable_origin_utc"] <= limit, ["timestamp_utc", "value"]]
        both = known[["timestamp_utc", "value"]].merge(s, on="timestamp_utc", suffixes=("_imb", "_spot"))
        both = both.dropna(subset=["value_imb", "value_spot"])
        p_high = round(float((both["value_imb"] > both["value_spot"] + SPIKE_MARGIN).mean()), 6)
        p_low = round(float((both["value_imb"] < both["value_spot"] - SPIKE_MARGIN).mean()), 6)
    else:
        p_high = p_low = 0.0

    return {
        "q10": q10,
        "q90": q90,
        "p_up": p_up,
        "p_down": p_down,
        "p_none": p_none,
        "p_spike_high": p_high,
        "p_spike_low": p_low,
    }


def generate_baseline(output_dir: Path = OUTPUT_DIR) -> Path:
    """Generate baseline validation template and predictions."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate template via make_templates.py
    cmd_make = [
        sys.executable,
        str(STARTER_DIR / "make_templates.py"),
        "--test-start", VALIDATION_START_DATE,
        "--test-end", VALIDATION_END_DATE,
        "--output-dir", str(output_dir),
    ]
    subprocess.run(cmd_make, check=True)

    origins_path = output_dir / "forecast_origins.csv"
    template_path = output_dir / "sample_submission.csv"
    submission_path = output_dir / "forecast_backtest.csv"

    origins = pd.to_datetime(pd.read_csv(origins_path)["forecast_origin_utc"], utc=True)

    print("Loading inputs and spot data...")
    inputs = load_inputs()
    spot = load_spot()

    print("Calibrating baseline...")
    cal = calibrate_baseline(inputs, spot, VALIDATION_FIRST_ORIGIN)
    imbalance = inputs.loc[inputs["series_id"] == IMBALANCE].sort_values("timestamp_utc").reset_index(drop=True)

    low = np.minimum(cal["q10"], 0.0)
    high = np.maximum(cal["q90"], 0.0)

    print(f"Building baseline predictions across {len(origins)} origins...")
    rows = []
    for origin in origins:
        val, ts = persistence_at(imbalance, origin)
        if val is None:
            raise ValueError(f"No usable imbalance price at {origin}")
        p50 = round(val, 4)
        for i, offset in enumerate(STEP_OFFSETS):
            rows.append({
                "forecast_origin_utc": origin.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "delivery_start_utc": (origin + offset).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "step": i + 1,
                "p10": round(p50 + low[i], 4),
                "p50": p50,
                "p90": round(p50 + high[i], 4),
                "p_up": cal["p_up"],
                "p_down": cal["p_down"],
                "p_none": cal["p_none"],
                "p_spike_high": cal["p_spike_high"],
                "p_spike_low": cal["p_spike_low"],
                "data_cutoff_utc": ts.strftime("%Y-%m-%dT%H:%M:%SZ") if ts is not None else "",
                "top_drivers": "last_imbalance_price",
            })

    df_out = pd.DataFrame(rows)
    template_cols = pd.read_csv(template_path, nrows=0).columns.tolist()
    df_out[template_cols].to_csv(submission_path, index=False, float_format="%.6f", lineterminator="\n")
    print(f"Wrote {len(df_out)} rows to {submission_path}")

    # 2. Validate
    cmd_val = [
        sys.executable,
        str(STARTER_DIR / "validate_submission.py"),
        "--backtest", str(submission_path),
        "--origins", str(origins_path),
    ]
    res_val = subprocess.run(cmd_val, capture_output=True, text=True)
    print(res_val.stdout)
    assert res_val.returncode == 0, f"Validator failed: {res_val.stderr}"

    # 3. Score
    score_dir = output_dir / "score"
    cmd_score = [
        sys.executable,
        str(STARTER_DIR / "score.py"),
        "--actuals", str(DATA_DIR / "actuals_validation.csv"),
        "--submission", str(submission_path),
        "--output-dir", str(score_dir),
    ]
    res_score = subprocess.run(cmd_score, capture_output=True, text=True)
    print(res_score.stdout)

    return submission_path


if __name__ == "__main__":
    generate_baseline()
