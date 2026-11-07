"""Outage experiments (agent: outages). Usage: python -m experiments.lab.exp_outages <name>"""
import sys

from experiments.lab.data import threads

threads(2)
import numpy as np  # noqa: E402

from experiments.lab.features.outages import rt_nuclear, umm_all, umm_delta, umm_fresh, umm_regime, umm_trip  # noqa: E402
from experiments.lab.features.package import package_features  # noqa: E402
from experiments.lab.run import run_experiment  # noqa: E402

SRC = ("pkg", "umm", "fg_rt")
P = package_features

EXPS = {
    "fresh": dict(feature_fns=[P, umm_fresh], notes="REF + fresh unplanned FI gen MW (1/3/6h), unit max, hrs since big msg"),
    "all": dict(feature_fns=[P, umm_all], notes="REF + all UMM: fresh + planned + cons + neighbours + FI border transmission"),
    "trip_rt": dict(feature_fns=[P, umm_trip, rt_nuclear], notes="REF + shock UMM + RT nuclear drop vs 24h max / 1h"),
    "delta": dict(feature_fns=[P, umm_delta], notes="coordinator idea: unpl MW known now - known 6h ago (same delivery), planned delta6, planned MW"),
    "trip": dict(feature_fns=[P, umm_trip], notes="REF + only shock features: fresh1/3/6, delta6, hrs since big (no slow level vars)"),
    "regime": dict(feature_fns=[P, umm_regime], notes="REF + slow UMM regime vars only (planned, cons, nb, transmission)"),
}


def main(name):
    e = dict(EXPS[name])
    run_experiment(f"outages {name}", agent="outages", model=e.pop("model", "mixture"), target="gap",
                   calibrate=True, sources=SRC, **e)


if __name__ == "__main__":
    main(sys.argv[1])
