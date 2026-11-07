"""Reference rows for the leaderboard: package-only crowd proxy (direct) and mixture, both calibrated."""
from experiments.lab.data import threads
threads(8)
from experiments.lab.run import run_experiment
from experiments.lab.features.package import package_features

run_experiment("REF package direct", agent="reference", feature_fns=[package_features], model="direct",
               notes="crowd proxy: direct quantiles + 3 classifiers, package features incl. spike thresholds")
run_experiment("REF package mixture", agent="reference", feature_fns=[package_features], model="mixture",
               notes="direction mixture, package features incl. spike thresholds")
