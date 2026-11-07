"""Paired day-block bootstrap of the score differences between two forecast files.

    python tools/paired_bootstrap.py A.csv B.csv [--actuals ...] [--n 2000] [--seed 1]

Prints, for A minus B: the four organiser metrics (definitions copied from
starter_package/score.py) and the points-weighted % gain of A over B, each with a
90 % interval. Resampling unit: whole Europe/Helsinki days of delivery_start_utc, the same
days for both models. Only differences are printed, never prices.
"""
import argparse
import numpy as np
import pandas as pd

WEIGHTS = {"mae": 30, "pinball": 20, "spike_brier": 20, "direction_brier": 10}
ACT = "starter_package/data/actuals_validation.csv"


def row_terms(sub: pd.DataFrame, margin: float = 50.0) -> dict:
    """Per-row loss terms; NaN where the row is not scored for that metric."""
    y, spot = sub["imbalance_price"], sub["spot_price"]
    def pin(q, p):
        d = y - p
        return np.maximum(q * d, (q - 1) * d)
    hi = (y > spot + margin).astype(float)
    lo = (y < spot - margin).astype(float)
    spike = ((sub["p_spike_high"] - hi) ** 2 + (sub["p_spike_low"] - lo) ** 2) / 2
    spike = spike.where(y.notna() & spot.notna())
    d = sub["direction"]
    dirb = sum((sub[f"p_{k}"] - (d == k).astype(float)) ** 2 for k in ("up", "down", "none"))
    return {
        "mae": (y - sub["p50"]).abs(),
        "pinball": (pin(0.1, sub["p10"]) + pin(0.9, sub["p90"])) / 2,
        "spike_brier": spike,
        "direction_brier": dirb.where(d.notna()),
    }


def load(path, act):
    s = pd.read_csv(path, usecols=["delivery_start_utc", "step", "forecast_origin_utc", "p10", "p50", "p90", "p_up",
                                   "p_down", "p_none", "p_spike_high", "p_spike_low"])
    s["delivery_start_utc"] = pd.to_datetime(s["delivery_start_utc"], utc=True)
    m = s.merge(act, on="delivery_start_utc", how="left")
    m["day"] = m["delivery_start_utc"].dt.tz_convert("Europe/Helsinki").dt.date
    return m.sort_values(["forecast_origin_utc", "step"]).reset_index(drop=True)


def day_stats(m):
    t = row_terms(m)
    out = {}
    for k, v in t.items():
        g = pd.DataFrame({"day": m["day"], "v": v})
        out[k] = (g.groupby("day")["v"].sum(), g.groupby("day")["v"].count())
    return out


def compare(a_path, b_path, act, n=2000, seed=1):
    A, B = load(a_path, act), load(b_path, act)
    assert (A["delivery_start_utc"].values == B["delivery_start_utc"].values).all() and (A["step"].values == B["step"].values).all()
    sa, sb = day_stats(A), day_stats(B)
    days = sa["mae"][0].index
    S = {k: np.vstack([sa[k][0].reindex(days).fillna(0).values, sb[k][0].reindex(days).fillna(0).values]) for k in sa}
    C = {k: np.vstack([sa[k][1].reindex(days).fillna(0).values, sb[k][1].reindex(days).fillna(0).values]) for k in sa}
    rng = np.random.default_rng(seed)
    idx = np.vstack([np.arange(len(days))] + [rng.integers(0, len(days), len(days)) for _ in range(n)])
    res = {}
    for k in S:
        sc = np.stack([S[k][i][idx].sum(axis=1) / C[k][i][idx].sum(axis=1) for i in (0, 1)])  # (2, n+1)
        res[k] = sc
    gain = sum(w * (res[k][1] - res[k][0]) / res[k][1] for k, w in WEIGHTS.items()) / sum(WEIGHTS.values()) * 100
    rows = []
    for k in WEIGHTS:
        d = res[k][0] - res[k][1]
        rows.append((k, res[k][0][0], res[k][1][0], d[0], *np.percentile(d[1:], [5, 95])))
    rows.append(("points_weighted_gain_pct", np.nan, np.nan, gain[0], *np.percentile(gain[1:], [5, 95])))
    return pd.DataFrame(rows, columns=["metric", "A", "B", "diff_A_minus_B", "lo90", "hi90"]), len(days)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("a"); ap.add_argument("b")
    ap.add_argument("--actuals", default=ACT)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    act = pd.read_csv(a.actuals)
    act["delivery_start_utc"] = pd.to_datetime(act["delivery_start_utc"], utc=True)
    act["direction"] = act["direction"].str.strip().str.lower().replace("", np.nan)
    df, nd = compare(a.a, a.b, act[["delivery_start_utc", "imbalance_price", "spot_price", "direction"]], a.n, a.seed)
    print(f"{nd} local days, {a.n} resamples, seed {a.seed}")
    print(df.to_string(index=False, float_format=lambda x: f"{x:.4f}"))
