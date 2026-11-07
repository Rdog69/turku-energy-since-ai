"""Two-fold calibration test inside validation: fit on one half, score on the other, average."""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
z = np.load("preds_base.npz")
imb, sp, yd, step = z["imb"], z["sp"], z["yd"], z["step"]
t = pd.to_datetime(z["dts"], utc=True)
A = t < pd.Timestamp("2026-09-20T21:00Z"); folds = [(A, ~A), (~A, A)]
y = imb - sp
band = np.select([step <= 4, step <= 12, step <= 24], [0, 1, 2], 3)
pin = lambda q, yy, f: np.mean(np.maximum(q * (yy - f), (q - 1) * (yy - f)))
logit = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))
def platt(p_fit, o_fit, p_app):
    m = LogisticRegression(C=1e6).fit(logit(p_fit)[:, None], o_fit)
    return m.predict_proba(logit(p_app)[:, None])[:, 1]
for name, q10, q50, q90, sh, sl in [("direct", z["D"][0], z["D"][1], z["D"][2], z["sh"], z["sl"]),
                                     ("mixture", z["m10"], z["m50"], z["m90"], z["msh"], z["msl"])]:
    r = {"pin_raw": [], "pin_cal": [], "cov_cal": [], "spk_raw": [], "spk_cal": [], "dir_raw": [], "dir_cal": [], "mae_raw": [], "mae_cal": []}
    hi, lo = (y > 50).astype(float), (y < -50).astype(float)
    ou, od, on = (yd == 1).astype(float), (yd == -1).astype(float), (yd == 0).astype(float)
    for fit, app in folds:
        c10, c90, c50 = q10.copy(), q90.copy(), q50.copy()
        for b in range(4):
            fb, ab = fit & (band == b), app & (band == b)
            c10[ab] += np.quantile(y[fb] - q10[fb], .1); c90[ab] += np.quantile(y[fb] - q90[fb], .9)
            c50[ab] += np.quantile(y[fb] - q50[fb], .5)
        r["pin_raw"].append((pin(.1, y[app], q10[app]) + pin(.9, y[app], q90[app])) / 2)
        r["pin_cal"].append((pin(.1, y[app], c10[app]) + pin(.9, y[app], c90[app])) / 2)
        r["cov_cal"].append(np.mean((y[app] >= c10[app]) & (y[app] <= c90[app])))
        r["mae_raw"].append(np.mean(np.abs(y[app] - q50[app]))); r["mae_cal"].append(np.mean(np.abs(y[app] - c50[app])))
        r["spk_raw"].append((np.mean((sh[app] - hi[app]) ** 2) + np.mean((sl[app] - lo[app]) ** 2)) / 2)
        csh, csl = platt(sh[fit], hi[fit], sh[app]), platt(sl[fit], lo[fit], sl[app])
        s = np.maximum(csh + csl, 1); csh, csl = csh / s, csl / s
        r["spk_cal"].append((np.mean((csh - hi[app]) ** 2) + np.mean((csl - lo[app]) ** 2)) / 2)
        pu, pdn, pn = z["pu"], z["pdn"], z["pn"]
        r["dir_raw"].append(np.mean((pu[app] - ou[app]) ** 2 + (pdn[app] - od[app]) ** 2 + (pn[app] - on[app]) ** 2))
        nn = fit & (yd != 0)
        cu = platt(pu[nn] / (pu[nn] + pdn[nn]), ou[nn], pu[app] / (pu[app] + pdn[app])) * (1 - pn[app])
        r["dir_cal"].append(np.mean((cu - ou[app]) ** 2 + ((1 - pn[app] - cu) - od[app]) ** 2 + (pn[app] - on[app]) ** 2))
    print(name, {k_: round(float(np.mean(v)), 4) for k_, v in r.items()})
