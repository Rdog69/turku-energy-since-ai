"""Team blends with members chosen per output group (equal weights within a group), scored on both folds plus
weekly wins vs team5050. Members are lab run tags.
    .venv/bin/python -W ignore -m experiments.lab.exp_trio
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from experiments.lab import ensemble as E
from experiments.lab.exp_banded import FRANK, OURS, T, fscore
from experiments.lab.exp_team_variants import week_scores, wscore
from experiments.lab.models import metrics

runs = E.load()
W6 = "lumi-p5__P5_W6+ss_lgb7_cal21_nobands"
W6b = "lumi-p2__P2_W6+ss_lgb_cal21"
INT1 = "lumi-p2__P2_INT1+ss_lgb_cal21"
F, O = FRANK, OURS


def build(spec, f):
    """spec: {group: [members]} ; 'p50s14' optional: members for p50 at steps 1-4."""
    out = {}
    for g, keys in E.GROUPS.items():
        for k in keys:
            out[k] = np.mean([runs[m][f][k] for m in spec[g]], axis=0)
    if "p50s14" in spec:
        st = T[f][3]; m = st <= 4
        out["p50"][m] = np.mean([runs[x][f]["p50"] for x in spec["p50s14"]], axis=0)[m]
    return E.fix(out)


TEAM = {"p50": [F, O], "q": [F, O], "spike": [F, O], "dir": [F, O]}
VAR = {
    "team5050": TEAM,
    "q+W6": {**TEAM, "q": [F, O, W6]},
    "q+W6+W6b": {**TEAM, "q": [F, O, W6, W6b]},
    "q+W6 p50s14ours": {**TEAM, "q": [F, O, W6], "p50s14": [O]},
    "all+W6": {g: [F, O, W6] for g in E.GROUPS},
    "q+W6 spike+W6": {**TEAM, "q": [F, O, W6], "spike": [F, O, W6]},
    "q+W6 dir+W6": {**TEAM, "q": [F, O, W6], "dir": [F, O, W6]},
    "q+W6 p50+W6": {**TEAM, "q": [F, O, W6], "p50": [F, O, W6]},
    "q+W6b": {**TEAM, "q": [F, O, W6b]},
    "q+W6b p50s14ours": {**TEAM, "q": [F, O, W6b], "p50s14": [O]},
    "q+W6+INT1": {**TEAM, "q": [F, O, W6, INT1]},
}

if __name__ == "__main__":
    outs = {n: {f: build(v, f) for f in "AB"} for n, v in VAR.items()}
    base_w = {f: week_scores(outs["team5050"][f], f) for f in "AB"}
    for n in VAR:
        ms = {f: metrics(outs[n][f], *T[f]) for f in "AB"}
        sc = {f: fscore(ms[f], f) for f in "AB"}
        wins = tot = 0
        for f in "AB":
            ws = week_scores(outs[n][f], f)
            for w in ws:
                tot += 1; wins += wscore(ws[w], base_w[f][w]) > 1e-9
        print(f"{n:18s} A {sc['A']:+.3f} B {sc['B']:+.3f} avg {(sc['A'] + sc['B']) / 2:+.3f} wk {wins}/{tot} | "
              + " | ".join(f"{f}: MAE {ms[f]['MAE']:.2f} pin {ms[f]['pinball']:.3f} cov {ms[f]['coverage']:.3f} "
                           f"spk {ms[f]['brier_spike']:.4f} dir {ms[f]['brier_dir']:.4f}" for f in "AB"))
