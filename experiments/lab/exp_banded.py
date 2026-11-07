"""Horizon-banded 2-member blend (Frank v4_n50 + ours), CROSS-FITTED between folds.

Tests Sakibul's "Grand Champion V2" idea (per-band, per-output weights) honestly: weights are picked on one fold
and scored on the other. Compared with flat 50/50 (team5050) and a flat cross-fitted weight.
    .venv/bin/python -W ignore -m experiments.lab.exp_banded [ours_tag]
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from experiments.lab import ensemble as E
from experiments.lab.models import metrics

FRANK = "frank__v4_n50"
OURS = sys.argv[1] if len(sys.argv) > 1 else "lumi-p2__P2_INT4+ss_lgb_leaves7"
GRID = np.round(np.arange(0, 1.0001, 0.1), 2)
BANDSETS = {
    "flat": [(1, 40)],
    "jim4": [(1, 4), (5, 12), (13, 24), (25, 40)],
    "two": [(1, 8), (9, 40)],
    "three": [(1, 4), (5, 16), (17, 40)],
}

runs = E.load()
P = {t: runs[t] for t in (FRANK, OURS)}
for f in "AB":
    assert (P[FRANK][f]["idx"] == P[OURS][f]["idx"]).all(), "idx mismatch"
T = {f: E.targets(P[FRANK][f]["idx"]) for f in "AB"}


def blend(w_by_group, bands, f):
    """w_by_group: {g: [w_frank per band]}"""
    st = T[f][3]
    out = {}
    for g, keys in E.GROUPS.items():
        for k in keys:
            a, b = P[FRANK][f][k], P[OURS][f][k]
            o = np.empty_like(a)
            for (lo, hi), w in zip(bands, w_by_group[g]):
                m = (st >= lo) & (st <= hi)
                o[m] = w * a[m] + (1 - w) * b[m]
            out[k] = o
    return E.fix(out)


def fit(bands, f):
    y, s, d, st = T[f]
    W = {}
    for g in E.GROUPS:
        ws = []
        for lo, hi in bands:
            m = (st >= lo) & (st <= hi)
            Pm = [{k: P[t][f][k][m] for k in E.GROUPS[g]} for t in (FRANK, OURS)]
            losses = [E.group_loss(g, Pm, y[m], s[m], d[m], np.array([w, 1 - w])) for w in GRID]
            ws.append(float(GRID[int(np.argmin(losses))]))
        W[g] = ws
    return W


def fscore(m, f):
    return sum(w * (E.REF[f][k] - m[k]) / E.REF[f][k] for k, w in E.W.items())


def weekly(o, f):
    y, s, d, st = T[f]
    b = E.base.loc[P[FRANK][f]["idx"]]
    wk = pd.to_datetime(b.origin if "origin" in b else b.index.get_level_values(0), utc=True)
    return wk


def report(label, Wfit, bands):
    sc, mets, outs = {}, {}, {}
    for f in "AB":
        o = blend(Wfit[f], bands, f)
        m = metrics(o, *T[f])
        sc[f], mets[f], outs[f] = fscore(m, f), m, o
    print(f"{label:28s} A {sc['A']:+.3f} B {sc['B']:+.3f} avg {(sc['A'] + sc['B']) / 2:+.3f} | "
          + " | ".join(f"{f}: MAE {mets[f]['MAE']:.2f} pin {mets[f]['pinball']:.3f} "
                       f"spk {mets[f]['brier_spike']:.4f} dir {mets[f]['brier_dir']:.4f}" for f in "AB"))
    return outs


if __name__ == "__main__":
    print(f"FRANK={FRANK}  OURS={OURS}")
    for t in (FRANK, OURS):
        report(f"single {t[:22]}", {f: {g: [1.0 if t == FRANK else 0.0] for g in E.GROUPS} for f in "AB"}, [(1, 40)])
    report("team5050 (flat 0.5)", {f: {g: [0.5] for g in E.GROUPS} for f in "AB"}, [(1, 40)])
    for name, bands in BANDSETS.items():
        cf = {"A": fit(bands, "B"), "B": fit(bands, "A")}  # weights for scoring fold X come from the other fold
        report(f"xfit {name}", cf, bands)
        print(f"   weights fit on B (Frank share): {cf['A']}")
        print(f"   weights fit on A (Frank share): {cf['B']}")
        ins = {"A": fit(bands, "A"), "B": fit(bands, "B")}
        report(f"   in-sample {name}", ins, bands)
