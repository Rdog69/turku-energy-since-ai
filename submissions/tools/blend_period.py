"""Equal-weight blend of our forecast file with one of Abdo's committed files, for any period, then score it.

    python -I blend_period.py <repo> <our_model> <period: validation|fold_b|test> <abdo git path> <out_name>

Writes results/ext_abdo_<stem>/<period>/forecast_backtest.csv (his file from git) and
results/<out_name>/<period>/forecast_backtest.csv (the blend); scores both unless period is test.
"""
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

repo = Path(sys.argv[1])
ours_name, period, abdo_path, out_name = sys.argv[2:6]
KEY = ["forecast_origin_utc", "step"]
AVG = ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]
pkg = repo / "starter_package" / "v1" / "starter_package_v1"
stem = Path(abdo_path).stem

blob = subprocess.check_output(["git", "-C", str(repo), "show", f"origin/brainstorming-abdo:{abdo_path}"])
ext = repo / "results" / f"ext_abdo_{stem}" / period
ext.mkdir(parents=True, exist_ok=True)
(ext / "forecast_backtest.csv").write_bytes(blob)

ours = pd.read_csv(repo / "results" / ours_name / period / "forecast_backtest.csv")
theirs = pd.read_csv(ext / "forecast_backtest.csv")
m = ours.merge(theirs, on=KEY, suffixes=("", "_t"), how="left", validate="1:1")
assert len(m) == len(ours) and m["p50_t"].notna().all(), "row mismatch"
out = ours.copy()
for c in AVG:
    out[c] = (m[c] + m[c + "_t"]) / 2
q = np.sort(out[["p10", "p50", "p90"]].to_numpy(), axis=1)
out["p10"], out["p50"], out["p90"] = q[:, 0], q[:, 1], q[:, 2]
p = out[["p_up", "p_down", "p_none"]]
out[["p_up", "p_down", "p_none"]] = p.div(p.sum(axis=1), axis=0)
s = out["p_spike_high"] + out["p_spike_low"]
scale = np.where(s > 1, 1 / s, 1.0)
out["p_spike_high"] *= scale
out["p_spike_low"] *= scale
out["data_cutoff_utc"] = np.maximum(pd.to_datetime(m["data_cutoff_utc"], utc=True),
                                    pd.to_datetime(m["data_cutoff_utc_t"], utc=True)).dt.strftime("%Y-%m-%dT%H:%M:%SZ")
bdir = repo / "results" / out_name / period
bdir.mkdir(parents=True, exist_ok=True)
out.to_csv(bdir / "forecast_backtest.csv", index=False, float_format="%.6f", lineterminator="\n")
print(f"wrote {bdir / 'forecast_backtest.csv'} ({len(out)} rows)")

if period != "test":
    actuals = (pkg / "data" / "actuals_validation.csv") if period == "validation" else (repo / "scoreboard" / "_local" / "actuals_fold_b.csv")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for d in (ext, bdir):
        r = subprocess.run([sys.executable, "score.py", "--submission", str(d / "forecast_backtest.csv"), "--actuals", str(actuals),
                            "--spike-margin", "50", "--output-dir", str(d / "score")], cwd=pkg, capture_output=True, text=True, env=env)
        print(d.parent.name, "score.py exit", r.returncode)
