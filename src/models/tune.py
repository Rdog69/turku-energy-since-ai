"""Tune LightGBM settings on training data only, with time-based folds.

    python -m src.models.tune

Folds: the last three 2-week blocks before the validation period (26 Jul, 9 Aug, 23 Aug). For each
fold, models train on rows whose targets were published before the block starts and are scored on
the block. The validation month (7 Sep - 4 Oct) is never used here, so it stays an honest check.

Scores per setting: MAE of the median gap model and Brier score of the up-regulation classifier,
averaged over folds. Writes results/tuning.csv and prints the best settings.
"""
from __future__ import annotations

import itertools
import random
import time

import lightgbm as lgb
import numpy as np
import pandas as pd

from src import config
from src.data.availability import build_index
from src.data.load import load_long
from src.data.weather import WeatherIndex
from src.features.build import FEATURE_COLUMNS, WEATHER_COLUMNS, build_features

FOLD_STARTS = [pd.Timestamp("2026-07-26T21:00Z"), pd.Timestamp("2026-08-09T21:00Z"),
               pd.Timestamp("2026-08-23T21:00Z")]   # last block ends 6 Sep, where validation starts
FOLD_DAYS = 14
FEATURES = FEATURE_COLUMNS + WEATHER_COLUMNS

GRID = {
    "num_leaves": [15, 31, 63],
    "min_child_samples": [100, 300, 800],
    "learning_rate": [0.03, 0.05],
    "n_estimators": [300, 600],
    "colsample_bytree": [0.6, 0.8],
    "reg_lambda": [1.0, 5.0],
}
CURRENT = {"num_leaves": 31, "min_child_samples": 300, "learning_rate": 0.05, "n_estimators": 400,
           "colsample_bytree": 0.8, "reg_lambda": 1.0}


def table() -> pd.DataFrame:
    path = config.RESULTS_DIR / "tune_table.parquet"
    if path.exists():
        return pd.read_parquet(path)
    long = load_long()
    weather = WeatherIndex.load("ecmwf_ifs025", capacity_weighted=True)
    origins = pd.date_range(config.DATA_START.ceil("h") + pd.Timedelta(hours=6),
                            config.VALIDATION_FIRST_ORIGIN, freq="h", inclusive="left")
    f = build_features(long, origins, index=build_index(long), weather=weather)
    f = f.dropna(subset=["y_gap", "y_dir"])
    path.parent.mkdir(parents=True, exist_ok=True)
    f.to_parquet(path, index=False)
    return f


def score(f: pd.DataFrame, params: dict) -> dict:
    base = {"subsample": 0.8, "subsample_freq": 1, "verbose": -1, "random_state": 0}
    maes, briers = [], []
    for start in FOLD_STARTS:
        end = start + pd.Timedelta(days=FOLD_DAYS)
        tr = f.loc[f["y_first_usable"] <= start]
        te = f.loc[(f["origin"] >= start) & (f["origin"] < end)]
        q = lgb.LGBMRegressor(objective="quantile", alpha=0.5, **base, **params).fit(tr[FEATURES], tr["y_gap"])
        maes.append(np.abs(te["y_gap"].to_numpy() - q.predict(te[FEATURES])).mean())
        c = lgb.LGBMClassifier(**base, **params).fit(tr[FEATURES], (tr["y_dir"] == 1).astype(int))
        p = c.predict_proba(te[FEATURES])[:, 1]
        briers.append(np.mean((p - (te["y_dir"] == 1).astype(int).to_numpy()) ** 2))
    return {"mae": float(np.mean(maes)), "brier_up": float(np.mean(briers)),
            "mae_folds": [round(m, 2) for m in maes], "brier_folds": [round(b, 4) for b in briers]}


def main(n_random: int = 14, seed: int = 0):
    f = table()
    print(f"training rows: {len(f)}")
    combos = [dict(zip(GRID, v)) for v in itertools.product(*GRID.values())]
    random.Random(seed).shuffle(combos)
    trials = [CURRENT] + combos[:n_random]
    rows = []
    for i, params in enumerate(trials):
        t0 = time.time()
        s = score(f, params)
        rows.append({**params, **s})
        print(f"[{i + 1}/{len(trials)}] {params} -> MAE {s['mae']:.2f}, Brier(up) {s['brier_up']:.4f} "
              f"({time.time() - t0:.0f}s)", flush=True)
    res = pd.DataFrame(rows)
    cur = res.iloc[0]
    # combined rank: relative improvement on both, MAE weighted like its points (30 vs 10)
    res["score"] = 0.75 * res["mae"] / cur["mae"] + 0.25 * res["brier_up"] / cur["brier_up"]
    res = res.sort_values("score")
    out = config.RESULTS_DIR / "tuning.csv"
    res.to_csv(out, index=False)
    print("\nbest settings:")
    print(res.head(5).drop(columns=["mae_folds", "brier_folds"]).to_string(index=False))
    print(f"\ncurrent settings score 1.000; best {res['score'].iloc[0]:.4f}. Written to {out}")


if __name__ == "__main__":
    main()
