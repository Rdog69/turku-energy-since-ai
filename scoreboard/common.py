"""Shared helpers for the scoreboard scripts: where things are, the periods, the points."""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ENTRIES = HERE / "entries"
LOCAL = HERE / "_local"          # actuals, baseline runs, exports: git-ignored (they hold spot prices)

# Level-1 points per score (organisers' starter-package README, "Level 1 (0-100 points)").
WEIGHTS = {"mae": 30, "pinball": 20, "spike_brier": 20, "direction_brier": 10}
SCORES = list(WEIGHTS) + ["coverage"]

# first_origin: the training cutoff (only data published before it may be used for that period).
PERIODS = {
    "validation": dict(label="September", start="2026-09-07", end="2026-10-04",
                       first_origin="2026-09-06T21:00:00Z",
                       about="7 Sep - 4 Oct 2026, the organisers' validation month"),
    "fold_b": dict(label="August", start="2026-08-01", end="2026-08-31",
                   first_origin="2026-07-31T21:00:00Z",
                   about="August 2026, trained only on data published before 1 Aug"),
}


def package_dir(given: str | None = None) -> Path:
    """The organisers' starter package folder (the one holding score.py)."""
    cands = [Path(given)] if given else [REPO / "starter_package", REPO / "starter_package" / "v1" / "starter_package_v1"]
    for c in cands:
        if (c / "score.py").exists():
            return c.resolve()
    raise FileNotFoundError("starter package not found; pass --package <folder with score.py>")


def load_entries() -> list[dict]:
    out = []
    for p in sorted(ENTRIES.glob("*.json")):
        e = json.loads(p.read_text(encoding="utf-8"))
        e["_file"] = p.name
        out.append(e)
    return out


def gain(base: dict, m: dict) -> float:
    """Points-weighted % by which m beats base (positive = m is better; lower scores are better)."""
    return sum(w * (base[k] - m[k]) / base[k] for k, w in WEIGHTS.items()) / sum(WEIGHTS.values()) * 100
