"""ONE-OFF fit of the learned wind map (Frank's idea, our implementation) on deliveries < CUT only.

CF(t) = fg181 measured wind / fg268 capacity  ~  b + sum_i w_i * sigmoid(v100_i(t)),  w_i >= 0
v100_i from the newest run usable 5 h before delivery (typical in-horizon lead), Frank's 14 IFS + 8 ICON points.
Prints coefficient dicts to paste into features/wmap.py. Never called by a feature function.
    .venv/bin/python -W ignore -m experiments.lab.fit_wmap
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import nnls

from .data import Data, U, nwp_latest
from .features.weather import CUT, _sig

LEAD = pd.Timedelta(hours=5)


def main():
    d = Data()
    fw = d["fw"]
    fw = fw[fw.fu <= CUT]
    g181 = d.series("fg_rt", "fg181_wind_rt")
    g181 = g181[(g181.fu <= CUT) & (g181.ts < CUT)]
    y = g181.assign(h=g181.ts.dt.floor("h")).groupby("h").value.mean()
    cap = d.series("fg_extra", "fg268_wind_capacity")
    cap = cap[cap.fu <= CUT].drop_duplicates("ts").set_index("ts").value.sort_index()
    t = U(pd.Series(pd.date_range(pd.Timestamp("2026-06-01", tz=CUT.tz), CUT - pd.Timedelta("1h"), freq="h")))
    sb = pd.DataFrame({"origin": U((t - LEAD).dt.floor("h")), "delivery": t, "step": 1})
    capv = cap.reindex(pd.DatetimeIndex(t), method="ffill").to_numpy()
    yv = y.reindex(pd.DatetimeIndex(t)).to_numpy() / capv
    pts = sorted(p for p in fw.point.unique() if not p.startswith("nord_"))
    X = np.column_stack([_sig(nwp_latest(fw, sb, "wind_speed_100m", point=p).to_numpy()) for p in pts])
    ok = ~np.isnan(X).any(1) & ~np.isnan(yv)
    print(f"fit rows {ok.sum()} of {len(t)}; CF mean {np.nanmean(yv):.3f}")
    res = {}
    for name, sel in (("all", pts), ("ifs", [p for p in pts if p.startswith("ifs_")]),
                      ("icon", [p for p in pts if p.startswith("icon_")])):
        j = [pts.index(p) for p in sel]
        A = np.column_stack([X[ok][:, j], np.ones(ok.sum())])
        w, _ = nnls(A, yv[ok])
        pred = A @ w
        r2 = 1 - np.sum((yv[ok] - pred) ** 2) / np.sum((yv[ok] - yv[ok].mean()) ** 2)
        res[name] = {p: round(float(c), 4) for p, c in zip(sel, w[:-1]) if c > 1e-4}
        res[name]["_b"] = round(float(w[-1]), 4)
        print(f"{name}: R2 {r2:.3f}  {res[name]}")
    # old 7-point IFS curve on the same rows, for comparison
    from .features.weather import cf_nwp
    old = cf_nwp(d["ifs"], sb).to_numpy()
    k = ok & ~np.isnan(old)
    print(f"old 7-pt curve R2 {1 - np.sum((yv[k] - old[k]) ** 2) / np.sum((yv[k] - yv[k].mean()) ** 2):.3f}")


if __name__ == "__main__":
    main()
