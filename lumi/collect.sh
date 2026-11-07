#!/bin/bash
# Run LOCALLY: fetch LUMI results + predictions, merge new rows into experiments/lab/leaderboard.csv.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p lumi/results experiments/lab/_cache/preds
rsync -az amojahid@lumi.csc.fi:te/lumi/results/ lumi/results/
rsync -az amojahid@lumi.csc.fi:te/experiments/lab/_cache/preds/ experiments/lab/_cache/preds/
.venv/bin/python - <<'PY'
import glob, pandas as pd
b = pd.read_csv("experiments/lab/leaderboard.csv")
parts = [pd.read_csv(f) for f in glob.glob("lumi/results/board_*.csv")]
if parts:
    new = pd.concat(parts, ignore_index=True)
    key = ["agent", "name", "fold"]
    seen = set(map(tuple, b[key].astype(str).values))
    add = new[[tuple(r) not in seen for r in new[key].astype(str).values]]
    pd.concat([b, add], ignore_index=True).to_csv("experiments/lab/leaderboard.csv", index=False)
    print(f"merged {len(add)} new rows from {len(parts)} LUMI tasks")
PY
