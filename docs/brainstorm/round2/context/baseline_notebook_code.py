# # Baseline forecast – Since AI 2026, Turku Energia challenge
# 
# This notebook builds the **naive baseline** of the 10-hour imbalance price forecast and shows how to
# validate and score a submission. It is also a starting point for your own model.
# 
# What the notebook does:
# 
# 1. Defines the helper function `rows_available_at()`, which returns only the data that is usable at a
#    forecast origin (data availability rule, column `first_usable_origin_utc`).
# 2. Builds the baseline for the **validation period** (7 Sep – 4 Oct 2026, Finnish time) and writes it to
#    `baseline_output/validation/forecast_backtest.csv`.
# 3. Runs `validate_submission.py` (format check) and `score.py` (metrics) for the validation period.
# 
# Baseline method:
# 
# - **p50**: the latest imbalance price that is usable at the forecast origin (persistence), the same value
#   for all 40 steps.
# - **p10 / p90**: p50 plus the 10 % and 90 % quantiles of historical persistence errors, separately for
#   each step 1–40.
# - **p_up / p_down / p_none**: historical shares of the dominating mFRR direction (Fingrid 369).
# - **p_spike_high / p_spike_low**: historical shares of exceptionally high and low prices
#   (imbalance price above spot + 50 EUR/MWh or below spot − 50 EUR/MWh).
# - History = only rows and (origin, target) pairs whose `first_usable_origin_utc` is at or before the first
#   forecast origin of the period. Nothing that would not have been known at that time is used.
# 
# The organiser runs the same notebook for the test period to produce the official baseline (the reference
# level B of the points, decision D14). That part runs only when the environment variable
# `SINCEAI_ORGANIZER=1` is set; for teams it is skipped.

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PACKAGE_DIR = Path.cwd()                      # run the notebook in the starter package folder
DATA_DIR = PACKAGE_DIR / "data"
OUTPUT_DIR = PACKAGE_DIR / "baseline_output"

HORIZON_STEPS = 40
STEP_MINUTES = 15
SPIKE_MARGIN = 50.0                           # EUR/MWh, the same as score.py (D5)

VALIDATION_FIRST_ORIGIN = pd.Timestamp("2026-09-06T21:00:00Z")   # 7 Sep 2026 00:00 Finnish time
VALIDATION_DAYS = ("2026-09-07", "2026-10-04")                    # local dates, for make_templates.py
TEST_FIRST_ORIGIN = pd.Timestamp("2026-10-04T21:00:00Z")         # 5 Oct 2026 00:00 Finnish time

ORGANIZER = os.environ.get("SINCEAI_ORGANIZER") == "1"
print(f"Python {sys.version.split()[0]}, pandas {pd.__version__}, numpy {np.__version__}")
print(f"Organizer mode: {ORGANIZER}")

# ## 1. Helper function `rows_available_at()`
# 
# At forecast origin *t* a row may be used only if `first_usable_origin_utc <= t`. The function returns the
# usable rows as a wide table: one row per `timestamp_utc` and one column per `series_id`. The table can
# contain future timestamps, for example day-ahead forecasts that had already been published.

def rows_available_at(data: pd.DataFrame, origin_utc) -> pd.DataFrame:
    """Return the data that is usable at the forecast origin as a wide table.

    data: long-format rows from inputs.csv / inputs.parquet and/or spot_nordpool.csv,
          with timestamp_utc and first_usable_origin_utc parsed as UTC timestamps.
    origin_utc: forecast origin (UTC).

    Keeps only rows with first_usable_origin_utc <= origin_utc and returns one
    row per timestamp_utc and one column per series_id.
    """
    origin = pd.Timestamp(origin_utc)
    origin = origin.tz_localize("UTC") if origin.tzinfo is None else origin.tz_convert("UTC")
    usable = data.loc[data["first_usable_origin_utc"] <= origin]
    wide = usable.pivot(index="timestamp_utc", columns="series_id", values="value")
    return wide.sort_index()

# ## 2. Baseline functions

IMBALANCE = "fi_imbalance_price"
DIRECTION = "fi_mfrr_direction"               # Fingrid 369: 1 up, -1 down, 0 none
STEP_OFFSETS = pd.to_timedelta(np.arange(40) * 15, unit="min")


def to_utc(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    return ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")


def read_long(path: Path) -> pd.DataFrame:
    """Read a long-format data file (parquet or csv) with UTC timestamps."""
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, dtype={"dataset_id": str})
    for col in ("timestamp_utc", "first_usable_origin_utc"):
        df[col] = pd.to_datetime(df[col], utc=True)
    return df


def series(data: pd.DataFrame, series_id: str) -> pd.DataFrame:
    """Rows of one series sorted by timestamp_utc."""
    return data.loc[data["series_id"] == series_id].sort_values("timestamp_utc").reset_index(drop=True)


def persistence_at(imbalance: pd.DataFrame, origin, lookback=pd.Timedelta(days=3)):
    """Latest imbalance price usable at the origin: (value, timestamp_utc) or (None, None).

    imbalance: rows of fi_imbalance_price sorted by timestamp_utc. Only rows with
    timestamp_utc <= origin are passed to rows_available_at() for speed; later rows can never be
    usable at the origin, so the result is the same as with the full data.
    """
    origin = to_utc(origin)
    ts = imbalance["timestamp_utc"]
    lo = ts.searchsorted(origin - lookback)
    hi = ts.searchsorted(origin, side="right")
    for part in (imbalance.iloc[lo:hi], imbalance.iloc[:hi]):
        wide = rows_available_at(part, origin)
        if IMBALANCE in wide and wide[IMBALANCE].notna().any():
            usable = wide[IMBALANCE].dropna()
            return float(usable.iloc[-1]), usable.index[-1]
    return None, None


def calibrate(inputs: pd.DataFrame, spot, first_origin, spike_margin: float = SPIKE_MARGIN,
              horizon_steps: int = HORIZON_STEPS) -> dict:
    """Historical error quantiles and probabilities for the baseline.

    Leakage rule: only rows and (origin, target) pairs whose first_usable_origin_utc is at or
    before first_origin (the first forecast origin of the period) are used. The persistence start
    value of each historical origin is chosen with rows_available_at(), as in the forecast.
    """
    limit = to_utc(first_origin)
    offsets = STEP_OFFSETS[:horizon_steps]
    imbalance = series(inputs, IMBALANCE)
    known = imbalance.loc[imbalance["first_usable_origin_utc"] <= limit]
    target = known.set_index("timestamp_utc")["value"]
    target_fu = known.set_index("timestamp_utc")["first_usable_origin_utc"]

    errors, used_targets = [], set()
    first_hour = imbalance["timestamp_utc"].min().ceil("h")
    for origin in pd.date_range(first_hour, limit, freq="h"):
        value, _ = persistence_at(imbalance, origin)
        if value is None:
            continue
        deliveries = origin + offsets
        actual = target.reindex(deliveries).to_numpy(dtype=float)
        if np.isnan(actual).all():
            continue
        errors.append(actual - value)
        used_targets.update(deliveries[~np.isnan(actual)])
    err = np.vstack(errors)
    q10 = np.nanquantile(err, 0.10, axis=0)
    q90 = np.nanquantile(err, 0.90, axis=0)

    direction = series(inputs, DIRECTION)
    direction = direction.loc[(direction["first_usable_origin_utc"] <= limit) & direction["value"].notna()]
    p_up = round(float((direction["value"] == 1).mean()), 6)
    p_down = round(float((direction["value"] == -1).mean()), 6)
    p_none = round(1.0 - p_up - p_down, 6)

    used_fu = [target_fu.loc[sorted(used_targets)].max(), direction["first_usable_origin_utc"].max()]
    if spot is not None and len(spot):
        s = spot.loc[spot["first_usable_origin_utc"] <= limit, ["timestamp_utc", "value", "first_usable_origin_utc"]]
        both = known[["timestamp_utc", "value"]].merge(s, on="timestamp_utc", suffixes=("_imb", "_spot"))
        both = both.dropna(subset=["value_imb", "value_spot"])
        p_high = round(float((both["value_imb"] > both["value_spot"] + spike_margin).mean()), 6)
        p_low = round(float((both["value_imb"] < both["value_spot"] - spike_margin).mean()), 6)
        n_spike = len(both)
        used_fu.append(both["first_usable_origin_utc"].max())
    else:
        p_high = p_low = 0.0
        n_spike = 0

    return {
        "first_origin": limit, "q10": q10, "q90": q90,
        "p_up": p_up, "p_down": p_down, "p_none": p_none,
        "p_spike_high": p_high, "p_spike_low": p_low, "spot_available": n_spike > 0,
        "n_origins": len(errors), "n_error_pairs": int(np.isfinite(err).sum()),
        "n_direction_rows": len(direction), "n_spike_rows": n_spike,
        "last_target_used": max(used_targets), "max_first_usable_used": max(used_fu),
    }


def build_forecast(inputs: pd.DataFrame, cal: dict, origins: pd.Series,
                   horizon_steps: int = HORIZON_STEPS) -> pd.DataFrame:
    """Baseline submission rows for the given forecast origins (UTC)."""
    imbalance = series(inputs, IMBALANCE)
    offsets = STEP_OFFSETS[:horizon_steps]
    low = np.minimum(cal["q10"][:horizon_steps], 0.0)    # keeps p10 <= p50
    high = np.maximum(cal["q90"][:horizon_steps], 0.0)   # keeps p50 <= p90
    parts = []
    for origin in origins:
        value, ts = persistence_at(imbalance, origin)
        if value is None:
            raise ValueError(f"no usable imbalance price at {origin}")
        p50 = round(value, 4)
        parts.append(pd.DataFrame({
            "forecast_origin_utc": origin, "delivery_start_utc": origin + offsets,
            "step": np.arange(1, horizon_steps + 1),
            "p10": np.round(p50 + low, 4), "p50": p50, "p90": np.round(p50 + high, 4),
            "p_up": cal["p_up"], "p_down": cal["p_down"], "p_none": cal["p_none"],
            "p_spike_high": cal["p_spike_high"], "p_spike_low": cal["p_spike_low"],
            "data_cutoff_utc": ts, "top_drivers": "last_imbalance_price",
        }))
    return pd.concat(parts, ignore_index=True)


def write_submission(df: pd.DataFrame, path: Path, template: Path) -> None:
    """Write the submission with the column order of the template and UTC timestamps ending in Z."""
    columns = pd.read_csv(template, nrows=0).columns.tolist()
    out = df.copy()
    for col in ("forecast_origin_utc", "delivery_start_utc", "data_cutoff_utc"):
        out[col] = pd.to_datetime(out[col], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    path.parent.mkdir(parents=True, exist_ok=True)
    out[columns].to_csv(path, index=False, float_format="%.6f", lineterminator="\n", encoding="utf-8")


def read_origins(path: Path) -> pd.Series:
    return pd.to_datetime(pd.read_csv(path)["forecast_origin_utc"], utc=True)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(*args: str) -> int:
    """Run a package script with relative paths and print its output."""
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}   # the same encoding on Windows, macOS and Linux
    result = subprocess.run([sys.executable, *args], cwd=PACKAGE_DIR, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", env=env)
    print(result.stdout.rstrip())
    if result.stderr.strip():
        print(result.stderr.rstrip())
    return result.returncode


def describe_calibration(cal: dict) -> None:
    print(f"Calibration limit (first origin of the period): {cal['first_origin']:%Y-%m-%dT%H:%M:%SZ}")
    print(f"  historical origins {cal['n_origins']}, error pairs {cal['n_error_pairs']}, "
          f"last target used {cal['last_target_used']:%Y-%m-%dT%H:%M:%SZ}")
    print(f"  latest first_usable_origin_utc used: {cal['max_first_usable_used']:%Y-%m-%dT%H:%M:%SZ}")
    print(f"  p10 offset, steps 1/20/40: {cal['q10'][0]:.2f} / {cal['q10'][19]:.2f} / {cal['q10'][39]:.2f} EUR/MWh")
    print(f"  p90 offset, steps 1/20/40: {cal['q90'][0]:.2f} / {cal['q90'][19]:.2f} / {cal['q90'][39]:.2f} EUR/MWh")
    print(f"  direction shares up/down/none: {cal['p_up']:.4f} / {cal['p_down']:.4f} / {cal['p_none']:.4f} "
          f"({cal['n_direction_rows']} rows)")
    if cal["spot_available"]:
        print(f"  exceptional price shares high/low: {cal['p_spike_high']:.4f} / {cal['p_spike_low']:.4f} "
              f"({cal['n_spike_rows']} quarter-hours)")
    else:
        print("  WARNING: no spot price data: p_spike_high = p_spike_low = 0.")
    assert cal["max_first_usable_used"] <= cal["first_origin"], "leakage: data after the limit was used"

# ## 3. Load the data
# 
# Only summary figures are shown. Do not print or publish rows of `spot_nordpool.csv` (Nord Pool licence
# terms, see README).

inputs_path = DATA_DIR / "inputs.parquet"
try:
    inputs = read_long(inputs_path)
except (ImportError, FileNotFoundError, ValueError):
    inputs_path = DATA_DIR / "inputs.csv"
    inputs = read_long(inputs_path)

spot_path = DATA_DIR / "spot_nordpool.csv"
spot = read_long(spot_path) if spot_path.exists() else None

print(f"{inputs_path.name}: {len(inputs)} rows, {inputs['series_id'].nunique()} series, "
      f"{inputs['timestamp_utc'].min():%Y-%m-%dT%H:%MZ} .. {inputs['timestamp_utc'].max():%Y-%m-%dT%H:%MZ}")
last = series(inputs, IMBALANCE)["timestamp_utc"].max()
print(f"latest {IMBALANCE} quarter-hour: {last:%Y-%m-%dT%H:%MZ}")
if spot is None:
    print("spot_nordpool.csv: not found. Exceptional price probabilities are set to 0 and the exceptional "
          "price metric cannot be scored.")
else:
    print(f"spot_nordpool.csv: {len(spot)} rows (values not shown, licence terms D3)")

# ## 4. Validation period: forecast origins and template
# 
# `make_templates.py` writes the validation-period origins and template to `baseline_output/validation/`.
# The package files `forecast_origins.csv` and `sample_submission.csv` (test period) are not changed; the
# SHA-256 check below confirms it.

validation_dir = OUTPUT_DIR / "validation"
package_files = [PACKAGE_DIR / "forecast_origins.csv", PACKAGE_DIR / "sample_submission.csv"]
before = {p.name: sha256(p) for p in package_files}

rc = run("make_templates.py", "--test-start", VALIDATION_DAYS[0], "--test-end", VALIDATION_DAYS[1],
         "--output-dir", str(validation_dir.relative_to(PACKAGE_DIR)))
assert rc == 0, "make_templates.py failed"

after = {p.name: sha256(p) for p in package_files}
for name in before:
    print(f"{name}: SHA-256 {before[name][:16]}... before, {after[name][:16]}... after")
assert before == after, "package templates changed"
print("Package templates unchanged.")

# ## 5. Validation period: calibrate and forecast
# 
# History for the validation baseline: rows usable at the first validation origin, 2026-09-06T21:00:00Z.

cal_validation = calibrate(inputs, spot, VALIDATION_FIRST_ORIGIN)
describe_calibration(cal_validation)

validation_origins = read_origins(validation_dir / "forecast_origins.csv")
baseline_validation = build_forecast(inputs, cal_validation, validation_origins)
validation_file = validation_dir / "forecast_backtest.csv"
write_submission(baseline_validation, validation_file, validation_dir / "sample_submission.csv")
print(f"\nWrote {validation_file.relative_to(PACKAGE_DIR)}: {len(baseline_validation)} rows, "
      f"{validation_origins.size} origins")
baseline_validation.head(3)

# ## 6. Validate the format (`validate_submission.py`)

rc = run("validate_submission.py",
         "--backtest", str(validation_file.relative_to(PACKAGE_DIR)),
         "--origins", str((validation_dir / "forecast_origins.csv").relative_to(PACKAGE_DIR)))
print(f"\nreturn code {rc}")

# ## 7. Score the validation period (`score.py`)
# 
# Rows without actual values are skipped. The last validation origins reach into the test period, so their
# last steps are not scored. Without spot prices the exceptional price metric is not calculated.

score_dir = validation_dir / "score"
rc = run("score.py", "--submission", str(validation_file.relative_to(PACKAGE_DIR)),
         "--actuals", "data/actuals_validation.csv", "--spike-margin", str(int(SPIKE_MARGIN)),
         "--output-dir", str(score_dir.relative_to(PACKAGE_DIR)))
print(f"\nreturn code {rc}")

# ### Compare your own model with the baseline
# 
# Write your validation-period forecast in the same format, then run:
# 
# ```bash
# python validate_submission.py --backtest my_validation.csv --origins baseline_output/validation/forecast_origins.csv
# python score.py --submission my_validation.csv --actuals data/actuals_validation.csv --spike-margin 50 --output-dir results/my_model --baseline-summary baseline_output/validation/score/score_summary.csv
# ```
# 
# Write each command on one line; the commands work in PowerShell, cmd and bash.
# 
# `--baseline-summary` adds the MAE difference and ratio against the baseline (for information, D16).
# Your official submission is the test-period file `forecast_backtest.csv` based on `sample_submission.csv`.

# ## 8. Organiser only: official baseline for the test period
# 
# Runs only with `SINCEAI_ORGANIZER=1`. Writes `baseline_test.csv` to the organiser folder outside the
# starter package (default `../organizer_only`, or `SINCEAI_ORGANIZER_DIR`) and validates it. The organiser
# scores it with `actuals_test.csv` (evaluation instructions 7.7.7); the result is the reference level B.
# The notebook is not saved after an organiser run.

if not ORGANIZER:
    print("Organizer section skipped (SINCEAI_ORGANIZER is not set to 1).")
else:
    organizer_dir = Path(os.environ.get("SINCEAI_ORGANIZER_DIR", PACKAGE_DIR.parent / "organizer_only")).resolve()
    assert PACKAGE_DIR.resolve() not in [organizer_dir, *organizer_dir.parents], \
        "the organiser folder must be outside the starter package"
    cal_test = calibrate(inputs, spot, TEST_FIRST_ORIGIN)
    describe_calibration(cal_test)
    if not cal_test["spot_available"]:
        print("WARNING: no spot price data - this file is NOT valid as the official baseline B.")
    test_origins = read_origins(PACKAGE_DIR / "forecast_origins.csv")
    baseline_test = build_forecast(inputs, cal_test, test_origins)
    test_file = organizer_dir / "baseline_test.csv"
    write_submission(baseline_test, test_file, PACKAGE_DIR / "sample_submission.csv")
    print(f"\nWrote {test_file.name} to the organiser folder: {len(baseline_test)} rows")
    rc = run("validate_submission.py", "--backtest", str(test_file), "--origins", "forecast_origins.csv")
    print(f"\nreturn code {rc}")
