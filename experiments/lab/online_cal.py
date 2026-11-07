"""Online recalibration from the forecast's own recent errors (allowed by the organisers: "auto-recursive
prediction feedback"). Works on any submission-format file, including blends; no retraining.

At each forecast hour o it looks back over the last W days of (forecast, realised) pairs that are known at o:
forecasts from earlier hours, scored only on quarters whose imbalance price was published by o
(first_usable_origin_utc <= o). From those pairs, per step group (1-8, 9-40), it fits
  * band scale: p10 = p50 - a (p50 - p10), p90 = p50 + b (p90 - p50); a, b minimise the q10 / q90 pinball loss
  * spike calibration: a logit shift per side (high, low) minimising the Brier score
each shrunk toward "no change" by n / (n + m0) pairs, and applies them to hour o's forecast.

    .venv/bin/python -m experiments.lab.online_cal               # scores Sep and Aug for the pre-declared grid
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "starter_package/data"
GRID_A = np.linspace(0.5, 1.5, 41)
GRID_C = np.linspace(-2.0, 2.0, 41)
GROUPS = [(1, 8), (9, 40)]


def actuals():
    L = pd.concat([pd.read_parquet(PKG / "inputs.parquet"), pd.read_csv(PKG / "spot_nordpool.csv")], ignore_index=True)
    L = L[L.series_id.isin(["fi_imbalance_price", "fi_spot_price", "fi_mfrr_direction"])]
    L["ts"] = pd.to_datetime(L.timestamp_utc, utc=True)
    L["fu"] = pd.to_datetime(L.first_usable_origin_utc, utc=True)
    W = L.pivot_table(index="ts", columns="series_id", values="value")
    fu = L[L.series_id == "fi_imbalance_price"].drop_duplicates("ts").set_index("ts")["fu"]
    return W, fu


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def recalibrate(df: pd.DataFrame, W: pd.DataFrame, fu: pd.Series, days: float = 7, m0: float = 2000,
                spikes: bool = True, narrow_only: bool = False) -> pd.DataFrame:
    d = df.copy()
    d["origin"] = pd.to_datetime(d.forecast_origin_utc, utc=True)
    d["delivery"] = pd.to_datetime(d.delivery_start_utc, utc=True)
    d["y"] = W["fi_imbalance_price"].reindex(d.delivery).to_numpy()
    d["spot"] = W["fi_spot_price"].reindex(d.delivery).to_numpy()
    d["yfu"] = fu.reindex(d.delivery).to_numpy()
    out = d.copy()
    codes, uniq = pd.factorize(d.origin, sort=True)
    for k, o in enumerate(uniq):
        lo_t = o - pd.Timedelta(days=days)
        hist = d[(d.origin < o) & (d.origin >= lo_t) & (d.yfu <= o) & d.y.notna()]
        rows = np.flatnonzero(codes == k)
        for a_s, b_s in GROUPS:
            h = hist[hist.step.between(a_s, b_s)]
            r = rows[(d.step.to_numpy()[rows] >= a_s) & (d.step.to_numpy()[rows] <= b_s)]
            n = len(h)
            if n < 50 or len(r) == 0:
                continue
            s = n / (n + m0)
            y, p10, p50, p90 = h.y.to_numpy(), h.p10.to_numpy(), h.p50.to_numpy(), h.p90.to_numpy()
            lo = p50[None, :] - GRID_A[:, None] * (p50 - p10)[None, :]
            hi = p50[None, :] + GRID_A[:, None] * (p90 - p50)[None, :]
            pin = lambda q, f: np.mean(np.maximum(q * (y - f), (q - 1) * (y - f)), axis=1)
            a = 1 + (GRID_A[np.argmin(pin(0.1, lo))] - 1) * s
            b = 1 + (GRID_A[np.argmin(pin(0.9, hi))] - 1) * s
            if narrow_only:                       # our models err wide: only ever tighten the band
                a, b = min(a, 1.0), min(b, 1.0)
            P50 = out.p50.to_numpy()[r]
            out.loc[out.index[r], "p10"] = P50 - a * (P50 - out.p10.to_numpy()[r])
            out.loc[out.index[r], "p90"] = P50 + b * (out.p90.to_numpy()[r] - P50)
            if spikes:
                for col, ev in (("p_spike_high", h.y > h.spot + 50), ("p_spike_low", h.y < h.spot - 50)):
                    z = _logit(h[col].to_numpy())
                    e = ev.to_numpy(float)
                    br = np.mean((1 / (1 + np.exp(-(z[None, :] + GRID_C[:, None]))) - e[None, :]) ** 2, axis=1)
                    c = GRID_C[np.argmin(br)] * s
                    zr = _logit(out[col].to_numpy()[r])
                    out.loc[out.index[r], col] = 1 / (1 + np.exp(-(zr + c)))
    q = np.sort(out[["p10", "p50", "p90"]].to_numpy(), axis=1)
    out["p10"], out["p50"], out["p90"] = q[:, 0], q[:, 1], q[:, 2]
    sl = np.maximum(out.p_spike_high + out.p_spike_low, 1.0)
    out["p_spike_high"], out["p_spike_low"] = out.p_spike_high / sl, out.p_spike_low / sl
    return out


def score(d: pd.DataFrame) -> dict:
    ok = d.y.notna() & d.spot.notna()
    y, s = d.y[ok].to_numpy(), d.spot[ok].to_numpy()
    pin = lambda q, f: np.mean(np.maximum(q * (y - f), (q - 1) * (y - f)))
    hi, lo = (y > s + 50).astype(float), (y < s - 50).astype(float)
    return dict(MAE=np.mean(np.abs(y - d.p50[ok])), pinball=(pin(.1, d.p10[ok].to_numpy()) + pin(.9, d.p90[ok].to_numpy())) / 2,
                cov=np.mean((y >= d.p10[ok]) & (y <= d.p90[ok])),
                spike=(np.mean((d.p_spike_high[ok] - hi) ** 2) + np.mean((d.p_spike_low[ok] - lo) ** 2)) / 2)


if __name__ == "__main__":
    W, fu = actuals()
    files = {"Sep": "submissions/validation_team_hist.csv", "Aug": "submissions/foldb_team_hist.csv"}
    files.update(dict(a.split("=") for a in sys.argv[1:]))
    rows = []
    for name, f in files.items():
        df = pd.read_csv(ROOT / f)
        base = recalibrate(df, W, fu, days=7, m0=1e12)        # m0 huge = no change (baseline)
        rows.append(dict(file=name, cfg="none", **score(base)))
        for days in (3, 7, 14):
            for m0 in (500, 2000, 8000):
                rows.append(dict(file=name, cfg=f"W{days}d m0={m0}", **score(recalibrate(df, W, fu, days, m0))))
    t = pd.DataFrame(rows)
    print(t.round({"MAE": 2, "pinball": 3, "cov": 3, "spike": 4}).to_string(index=False))
