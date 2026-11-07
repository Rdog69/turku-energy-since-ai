#!/bin/bash
# After the mfrr2 download: leak-check the new feature sets, then queue phase 5b on LUMI.
set -e
cd "$(dirname "$0")/.."
until [ -f external_data/fingrid/mfrr2_main.csv.gz ]; do sleep 20; done
sleep 5
OMP_NUM_THREADS=2 .venv/bin/python -W ignore -c "
from experiments.lab.data import build_base, Data, leakcheck
from experiments.lab.features.mfrr2 import mfrr2_features, dafcr_features, ace_features
b = build_base(); d = Data()
for fn in (mfrr2_features, dafcr_features, ace_features):
    F = fn(b, d); print(fn.__name__, F.shape, 'NaN share', round(float(F.isna().mean().mean()), 3)); leakcheck(fn, b, d, n=6)
"
.venv/bin/python - <<'PY'
import json
INT4 = ["rt_imb", "rt_wind", "rt_misc", "runs", "dir", "wind_hat", "spot_shape"]
LEAD = ["rt_imb", "rt_wind", "rt_misc", "runs", "dir", "ifs_rev", "wind_err", "ifs_now", "wind_hat", "spot_shape"]
W6 = ["ifs_rev", "wind_err", "ifs_now", "wind_hat", "spot_shape"]
H15 = {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150}
L7 = {"num_leaves": 7, "n_estimators": 350}
B3 = [[1, 4], [5, 8], [9, 16]]
def S(name, feats, engine="lgb", lgb=L7, bands=B3, dirs=True):
    s = {"name": f"P5b {name}", "agent": "lumi-p5b", "features": feats, "model": "mixture", "hgb": H15, "calib": "eb50",
         "cal_days": 14, "causal": 0.2}
    if bands: s["bands"] = bands
    if dirs: s["hist_blend"] = 0.6
    if engine == "lgb": s["engine"] = "lgb"; s["lgb"] = lgb
    return s
specs = [S("INT4ss lgb7 +mfrr2", INT4 + ["mfrr2"]), S("INT4ss lgb7 +dafcr", INT4 + ["dafcr"]),
         S("INT4ss lgb7 +mfrr2+dafcr", INT4 + ["mfrr2", "dafcr"]), S("INT4ss lgb7 +ace", INT4 + ["ace"]),
         S("INT4ss lgb7 +mfrr2+dafcr+ace", INT4 + ["mfrr2", "dafcr", "ace"]),
         S("LEADss lgb +mfrr2+dafcr", LEAD + ["mfrr2", "dafcr"], lgb=None),
         S("W6ss lgb7 +dafcr", W6 + ["dafcr"], dirs=False),
         S("INT4ss hgb +mfrr2", INT4 + ["mfrr2"], engine="hgb"), S("INT4ss hgb +dafcr", INT4 + ["dafcr"], engine="hgb"),
         S("INT4ss hgb +mfrr2+dafcr", INT4 + ["mfrr2", "dafcr"], engine="hgb")]
open("lumi/specs_p5b.jsonl", "w").write("".join(json.dumps(s) + "\n" for s in specs)); print(len(specs), "p5b specs")
PY
./lumi/sync.sh
ssh amojahid@lumi.csc.fi 'cd ~/te && sbatch --array=0-9 --time=03:00:00 --export=ALL,SPECS=lumi/specs_p5b.jsonl lumi/grid.sbatch'
