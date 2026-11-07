"""Agent 'nowcast' experiments: Fingrid real-time data on top of package_features.

    OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_nowcast check
    OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_nowcast E1 E2 ...   (sequential)
"""
from __future__ import annotations

import sys

from experiments.lab.data import threads

threads(2)

from experiments.lab.data import Data, build_base, leakcheck  # noqa: E402
from experiments.lab.features.nowcast import rt_cons, rt_imb, rt_misc, rt_wind  # noqa: E402
from experiments.lab.features.package import package_features  # noqa: E402
from experiments.lab.run import run_experiment  # noqa: E402

P = package_features
EXPS = {
    "E1": ("rt198 imb", [P, rt_imb], "mixture", "fg198 lags0-3, means 4/8/16, trend, abs, sd + fg186 cum"),
    "E2": ("rt198+wind", [P, rt_imb, rt_wind], "mixture", "+ wind rt - DA fc (newest, m4, m8, trend, /capacity, corrected delivery wind)"),
    "E3": ("rt198+wind+cons", [P, rt_imb, rt_wind, rt_cons], "mixture", "+ consumption rt - DA fc, production rt - fg242 plan, planned import at delivery"),
    "E4": ("rt all", [P, rt_imb, rt_wind, rt_cons, rt_misc], "mixture", "+ freq, nuclear drop vs 24h max, net import, hydro ramp, fg176"),
    "E5": ("rt imb+wind+misc", [P, rt_imb, rt_wind, rt_misc], "mixture", "E4 without the cons/plan group"),
    "E2d": ("rt198+wind direct", [P, rt_imb, rt_wind], "direct", "E2 features, direct model"),
    "E4d": ("rt all direct", [P, rt_imb, rt_wind, rt_cons, rt_misc], "direct", "E4 features, direct model"),
}


def check():
    base, data = build_base(), Data()
    for fn in (rt_imb, rt_wind, rt_cons, rt_misc):
        leakcheck(fn, base, data, n=6)
        X = fn(base, data)
        v = base.foldA == "val"
        print(X[v].describe().T[["count", "mean", "std", "min", "max"]].round(2).to_string())
        print("NaN share (all rows):", X.isna().mean().round(3).to_dict())


def bands(tags):
    """Per-step-band metrics (incl. both Briers) from saved predictions: tags like 'reference__REF_package_mixture'."""
    import numpy as np
    import pandas as pd

    from experiments.lab.models import metrics
    from experiments.lab.run import PRED
    base = build_base()
    rows = []
    for t in tags:
        for f in ("A", "B"):
            z = np.load(PRED / f"{t}__{f}.npz")
            va = base.loc[z["idx"]]
            for a, b in [(1, 4), (5, 12), (13, 40), (1, 40)]:
                m = ((va.step >= a) & (va.step <= b)).to_numpy()
                p = {k: z[k][m] for k in z.files if k != "idx"}
                v = va[m]
                r = metrics(p, v.imb, v.spot, v.dir)
                rows.append(dict(tag=t.split("__")[1], fold=f, band=f"{a}-{b}", **{k: round(float(x), 4) for k, x in r.items()}))
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["check"]:
        check()
    elif args and args[0] == "bands":
        bands(args[1:])
    else:
        for k in args:
            name, fns, model, notes = EXPS[k]
            run_experiment(name, agent="nowcast", feature_fns=fns, model=model, target="gap", calibrate=True, notes=notes)
