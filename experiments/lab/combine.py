"""Combine member submission files into a per-group weighted ensemble, then validate (and score in val mode).

    .venv/bin/python -m experiments.lab.combine --recipe experiments/lab/final_recipe.json --tag final

Members are the per-spec files written by submit.py (submissions/validation_<tag>.csv and
forecast_backtest_<tag>.csv); "frank" maps to teammate Frank's final_capw files in external_data/_frank/.
Recipe: {"p50": [[member, weight], ...], "q": [...], "spike": [...], "dir": [...]} (weights = multiplicities).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PKG, SUB = ROOT / "starter_package", ROOT / "submissions"
FRANK = {"val": ROOT / "external_data/_frank/frank_foldA_val.csv", "test": ROOT / "external_data/_frank/frank_test.csv"}
GROUPS = {"p50": ["p50"], "q": ["p10", "p90"], "spike": ["p_spike_high", "p_spike_low"], "dir": ["p_up", "p_down", "p_none"]}
KEY = ["forecast_origin_utc", "step"]


def member_file(name: str, mode: str) -> Path:
    if name == "frank":
        return FRANK[mode]
    return SUB / (f"validation_{name}.csv" if mode == "val" else f"forecast_backtest_{name}.csv")


def combine(recipe: dict, mode: str, tag: str) -> Path:
    names = sorted({m for g in recipe.values() for m, _ in g})
    frames = {}
    for n in names:
        df = pd.read_csv(member_file(n, mode), dtype={"forecast_origin_utc": str, "delivery_start_utc": str})
        frames[n] = df.set_index(KEY)
    tpl = frames[names[0]].copy()
    for n, df in frames.items():
        assert df.index.equals(tpl.index) or set(df.index) == set(tpl.index), f"{n}: rows differ from template"
    out = tpl.copy()
    for g, cols in GROUPS.items():
        mem = recipe[g]
        w = np.array([float(x) for _, x in mem]); w = w / w.sum()
        for c in cols:
            out[c] = sum(wi * frames[m].loc[out.index, c].to_numpy(float) for (m, _), wi in zip(mem, w))
    p10, p50, p90 = np.sort(np.stack([out.p10, out.p50, out.p90]), axis=0)
    out["p10"], out["p50"], out["p90"] = p10, p50, p90
    s = out.p_up + out.p_down + out.p_none
    out["p_up"], out["p_down"] = out.p_up / s, out.p_down / s
    out["p_none"] = 1 - out.p_up - out.p_down
    sl = np.maximum(out.p_spike_high + out.p_spike_low, 1.0)
    out["p_spike_high"], out["p_spike_low"] = out.p_spike_high / sl, out.p_spike_low / sl
    for c in ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]:
        out[c] = out[c].round(6)
    out["top_drivers"] = ""
    out = out.reset_index()[list(pd.read_csv(member_file(names[0], mode), nrows=1).columns)]
    path = SUB / (f"forecast_backtest_{tag}.csv" if mode == "test" else f"validation_{tag}.csv")
    out.to_csv(path, index=False, lineterminator="\n")
    print(f"wrote {path.relative_to(ROOT)} ({len(out)} rows) from {len(names)} members")
    if mode == "test":
        origins = PKG / "forecast_origins.csv"
    else:
        tmp = Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(PKG / "make_templates.py"), "--test-start", "2026-09-07", "--test-end",
                        "2026-10-04", "--output-dir", str(tmp)], check=True, cwd=PKG, capture_output=True)
        origins = tmp / "forecast_origins.csv"
    r = subprocess.run([sys.executable, "validate_submission.py", "--backtest", str(path), "--origins", str(origins)],
                       cwd=PKG, capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[0], f"(rc={r.returncode})")
    if mode == "val":
        sd = SUB / f"score_{tag}"
        subprocess.run([sys.executable, "score.py", "--submission", str(path), "--actuals", "data/actuals_validation.csv",
                        "--spike-margin", "50", "--output-dir", str(sd), "--baseline-summary",
                        "baseline_output/validation/score/score_summary.csv"], cwd=PKG, capture_output=True, text=True)
        md = (sd / "score_summary.md").read_text()
        print("\n".join(l for l in md.splitlines() if any(k in l for k in ("MAE (p50)", "Mean pinball", "coverage",
                                                                             "Mean Brier", "Three-class"))))
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--modes", default="val,test")
    a = ap.parse_args()
    rec = json.loads(Path(a.recipe).read_text())
    for m in a.modes.split(","):
        combine(rec, m, a.tag)
