"""Run the organisers' baseline (their baseline.ipynb code, unchanged) on any scoring period, then score it.

    python scoreboard/baseline.py --period fold_b

1. make_templates.py writes the period's forecast origins and template.
2. The notebook's own definition cells run, then calibrate() / build_forecast() / write_submission(),
   calibrated only on data before the period's first origin, exactly as the notebook does for validation.
3. score.py scores it (August against scoreboard/make_actuals.py's file).

For --period validation this reproduces the organisers' baseline_output/validation/forecast_backtest.csv
exactly (checked 7 Nov 2026), which is why the August baseline is trusted. Everything goes to
scoreboard/_local/baseline/<period>/ (git-ignored). Log the result with log_score.py --owner Organisers
--model baseline --scorer official.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import LOCAL, PERIODS, package_dir  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--period", choices=sorted(PERIODS), default="fold_b")
    ap.add_argument("--package", help="starter package folder (the one with score.py)")
    a = ap.parse_args(argv)
    p = PERIODS[a.period]
    pkg = package_dir(a.package)
    out = (LOCAL / "baseline" / a.period).resolve()
    out.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    def run(*args: str) -> None:
        subprocess.run([sys.executable, *args], cwd=pkg, check=True, env=env)

    run("make_templates.py", "--test-start", p["start"], "--test-end", p["end"], "--output-dir", str(out))
    nb = json.loads((pkg / "baseline.ipynb").read_text(encoding="utf-8"))
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    ns: dict = {}
    cwd = os.getcwd()
    os.chdir(pkg)                      # the notebook expects to run in the package folder
    try:
        for cell in code[:3]:          # settings, rows_available_at(), the baseline functions
            exec("".join(cell["source"]), ns)
        missing = [n for n in ("read_long", "calibrate", "read_origins", "build_forecast", "write_submission") if n not in ns]
        if missing:
            raise SystemExit(f"baseline.ipynb changed; missing {missing}")
        try:
            inputs = ns["read_long"](pkg / "data" / "inputs.parquet")
        except (ImportError, FileNotFoundError, ValueError):
            inputs = ns["read_long"](pkg / "data" / "inputs.csv")
        spot = ns["read_long"](pkg / "data" / "spot_nordpool.csv")
        cal = ns["calibrate"](inputs, spot, pd.Timestamp(p["first_origin"]))
        origins = ns["read_origins"](out / "forecast_origins.csv")
        forecast = ns["build_forecast"](inputs, cal, origins)
        sub = out / "forecast_backtest.csv"
        ns["write_submission"](forecast, sub, out / "sample_submission.csv")
    finally:
        os.chdir(cwd)
    print(f"wrote {sub} ({len(forecast)} rows)")

    if a.period == "validation":
        actuals = pkg / "data" / "actuals_validation.csv"
    else:
        actuals = LOCAL / f"actuals_{a.period}.csv"
        if not actuals.exists():
            subprocess.run([sys.executable, str(Path(__file__).with_name("make_actuals.py")), "--period", a.period,
                            "--package", str(pkg)], check=True, env=env)
    run("score.py", "--submission", str(sub), "--actuals", str(actuals.resolve()), "--spike-margin", "50",
        "--output-dir", str(out / "score"))
    print(f"score summary: {out / 'score' / 'score_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
