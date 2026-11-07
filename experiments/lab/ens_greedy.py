"""Cross-fitted greedy ensemble selection (Caruana, with replacement) over the WHOLE pool of saved runs.

For each output group (p50 / p10+p90 / spikes / direction) members are picked greedily on one fold and the
resulting blend is scored on the other fold (and vice versa). Reports the honest cross-fitted score and the
members chosen when fitting on both folds jointly (for the final build).
    OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.ens_greedy
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

sys.path.insert(0, "tools")
from experiments.lab import ensemble as E  # noqa: E402
from experiments.lab.models import metrics  # noqa: E402

W = dict(MAE=30, pinball=20, brier_spike=20, brier_dir=10)
GROUPS = {"p50": ("p50",), "q": ("p10", "p90"), "spike": ("p_hi", "p_lo"), "dir": ("p_up", "p_down", "p_none")}
MET = {"p50": "MAE", "q": "pinball", "spike": "brier_spike", "dir": "brier_dir"}


def fold_score(m, f):
    return sum(w * (E.REF[f][k] - m[k]) / E.REF[f][k] for k, w in W.items())


def main(min_score=4.0, maxk=6):
    import fl_lab
    runs = E.load()
    sb = fl_lab.scored_board()
    sb["tag"] = sb.agent + "__" + sb.name.str.replace(",", ";")
    sb["tag"] = sb.tag.str.replace(" ", "_").str.replace("/", "-").str[:120]
    good = set(sb[sb.score >= min_score].tag) | {t for t in runs if t.startswith("frank__")}
    pool = sorted(t for t in runs if t in good)
    print(f"pool: {len(pool)} runs (score >= {min_score} + Frank)")
    T = {f: E.targets(runs[pool[0]][f]["idx"]) for f in "AB"}

    def gloss(g, preds, f):
        y, s, d, st = T[f]
        p = {k: np.mean([q[k] for q in preds], axis=0) for k in GROUPS[g]}
        if g == "p50":
            return np.mean(np.abs(y - p["p50"]))
        if g == "q":
            pin = lambda q, x: np.mean(np.maximum(q * (y - x), (q - 1) * (y - x)))
            return (pin(.1, p["p10"]) + pin(.9, p["p90"])) / 2
        if g == "spike":
            return (np.mean((p["p_hi"] - (y > s + 50)) ** 2) + np.mean((p["p_lo"] - (y < s - 50)) ** 2)) / 2
        return np.mean((p["p_up"] - (d == 1)) ** 2 + (p["p_down"] - (d == -1)) ** 2 + (p["p_none"] - (d == 0)) ** 2)

    def greedy(g, folds):
        chosen = []
        for _ in range(maxk):
            best = min(pool, key=lambda t: sum(gloss(g, [runs[c][f] for c in chosen + [t]], f) for f in folds))
            if chosen and sum(gloss(g, [runs[c][f] for c in chosen + [best]], f) for f in folds) >= \
                    sum(gloss(g, [runs[c][f] for c in chosen], f) for f in folds) - 1e-9:
                break
            chosen.append(best)
        return chosen

    def blend(members, f):
        out = {}
        for g, keys in GROUPS.items():
            for k in keys:
                out[k] = np.mean([runs[c][f][k] for c in members[g]], axis=0)
        return E.fix(out)

    res = {}
    for fit, ev in (("B", "A"), ("A", "B")):
        mem = {g: greedy(g, [fit]) for g in GROUPS}
        y, s, d, st = T[ev]
        m = metrics(blend(mem, ev), y, s, d, st)
        res[ev] = (fold_score(m, ev), m, mem)
        print(f"\nfit on {fit} -> score on {ev}: {res[ev][0]:+.3f} | " +
              " ".join(f"{k} {m[k]:.4f}" for k in W))
    print(f"\nCROSS-FITTED SCORE (avg A,B): {(res['A'][0] + res['B'][0]) / 2:+.3f}")
    joint = {g: greedy(g, ["A", "B"]) for g in GROUPS}
    print("\nmembers when fitting on BOTH folds (use for the final build):")
    for g, ms in joint.items():
        print(f"  {g}: " + ", ".join(f"{t} x{ms.count(t)}" for t in dict.fromkeys(ms)))
    both = {f: metrics(blend(joint, f), *T[f]) for f in "AB"}
    print("in-sample (optimistic): " + " | ".join(f"{f}: {fold_score(both[f], f):+.3f} MAE {both[f]['MAE']:.2f} "
                                               f"pin {both[f]['pinball']:.3f} spk {both[f]['brier_spike']:.4f} dir {both[f]['brier_dir']:.4f}"
                                               for f in "AB"))
    best_single = sb.iloc[0]
    print(f"best single run: {best_single['name']} {best_single.score:+.3f}")
    return joint


if __name__ == "__main__":
    main()
