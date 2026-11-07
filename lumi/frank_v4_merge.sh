#!/bin/bash
set -e
cd "$(dirname "$0")/.."
./lumi/wait.sh 23536143,23536144,23536145
mkdir -p external_data/_frank
for p in validation fold_b test; do
  rsync -az amojahid@lumi.csc.fi:frank/results/v4_n50/$p/forecast_backtest.csv external_data/_frank/v4_n50_$p.csv || echo "missing $p"
done
OMP_NUM_THREADS=2 .venv/bin/python -W ignore - <<'PY'
import numpy as np, pandas as pd
from experiments.lab.data import build_base, U
from experiments.lab.models import metrics
b = build_base()
for fold, f in (("A", "external_data/_frank/v4_n50_validation.csv"), ("B", "external_data/_frank/v4_n50_fold_b.csv")):
    fr = pd.read_csv(f); fr["origin"] = U(fr.forecast_origin_utc)
    va = b[b[f"fold{fold}"] == "val"]
    fr = fr.set_index(["origin", "step"]).reindex(pd.MultiIndex.from_arrays([va.origin, va.step]))
    P = {"p10": fr.p10.values, "p50": fr.p50.values, "p90": fr.p90.values, "p_up": fr.p_up.values, "p_down": fr.p_down.values,
         "p_none": fr.p_none.values, "p_hi": fr.p_spike_high.values, "p_lo": fr.p_spike_low.values}
    np.savez_compressed(f"experiments/lab/_cache/preds/frank__v4_n50__{fold}.npz", idx=va.index.to_numpy(), **P)
    m = metrics(P, va.imb, va.spot, va.dir, va.step)
    print(f"Frank v4_n50 fold {fold}: missing {int(np.isnan(P['p50']).sum())}",
          {k: round(float(m[k]), 4) for k in ("MAE", "pinball", "coverage", "brier_spike", "brier_dir")})
PY
./lumi/collect.sh
OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.ens_greedy
