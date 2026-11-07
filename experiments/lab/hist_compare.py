"""Compare history-mode runs (leaderboard_hist.csv) against a reference run, fold by fold.

    .venv/bin/python -m experiments.lab.hist_compare "H-win96 core lgb7"

gain = points-weighted % improvement over the reference (MAE 30, pinball 20, spike Brier 20, direction Brier 10),
per fold, plus the mean and the worst fold. A change only counts if it wins on A, B AND C.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

LAB = Path(__file__).resolve().parent
W = {"MAE": 30, "pinball": 20, "brier_spike": 20, "brier_dir": 10}


def gain(row, ref):
    return 100 * sum(w * (ref[k] - row[k]) / ref[k] for k, w in W.items()) / sum(W.values())


def main(ref_name: str, board: str = "leaderboard_hist.csv"):
    b = pd.read_csv(LAB / board).drop_duplicates(["name", "fold"], keep="last")
    ref = b[b.name == ref_name].set_index("fold")
    rows = []
    for name, g in b.groupby("name", sort=False):
        g = g.set_index("fold")
        r = {"name": name}
        for f in sorted(g.index):
            r.update({f"{f}_{k}": round(g.loc[f, k], 4 if "brier" in k else 2) for k in W})
            if f in ref.index:
                r[f"gain_{f}"] = round(gain(g.loc[f], ref.loc[f]), 2)
        gs = [r[c] for c in r if c.startswith("gain_")]
        r["gain_mean"], r["gain_worst"] = (round(sum(gs) / len(gs), 2), min(gs)) if gs else (None, None)
        rows.append(r)
    out = pd.DataFrame(rows).sort_values("gain_mean", ascending=False)
    cols = ["name"] + [c for c in out.columns if c.startswith("gain")]
    print(f"reference: {ref_name}\n")
    print(out[cols].to_string(index=False))
    print()
    print(out[[c for c in out.columns if not c.startswith("gain")]].to_string(index=False))


if __name__ == "__main__":
    main(*sys.argv[1:])
