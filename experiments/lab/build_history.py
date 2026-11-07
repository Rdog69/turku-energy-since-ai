"""Build a package-format history (Mar 2025 – 31 May 2026) so the lab can train on ~15 months instead of 4.

- Fingrid package series (verified identical to the package on the overlap, values and first_usable)
- fi_spot_price from Elering (identical to the organisers' Nord Pool file on all 14,824 overlapping quarters)
- fi_imbalance_price RECOMPUTED with the 1 June 2026 rule (volume-weighted mFRR/aFRR price in the dominating
  direction; mFRR price if no aFRR; spot if no direction). The rule reproduces the official price on 99.5 % of
  Jun–Oct 2026 quarters. The raw old-rule price is kept as fi_imbalance_price_oldrule (not a target).
- calendar series computed like the package (local hour/weekday, DST, Finnish holidays incl. Midsummer Eve)

    .venv/bin/python -m experiments.lab.build_history
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .data import EXT

END = pd.Timestamp("2026-05-31T21:00Z")          # package starts here
MAP = {"fg319_imbalance_price": "fi_imbalance_price_oldrule", "fg369_mfrr_direction": "fi_mfrr_direction",
       "fg244_mfrr_up_price": "fi_mfrr_up_price", "fg106_mfrr_down_price": "fi_mfrr_down_price",
       "fg375_mfrr_up_activated": "fi_mfrr_up_activated", "fg376_mfrr_down_activated": "fi_mfrr_down_activated",
       "fg347_afrr_up_price": "fi_afrr_up_price", "fg348_afrr_down_price": "fi_afrr_down_price",
       "fg124_consumption": "fi_consumption", "fg74_production": "fi_production", "fg61_se3_flow": "fi_se3_flow",
       "fg57_no4_flow": "fi_no4_flow", "fg60_se1_flow": "fi_se1_flow", "fg55_ee_flow": "fi_ee_flow",
       "fg165_consumption_fc_da": "fi_consumption_fc_da", "fg246_wind_fc_da": "fi_wind_fc_da", "fg247_solar_fc_da": "fi_solar_fc_da"}
HOLIDAYS = ["2025-04-18", "2025-04-21", "2025-05-01", "2025-05-29", "2025-06-20", "2025-06-21", "2025-11-01", "2025-12-06",
            "2025-12-24", "2025-12-25", "2025-12-26", "2026-01-01", "2026-01-06", "2026-04-03", "2026-04-06", "2026-05-01",
            "2026-05-14"]


def main():
    h = pd.read_csv(EXT / "fingrid/package_history.csv.gz", parse_dates=["timestamp_utc", "first_usable_origin_utc"])
    h = h[h.series_id.isin(MAP) & (h.timestamp_utc < END)].copy()
    h["series_id"] = h.series_id.map(MAP)
    sp = pd.read_csv(EXT / "elering/fi_spot_history.csv.gz", parse_dates=["timestamp_utc", "first_usable_origin_utc"])
    sp = sp[sp.timestamp_utc < END]
    av = pd.read_csv(EXT / "fingrid/afrr_vol_history.csv.gz", parse_dates=["timestamp_utc", "first_usable_origin_utc"])
    av = av[av.timestamp_utc < END]
    W = pd.concat([h, sp, av]).pivot_table(index="timestamp_utc", columns="series_id", values="value")
    d, s = W.fi_mfrr_direction, W.fi_spot_price
    mu, md, au, ad = W.fi_mfrr_up_price, W.fi_mfrr_down_price, W.fi_afrr_up_price, W.fi_afrr_down_price
    vmu, vmd = W.fi_mfrr_up_activated.abs(), W.fi_mfrr_down_activated.abs()
    vau, vad = W.fg349_afrr_up_vol.abs(), W.fg350_afrr_down_vol.abs()
    y = pd.Series(np.nan, index=W.index)
    y[d == 0] = s[d == 0]
    upw, dnw = (vau > 0) & au.notna() & (vmu + vau > 0), (vad > 0) & ad.notna() & (vmd + vad > 0)
    y[(d == 1) & upw] = ((mu * vmu + au * vau) / (vmu + vau))[(d == 1) & upw]
    y[(d == 1) & ~upw] = mu[(d == 1) & ~upw]
    y[(d == -1) & dnw] = ((md * vmd + ad * vad) / (vmd + vad))[(d == -1) & dnw]
    y[(d == -1) & ~dnw] = md[(d == -1) & ~dnw]
    y = y.dropna()
    fu = (y.index + pd.Timedelta(minutes=15) + pd.Timedelta(minutes=60)).ceil("h")    # same rule as dataset 319
    imb = pd.DataFrame({"series_id": "fi_imbalance_price", "source": "reconstructed", "dataset_id": "319-newrule",
                        "timestamp_utc": y.index, "value": y.values, "unit": "EUR/MWh", "first_usable_origin_utc": fu})
    # calendar
    t = pd.date_range("2025-03-01T00:00Z", END - pd.Timedelta(minutes=15), freq="15min")
    loc = t.tz_convert("Europe/Helsinki")
    t0 = pd.Timestamp("2025-03-01T00:00Z")
    cal = []
    for sid, v, unit in (("cal_hour_local", loc.hour, "hour"), ("cal_weekday_local", loc.weekday, "0=Mon"),
                         ("cal_is_dst", np.array([x.dst() != pd.Timedelta(0) for x in loc], int), "0/1"),
                         ("cal_is_holiday_fi", loc.normalize().strftime("%Y-%m-%d").isin(HOLIDAYS).astype(int), "0/1")):
        cal.append(pd.DataFrame({"series_id": sid, "source": "calendar", "dataset_id": "", "timestamp_utc": t,
                                 "value": np.asarray(v, float), "unit": unit, "first_usable_origin_utc": t0}))
    out = pd.concat([h, sp, imb] + cal, ignore_index=True)
    out = out[["series_id", "source", "dataset_id", "timestamp_utc", "value", "unit", "first_usable_origin_utc"]]
    out = out.drop_duplicates(["series_id", "timestamp_utc"], keep="first")   # Fingrid repeats ~360 quarters in Mar 2025
    (EXT / "history").mkdir(exist_ok=True)
    out.to_csv(EXT / "history/pkg_history.csv.gz", index=False, date_format="%Y-%m-%dT%H:%M:%SZ", compression="gzip")
    print(f"pkg_history: {len(out):,} rows, {out.series_id.nunique()} series, {out.timestamp_utc.min()} .. {out.timestamp_utc.max()}")
    print("direction shares:", (d.value_counts(normalize=True).round(3)).to_dict(),
          "| new-rule vs old-rule mean |diff|:", round(float((y - W.fi_imbalance_price_oldrule.reindex(y.index)).abs().mean()), 2))


if __name__ == "__main__":
    main()
