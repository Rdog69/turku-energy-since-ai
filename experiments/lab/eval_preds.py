"""Score saved prediction files (any finished fold) without waiting for the whole run.

    LAB_HISTORY=1 .venv/bin/python -m experiments.lab.eval_preds [substring]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from .data import build_base
from .models import metrics
from .features.structure import PRED

base = build_base()
rows = []
for p in sorted(PRED.glob(f"*{sys.argv[1] if len(sys.argv) > 1 else ''}*.npz")):
    z = np.load(p)
    va = base.loc[z["idx"]]
    m = metrics({k: z[k] for k in z.files if k != "idx"}, va.imb, va.spot, va.dir)
    tag, fold = p.stem.rsplit("__", 1)
    rows.append(dict(run=tag, fold=fold, **{k: round(v, 4) for k, v in m.items()}))
print(pd.DataFrame(rows).sort_values(["fold", "run"]).to_string(index=False))
