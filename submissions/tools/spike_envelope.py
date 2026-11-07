"""Cap the spike probabilities by the matching direction: p_spike_high <= p_up, p_spike_low <= p_down.

Why: a price more than 50 EUR/MWh above spot comes with up-regulation (September: 324 of 324 high
spikes; August: 308 of 312), and one more than 50 below spot with down-regulation (338 of 346; 195
of 197). No parameter is fitted. Idea from Jim's branch (brainstorming-jim, experiment E09).
The cap only lowers probabilities, so p_spike_high + p_spike_low <= p_up + p_down <= 1 still holds.

    python -I spike_envelope.py <repo> <in_model> <out_model> <period> [<period> ...]

Reads results/<in_model>/<period>/forecast_backtest.csv, writes results/<out_model>/<period>/...,
scores validation / fold_b with the organisers' score.py.
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

repo = Path(sys.argv[1]).resolve()
src, dst, periods = sys.argv[2], sys.argv[3], sys.argv[4:]
pkg = repo / "starter_package" / "v1" / "starter_package_v1"
ACT = {"validation": pkg / "data" / "actuals_validation.csv", "fold_b": repo / "scoreboard" / "_local" / "actuals_fold_b.csv"}

for period in periods:
    f = pd.read_csv(repo / "results" / src / period / "forecast_backtest.csv", dtype={"top_drivers": str},
                    keep_default_na=False)
    f["p_spike_high"] = np.minimum(f["p_spike_high"].astype(float), f["p_up"].astype(float))
    f["p_spike_low"] = np.minimum(f["p_spike_low"].astype(float), f["p_down"].astype(float))
    out = repo / "results" / dst / period
    out.mkdir(parents=True, exist_ok=True)
    f.to_csv(out / "forecast_backtest.csv", index=False, float_format="%.6f", lineterminator="\n")
    print(f"wrote {out / 'forecast_backtest.csv'} ({len(f)} rows)")
    if period in ACT:
        env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        r = subprocess.run([sys.executable, "score.py", "--submission", str(out / "forecast_backtest.csv"), "--actuals",
                            str(ACT[period]), "--spike-margin", "50", "--output-dir", str(out / "score")],
                           cwd=pkg, capture_output=True, text=True, env=env)
        print(period, "score.py exit", r.returncode, r.stderr[-300:] if r.returncode else "")
