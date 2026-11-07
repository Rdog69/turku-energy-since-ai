"""Blend saved HGB INT5 and LGB INT5 predictions: python -m experiments.lab.exp_lgb_blend LGBNAME_TAG NEWNAME [w_lgb]"""
import sys, time
import numpy as np
from experiments.lab.data import build_base
from experiments.lab.models import metrics
from experiments.lab import run

lgb_tag, name = sys.argv[1], sys.argv[2]
w = float(sys.argv[3]) if len(sys.argv) > 3 else 0.5
base = build_base()
rows = []
for f in "AB":
    a = np.load(run.PRED / f"fl-GLM-5.3__INT5_int2+causal0.2__{f}.npz")
    b = np.load(run.PRED / f"lgb__{lgb_tag}__{f}.npz")
    assert (a["idx"] == b["idx"]).all()
    pred = {k: (1 - w) * a[k] + w * b[k] for k in a.files if k != "idx"}
    pred["p10"] = np.minimum(pred["p10"], pred["p50"]); pred["p90"] = np.maximum(pred["p90"], pred["p50"])
    va = base.loc[a["idx"]]
    m = metrics(pred, va.imb, va.spot, va.dir, va.step)
    np.savez_compressed(run.PRED / f"lgb__{name}__{f}.npz".replace(" ", "_").replace("/", "-"), idx=a["idx"], **pred)
    rows.append(dict(time=time.strftime("%Y-%m-%d %H:%M"), agent="lgb", name=name, fold=f, model="blend", target="gap",
                     calibrate=True, n_features=0, **{k: round(float(v), 5) for k, v in m.items()}, secs=0,
                     notes=f"blend HGB INT5 {1-w:.2f} + {lgb_tag} {w:.2f}"))
import pandas as pd
run._append(pd.DataFrame(rows))
