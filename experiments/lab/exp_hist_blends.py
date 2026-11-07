"""Pre-declared blends of Frank's v4_n50 with our history-mode models, scored on folds A and B (validation only),
plus weeks won against team5050. History preds are first copied into the lab's index with hist_to_lab.

    .venv/bin/python -W ignore -m experiments.lab.exp_hist_blends
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from experiments.lab import ensemble as E
from experiments.lab.models import metrics

F, OLD = "frank__v4_n50", "lumi-p2__P2_INT4+ss_lgb_leaves7"
H4, H4V = "hist__H-all+regime_INT4ss_lgb7", "hist__H-INT4ss+vol_lgb7"
CANDS = {
    "team5050": {F: 1, OLD: 1},
    "T1 Frank+H-INT4": {F: 1, H4: 1},
    "T2 Frank+H-INT4vol": {F: 1, H4V: 1},
    "T3 Frank+H-INT4+oldINT4": {F: 1, H4: 1, OLD: 1},
    "T4 Frank 1/2 + H-INT4 1/4 + H-INT4vol 1/4": {F: 2, H4: 1, H4V: 1},
    "H-INT4 alone": {H4: 1},
    "H-INT4vol alone": {H4V: 1},
}
W = {"MAE": 30, "pinball": 20, "brier_spike": 20, "brier_dir": 10}


def blend(runs, mem, f):
    w = np.array(list(mem.values()), float); w /= w.sum()
    return E.fix({k: sum(wi * runs[m][f][k] for m, wi in zip(mem, w)) for k in E.KEYS})


def gain(m, r):
    return 100 * sum(w * (r[k] - m[k]) / r[k] for k, w in W.items()) / sum(W.values())


if __name__ == "__main__":
    runs = E.load()
    rows = []
    for name, mem in CANDS.items():
        if not all(m in runs for m in mem):
            continue
        r = {"blend": name}
        wins = tot = 0
        for f in "AB":
            T = E.targets(runs[F][f]["idx"])
            o, ref = blend(runs, mem, f), blend(runs, CANDS["team5050"], f)
            m, m0 = metrics(o, *T[:3]), metrics(ref, *T[:3])
            r.update({f"{f}_MAE": round(m["MAE"], 2), f"{f}_pin": round(m["pinball"], 3), f"{f}_spk": round(m["brier_spike"], 4),
                      f"{f}_dir": round(m["brier_dir"], 4), f"{f}_gain%": round(gain(m, m0), 2)})
            wk = pd.to_datetime(E.base.loc[runs[F][f]["idx"]].origin.values, utc=True).floor("7D")
            for w_ in np.unique(wk):
                s = wk == w_
                a = metrics({k: v[s] for k, v in o.items()}, T[0][s], T[1][s], T[2][s])
                b = metrics({k: v[s] for k, v in ref.items()}, T[0][s], T[1][s], T[2][s])
                tot += 1; wins += gain(a, b) > 1e-9
        r["weeks_won"] = f"{wins}/{tot}"
        rows.append(r)
    print(pd.DataFrame(rows).to_string(index=False))
