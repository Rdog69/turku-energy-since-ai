"""Stretch P90 away from P50 by a fixed factor: p90' = p50 + k * (p90 - p50). Nothing else changes.

Why: the ½ v7_rt + ½ h_int4ss blend's upper tail is too narrow in both months (prices land above
P90 more than 10 % of the time) while the lower tail is fine. k = 1.15 was chosen by cross-fit:
fitted on August (best k 1.15) it improves September pinball by 0.34 %; fitted on September
(best 1.125) it improves August by 0.98 %. Never fitted on the test month.

    python -I stretch_p90.py <repo> <in_model> <out_model> <k> <period> [<period> ...]

Reads results/<in_model>/<period>/forecast_backtest.csv, writes results/<out_model>/<period>/...,
scores validation / fold_b with the organisers' score.py.
"""
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

repo = Path(sys.argv[1]).resolve()
src, dst, k, periods = sys.argv[2], sys.argv[3], float(sys.argv[4]), sys.argv[5:]
pkg = repo / "starter_package" / "v1" / "starter_package_v1"
ACT = {"validation": pkg / "data" / "actuals_validation.csv", "fold_b": repo / "scoreboard" / "_local" / "actuals_fold_b.csv"}

for period in periods:
    f = pd.read_csv(repo / "results" / src / period / "forecast_backtest.csv", dtype={"top_drivers": str},
                    keep_default_na=False)
    p50, p90 = f["p50"].astype(float), f["p90"].astype(float)
    assert (p90 >= p50).all()
    f["p90"] = p50 + k * (p90 - p50)
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
