"""Retune the tree settings of v7_rt now that it trains on the pre-June history (238k-265k rows).

    python -m src.models.tune_hist [n_random]

Uses the real v7_rt base model (HorizonSplit, calibration, history rows, real-time features), with
one seed instead of five to save time. The median-from-Nordic twin is left out: it shares the
settings, so tuning the base model tunes both.

Folds: three 2-week blocks of origins, 14 Jun - 26 Jul 2026. For each fold the model trains on
rows whose targets were published before the block starts (the model's own 28-day calibration
holdout comes out of that) and is scored on the block. Everything ends before 1 Aug, so neither
check month (August = fold_b, September = validation) is used, and the test month never is.

The feature table is built once with the fold_b cutoff (31 Jul). The learned wind map is fitted at
that cutoff too, so folds see a wind map that knows up to 5 weeks more data; that only affects the
choice of settings here, never a scored forecast.

Score per setting: the four official metrics (MAE, pinball P10/P90, spike Brier, direction Brier),
averaged over folds, combined with the points weights 30/20/20/10 relative to the current settings
(negative = better). Appends each trial to results/tuning_hist.csv as it finishes.
"""
from __future__ import annotations

import itertools
import random
import sys
import time

import numpy as np
import pandas as pd

from src import config
from src.backtest.run import TUNED_PARAMS, make_final, training_table
from src.data.availability import build_index
from src.data.load import load_long_all, with_history, with_rt_history

FOLD_STARTS = [pd.Timestamp("2026-06-14T21:00Z"), pd.Timestamp("2026-06-28T21:00Z"),
               pd.Timestamp("2026-07-12T21:00Z")]   # last block ends 26 Jul 21:00
FOLD_DAYS = 14
TABLE_CUTOFF = pd.Timestamp("2026-07-31T21:00Z")     # fold_b cutoff: no August target is in the table
POINTS = {"mae": 30, "pin": 20, "spk": 20, "dir": 10}

GRID = {
    "num_leaves": [15, 31, 63, 127],
    "min_child_samples": [200, 800, 2000],
    "learning_rate": [0.03, 0.05],
    "n_estimators": [300, 600, 1000],
    "colsample_bytree": [0.6, 0.8],
    "reg_lambda": [1.0, 5.0],
}
KEYS = list(GRID)
CURRENT = {k: TUNED_PARAMS[k] for k in KEYS}


def new_model():
    m = make_final("tune", "b", memory=True, icon=True, spike_shrink=50, wind_hat=True,
                   history=True, history_flag=True, history_rt=True)
    for sub in (m.short, m.long):
        sub.n_seeds = 1
    return m


def table(model) -> pd.DataFrame:
    from src.data.weather import WeatherIndex
    from src.models.wind_power import WindPowerMap, load_points
    long = with_rt_history(with_history(load_long_all()))
    index = build_index(long)
    weather = WeatherIndex.load("ecmwf_ifs025", capacity_weighted=True)
    weather2 = WeatherIndex.load("icon_eu")
    wind_map = WindPowerMap(load_points()).fit(index, TABLE_CUTOFF)
    return training_table(long, index, TABLE_CUTOFF, weather, None, weather2, wind_map, None,
                          history=True, every=model.history_every)


def metrics(pred: pd.DataFrame, te: pd.DataFrame) -> dict:
    y = (te["spot"] + te["y_gap"]).to_numpy()
    pin = lambda q, p: np.maximum(q * (y - p), (q - 1) * (y - p))
    d = te["y_dir"].to_numpy()
    return {
        "mae": float(np.abs(y - pred["p50"].to_numpy()).mean()),
        "pin": float(((pin(.1, pred["p10"].to_numpy()) + pin(.9, pred["p90"].to_numpy())) / 2).mean()),
        "spk": float((((pred["p_spike_high"].to_numpy() - te["y_spike_high"].to_numpy()) ** 2
                       + (pred["p_spike_low"].to_numpy() - te["y_spike_low"].to_numpy()) ** 2) / 2).mean()),
        "dir": float(((pred["p_up"].to_numpy() - (d == 1)) ** 2 + (pred["p_down"].to_numpy() - (d == -1)) ** 2
                      + (pred["p_none"].to_numpy() - (d == 0)) ** 2).mean()),
    }


def score(f: pd.DataFrame, params: dict) -> dict:
    per_fold = []
    for start in FOLD_STARTS:
        model = new_model()
        for sub in (model.short, model.long):
            sub.params = {**sub.params, **params}
        tr = f.loc[f["y_first_usable"] <= start]
        te = f.loc[(f["origin"] >= start) & (f["origin"] < start + pd.Timedelta(days=FOLD_DAYS))].reset_index(drop=True)
        model.fit(tr, start)
        per_fold.append(metrics(model.predict(te), te))
    return {k: float(np.mean([m[k] for m in per_fold])) for k in POINTS} | {
        f"{k}_folds": ";".join(f"{m[k]:.4g}" for m in per_fold) for k in POINTS}


def main(n_random: int = 10, seed: int = 0):
    t0 = time.time()
    f = table(new_model()).dropna(subset=["y_gap", "y_dir"]).reset_index(drop=True)
    print(f"table: {len(f)} rows ({time.time() - t0:.0f}s)", flush=True)
    combos = [dict(zip(KEYS, v)) for v in itertools.product(*GRID.values())]
    random.Random(seed).shuffle(combos)
    trials = [CURRENT] + [c for c in combos if c != CURRENT][:n_random]
    out = config.RESULTS_DIR / "tuning_hist.csv"
    rows, ref = [], None
    for i, params in enumerate(trials):
        t1 = time.time()
        s = score(f, params)
        ref = ref or s
        s["points_change_pct"] = sum(POINTS[k] * (s[k] - ref[k]) / ref[k] for k in POINTS) / sum(POINTS.values()) * 100
        rows.append({**params, **s, "seconds": round(time.time() - t1)})
        pd.DataFrame(rows).to_csv(out, index=False)
        print(f"[{i + 1}/{len(trials)}] {params} -> MAE {s['mae']:.3f} pin {s['pin']:.3f} spk {s['spk']:.4f} "
              f"dir {s['dir']:.4f} | {s['points_change_pct']:+.2f}% vs current ({time.time() - t1:.0f}s)", flush=True)
    res = pd.DataFrame(rows).sort_values("points_change_pct")
    print("\nbest settings:\n" + res.head(5)[KEYS + ["mae", "pin", "spk", "dir", "points_change_pct"]].to_string(index=False))
    print(f"written to {out}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 10)
