"""Backtest runner: train, forecast every origin of a period, write, validate and score.

    python -m src.backtest.run --period validation --model spot_anchor
    python -m src.backtest.run --period test --model spot_anchor

Validation: trains on rows whose targets were published by the first validation origin
(7 Sep 00:00), forecasts 7 Sep - 4 Oct and scores against actuals_validation.csv with the
organisers' score.py. Test: trains on everything published by 5 Oct 00:00 and writes
results/<model>/test/forecast_backtest.csv, ready for the validator and submission.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from src import config
from src.data.availability import build_index
from src.data.load import load_long, load_long_all
from src.features.build import build_features
from src.models.anchor import SpotAnchor
from src.models.blend import HorizonSplit
from src.models.gbm import GBMModel

# Each entry builds a fresh, unfitted model. Names are used for the results folder.
MODELS = {
    "spot_anchor": SpotAnchor,
    "gbm": lambda: GBMModel(name="gbm"),
    "gbm_recency": lambda: GBMModel(name="gbm_recency", tau_days=30),
    "gbm_cal": lambda: GBMModel(name="gbm_cal", tau_days=30, calibrate=True),
    "gbm_cal_product": lambda: GBMModel(name="gbm_cal_product", tau_days=30, calibrate=True,
                                        spike_mode="product"),
    "gbm_cal_product_norecency": lambda: GBMModel(name="gbm_cal_product_norecency", calibrate=True,
                                                  spike_mode="product"),
    "gbm_weather": lambda: GBMModel(name="gbm_weather", calibrate=True, spike_mode="product",
                                    use_weather=True),
    "gbm_fingrid": lambda: GBMModel(name="gbm_fingrid", calibrate=True, spike_mode="product",
                                    use_fingrid=True),
    "gbm_fingrid_early": lambda: GBMModel(name="gbm_fingrid_early", calibrate=True, spike_mode="product",
                                          use_fingrid=True, fresh_max_step=8),
    "split_fingrid": lambda: HorizonSplit(
        name="split_fingrid", split_step=8,
        short=GBMModel(name="short_fingrid", calibrate=True, spike_mode="product", use_fingrid=True),
        long=GBMModel(name="long_package", calibrate=True, spike_mode="product")),
    "split_all": lambda: HorizonSplit(
        name="split_all", split_step=8,
        short=GBMModel(name="short_fingrid_weather", calibrate=True, spike_mode="product",
                       use_fingrid=True, use_weather=True),
        long=GBMModel(name="long_weather", calibrate=True, spike_mode="product", use_weather=True)),
    "split_all_icon": lambda: HorizonSplit(
        name="split_all_icon", split_step=8,
        short=GBMModel(name="short_fingrid_weather_icon", calibrate=True, spike_mode="product",
                       use_fingrid=True, use_weather=True, use_icon=True),
        long=GBMModel(name="long_weather_icon", calibrate=True, spike_mode="product",
                      use_weather=True, use_icon=True)),
    "split_all_spread": lambda: HorizonSplit(
        name="split_all_spread", split_step=8,
        short=GBMModel(name="short_fingrid_weather_spread", calibrate=True, spike_mode="product",
                       use_fingrid=True, use_weather=True, use_icon=True, icon_spread_only=True),
        long=GBMModel(name="long_weather_spread", calibrate=True, spike_mode="product",
                      use_weather=True, use_icon=True, icon_spread_only=True)),
    "gbm_weather_fingrid": lambda: GBMModel(name="gbm_weather_fingrid", calibrate=True,
                                            spike_mode="product", use_weather=True, use_fingrid=True),
}
SUBMISSION_TS = ("forecast_origin_utc", "delivery_start_utc", "data_cutoff_utc")
# Inputs saved next to the forecast so the dashboard can explain it.
DASHBOARD_INPUTS = ["spot", "wind_fc", "cons_fc", "solar_fc", "spot_abs_ramp", "hour", "last_gap",
                    "last_dir", "last_imb", "rt_wind_err", "rt_freq_dev", "rt_nuclear",
                    "rt_nuclear_change_6h", "rt_cons_err", "om_wind_rev", "om_wind_rev_mw",
                    "om_icing", "om_temp"]


def run_script(pkg: Path, *args: str) -> int:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    res = subprocess.run([sys.executable, *args], cwd=pkg, capture_output=True, text=True,
                         encoding="utf-8", errors="replace", env=env)
    print(res.stdout.rstrip())
    if res.stderr.strip():
        print(res.stderr.rstrip())
    return res.returncode


def period_files(pkg: Path, period: str) -> tuple[Path, Path]:
    """(origins csv, template csv) for the period."""
    if period == "test":
        return pkg / "forecast_origins.csv", pkg / "sample_submission.csv"
    out = config.RESULTS_DIR / "templates" / "validation"
    if not (out / "sample_submission.csv").exists():
        out.mkdir(parents=True, exist_ok=True)
        rc = run_script(pkg, "make_templates.py", "--test-start", "2026-09-07", "--test-end",
                        "2026-10-04", "--output-dir", str(out))
        if rc != 0:
            raise RuntimeError("make_templates.py failed")
    return out / "forecast_origins.csv", out / "sample_submission.csv"


def training_table(long, index, cutoff: pd.Timestamp, weather=None, weather2=None) -> pd.DataFrame:
    """All (origin, step) rows with origin < cutoff whose targets were published by cutoff."""
    first = config.DATA_START.ceil("h") + pd.Timedelta(hours=6)  # leave room for a first lag
    origins = pd.date_range(first, cutoff, freq="h", inclusive="left")
    f = build_features(long, origins, index=index, weather=weather, weather2=weather2)
    return f.loc[f["y_first_usable"] <= cutoff].reset_index(drop=True)


def write_submission(feats: pd.DataFrame, pred: pd.DataFrame, template: Path, path: Path) -> None:
    sub = pd.DataFrame({
        "forecast_origin_utc": feats["origin"],
        "delivery_start_utc": feats["delivery"],
        "step": feats["step"].astype(int),
        **{c: pred[c] for c in pred.columns},
        "data_cutoff_utc": feats["data_cutoff"],
    })
    # consistency guards (the validator rejects these)
    q = np.sort(sub[["p10", "p50", "p90"]].to_numpy(), axis=1)
    sub["p10"], sub["p50"], sub["p90"] = q[:, 0], q[:, 1], q[:, 2]
    probs = sub[["p_up", "p_down", "p_none"]].clip(0, 1)
    probs = probs.div(probs.sum(axis=1), axis=0)
    sub[["p_up", "p_down", "p_none"]] = probs
    s = sub["p_spike_high"] + sub["p_spike_low"]
    scale = np.where(s > 1, 1 / s, 1.0)
    sub["p_spike_high"] *= scale
    sub["p_spike_low"] *= scale
    sub["data_cutoff_utc"] = sub["data_cutoff_utc"].where(
        sub["data_cutoff_utc"] <= sub["forecast_origin_utc"], sub["forecast_origin_utc"])
    for col in SUBMISSION_TS:
        sub[col] = pd.to_datetime(sub[col], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

    columns = pd.read_csv(template, nrows=0).columns.tolist()
    ids = pd.read_csv(template, usecols=["forecast_origin_utc", "step"])
    sub = ids.merge(sub, on=["forecast_origin_utc", "step"], how="left")  # template row order
    if sub["p50"].isna().any():
        raise ValueError(f"{sub['p50'].isna().sum()} template rows without a forecast")
    path.parent.mkdir(parents=True, exist_ok=True)
    sub[columns].to_csv(path, index=False, float_format="%.6f", lineterminator="\n", encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--period", choices=["validation", "test"], default="validation")
    ap.add_argument("--model", choices=sorted(MODELS), default="spot_anchor")
    args = ap.parse_args(argv)

    pkg = config.package_dir()
    model = MODELS[args.model]()
    long = load_long_all() if getattr(model, "use_fingrid", False) else load_long()
    index = build_index(long)
    origins_csv, template = period_files(pkg, args.period)
    origins = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(origins_csv)["forecast_origin_utc"], utc=True))
    cutoff = origins.min() if args.period == "validation" else config.TRAIN_CUTOFF
    assert cutoff <= config.TRAIN_CUTOFF

    weather = None
    if getattr(model, "use_weather", False):
        from src.data.weather import WeatherIndex
        weather = WeatherIndex.load("ecmwf_ifs025")
    weather2 = None
    if getattr(model, "use_icon", False):
        weather2 = WeatherIndex.load("icon_eu")
    train = training_table(long, index, cutoff, weather, weather2)
    model.fit(train, cutoff)
    print(model.describe())
    print(f"training rows: {len(train)} (targets published by {cutoff:%Y-%m-%dT%H:%MZ})")

    feats = build_features(long, origins, index=index, with_targets=False, weather=weather,
                           weather2=weather2)
    pred = model.predict(feats)
    out_dir = config.RESULTS_DIR / args.model / args.period
    sub_path = out_dir / "forecast_backtest.csv"
    write_submission(feats, pred, template, sub_path)
    print(f"wrote {sub_path.relative_to(config.REPO_ROOT)} ({len(feats)} rows)")
    # Full table (forecast + the inputs worth explaining) for the dashboard export.
    # Contains spot prices: stays in results/ (git-ignored), never published.
    keep = [c for c in DASHBOARD_INPUTS if c in feats]
    full = pd.concat([feats[["origin", "step", "delivery", "data_cutoff"] + keep].reset_index(drop=True),
                      pred.reset_index(drop=True)], axis=1)
    full.to_parquet(out_dir / "forecast_full.parquet", index=False)

    rc = run_script(pkg, "validate_submission.py", "--backtest", str(sub_path), "--origins", str(origins_csv))
    if rc != 0:
        return rc
    if args.period == "validation":
        baseline = pkg / "baseline_output" / "validation" / "score" / "score_summary.csv"
        extra = ["--baseline-summary", str(baseline)] if baseline.exists() else []
        rc = run_script(pkg, "score.py", "--submission", str(sub_path), "--actuals",
                        "data/actuals_validation.csv", "--spike-margin", str(int(config.SPIKE_MARGIN)),
                        "--output-dir", str(out_dir / "score"), *extra)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
