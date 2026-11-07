"""Build the situation view's data: frontend/public/payload.json (git-ignored: it holds licensed spot prices).

    .venv\\Scripts\\python.exe frontend/scripts/build_data.py        (from the repo root)

Copied from Abdo's front-end branch (origin/front-end, commit 891f536; app updated to 69cee5a) into brainstorming-frank and pointed at
the team's current submission: 1/2 Frank's v7_rt + 1/2 Abdo's h_int4ss, P90 stretched x1.15, spike
probabilities capped by direction (submissions/MANIFEST.md). The forecast shown is the submitted file itself;
the two members are loaded too (for the "models disagree" alert), and the script checks that blending them
with the same recipe reproduces the submitted file.

For each replay period it writes
  * the quarter-hour grid: spot, realised imbalance price and mFRR direction, each with the time it was published
    (first_usable_origin_utc), so the page can show only what was known at the review time;
  * every hourly forecast (40 quarter-hours): the submitted blend, plus both members' median and direction,
    so disagreements can be flagged;
  * alerts per forecast hour (spike risk, direction, material change, model conflict, wide uncertainty).
"""
from __future__ import annotations

import io
import json
import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
MAIN = Path(os.environ.get("TE_DATA_ROOT", ROOT.parent / "turku-energy-since-ai"))   # untracked team files live here
OUT = ROOT / "frontend/public/payload.json"
STEPS = 40
Q = pd.Timedelta(minutes=15)


def find(rel: str) -> Path | None:
    for base in (ROOT, MAIN):
        if (base / rel).exists():
            return base / rel
    return None


MODEL = "v7_rt + h_int4ss (equal-weight blend)"
# blend: the submitted file; frank: our v7_rt; ours: Abdo's h_int4ss (local copy, else read from his branch in git)
PERIODS = {
    "val": dict(label={"en": "Validation, 7 Sep – 4 Oct 2026", "fi": "Validointi, 7.9.–4.10.2026"},
                blend="submissions/blend_v7_rt_h_int4ss_validation.csv", frank="submissions/v7_rt_validation.csv",
                ours=("results/ext_abdo_h_int4ss/validation/forecast_backtest.csv", "submissions/validation_h_int4ss.csv")),
    "aug": dict(label={"en": "August 2026 (second check)", "fi": "Elokuu 2026 (toinen tarkistus)"},
                blend="submissions/blend_v7_rt_h_int4ss_august.csv", frank="submissions/v7_rt_august.csv",
                ours=("results/ext_abdo_h_int4ss/fold_b/forecast_backtest.csv", "submissions/foldb_h_int4ss.csv")),
    "test": dict(label={"en": "Test, 5 Oct – 1 Nov 2026", "fi": "Testi, 5.10.–1.11.2026"},
                 blend="submissions/blend_v7_rt_h_int4ss_test.csv", frank="submissions/v7_rt_test.csv",
                 ours=("results/ext_abdo_forecast_backtest_h_int4ss/test/forecast_backtest.csv",
                       "submissions/forecast_backtest_h_int4ss.csv")),
}
ABDO_REF = "origin/brainstorming-abdo"
COLS = ["p10", "p50", "p90", "p_up", "p_down", "p_none", "p_spike_high", "p_spike_low"]
# The submitted blend stretches P90 away from P50 (too many prices landed above the 50/50 blend's P90 in
# September and August; factor cross-fitted between the two months, docs/RESULTS.md round 9).
P90_STRETCH = 1.0       # the shown model is the plain 50/50 blend (highest scorer); 1.15 = Frank's stretched variant
SPIKE_CAP = False


def load_member(src) -> pd.DataFrame:
    d = pd.read_csv(src)
    d["origin"] = pd.to_datetime(d["forecast_origin_utc"], utc=True)
    return d.sort_values(["origin", "step"]).reset_index(drop=True)


def load_abdo(local: str, in_git: str) -> pd.DataFrame | None:
    path = find(local)
    if path is not None:
        return load_member(path)
    try:
        blob = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{ABDO_REF}:{in_git}"], stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None
    return load_member(io.BytesIO(blob))


def blend(a: pd.DataFrame, b: pd.DataFrame) -> pd.DataFrame:
    """The submission's recipe: 50/50 (same rules as experiments/lab/combine.py), then P90 stretched by
    P90_STRETCH and the spike probabilities capped by the matching direction (p_spike_high <= p_up,
    p_spike_low <= p_down)."""
    out = a[["origin", "step"]].copy()
    for c in COLS:
        out[c] = (a[c].to_numpy(float) + b[c].to_numpy(float)) / 2
    q = np.sort(out[["p10", "p50", "p90"]].to_numpy(), axis=1)
    out["p10"], out["p50"], out["p90"] = q[:, 0], q[:, 1], q[:, 2]
    s = out[["p_up", "p_down", "p_none"]].clip(0, 1)
    s = s.div(s.sum(axis=1), axis=0)
    out["p_up"], out["p_down"], out["p_none"] = s["p_up"], s["p_down"], s["p_none"]
    sl = np.maximum(out.p_spike_high + out.p_spike_low, 1.0)
    out["p_spike_high"], out["p_spike_low"] = out.p_spike_high / sl, out.p_spike_low / sl
    out["p90"] = out["p50"] + P90_STRETCH * (out["p90"] - out["p50"])
    if SPIKE_CAP:
        out["p_spike_high"] = np.minimum(out["p_spike_high"], out["p_up"])
        out["p_spike_low"] = np.minimum(out["p_spike_low"], out["p_down"])
    return out


def runs(mask: np.ndarray, min_len: int = 1) -> list[tuple[int, int]]:
    """Contiguous True runs as (first, last) step indices."""
    out, start = [], None
    for i, m in enumerate(list(mask) + [False]):
        if m and start is None:
            start = i
        elif not m and start is not None:
            if i - start >= min_len:
                out.append((start, i - 1))
            start = None
    return out


def alerts_for(i: int, F: dict, prev: dict | None) -> list[dict]:
    """Alert rules for forecast hour i (F: arrays [n_origins, 40]); prev = same quarters in the previous hour's forecast."""
    al = []
    hi, lo, pu, pd_ = F["hi"][i], F["lo"][i], F["pu"][i], F["pd"][i]
    # thresholds put each alert type in roughly the top 10-15 % of hours (test month), so quiet hours stay quiet
    for kind, p, thr, hard in (("spike_high", hi, 0.40, 0.55), ("spike_low", lo, 0.50, 0.65)):
        for a, b in runs(p >= thr, 1):
            mx = float(p[a:b + 1].max())
            rise = None
            if prev is not None:
                pp = prev["hi" if kind == "spike_high" else "lo"][a:b + 1]
                if np.isfinite(pp).any():
                    rise = mx - float(np.nanmax(pp))
            al.append(dict(kind=kind, a=a, b=b, value=round(mx, 3), rise=None if rise is None else round(rise, 3),
                           level="high" if mx >= hard else "medium"))
    # down-regulation is the normal state (about 60 % of quarters); only up-regulation is flagged
    for a, b in runs(pu >= 0.70, 4):
        al.append(dict(kind="dir_up", a=a, b=b, value=round(float(pu[a:b + 1].mean()), 3), level="info"))
    if prev is not None:
        d = F["p50"][i] - prev["p50"]
        for a, b in runs(np.abs(np.nan_to_num(d)) >= 35, 2):
            k = int(a + np.nanargmax(np.abs(d[a:b + 1])))
            al.append(dict(kind="changed", a=a, b=b, value=round(float(d[k]), 1), level="medium"))
    gap = np.abs(F["fr_p50"][i] - F["ou_p50"][i])
    dirx = ((F["fr_pu"][i] >= 0.6) & (F["ou_pd"][i] >= 0.6)) | ((F["fr_pd"][i] >= 0.6) & (F["ou_pu"][i] >= 0.6))
    for a, b in runs((gap >= 60) | dirx, 2):
        al.append(dict(kind="conflict", a=a, b=b, value=round(float(gap[a:b + 1].max()), 1), level="medium"))
    width = F["p90"][i] - F["p10"][i]
    for a, b in runs(width >= 250, 4):
        al.append(dict(kind="review", a=a, b=b, value=round(float(width[a:b + 1].max()), 1), level="medium"))
    return al


def period_payload(pid: str, cfg: dict, L: pd.DataFrame) -> dict | None:
    bp, fp = find(cfg["blend"]), find(cfg["frank"])
    ou = load_abdo(*cfg["ours"])
    if bp is None or fp is None or ou is None:
        print(f"{pid}: skipped (missing {cfg['blend'] if bp is None else cfg['frank'] if fp is None else cfg['ours'][1]})")
        return None
    fr, sub = load_member(fp), load_member(bp)
    for m in (ou, sub):
        assert (fr.origin.values == m.origin.values).all() and (fr.step.values == m.step.values).all(), "files misaligned"
    bl = sub[["origin", "step"] + COLS].copy()            # exactly what was submitted
    gap = max(float(np.abs(blend(fr, ou)[c].to_numpy() - bl[c].to_numpy()).max()) for c in COLS)
    assert gap < 1e-5, f"{pid}: members + recipe differ from the submitted file by {gap}"
    origins = bl.origin.drop_duplicates().sort_values()
    n = len(origins)
    A = lambda df, c: df[c].to_numpy(float).reshape(n, STEPS)
    F = dict(p10=A(bl, "p10"), p50=A(bl, "p50"), p90=A(bl, "p90"), pu=A(bl, "p_up"), pd=A(bl, "p_down"),
             pn=A(bl, "p_none"), hi=A(bl, "p_spike_high"), lo=A(bl, "p_spike_low"),
             fr_p50=A(fr, "p50"), fr_pu=A(fr, "p_up"), fr_pd=A(fr, "p_down"),
             ou_p50=A(ou, "p50"), ou_pu=A(ou, "p_up"), ou_pd=A(ou, "p_down"))
    # previous hour's forecast for the same delivery quarters (shift by 4 steps)
    alerts = []
    for i in range(n):
        prev = None
        if i > 0 and origins.iloc[i] - origins.iloc[i - 1] == pd.Timedelta(hours=1):
            prev = {k: np.concatenate([F[k][i - 1][4:], np.full(4, np.nan)]) for k in ("p50", "hi", "lo")}
        alerts.append(alerts_for(i, F, prev))
    # drivers (Frank's TreeSHAP names), deduplicated combos
    drv = fr["top_drivers"].fillna("").tolist()
    combos = sorted(set(drv))
    cidx = {c: k for k, c in enumerate(combos)}
    # quarter grid: 24 h before the first origin to the last delivery quarter
    t0 = origins.iloc[0] - pd.Timedelta(hours=24)
    t1 = origins.iloc[-1] + (STEPS - 1) * Q
    grid = pd.date_range(t0, t1, freq="15min")
    ser = {}
    for sid, key in (("fi_spot_price", "spot"), ("fi_imbalance_price", "imb"), ("fi_mfrr_direction", "dir")):
        s = L[L.series_id == sid].drop_duplicates("ts").set_index("ts")
        ser[key] = s["value"].reindex(grid)
        ser[key + "_fu"] = s["fu"].reindex(grid)
    mins = lambda t: ((t - t0) / pd.Timedelta(minutes=1)).round()
    r1, r3 = (lambda x: np.round(x, 1)), (lambda x: np.round(x, 3))
    nan2none = lambda a: [None if not np.isfinite(v) else float(v) for v in a]
    out = {
        "label": cfg["label"], "t0": int(t0.timestamp() * 1000), "nq": len(grid),
        "origins": [int((o - t0) / Q) for o in origins],          # grid index of each origin's first quarter
        "spot": nan2none(r1(ser["spot"].to_numpy(float))), "spot_fu": nan2none(mins(ser["spot_fu"]).to_numpy(float)),
        "imb": nan2none(r1(ser["imb"].to_numpy(float))), "imb_fu": nan2none(mins(ser["imb_fu"]).to_numpy(float)),
        "dir": nan2none(ser["dir"].to_numpy(float)), "dir_fu": nan2none(mins(ser["dir_fu"]).to_numpy(float)),
        "cutoff": [int(((pd.Timestamp(c) - t0) / pd.Timedelta(minutes=1))) for c in             # freshest data used
                   pd.concat([m.groupby("origin")["data_cutoff_utc"].max() for m in (fr, ou)], axis=1).max(axis=1).reindex(origins)],
        "fc": {k: (r1(v) if k in ("p10", "p50", "p90", "fr_p50", "ou_p50") else r3(v)).ravel().tolist() for k, v in F.items()},
        "drivers": [cidx[d] for d in drv], "driver_combos": combos,
        "alerts": alerts,
    }
    na = np.array([len(a) for a in alerts])
    kinds = pd.Series([a["kind"] for al in alerts for a in al]).value_counts().to_dict()
    print(f"{pid}: {n} origins, grid {len(grid)} quarters, alerts per hour mean {na.mean():.2f} (quiet hours {np.mean(na == 0):.0%}); {kinds}")
    return out


def main():
    pkg = find("starter_package/v1/starter_package_v1/data/inputs.parquet") or find("starter_package/data/inputs.parquet")
    inp = pd.read_parquet(pkg)
    spot = pd.read_csv(pkg.parent / "spot_nordpool.csv")
    L = pd.concat([inp, spot], ignore_index=True)
    L = L[L.series_id.isin(["fi_spot_price", "fi_imbalance_price", "fi_mfrr_direction"])].copy()
    L["ts"] = pd.to_datetime(L.timestamp_utc, utc=True)
    L["fu"] = pd.to_datetime(L.first_usable_origin_utc, utc=True)
    payload = {"generated": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"), "model": MODEL,
               "periods": {}}
    for pid, cfg in PERIODS.items():
        p = period_payload(pid, cfg, L)
        if p:
            payload["periods"][pid] = p
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, separators=(",", ":"), allow_nan=False))
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
