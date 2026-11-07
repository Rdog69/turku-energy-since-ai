"""Pre-declared variants of team5050 (Frank v4_n50 + ours), motivated by weights that were stable on BOTH folds in
exp_banded. No fitting here: fixed weights, scored on both folds plus weekly wins vs team5050.
    .venv/bin/python -W ignore -m experiments.lab.exp_team_variants
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from experiments.lab import ensemble as E
from experiments.lab.exp_banded import FRANK, OURS, P, T, blend, fscore
from experiments.lab.models import metrics

B1 = [(1, 4), (5, 40)]
VARIANTS = {  # Frank share per group, per band of B1
    "team5050": {"p50": [.5, .5], "q": [.5, .5], "spike": [.5, .5], "dir": [.5, .5]},
    "q30": {"p50": [.5, .5], "q": [.3, .3], "spike": [.5, .5], "dir": [.5, .5]},
    "q30+p50s1-4ours": {"p50": [0., .5], "q": [.3, .3], "spike": [.5, .5], "dir": [.5, .5]},
    "p50s1-4ours": {"p50": [0., .5], "q": [.5, .5], "spike": [.5, .5], "dir": [.5, .5]},
    "q40": {"p50": [.5, .5], "q": [.4, .4], "spike": [.5, .5], "dir": [.5, .5]},
}


def week_scores(o, f):
    y, s, d, st = T[f]
    b = E.base.loc[P[FRANK][f]["idx"]]
    wk = pd.to_datetime(b.origin.values, utc=True).floor("7D")
    res = {}
    for w in np.unique(wk):
        m = wk == w
        res[w] = metrics({k: v[m] for k, v in o.items()}, y[m], s[m], d[m])
    return res


def wscore(m, ref):  # points-weighted gain of m over ref (same week)
    return sum(w * (ref[k] - m[k]) / ref[k] for k, w in E.W.items())


if __name__ == "__main__":
    outs = {n: {f: blend(v, B1, f) for f in "AB"} for n, v in VARIANTS.items()}
    base_w = {f: week_scores(outs["team5050"][f], f) for f in "AB"}
    for n in VARIANTS:
        ms = {f: metrics(outs[n][f], *T[f]) for f in "AB"}
        sc = {f: fscore(ms[f], f) for f in "AB"}
        wins = tot = 0
        for f in "AB":
            ws = week_scores(outs[n][f], f)
            for w in ws:
                g = wscore(ws[w], base_w[f][w]); tot += 1; wins += g > 1e-9
        print(f"{n:18s} A {sc['A']:+.3f} B {sc['B']:+.3f} avg {(sc['A'] + sc['B']) / 2:+.3f}  weeks won vs team5050 "
              f"{wins}/{tot} | " + " | ".join(f"{f}: MAE {ms[f]['MAE']:.2f} pin {ms[f]['pinball']:.3f} cov "
                                              f"{ms[f]['coverage']:.3f} spk {ms[f]['brier_spike']:.4f} dir "
                                              f"{ms[f]['brier_dir']:.4f}" for f in "AB"))
