"""Submission pipeline: official templates in, validated CSV out.

    python -m experiments.lab.submit --mode val    # 7 Sep - 4 Oct, scored with the OFFICIAL score.py vs the baseline
    python -m experiments.lab.submit --mode test   # 673 test origins -> submissions/forecast_backtest_<tag>.csv + validator

* Training rows: deliveries before the cutoff MINUS a 2 h label embargo (the last imbalance labels
  are published up to 1 h 45 min after their quarter), so no label used in fitting was unpublished
  at the first forecast origin. Cutoff = 4 Oct 21:00Z (test) or 6 Sep 21:00Z (val).
* Calibration (optional): last 14 days of the training window, model refit without them.
* Features: the same leak-checked feature functions as the lab; leak-checked again on the
  submission origins themselves.
* data_cutoff_utc = start of the newest measured quarter used (imbalance/consumption), always < origin.
"""
from __future__ import annotations

import argparse
import importlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from .data import threads

threads(4)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from .data import END, PKG, ROOT, U, Data, asof, at_delivery, build_base, leakcheck  # noqa: E402
from .models import calibrate, fit_predict  # noqa: E402
from .run import public  # noqa: E402

OUT = ROOT / "submissions"
EMBARGO = pd.Timedelta(hours=2)
VAL_CUTOFF = pd.Timestamp("2026-09-06T21:00Z")
COLS = ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]


def rows_from_template(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    tpl = pd.read_csv(path, dtype=str, keep_default_na=False)
    rows = pd.DataFrame({"origin": U(tpl["forecast_origin_utc"]), "step": tpl["step"].astype(int),
                         "delivery": U(tpl["delivery_start_utc"])})
    assert (rows.delivery == rows.origin + (rows.step - 1) * pd.Timedelta(minutes=15)).all()
    return tpl, rows


def load_fns(specs: list[str]):
    fns = []
    for s in specs:                       # "experiments.lab.features.package:package_features"
        mod, name = s.split(":")
        fns.append(getattr(importlib.import_module(mod), name))
    return fns


def feats(fns, rows, data):
    X = pd.concat([fn(public(rows), data) for fn in fns], axis=1)
    return X.loc[:, ~X.columns.duplicated()]


def data_cutoff(rows: pd.DataFrame, data: Data) -> pd.Series:
    o = rows["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    newest = []
    for sid in ("fi_imbalance_price", "fi_consumption"):
        a = asof(data.series("pkg", sid), o)
        newest.append(U(o) - pd.to_timedelta(a["age_q"].to_numpy() * 15, unit="min"))
    cut = pd.Series(np.maximum(newest[0].to_numpy(), newest[1].to_numpy()), index=pd.DatetimeIndex(U(o)))
    return pd.Series(cut.reindex(U(rows["origin"])).to_numpy(), index=rows.index)


def sub_fit(fns, Xb, train, Xr, rows, model, target, hgb, cal, calib=None, cal_days=14):
    """fit on train, predict rows; optional calibration on the last `cal_days` of the (given) training rows.
    calib="eb50": probs' EB-shrunk Platt + multiplicative widths (experiments/lab/calib_eb.py), as in combo.py."""
    pred = fit_predict(Xb.loc[train.index], train, Xr, rows, model=model, target=target, hgb=hgb)
    if cal:
        c0 = train.delivery.max() - pd.Timedelta(days=cal_days)
        inner, calw = train[train.origin < c0 - pd.Timedelta(hours=10)], train[train.origin >= c0]
        pc = fit_predict(Xb.loc[inner.index], inner, Xb.loc[calw.index], calw, model=model, target=target, hgb=hgb)
        if calib == "eb50":
            from .calib_eb import calibrate_eb
            pred = calibrate_eb(pc, calw, pred, rows)
        else:
            pred = calibrate(pc, calw, pred, rows)
    return pred


def sub_bands(pred, fns, Xb, train, Xr, rows, bands, model, target, hgb, cal, calib=None, cal_days=14):
    """Per step band refit on the submission training rows (submission analogue of combo.band_post)."""
    out = {k: np.asarray(v, float).copy() for k, v in pred.items()}
    for a, b in bands:
        trb = train[train.step.between(a, b)]
        mv = rows.step.between(a, b).to_numpy()
        rb = rows[mv]
        pb = sub_fit(fns, Xb, trb, Xr.loc[rb.index], rb, model, target, hgb, cal, calib, cal_days)
        for k in out:
            out[k][mv] = pb[k]
    return out


def make(mode: str, fn_specs: list[str], model: str, target: str, cal: bool, tag: str, spec=None) -> Path:
    """spec: None (package-style CLI args), one combo spec dict, or a list of specs (equal-weight average)."""
    data, base = Data(), build_base()
    specs = [spec] if isinstance(spec, dict) else list(spec or [{}])
    if mode == "test":
        cutoff, tpl_path, origins_path = END, PKG / "sample_submission.csv", PKG / "forecast_origins.csv"
    else:
        cutoff = VAL_CUTOFF
        tmp = Path(tempfile.mkdtemp())
        subprocess.run([sys.executable, str(PKG / "make_templates.py"), "--test-start", "2026-09-07", "--test-end",
                        "2026-10-04", "--output-dir", str(tmp)], check=True, cwd=PKG, capture_output=True)
        tpl_path, origins_path = tmp / "sample_submission.csv", tmp / "forecast_origins.csv"
    tpl, rows = rows_from_template(tpl_path)
    print(f"{mode}: {rows.origin.nunique()} origins, {len(rows)} rows; cutoff {cutoff}, embargo {EMBARGO}, {len(specs)} spec(s)")
    train = base[(base.delivery < cutoff - EMBARGO) & base.gap.notna()]
    rows = rows.assign(spot=at_delivery(data.series("pkg", "fi_spot_price"), rows).to_numpy())
    assert rows.spot.notna().all(), "spot missing for some submission rows"

    preds = []
    for sp in specs:
        m, t, c = model, target, cal
        hgb = sp.get("hgb") or None
        if sp:
            from .combo import resolve
            m, t, c = sp.get("model", model), sp.get("target", target), sp.get("calibrate", cal)
            fns = resolve(list(dict.fromkeys(["package"] + list(sp["features"]))))
        else:
            fns = load_fns(fn_specs)
        print("spec:", sp.get("name", "(cli)"))
        for fn in fns:                           # leak-check on the submission origins themselves
            leakcheck(fn, rows.drop(columns="spot"), Data(), n=8, seed=7)
        Xb, Xr = feats(fns, base, data), feats(fns, rows.drop(columns="spot"), data)
        calib, cal_days = sp.get("calib"), int(sp.get("cal_days", 14))
        pred = sub_fit(fns, Xb, train, Xr, rows, m, t, hgb, c, calib, cal_days)
        if sp.get("bands"):
            pred = sub_bands(pred, fns, Xb, train, Xr, rows, [tuple(x) for x in sp["bands"]], m, t, hgb, c, calib, cal_days)
        if sp.get("hist_blend"):
            from .exp_history import blend_post
            pred = blend_post(float(sp["hist_blend"]))(pred, rows, Xr)
        if sp.get("causal"):
            from .features.structure import causal_post, ramp
            pred = causal_post(ramp(float(sp["causal"])))(pred, rows, Xr)
        preds.append({k: np.asarray(v, float) for k, v in pred.items()})
    pred = {k: np.mean([p[k] for p in preds], axis=0) for k in preds[0]}

    out = tpl.copy()
    p10, p50, p90 = np.sort(np.stack([pred["p10"], pred["p50"], pred["p90"]]), axis=0)
    pu, pdn, pn = (np.clip(pred[k], 0, 1) for k in ("p_up", "p_down", "p_none"))
    s = pu + pdn + pn
    pu, pdn, pn = pu / s, pdn / s, pn / s
    hi, lo = np.clip(pred["p_hi"], 0, 1), np.clip(pred["p_lo"], 0, 1)
    sl = np.maximum(hi + lo, 1.0)
    vals = dict(p10=p10, p50=p50, p90=p90, p_up=pu, p_down=pdn, p_none=1 - pu - pdn,
                p_spike_high=hi / sl, p_spike_low=lo / sl)
    for k in COLS:
        out[k] = np.round(vals[k], 6)
    dc = data_cutoff(rows, data)
    assert (dc <= rows.origin).all()
    out["data_cutoff_utc"] = pd.DatetimeIndex(dc).strftime("%Y-%m-%dT%H:%M:%SZ")
    out["top_drivers"] = ""
    OUT.mkdir(exist_ok=True)
    path = OUT / (f"forecast_backtest_{tag}.csv" if mode == "test" else f"validation_{tag}.csv")
    out.to_csv(path, index=False, lineterminator="\n")
    print(f"wrote {path.relative_to(ROOT)}")

    r = subprocess.run([sys.executable, "validate_submission.py", "--backtest", str(path), "--origins", str(origins_path)],
                       cwd=PKG, capture_output=True, text=True)
    print(r.stdout.strip().splitlines()[0] if r.stdout else r.stderr[-500:], f"(validator rc={r.returncode})")
    if r.returncode:
        print(r.stdout[-2000:])
    if mode == "val":
        sd = OUT / f"score_{tag}"
        r = subprocess.run([sys.executable, "score.py", "--submission", str(path), "--actuals", "data/actuals_validation.csv",
                            "--spike-margin", "50", "--output-dir", str(sd), "--baseline-summary",
                            "baseline_output/validation/score/score_summary.csv"], cwd=PKG, capture_output=True, text=True)
        print(f"score.py rc={r.returncode}")
        md = (sd / "score_summary.md")
        if md.exists():
            print("\n".join(l for l in md.read_text().splitlines() if l.startswith("| ") and any(
                k in l for k in ("MAE (p50)", "Mean pinball", "coverage", "Mean Brier", "Three-class", "ratio"))))
    return path


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["val", "test"], required=True)
    ap.add_argument("--features", nargs="+", default=["experiments.lab.features.package:package_features"])
    ap.add_argument("--model", default="mixture")
    ap.add_argument("--target", default="gap")
    ap.add_argument("--no-cal", action="store_true")
    ap.add_argument("--tag", default="ref_mixture")
    ap.add_argument("--spec", help="combo spec JSON string")
    ap.add_argument("--spec-file")
    a = ap.parse_args()
    sp = json.loads(a.spec) if a.spec else json.loads(Path(a.spec_file).read_text()) if a.spec_file else None  # dict or list
    make(a.mode, a.features, a.model, a.target, not a.no_cal, a.tag, sp)
