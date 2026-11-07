#!/bin/bash
cd "$(dirname "$0")/.."
ALL=$(ssh amojahid@lumi.csc.fi 'cat ~/frank/batch2_ids.txt ~/te/lumi/build2_ids.txt' | tr -d '\n')"23536275,23536277,23536278,23536279,23536077,23536101"
./lumi/wait.sh "${ALL%,}"
for m in v3_bmi_n50 v4_eb v4_wh v4_b4 final_tuned final_tuned_long final_nordic; do
  for p in validation fold_b test; do rsync -az amojahid@lumi.csc.fi:frank/results/$m/$p/forecast_backtest.csv external_data/_frank/${m}_$p.csv 2>/dev/null; done
done
rsync -az amojahid@lumi.csc.fi:te/submissions/ submissions/
./lumi/collect.sh
OMP_NUM_THREADS=2 .venv/bin/python -W ignore - <<'PY'
import numpy as np, pandas as pd, os
from experiments.lab.data import build_base, U
b = build_base()
for m in ["v3_bmi_n50", "v4_eb", "v4_wh", "v4_b4", "final_tuned", "final_tuned_long", "final_nordic"]:
    for fold, p in (("A", "validation"), ("B", "fold_b")):
        f = f"external_data/_frank/{m}_{p}.csv"
        if not os.path.exists(f): print("missing", f); continue
        fr = pd.read_csv(f); fr["origin"] = U(fr.forecast_origin_utc); va = b[b[f"fold{fold}"] == "val"]
        fr = fr.set_index(["origin", "step"]).reindex(pd.MultiIndex.from_arrays([va.origin, va.step]))
        P = {"p10": fr.p10.values, "p50": fr.p50.values, "p90": fr.p90.values, "p_up": fr.p_up.values, "p_down": fr.p_down.values,
             "p_none": fr.p_none.values, "p_hi": fr.p_spike_high.values, "p_lo": fr.p_spike_low.values}
        np.savez_compressed(f"experiments/lab/_cache/preds/frank__{m}__{fold}.npz", idx=va.index.to_numpy(), **P)
print("frank variants converted")
PY
echo ROUND5-MERGED
