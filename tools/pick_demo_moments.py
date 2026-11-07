"""Pick demo moments (hit / miss) and alert statistics from a model's VALIDATION forecasts.

Usage: python tools/pick_demo_moments.py --model split_all_rt_icon [--forecast path/forecast_full.parquet]
       [--hit "2026-10-02 12:00"] [--miss "2026-09-15 05:00"] [--top 8]

Alert rule (reports/alerts_tuning.md): block max p_spike_high rises by >= 0.20 versus the previous
origin's forecast for the same hour, and reaches >= 0.30.
Prints gaps to spot and probabilities only, never spot or price levels. Validation period only.
"""
import argparse
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TZ = "Europe/Helsinki"
INPUTS = ["rt_wind_err", "rt_freq_dev", "rt_sd_last", "rt_plan_err", "rt_hydro_change_1h", "om_wind_rev"]


def L(t):
    return t.tz_convert(TZ).strftime("%a %d %b %H:%M")


def load(path):
    f = pd.read_parquet(path)
    f["origin"] = pd.to_datetime(f["origin"], utc=True)
    f["delivery"] = pd.to_datetime(f["delivery"], utc=True)
    a = pd.read_csv(ROOT / "starter_package/data/actuals_validation.csv", parse_dates=["delivery_start_utc"])
    a["gap"] = a["imbalance_price"] - a["spot_price"]
    a = a.rename(columns={"delivery_start_utc": "delivery"})[["delivery", "gap"]]
    a["delivery"] = pd.to_datetime(a["delivery"], utc=True)
    d = f.merge(a, on="delivery", how="left")
    for q in ("p10", "p50", "p90"):
        d["g" + q[1:]] = d[q] - d["spot"]
    d["blk"] = d["delivery"].dt.floor("h")
    d["lead_h"] = (d["blk"] - d["origin"]) / pd.Timedelta(hours=1)
    return d


def blocks(d):
    b = d.groupby(["origin", "blk"]).agg(
        ps=("p_spike_high", "max"), lead=("lead_h", "min"), gmax=("gap", "max"),
        g90=("g90", "max"), g50=("g50", "mean"), n=("step", "size")).reset_index()
    b = b[b.n == 4].sort_values(["blk", "origin"])
    b["prev"] = b.groupby("blk")["ps"].shift(1)
    b["alert"] = (b.ps >= 0.30) & ((b.ps - b.prev) >= 0.20)
    return b


def inputs_of(df):
    cols = [c for c in INPUTS if c in df.columns]  # other models save other inputs
    return df.iloc[0][cols].astype(float).round(3).to_dict() if cols and len(df) else {}


def drivers_of(df):
    if "top_drivers" not in df.columns:
        return "(no top_drivers column)"
    return Counter(x for s in df["top_drivers"].dropna() for x in str(s).split(";") if x).most_common(6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--forecast")
    ap.add_argument("--hit", default="2026-10-02 12:00", help="local time of the chosen hit origin")
    ap.add_argument("--miss", default="2026-09-15 05:00", help="local time of the chosen miss origin")
    ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    path = Path(a.forecast) if a.forecast else ROOT / "results" / a.model / "validation" / "forecast_full.parquet"
    d = load(path)
    assert d["origin"].max() < pd.Timestamp("2026-10-05", tz="UTC"), "validation only"
    b = blocks(d)
    days = d.origin.dt.tz_convert(TZ).dt.date.nunique()
    al = b[b.alert]
    print(f"# Demo moments, model {a.model} (validation; gaps to spot and probabilities only)\n")
    print(f"ALERTS: {len(al)} over {days} days = {len(al)/days:.2f}/day; precision (gap > +50 in block) "
          f"{(al.gmax > 50).mean():.2f}; base rate {(b.gmax > 50).mean():.3f}\n")

    hits = b[b.alert & (b.gmax > 50) & (b.lead >= 2)].copy()
    hits["over_p90"] = hits.gmax - hits.g90
    print(f"HIT candidates (alert >= 2 h ahead, spike happened, ranked by realised max gap minus P90 gap); {len(hits)} total")
    for _, r in hits.sort_values("over_p90").head(a.top).iterrows():
        p = b[(b.blk == r.blk) & b.lead.between(1, 8)].sort_values("lead", ascending=False)
        traj = " ".join(f"{int(x.lead)}h:{x.ps:.2f}" for _, x in p.iterrows())
        print(f"- origin {L(r.origin)} -> hour {L(r.blk)} lead {int(r.lead)}h | p_spike_high {r.ps:.2f} (prev {r.prev:.2f}) | "
              f"P50 gap {r.g50:+.0f}, P90 gap {r.g90:+.0f}, realised max gap {r.gmax:+.0f} | path {traj}")

    d3 = d[d.lead_h.between(0, 2)].copy()
    d3["miss_hi"] = d3.gap - d3.g90
    m = d3[(d3.miss_hi > 80) & (d3.p_spike_high < 0.10)].sort_values("miss_hi", ascending=False).drop_duplicates("delivery")
    print(f"\nMISS candidates (realised gap > P90 gap + 80, p_spike_high < 0.10, lead <= 2 h); {len(m)} total")
    for _, r in m.head(a.top).iterrows():
        print(f"- origin {L(r.origin)} step {r.step} delivery {L(r.delivery)} | P10..P90 gap {r.g10:+.0f}..{r.g90:+.0f}, "
              f"realised gap {r.gap:+.0f} | p_up {r.p_up:.2f} p_spike_high {r.p_spike_high:.2f}")

    ho = pd.Timestamp(a.hit, tz=TZ).tz_convert("UTC")
    h = d[(d.origin == ho) & d.delivery.dt.tz_convert(TZ).dt.hour.between(16, 18)]
    pv = d[(d.origin == ho - pd.Timedelta(hours=1)) & d.delivery.dt.tz_convert(TZ).dt.hour.between(16, 17)]
    cur = h[h.delivery.dt.tz_convert(TZ).dt.hour.between(16, 17)]
    print(f"\nCHOSEN HIT origin {L(ho)}")
    print(f"- max p_spike_high 16-17h: previous origin {pv.p_spike_high.max():.2f} -> this origin {cur.p_spike_high.max():.2f}")
    print(f"- driver counts 16-18h: {drivers_of(h)}")
    print(f"- inputs (step 1 row): {inputs_of(d[d.origin == ho].sort_values('step'))}")
    mo = pd.Timestamp(a.miss, tz=TZ).tz_convert("UTC")
    ms = d[(d.origin == mo) & (d.step <= 8)].sort_values("step")
    print(f"\nCHOSEN MISS origin {L(mo)}")
    for _, r in ms.iterrows():
        print(f"- {L(r.delivery)} step {r.step}: P10..P90 gap {r.g10:+.0f}..{r.g90:+.0f}, p_up {r.p_up:.2f}, "
              f"p_spike_high {r.p_spike_high:.2f}, realised gap {r.gap:+.0f}")
    print(f"- driver counts: {drivers_of(ms)}")
    print(f"- inputs (step 1 row): {inputs_of(ms)}")


if __name__ == "__main__":
    main()
