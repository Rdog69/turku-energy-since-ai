"""How much do Fingrid real-time series predict direction and gap, at usable lags?

At origin t, a real-time quarter q is usable iff first_usable_origin_utc <= t
(= ceil_hour(q_end + 30 min)), i.e. the newest usable quarter starts 3 quarters before step 1.
The package's imbalance family is 5 quarters old. Training data only (< 4 Oct 21:00Z).
Run from the repo root:  python experiments/brainstorm_round2/check_fingrid_rt.py
"""
import numpy as np
import pandas as pd

END = pd.Timestamp("2026-10-04T21:00Z")
D = pd.concat([pd.read_parquet("starter_package/data/inputs.parquet"), pd.read_csv("starter_package/data/spot_nordpool.csv")])
D["timestamp_utc"] = pd.to_datetime(D.timestamp_utc, utc=True)
W = D.pivot(index="timestamp_utc", columns="series_id", values="value")
rt = pd.read_csv("external_data/fingrid/rt_main.csv.gz", parse_dates=["timestamp_utc", "first_usable_origin_utc"])
R = rt.pivot(index="timestamp_utc", columns="series_id", values="value")
FU = rt.pivot(index="timestamp_utc", columns="series_id", values="first_usable_origin_utc")
W = W.join(R, how="left")
W = W[(W.index >= pd.Timestamp("2026-06-01T00:00Z")) & (W.index < END)]
gap = W.fi_imbalance_price - W.fi_spot_price
up = (W.fi_mfrr_direction == 1).astype(float)

# freshness check: quarters between newest usable RT quarter and step 1, at hourly origins
origins = W.index[(W.index.minute == 0)]
newest = FU["fg198_surplus_deficit_rt"].dropna()
lag = [(o - newest[newest <= o].index.max()) / pd.Timedelta("15min") for o in origins[::97][:50]]
print("RT freshness: quarters from newest usable 198 row to step 1 (sample of origins):", sorted(set(lag)))

W["wind_err"] = W["fg181_wind_rt"] - W["fi_wind_fc_da"]
W["cons_err_rt"] = W["fg193_consumption_rt"] - W["fi_consumption_fc_da"]
cands = {
    "198 surplus/deficit": W["fg198_surplus_deficit_rt"],
    "186 cumulative surplus": W["fg186_surplus_deficit_cum_rt"],
    "wind error (181 - DA fc)": W["wind_err"],
    "consumption error (193 - DA fc)": W["cons_err_rt"],
    "frequency - 50 Hz (177)": W["fg177_frequency_rt"] - 50,
    "package gap (lag 5, baseline)": gap,
}
print("\nSpearman-like rank corr with the quarter k steps after the newest usable value")
print("(RT newest usable = 3 quarters before step 1; package gap = 5 quarters before step 1)")
rows = []
for name, s in cands.items():
    base = 5 if name.startswith("package") else 3
    r = {"feature": name}
    for step in (1, 4, 8, 16, 40):
        L = base + step - 1
        x = s.shift(L).rank(); y1 = gap.rank(); y2 = up
        m = x.notna() & y1.notna()
        r[f"gap s{step}"] = round(x[m].corr(y1[m]), 3)
        r[f"up s{step}"] = round(x[m].corr(y2[m]), 3)
    rows.append(r)
print(pd.DataFrame(rows).set_index("feature").to_string())

# direction agreement: sign of 198 (deficit -> up?) vs actual direction at step 1
s198 = W["fg198_surplus_deficit_rt"]
for L, lab in [(3, "step 1"), (6, "step 4"), (10, "step 8")]:
    pred_up = (s198.shift(L) < 0).astype(float)   # deficit (negative) => up-regulation? sign checked below
    m = s198.shift(L).notna()
    acc = (pred_up[m] == up[m]).mean()
    print(f"sign(198) predicts direction at {lab}: agreement {max(acc, 1 - acc):.3f} (sign {'deficit->up' if acc >= .5 else 'surplus->up'})"
          f"  vs package lag-direction {((W.fi_mfrr_direction.shift(L + 2) == W.fi_mfrr_direction)[m]).mean():.3f}")
