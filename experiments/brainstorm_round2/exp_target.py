import sys, numpy as np
src = open(sys.argv[1]).read().split("res = {}")[0]
sys.argv = [sys.argv[1], sys.argv[2]]
exec(src)
HPf = dict(HP, early_stopping=False, max_iter=300)
for name, target, back in [("gap target", y, lambda p: p), ("price target", imb, lambda p: p - sp[va])]:
    ok = tr & ~np.isnan(target)
    p50 = back(HGR(loss="quantile", quantile=.5, **HPf).fit(X[ok], target[ok]).predict(Xva))
    mae = np.abs(y[va] - p50)
    A = idx[o][va] < pd.Timestamp("2026-09-20T21:00Z")
    print(f"{name}: MAE {mae.mean():.2f} (fold A {mae[A].mean():.2f}, fold B {mae[~A].mean():.2f})")
