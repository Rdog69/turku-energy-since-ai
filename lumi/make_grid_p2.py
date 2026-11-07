"""Phase 2 grid: combine tonight's winners (eb50 calibration, LightGBM engine, spot_shape, cal2, weather, bands)."""
import json
INT4 = ["rt_imb", "rt_wind", "rt_misc", "runs", "dir", "wind_hat"]
INT1 = ["rt_imb", "rt_wind", "rt_misc"]
WX = ["ifs_rev", "wind_err", "ifs_now"]
W6 = WX + ["wind_hat"]
SS, C2 = ["spot_shape"], ["cal2"]
H15 = {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150}
B3, B5 = [[1, 4], [5, 8], [9, 16]], [[1, 2], [3, 4], [5, 8], [9, 16], [17, 40]]
FAM = {"INT4": (INT4, B3, True), "INT4+ss": (INT4 + SS, B3, True), "INT4+ss+c2": (INT4 + SS + C2, B3, True),
       "INT4+ss+wx": (INT4 + SS + WX, B3, True), "INT4+ss+c2+wx": (INT4 + SS + C2 + WX, B3, True),
       "W6+ss": (W6 + SS, None, False), "INT1+ss": (INT1 + SS, B3, False)}
specs = []
def add(name, feats, bands, dirs, engine="hgb", cal_days=14, causal=0.2, hist=0.6, model="mixture", lgb=None, hgb=H15):
    s = {"name": f"P2 {name}", "agent": "lumi-p2", "features": feats, "model": model, "hgb": hgb, "calib": "eb50",
         "cal_days": cal_days}
    if bands: s["bands"] = bands
    if dirs and hist: s["hist_blend"] = hist
    if causal: s["causal"] = causal
    if engine == "lgb":
        s["engine"] = "lgb"
        if lgb: s["lgb"] = lgb
    specs.append(s)
for fam, (f, b, d) in FAM.items():
    for eng in ("hgb", "lgb"):
        for cd in (14, 21):
            add(f"{fam} {eng} cal{cd}", f, b, d, eng, cd)
for fam in ("INT4+ss", "INT4+ss+c2"):                       # 5 bands
    for eng in ("hgb", "lgb"):
        add(f"{fam} {eng} B5", FAM[fam][0], B5, True, eng)
for eng in ("hgb", "lgb"):                                    # no-causal controls, no-band W6 with bands
    for cd in (14, 21):
        add(f"INT4+ss {eng} cal{cd} nocausal", INT4 + SS, B3, True, eng, cd, causal=0)
    add(f"W6+ss {eng} B3", W6 + SS, B3, False, eng)
    add(f"INT4+ss direct {eng}", INT4 + SS, B3, True, eng, model="direct")
for h in (0.4, 0.8):
    add(f"INT4+ss hgb hist{h}", INT4 + SS, B3, True, hist=h)
add("INT4+ss lgb 5seeds", INT4 + SS, B3, True, "lgb", lgb={"n_seeds": 5})
add("INT4+ss lgb leaves7", INT4 + SS, B3, True, "lgb", lgb={"num_leaves": 7, "n_estimators": 350})
for msl in (200, 800):
    add(f"INT4+ss hgb msl{msl}", INT4 + SS, B3, True, hgb=dict(H15, min_samples_leaf=msl))
add("INT4+ss hgb iter300", INT4 + SS, B3, True, hgb=dict(H15, max_iter=300, learning_rate=0.05))
with open("lumi/specs_p2.jsonl", "w") as fh:
    for s in specs: fh.write(json.dumps(s) + "\n")
print(len(specs), "phase-2 specs")
