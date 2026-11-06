"""Paths and constants shared by the whole pipeline."""
from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]

# Where the organisers' starter package (starter_package_v1/) lives. Teammates unzip it in
# different places, so we look in a few likely spots. Override with TE_PACKAGE_DIR.
_CANDIDATES = [
    REPO_ROOT / "starter_package" / "v1" / "starter_package_v1",
    REPO_ROOT / "starter_package" / "starter_package_v1",
    REPO_ROOT / "starter_package_v1",
    REPO_ROOT / "starter_package",
]


def package_dir() -> Path:
    env = os.environ.get("TE_PACKAGE_DIR")
    candidates = [Path(env)] if env else _CANDIDATES
    for path in candidates:
        if (path / "data" / "inputs.parquet").exists() or (path / "data" / "inputs.csv").exists():
            return path
    raise FileNotFoundError(
        "Starter package not found. Unzip starter_package_v1.zip into the repo "
        "(e.g. starter_package/starter_package_v1/) or set TE_PACKAGE_DIR. Looked in: "
        + ", ".join(str(p) for p in candidates)
    )


RESULTS_DIR = REPO_ROOT / "results"          # git-ignored

HORIZON_STEPS = 40
STEP = pd.Timedelta(minutes=15)
SPIKE_MARGIN = 50.0                           # EUR/MWh, same as score.py

# Periods (UTC). Origins are full hours; local Finnish dates in comments.
DATA_START = pd.Timestamp("2026-05-31T21:00:00Z")          # 1 Jun 00:00
VALIDATION_FIRST_ORIGIN = pd.Timestamp("2026-09-06T21:00:00Z")  # 7 Sep 00:00
VALIDATION_LAST_ORIGIN = pd.Timestamp("2026-10-04T20:00:00Z")   # 4 Oct 23:00
TEST_FIRST_ORIGIN = pd.Timestamp("2026-10-04T21:00:00Z")        # 5 Oct 00:00
TEST_LAST_ORIGIN = pd.Timestamp("2026-11-01T21:00:00Z")         # 1 Nov 23:00

# Train only on data up to the end of 4 Oct (README section 3).
TRAIN_CUTOFF = TEST_FIRST_ORIGIN
