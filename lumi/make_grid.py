"""Systematic spec grid for LUMI (replaces LLM proposals). Writes lumi/specs.jsonl."""
import itertools, json
RT, DIR, WX = ["rt_imb", "rt_wind", "rt_misc"], ["runs", "dir"], ["ifs_rev", "wind_err", "ifs_now", "wind_hat"]
FEATS = {"rt": RT, "rt+dir": RT + DIR, "wx": WX, "wx+dir": WX + DIR, "rt+wx": RT + WX, "rt+dir+wx": RT + DIR + WX,
         "rt+dir+hat": RT + DIR + ["wind_hat"], "dir": DIR}
BANDS = {"B0": None, "B3": [[1, 4], [5, 8], [9, 16]], "B5": [[1, 2], [3, 4], [5, 8], [9, 16], [17, 40]], "B2": [[1, 8], [9, 40]]}
HGB = {"H15": {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150},
       "H7": {"max_leaf_nodes": 7, "min_samples_leaf": 400, "max_iter": 300, "learning_rate": 0.05}}
specs = []
for (fn, f), (bn, b), (hn, h) in itertools.product(FEATS.items(), BANDS.items(), HGB.items()):
    s = {"name": f"G {fn} {bn} {hn}", "agent": "lumi-grid", "features": f, "model": "mixture", "hgb": h, "causal": 0.2}
    if b: s["bands"] = b
    if "dir" in fn: s["hist_blend"] = 0.6
    specs.append(s)
for fn in ("rt", "wx", "rt+dir+wx", "rt+dir+hat"):          # direct models for ensemble diversity
    for bn in ("B0", "B3"):
        s = {"name": f"G direct {fn} {bn} H15", "agent": "lumi-grid", "features": FEATS[fn], "model": "direct", "hgb": HGB["H15"]}
        if BANDS[bn]: s["bands"] = BANDS[bn]
        specs.append(s)
for fn in ("rt+dir", "rt+dir+hat", "rt+dir+wx", "wx"):       # calibration variants
    for cal in ({"calib": "eb50"}, {"cal_days": 28, "calib": "eb50"}):
        s = {"name": f"G {fn} B3 H15 {'cal28' if 'cal_days' in cal else 'eb50'}", "agent": "lumi-grid", "features": FEATS[fn],
             "model": "mixture", "hgb": HGB["H15"], "bands": BANDS["B3"], "causal": 0.2, **cal}
        if "dir" in fn: s["hist_blend"] = 0.6
        specs.append(s)
with open("lumi/specs.jsonl", "w") as fh:
    for s in specs: fh.write(json.dumps(s) + "\n")
print(len(specs), "specs")
