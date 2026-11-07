"""LightGBM experiments on the INT5 pipeline.  python -m experiments.lab.exp_lgb NAME [key=val ...] (n_seeds, num_leaves, ...)"""
import sys
from experiments.lab.data import threads
threads(2)
from experiments.lab import models, run, models_lgb as L

INT5 = {"features": ["package", "rt_imb", "rt_wind", "rt_misc", "runs", "dir"], "model": "mixture",
        "hgb": {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150},
        "bands": [[1, 4], [5, 8], [9, 16]], "hist_blend": 0.6, "causal": 0.2}

if __name__ == "__main__":
    name = sys.argv[1]
    kw = {k: (float(v) if "." in v else int(v)) for k, v in (a.split("=") for a in sys.argv[2:])}
    L.configure(**kw)
    models.fit_predict = L.fit_predict_lgb
    run.fit_predict = L.fit_predict_lgb
    from experiments.lab import combo
    combo.run_spec({**INT5, "name": name, "agent": "lgb", "rationale": str(kw)})
