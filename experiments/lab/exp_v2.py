import sys, json
import experiments.lab.combo as C
M = "experiments.lab.features.v2"
C.REGISTRY["spot_shape"] = (M, "spot_shape", "spot rank/ramps within day")
C.REGISTRY["netpos"] = (M, "netpos_shape", "net position vs day mean/max")
C.REGISTRY["cal2"] = (M, "calendar2", "weekend x hour, DST day")
C.REGISTRY["capw"] = (M, "cap_wind", "capacity-weighted IFS wind")
C.REGISTRY["icon_ifs"] = (M, "icon_ifs", "ICON vs IFS wind disagreement")
BASE = {"features": ["package", "rt_imb", "rt_wind", "rt_misc", "runs", "dir"], "model": "mixture",
        "hgb": {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150},
        "bands": [[1, 4], [5, 8], [9, 16]], "hist_blend": 0.6, "causal": 0.2}
if __name__ == "__main__":
    for extra in sys.argv[1:]:
        names = extra.split("+")
        spec = dict(BASE, features=BASE["features"] + names, name="V2 INT5 + " + extra, agent="v2")
        C.run_spec(spec)
