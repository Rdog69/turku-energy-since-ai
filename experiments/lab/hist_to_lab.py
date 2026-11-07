"""Copy history-mode predictions (folds A/B) into the package-only lab's prediction folder, re-indexed by
(origin, step), so the ensemble/blend tools (ensemble.py, exp_banded.py, exp_team_variants.py) can use them.

    .venv/bin/python -m experiments.lab.hist_to_lab hist__H-all+regime_INT3rt_lgb7
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from .data import CACHE

bh, bl = pd.read_pickle(CACHE / "base_hist.pkl"), pd.read_pickle(CACHE / "base.pkl")
key_l = pd.Series(bl.index, index=pd.MultiIndex.from_arrays([bl.origin, bl.step]))
for tag in sys.argv[1:]:
    for f in "AB":
        z = np.load(CACHE / "preds_hist" / f"{tag}__{f}.npz")
        r = bh.loc[z["idx"]]
        idx = key_l.reindex(pd.MultiIndex.from_arrays([r.origin, r.step])).to_numpy()
        assert not pd.isna(idx).any(), f"{tag} {f}: rows missing in the package base"
        np.savez_compressed(CACHE / "preds" / f"{tag}__{f}.npz", idx=idx.astype(int),
                            **{k: z[k] for k in z.files if k != "idx"})
        print(f"{tag} {f}: {len(idx)} rows -> preds/")
