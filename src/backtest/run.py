"""Backtest runner: train, forecast every origin of a period, write, validate and score.

    python -m src.backtest.run --period validation --model spot_anchor
    python -m src.backtest.run --period test --model spot_anchor

Validation: trains on rows whose targets were published by the first validation origin
(7 Sep 00:00), forecasts 7 Sep - 4 Oct and scores against actuals_validation.csv with the
organisers' score.py. fold_b: the same for August (trained on June-July only), scored against
actuals built from the package by src/backtest/actuals.py. Test: trains on everything published
by 5 Oct 00:00 and writes results/<model>/test/forecast_backtest.csv, ready for the validator
and submission.
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
from src.models.blend import HorizonSplit, MedianFrom
from src.models.gbm import BASE_PARAMS, GBMModel

TUNED_PARAMS = {**BASE_PARAMS, "num_leaves": 15, "min_child_samples": 800, "learning_rate": 0.03,
                "n_estimators": 300, "colsample_bytree": 0.6, "reg_lambda": 1.0}

TUNE9_PARAMS = {"num_leaves": 15, "min_child_samples": 200, "learning_rate": 0.03, "n_estimators": 300,
                "colsample_bytree": 0.8, "reg_lambda": 5.0}

def make_final(name: str, tuned: str = "x", memory: bool = False, nordic: bool = False,
               icon: bool = False, bands4: bool = False, spike_shrink: int | None = None,
               wind_hat: bool = False, town_solar: bool = False, town_temp: bool = False,
               history: bool = False, history_flag: bool = False, history_every: int = config.HISTORY_EVERY_H,
               history_weight: float = 1.0, runs: bool = False, history_rt: bool = False,
               rt3: bool = False, thr: bool = False, params_override: dict | None = None) -> HorizonSplit:
    """final_capw plus optional round-3/4/5/6 changes. tuned: x = none, l = long model, b = both models.

    bands4: the short model is split again, hours 1 (steps 1-4) and 2 (steps 5-8).
    spike_shrink: m0 for the shrunk spike calibration (GBMModel.spike_shrink).
    wind_hat: learned wind production from the weather points (src/models/wind_power.py).
    town_solar / town_temp: solar and temperature revisions at 8 towns (src/data/weather.load_towns).
    history: also train on the pre-June history (config.HISTORY_PATH); history_flag adds regime_2026;
    history_every: every n-th hourly origin before June; history_weight: sample weight of those rows.
    runs: direction runs, 24-hour shares and the same quarter yesterday (build.RUNS_COLUMNS).
    """
    def params(on: bool) -> dict:
        return {**(TUNED_PARAMS if on else BASE_PARAMS), **(params_override or {})}
    common = dict(calibrate=True, spike_mode="product", holdout_days=28, use_weather=True, n_seeds=5,
                  use_memory=memory, use_nordic=nordic, use_icon=icon, spike_shrink=spike_shrink,
                  use_wind_hat=wind_hat, use_town_solar=town_solar, use_town_temp=town_temp,
                  use_history=history, history_flag=history_flag, history_every=history_every,
                  history_weight=history_weight, use_runs=runs, history_rt=history_rt,
                  use_rt3=rt3, use_thr=thr)
    short_kw = dict(use_fingrid=True, use_fingrid2=True, params=params(tuned == "b"), **common)
    if bands4:
        short = HorizonSplit(name=f"{name}_short", split_step=4,
                             short=GBMModel(name=f"{name}_hour1", **short_kw),
                             long=GBMModel(name=f"{name}_hour2", **short_kw))
    else:
        short = GBMModel(name=f"{name}_short", **short_kw)
    return HorizonSplit(
        name=name, split_step=8, capacity_weighted=True, short=short,
        long=GBMModel(name=f"{name}_long", params=params(tuned in ("l", "b")), **common))

def _v4_hybrid(name: str, **extra) -> MedianFrom:
    """v4_n50 (median from the Nordic twin, shrunk spike calibration, learned wind) plus `extra`."""
    kw = dict(memory=True, icon=True, spike_shrink=50, wind_hat=True, **extra)
    return MedianFrom(name=name, base=make_final(f"{name}_base", "b", **kw),
                      median=make_final(f"{name}_median", "b", nordic=True, **kw))


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
    "split_all_rt2": lambda: HorizonSplit(
        name="split_all_rt2", split_step=8,
        short=GBMModel(name="short_rt2", calibrate=True, spike_mode="product",
                       use_fingrid=True, use_fingrid2=True, use_weather=True),
        long=GBMModel(name="long_weather", calibrate=True, spike_mode="product", use_weather=True)),
    "split_all_seeds": lambda: HorizonSplit(
        name="split_all_seeds", split_step=8,
        short=GBMModel(name="short_fingrid_weather_x5", calibrate=True, spike_mode="product",
                       use_fingrid=True, use_weather=True, n_seeds=5),
        long=GBMModel(name="long_weather_x5", calibrate=True, spike_mode="product", use_weather=True,
                      n_seeds=5)),
    "split_all_rt2_seeds": lambda: HorizonSplit(
        name="split_all_rt2_seeds", split_step=8,
        short=GBMModel(name="short_rt2_x5", calibrate=True, spike_mode="product",
                       use_fingrid=True, use_fingrid2=True, use_weather=True, n_seeds=5),
        long=GBMModel(name="long_weather_x5", calibrate=True, spike_mode="product", use_weather=True,
                      n_seeds=5)),
    "final": lambda: HorizonSplit(
        name="final", split_step=8, capacity_weighted=False,
        short=GBMModel(name="short_rt2_x5_h28", calibrate=True, spike_mode="product", holdout_days=28,
                       use_fingrid=True, use_fingrid2=True, use_weather=True, n_seeds=5),
        long=GBMModel(name="long_weather_x5_h28", calibrate=True, spike_mode="product", holdout_days=28,
                      use_weather=True, n_seeds=5)),
    "final_capw": lambda: HorizonSplit(
        name="final_capw", split_step=8, capacity_weighted=True,
        short=GBMModel(name="short_rt2_x5_h28", calibrate=True, spike_mode="product", holdout_days=28,
                       use_fingrid=True, use_fingrid2=True, use_weather=True, n_seeds=5),
        long=GBMModel(name="long_weather_x5_h28", calibrate=True, spike_mode="product", holdout_days=28,
                      use_weather=True, n_seeds=5)),
    "final_nordic": lambda: HorizonSplit(
        name="final_nordic", split_step=8, capacity_weighted=True,
        short=GBMModel(name="short_rt2_x5_h28_nordic", calibrate=True, spike_mode="product", holdout_days=28,
                       use_fingrid=True, use_fingrid2=True, use_weather=True, use_nordic=True, n_seeds=5),
        long=GBMModel(name="long_weather_x5_h28_nordic", calibrate=True, spike_mode="product", holdout_days=28,
                      use_weather=True, use_nordic=True, n_seeds=5)),
    # Round 3 combinations on top of final_capw: t = tuned settings (x = none / l = long model only /
    # b = both), m = 4-hour memory, n = Nordic weather, i = ICON-EU second weather model (from Pavlo's
    # branch). E.g. "v3_lm" = tuned long model + memory, "v3_bmi" = both tuned + memory + ICON.
    **{f"v3_{t}{'m' * m}{'n' * n}{'i' * i}": (lambda t=t, m=m, n=n, i=i: make_final(f"v3_{t}{'m' * m}{'n' * n}{'i' * i}", t, m, n, i))
       for t in ("x", "l", "b") for m in (False, True) for n in (False, True) for i in (False, True)},
    # Submitted model: v3_bmi, with the median (P50) and its drivers from the same model plus Nordic
    # wind. Nordic wind improved the median in September and August but made the band and the spike
    # probabilities worse in both, so it's used for the median only (docs/RESULTS.md).
    "v3_bmi_n50": lambda: MedianFrom(name="v3_bmi_n50",
                                     base=make_final("v3_bmi", "b", memory=True, icon=True),
                                     median=make_final("v3_bmni", "b", memory=True, nordic=True, icon=True)),
    # Round 4 experiments: v3_bmi plus exactly one change each, scored on September and August.
    "v4_b4": lambda: make_final("v4_b4", "b", memory=True, icon=True, bands4=True),
    "v4_eb": lambda: make_final("v4_eb", "b", memory=True, icon=True, spike_shrink=50),
    "v4_wh": lambda: make_final("v4_wh", "b", memory=True, icon=True, wind_hat=True),
    # The two that won in both months (shrunk spike calibration, learned wind production), in the
    # same median-from-Nordic hybrid as v3_bmi_n50.
    "v4_n50": lambda: MedianFrom(
        name="v4_n50",
        base=make_final("v4_ebwh", "b", memory=True, icon=True, spike_shrink=50, wind_hat=True),
        median=make_final("v4_ebwhn", "b", memory=True, nordic=True, icon=True, spike_shrink=50, wind_hat=True)),
    # Round 5: v4_n50 plus town weather, one feature group each (solar revision / temperature revision).
    "v5_sol": lambda: _v4_hybrid("v5_sol", town_solar=True),
    "v5_tmp": lambda: _v4_hybrid("v5_tmp", town_temp=True),
    "v5_st": lambda: _v4_hybrid("v5_st", town_solar=True, town_temp=True),
    # Round 6: v4_n50 trained on the pre-June history too (Mar 2025 - May 2026, every 3rd hourly
    # origin), without and with the pricing-rule flag. Needs the organisers' OK on pre-June data.
    "v6_h": lambda: _v4_hybrid("v6_h", history=True),
    "v6_hf": lambda: _v4_hybrid("v6_hf", history=True, history_flag=True),
    # Round 7: v6_hf plus one change each: every hourly history origin; history rows at half
    # weight; direction runs / 24-hour shares / same quarter yesterday.
    "v7_all": lambda: _v4_hybrid("v7_all", history=True, history_flag=True, history_every=1),
    "v7_w": lambda: _v4_hybrid("v7_w", history=True, history_flag=True, history_weight=0.5),
    "v7_runs": lambda: _v4_hybrid("v7_runs", history=True, history_flag=True, runs=True),
    # v6_hf with Fingrid real-time series on the history rows too (Mar 2025 - May 2026).
    "v7_rt": lambda: _v4_hybrid("v7_rt", history=True, history_flag=True, history_rt=True),
    # Round 8 on top of v7_rt: Fingrid surplus/deficit 198/186 in the short model; spike-threshold
    # distances from the newest mFRR prices; both.
    "v8_imb": lambda: _v4_hybrid("v8_imb", history=True, history_flag=True, history_rt=True, rt3=True),
    "v8_thr": lambda: _v4_hybrid("v8_thr", history=True, history_flag=True, history_rt=True, thr=True),
    "v8_both": lambda: _v4_hybrid("v8_both", history=True, history_flag=True, history_rt=True, rt3=True, thr=True),
    # Round 9: v7_rt with the best tree settings from src/models/tune_hist.py (training-only folds,
    # 14 Jun - 26 Jul; -0.53 % vs the current settings there).
    "v9_tune": lambda: _v4_hybrid("v9_tune", history=True, history_flag=True, history_rt=True,
                                  params_override=TUNE9_PARAMS),
    # Settings from src/models/tune.py (training-only folds 26 Jul - 6 Sep): smaller, slower trees.
    "final_tuned": lambda: HorizonSplit(
        name="final_tuned", split_step=8, capacity_weighted=True,
        short=GBMModel(name="short_rt2_x5_h28_tuned", calibrate=True, spike_mode="product", holdout_days=28,
                       use_fingrid=True, use_fingrid2=True, use_weather=True, n_seeds=5, params=dict(TUNED_PARAMS)),
        long=GBMModel(name="long_weather_x5_h28_tuned", calibrate=True, spike_mode="product", holdout_days=28,
                      use_weather=True, n_seeds=5, params=dict(TUNED_PARAMS))),
    "final_tuned_long": lambda: HorizonSplit(
        name="final_tuned_long", split_step=8, capacity_weighted=True,
        short=GBMModel(name="short_rt2_x5_h28", calibrate=True, spike_mode="product", holdout_days=28,
                       use_fingrid=True, use_fingrid2=True, use_weather=True, n_seeds=5),
        long=GBMModel(name="long_weather_x5_h28_tuned", calibrate=True, spike_mode="product", holdout_days=28,
                      use_weather=True, n_seeds=5, params=dict(TUNED_PARAMS))),
    # calibration window check: re-tune on the last 21 / 28 training days instead of 14
    **{f"split_all_h{d}": (lambda d=d: HorizonSplit(
        name=f"split_all_h{d}", split_step=8,
        short=GBMModel(name="short_fingrid_weather", calibrate=True, spike_mode="product",
                       use_fingrid=True, use_weather=True, holdout_days=d),
        long=GBMModel(name="long_weather", calibrate=True, spike_mode="product", use_weather=True,
                      holdout_days=d))) for d in (21, 28)},
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
    out = config.RESULTS_DIR / "templates" / period
    if not (out / "sample_submission.csv").exists():
        out.mkdir(parents=True, exist_ok=True)
        rc = run_script(pkg, "make_templates.py", "--test-start", config.PERIODS[period]["start"],
                        "--test-end", config.PERIODS[period]["end"], "--output-dir", str(out))
        if rc != 0:
            raise RuntimeError("make_templates.py failed")
    return out / "forecast_origins.csv", out / "sample_submission.csv"


def training_table(long, index, cutoff: pd.Timestamp, weather=None, nordic=None, weather2=None,
                   wind_map=None, towns=None, history: bool = False,
                   every: int = config.HISTORY_EVERY_H) -> pd.DataFrame:
    """All (origin, step) rows with origin < cutoff whose targets were published by cutoff.

    history: also every `every`-th hourly origin from HISTORY_START until the package starts
    (long must then include the history rows, see src.data.load.with_history).
    """
    first = config.DATA_START.ceil("h") + pd.Timedelta(hours=6)  # leave room for a first lag
    origins = pd.date_range(first, cutoff, freq="h", inclusive="left")
    if history:
        early = pd.date_range(config.HISTORY_START + pd.Timedelta(hours=6), first,
                              freq=f"{every}h", inclusive="left")
        origins = early.append(origins)
    f = build_features(long, origins, index=index, weather=weather, nordic=nordic, weather2=weather2,
                       wind_map=wind_map, towns=towns)
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
    ap.add_argument("--period", choices=["validation", "fold_b", "test"], default="validation")
    ap.add_argument("--model", choices=sorted(MODELS), default="spot_anchor")
    args = ap.parse_args(argv)

    pkg = config.package_dir()
    model = MODELS[args.model]()
    long = (load_long_all() if getattr(model, "use_fingrid", False) or getattr(model, "use_wind_hat", False)
            else load_long())
    history = getattr(model, "use_history", False)
    if history:
        from src.data.load import with_history
        long = with_history(long)
        if getattr(model, "history_rt", False):
            from src.data.load import with_rt_history
            long = with_rt_history(long)
    index = build_index(long)
    origins_csv, template = period_files(pkg, args.period)
    origins = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(origins_csv)["forecast_origin_utc"], utc=True))
    cutoff = origins.min() if args.period != "test" else config.TRAIN_CUTOFF
    assert cutoff <= config.TRAIN_CUTOFF
    if args.period != "test":
        assert cutoff == config.PERIODS[args.period]["first_origin"], "template origins don't match the period"

    weather = None
    if getattr(model, "use_weather", False):
        from src.data.weather import WeatherIndex
        weather = WeatherIndex.load("ecmwf_ifs025",
                                    capacity_weighted=getattr(model, "capacity_weighted", False))
    nordic = None
    if getattr(model, "use_nordic", False):
        from src.data.weather import load_nordic
        nordic = load_nordic("ecmwf_ifs025")
    weather2 = None
    if getattr(model, "use_icon", False):
        from src.data.weather import WeatherIndex
        # Only the 8 main points were downloaded for ICON, so its points count equally
        # (capacity weights are defined over ECMWF's 14 points).
        weather2 = WeatherIndex.load("icon_eu")
    wind_map = None
    if getattr(model, "use_wind_hat", False):
        from src.models.wind_power import WindPowerMap, load_points
        wind_map = WindPowerMap(load_points()).fit(index, cutoff)   # data published by the cutoff only
        print(wind_map.describe())
    towns = None
    if getattr(model, "use_towns", False):
        from src.data.weather import load_towns
        towns = load_towns()
        if towns is None:
            raise FileNotFoundError("town weather missing: python -m src.data.open_meteo --points solar")
    train = training_table(long, index, cutoff, weather, nordic, weather2, wind_map, towns, history,
                           getattr(model, "history_every", config.HISTORY_EVERY_H))
    model.fit(train, cutoff)
    print(model.describe())
    print(f"training rows: {len(train)} (targets published by {cutoff:%Y-%m-%dT%H:%MZ})")

    feats = build_features(long, origins, index=index, with_targets=False, weather=weather, nordic=nordic,
                           weather2=weather2, wind_map=wind_map, towns=towns)
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
    if args.period != "test":
        if args.period == "validation":
            actuals = "data/actuals_validation.csv"            # the organisers' own file
            baseline = pkg / "baseline_output" / "validation" / "score" / "score_summary.csv"
            extra = ["--baseline-summary", str(baseline)] if baseline.exists() else []
        else:
            from src.backtest.actuals import write_actuals
            actuals, extra = str(write_actuals(args.period)), []   # built from the package
        rc = run_script(pkg, "score.py", "--submission", str(sub_path), "--actuals", actuals,
                        "--spike-margin", str(int(config.SPIKE_MARGIN)),
                        "--output-dir", str(out_dir / "score"), *extra)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
