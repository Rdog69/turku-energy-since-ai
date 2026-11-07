"""Weather-agent experiments.  Usage (repo root):
    OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_weather <name>
"""
import sys

from experiments.lab.data import threads

threads(2)
from experiments.lab.features import weather as W  # noqa: E402
from experiments.lab.features.package import package_features  # noqa: E402
from experiments.lab.run import run_experiment  # noqa: E402

SRC = ("pkg", "ifs", "fg_rt", "fg_extra", "fmi")
EXPS = {
    "W0 rt wind err": ([W.wind_err_features], "fg181 now vs fi_wind_fc_da (no NWP), baseline for IFS marginal value"),
    "W1 ifs rev": ([W.ifs_rev], "power-curve MW from newest IFS run vs fc_da (+nth1 change, DA-run revision, 7d-debiased)"),
    "W2 ifs rev + rt err": ([W.ifs_rev, W.wind_err_features, W.ifs_now_features], "W1 + fg181 now errors vs fc_da and vs IFS"),
    "W3 W6 + fmi": ([W.ifs_rev, W.wind_err_features, W.ifs_now_features, W.wind_hat_features, W.fmi_features], "W6 + FMI coastal obs vs IFS 10m"),
    "W4 W6 + temp": ([W.ifs_rev, W.wind_err_features, W.ifs_now_features, W.wind_hat_features, W.temp_features], "W6 + Helsinki T, T revision since DA run, icing frac"),
    "W6 W2 + hat": ([W.ifs_rev, W.wind_err_features, W.ifs_now_features, W.wind_hat_features], "W2 + wind_err_hat (pre-cutoff OLS combo per step band)"),
    "W5 icon rev": ([W.ifs_rev, W.icon_rev, W.wind_err_features, W.ifs_now_features], "W2 + ICON-EU power-curve revision"),
}

if __name__ == "__main__":
    name = sys.argv[1]
    model = sys.argv[2] if len(sys.argv) > 2 else "mixture"
    reg = len(sys.argv) > 3 and sys.argv[3] == "reg"
    hgb = {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150} if reg else None
    fns, notes = EXPS[name]
    srcs = SRC + (("icon",) if any(f.__name__ == "icon_rev" for f in fns) else ())
    tag = (name if model == "mixture" else f"{name} {model}") + (" regHGB" if reg else "")
    run_experiment(tag, agent="weather", feature_fns=[package_features] + fns, model=model, sources=srcs,
                   notes=notes + ("; HGB leaves15 msl400 iter150" if reg else ""), hgb=hgb)
