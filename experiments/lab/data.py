"""Shared, leak-safe data layer for the experiment swarm.

Everything is keyed by (origin, step). A feature function has the signature

    fn(base: DataFrame, data: Data) -> DataFrame   # same index as base, one column per feature

and must ONLY read source rows through the helpers below (asof / at_delivery / nwp_latest),
which drop every row whose first-usable time (`fu`) is after the row's origin.
`leakcheck(fn)` proves it: for random origins it recomputes the features with all sources
truncated to fu <= origin and requires identical values.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PKG = ROOT / "starter_package"
EXT = ROOT / "external_data"
CACHE = Path(__file__).resolve().parent / "_cache"
CACHE.mkdir(exist_ok=True)
Q = pd.Timedelta(minutes=15)


def U(x):
    """Coerce timestamps (Series/Index/array/scalar) to tz-aware UTC, nanosecond unit."""
    if isinstance(x, pd.Series):
        return pd.to_datetime(x, utc=True).dt.as_unit("ns")
    if isinstance(x, pd.Timestamp):
        return (x.tz_localize("UTC") if x.tzinfo is None else x.tz_convert("UTC")).as_unit("ns")
    return pd.DatetimeIndex(pd.to_datetime(x, utc=True)).as_unit("ns")

# LAB_HISTORY=1: train on Mar 2025 - Oct 2026 (package + external_data/history/pkg_history.csv.gz, built by
# build_history.py; imbalance price recomputed with the 1 Jun 2026 rule) and add fold C = last year's test period.
# Separate caches, prediction folder and leaderboard, so nothing mixes with the package-only lab.
HISTORY = os.environ.get("LAB_HISTORY") == "1"
SUFFIX = "_hist" if HISTORY else ""
FIRST_ORIGIN = pd.Timestamp("2025-03-05T00:00Z" if HISTORY else "2026-06-02T00:00Z")
END = pd.Timestamp("2026-10-04T21:00Z")              # training data ends (deliveries < END)
FOLDS = {
    # fold A = the organisers' validation window; fold B = August, trained on June-July only
    "A": dict(train_end=pd.Timestamp("2026-09-06T21:00Z"), val_start=pd.Timestamp("2026-09-06T21:00Z"), val_end=END),
    "B": dict(train_end=pd.Timestamp("2026-07-31T21:00Z"), val_start=pd.Timestamp("2026-07-31T21:00Z"),
              val_end=pd.Timestamp("2026-08-31T21:00Z")),
}
if HISTORY:   # fold C = 5 Oct - 1 Nov 2025 (same weeks as the test, one year earlier), trained on Mar - Sep 2025
    FOLDS["C"] = dict(train_end=pd.Timestamp("2025-10-04T21:00Z"), val_start=pd.Timestamp("2025-10-04T21:00Z"),
                      val_end=pd.Timestamp("2025-11-01T22:00Z"))


def _atomic_pickle(df: pd.DataFrame, path: Path) -> None:
    """Parallel jobs (LUMI arrays, the local queue) may build the same cache at once: write, then rename."""
    tmp = path.with_suffix(f".tmp{os.getpid()}")
    df.to_pickle(tmp)
    tmp.replace(path)


# ----------------------------------------------------------------------------- loading
def _long(df: pd.DataFrame, ts="timestamp_utc", fu="first_usable_origin_utc") -> pd.DataFrame:
    out = pd.DataFrame({"series_id": df["series_id"], "ts": U(df[ts]),
                        "value": pd.to_numeric(df["value"], errors="coerce"), "fu": U(df[fu])})
    return out.dropna(subset=["ts", "fu"])


class Data:
    """Lazy access to every source in a common format. Long sources have columns
    series_id, ts, value, fu. Event/run sources keep their own columns plus `fu`."""

    def __init__(self, frames: dict[str, pd.DataFrame] | None = None, cut: pd.Timestamp | None = None):
        self._f = dict(frames or {})
        self._cut = cut          # if set, every source (even one loaded later) keeps only fu <= cut

    def __contains__(self, k):
        return k in self._f or self._path(k) is not None

    def _path(self, k):
        m = {
            "pkg": None,
            "fg_rt": [EXT / "fingrid/rt_last_autumn.csv.gz", EXT / "fingrid/rt_main.csv.gz"]
                     + ([EXT / "fingrid/rt_history.csv.gz"] if HISTORY else []),
            "fg_extra": [EXT / "fingrid/extra_last_autumn.csv.gz", EXT / "fingrid/extra_main.csv.gz"],
            "fg_mfrr2": [EXT / "fingrid/mfrr2_main.csv.gz"] + ([EXT / "fingrid/mfrr2_history.csv.gz"] if HISTORY else []),
            "fg_rt2": [EXT / "fingrid/rt2_last_autumn.csv.gz", EXT / "fingrid/rt2_main.csv.gz"]
                      + ([EXT / "fingrid/rt2_history.csv.gz"] if HISTORY else []),
            "fg_hist": [EXT / "fingrid/package_history.csv.gz"],
            "umm": [EXT / "umm/messages_last_autumn.csv.gz", EXT / "umm/messages_main.csv.gz"],
            "fmi": [EXT / "fmi/obs_last_autumn.csv.gz", EXT / "fmi/obs_main.csv.gz"],
            "ifs": [EXT / "open_meteo/runs_ecmwf_ifs_last_autumn.csv.gz", EXT / "open_meteo/runs_ecmwf_ifs_main.csv.gz"]
                   + ([EXT / f"open_meteo/runs_ecmwf_ifs_history_{x}.csv.gz" for x in "ab"] if HISTORY else []),
            "icon": [EXT / "open_meteo/runs_icon_eu_main.csv.gz"],
            # Frank's Open-Meteo single runs (same delays: IFS +8 h, ICON +5 h): points ifs_*, icon_*, nord_*
            "fw": [EXT / "_frank/open_meteo/runs_frank_points.csv.gz"],
            "metno": [EXT / "open_meteo/runs_metno_nordic_main.csv.gz"],
            "era5": [EXT / "open_meteo/era5_last_autumn.csv.gz", EXT / "open_meteo/era5_main.csv.gz"],
            "elering": [EXT / "elering/system_last_autumn.csv.gz", EXT / "elering/system_main.csv.gz"],
            "energinet": [EXT / "energinet/power_system_last_autumn.csv.gz", EXT / "energinet/power_system_main.csv.gz"],
        }.get(k, "missing")
        if m is None or m == "missing":
            return None
        files = [p for p in m if p.exists()]
        return files or None

    def __getitem__(self, k) -> pd.DataFrame:
        if k in self._f:
            return self._f[k]
        if k == "pkg":
            cp = CACHE / f"pkg_long{SUFFIX}.pkl"
            if cp.exists():
                df = pd.read_pickle(cp)
            else:
                inp = pd.read_parquet(PKG / "data/inputs.parquet")
                spot = pd.read_csv(PKG / "data/spot_nordpool.csv")
                df = _long(pd.concat([inp, spot], ignore_index=True))
                if HISTORY:     # history rows only before each series' first package quarter
                    h = _long(pd.read_csv(EXT / "history/pkg_history.csv.gz"))
                    h = h[h.series_id.isin(df.series_id.unique())]
                    first = df.groupby("series_id").ts.min()
                    h = h[h.ts < h.series_id.map(first)]
                    df = pd.concat([h, df], ignore_index=True).sort_values(["series_id", "ts"]).reset_index(drop=True)
                _atomic_pickle(df, cp)
        else:
            files = self._path(k)
            if not files:
                raise KeyError(f"source {k!r} not downloaded yet")
            parts = [pd.read_csv(p) for p in files]
            raw = pd.concat(parts, ignore_index=True)
            if k in ("fg_rt", "fg_rt2", "fg_mfrr2", "fg_extra", "fg_hist"):
                df = _long(raw)
            else:
                df = raw
                for c in df.columns:
                    if c.endswith("_utc") or c in ("publicationDate",):
                        df[c] = U(pd.to_datetime(df[c], utc=True, format="ISO8601"))
                df["fu"] = df["first_usable_origin_utc"]
        if self._cut is not None:
            df = df[df["fu"] <= self._cut]
        self._f[k] = df
        return df

    def series(self, src: str, series_id: str) -> pd.DataFrame:
        df = self[src]
        return df[df.series_id == series_id]

    def truncated(self, origin: pd.Timestamp) -> "Data":
        """A copy where every loaded source only keeps rows with fu <= origin (for leakcheck)."""
        return Data({k: v[v["fu"] <= origin] for k, v in self._f.items()}, cut=origin)


# ----------------------------------------------------------------------------- helpers (the ONLY way to read sources)
def asof(s: pd.DataFrame, origins: pd.Series, lags=(0,)) -> pd.DataFrame:
    """Per origin: value of the newest usable quarter (fu <= origin) and of quarters `lag`
    steps before it (also only if usable). Also `age_q` = quarters from newest ts to origin.
    `s` = one series (columns ts, value, fu). Returns DataFrame indexed like `origins`."""
    o = pd.DataFrame({"origin": U(pd.Series(origins.to_numpy())).to_numpy()}, index=origins.index)
    o["origin"] = U(o["origin"])
    s = s.dropna(subset=["value"])
    out = pd.DataFrame(index=origins.index)
    if s.empty:
        for L in lags:
            out[f"lag{L}"] = np.nan
        out["age_q"] = np.nan
        return out
    by_fu = s.sort_values("fu")[["fu", "ts"]].copy()
    by_fu["ts_max"] = by_fu.ts.cummax()
    m = pd.merge_asof(o.reset_index().sort_values("origin"), by_fu[["fu", "ts_max"]], left_on="origin",
                      right_on="fu", direction="backward").set_index("index").reindex(o.index)
    newest = m["ts_max"]
    vals = s.drop_duplicates("ts").set_index("ts")
    for L in lags:
        t = newest - L * Q
        v = vals["value"].reindex(t).to_numpy()
        f = vals["fu"].reindex(t).to_numpy()
        ok = pd.notna(f) & (U(f) <= U(o["origin"]))
        out[f"lag{L}"] = np.where(ok, v, np.nan)
    out["age_q"] = ((o["origin"] - newest) / Q).to_numpy()
    return out


def asof_window(s: pd.DataFrame, origins: pd.Series, n: int, how="mean") -> pd.Series:
    """Mean/min/max/std over the n newest usable quarters at each origin."""
    a = asof(s, origins, lags=tuple(range(n)))
    cols = [f"lag{i}" for i in range(n)]
    return getattr(a[cols], how)(axis=1)


def at_delivery(s: pd.DataFrame, base: pd.DataFrame, offset_q: int = 0) -> pd.Series:
    """Value at the delivery quarter (+offset), only where it is usable at the row's origin."""
    v = s.drop_duplicates("ts").set_index("ts")
    t = base["delivery"] + offset_q * Q
    val = v["value"].reindex(t).to_numpy()
    fu = U(v["fu"].reindex(t).to_numpy())
    ok = pd.notna(fu) & (fu <= U(base["origin"]))
    return pd.Series(np.where(ok, val, np.nan), index=base.index)


def per_origin(base: pd.DataFrame, per_origin_df: pd.DataFrame) -> pd.DataFrame:
    """Broadcast an origin-indexed frame (index = unique origins) to all base rows."""
    df = per_origin_df.copy()
    df.index = U(df.index)
    return df.reindex(U(base["origin"])).set_index(base.index)


def nwp_latest(nwp: pd.DataFrame, base: pd.DataFrame, var: str, point: str | None = None, nth: int = 0) -> pd.Series:
    """Value of `var` (mean over points, or one point) at the delivery hour from the newest
    model run usable at the row's origin (nth=1: the run before that). Linear in time between hours."""
    df = nwp if point is None else nwp[nwp.point == point]
    g = df.groupby(["run_init_utc", "valid_utc"])[var].mean().reset_index()
    runs = g[["run_init_utc"]].drop_duplicates().copy()
    fu_of_run = df.groupby("run_init_utc")["fu"].max()
    runs["fu"] = runs.run_init_utc.map(fu_of_run)
    runs = runs.sort_values("fu").reset_index(drop=True)
    uo = pd.DataFrame({"origin": U(base["origin"].drop_duplicates().sort_values()).to_numpy()})
    uo["origin"] = U(uo["origin"])
    runs["fu"] = U(runs["fu"])
    m = pd.merge_asof(uo, runs.rename(columns={"fu": "rfu"}), left_on="origin", right_on="rfu", direction="backward")
    if nth:
        idx = runs.index[runs.run_init_utc.isin(m.run_init_utc)]
        pos = pd.Series(range(len(runs)), index=runs.run_init_utc)
        k = m.run_init_utc.map(pos) - nth
        m["run_init_utc"] = [runs.run_init_utc.iloc[int(i)] if pd.notna(i) and i >= 0 else pd.NaT for i in k]
    run_of_origin = m.set_index("origin").run_init_utc
    r = base["origin"].map(run_of_origin)
    h0 = base["delivery"].dt.floor("h")
    frac = ((base["delivery"] - h0) / pd.Timedelta("1h")).to_numpy()
    look = g.set_index(["run_init_utc", "valid_utc"])[var]
    v0 = look.reindex(pd.MultiIndex.from_arrays([r, h0])).to_numpy()
    v1 = look.reindex(pd.MultiIndex.from_arrays([r, h0 + pd.Timedelta("1h")])).to_numpy()
    v = np.where(np.isnan(v1), v0, v0 + (v1 - v0) * frac)
    return pd.Series(v, index=base.index)


# ----------------------------------------------------------------------------- base table
def _window(base: pd.DataFrame) -> pd.DataFrame:
    """LAB_TRAIN_DAYS=N: keep only the last N days before each fold's train_end as training rows (ablation)."""
    n = os.environ.get("LAB_TRAIN_DAYS")
    if n:
        for f, c in FOLDS.items():
            old = (base[f"fold{f}"] == "train") & (base.delivery < c["train_end"] - pd.Timedelta(days=float(n)))
            base.loc[old, f"fold{f}"] = ""
    return base


def build_base() -> pd.DataFrame:
    cp = CACHE / f"base{SUFFIX}.pkl"
    if cp.exists():
        return _window(pd.read_pickle(cp))
    d = Data()
    pkg = d["pkg"]
    W = pkg.pivot_table(index="ts", columns="series_id", values="value")
    origins = pd.date_range(FIRST_ORIGIN, END - pd.Timedelta(hours=1), freq="h")
    base = pd.DataFrame({"origin": np.repeat(origins, 40), "step": np.tile(np.arange(1, 41), len(origins))})
    base["origin"] = U(base["origin"])
    base["delivery"] = base.origin + (base.step - 1) * Q
    tg = W.reindex(base.delivery)
    base["imb"] = tg["fi_imbalance_price"].to_numpy()
    base["spot"] = tg["fi_spot_price"].to_numpy()
    base["gap"] = base.imb - base.spot
    base["dir"] = tg["fi_mfrr_direction"].to_numpy()
    for f, c in FOLDS.items():
        role = np.full(len(base), "", dtype=object)
        role[(base.delivery < c["train_end"]).to_numpy()] = "train"
        role[((base.origin >= c["val_start"]) & (base.delivery < c["val_end"])).to_numpy()] = "val"
        base[f"fold{f}"] = role
    base = base[base.delivery < END].reset_index(drop=True)
    _atomic_pickle(base, cp)
    return _window(base)


TARGET_COLS = {"imb", "gap", "dir"}   # never usable as features


# ----------------------------------------------------------------------------- leak check
def leakcheck(fn, base: pd.DataFrame | None = None, data: Data | None = None, n: int = 12, seed: int = 0,
              sources: tuple = ("pkg",), full: pd.DataFrame | None = None) -> None:
    """Recompute fn for n random origins with every source truncated to fu <= origin.
    Raises AssertionError on any difference. `full`: fn(base, data) if already computed (disk cache)."""
    base = build_base() if base is None else base
    base = base.drop(columns=[c for c in ("imb", "gap", "dir", "spot") if c in base.columns])  # no targets in feature fns
    data = Data() if data is None else data
    for s in sources:
        data[s]  # load
    full = fn(base, data) if full is None else full
    bad = set(full.columns) & TARGET_COLS
    assert not bad, f"feature names collide with targets: {bad}"
    rng = np.random.default_rng(seed)
    origins = rng.choice(base.origin.unique(), size=n, replace=False)
    for o in origins:
        o = U(pd.Timestamp(o))
        b = base[base.origin == o]
        part = fn(b, data.truncated(o))
        ref = full.loc[b.index, part.columns]
        a, r = part.to_numpy(float), ref.to_numpy(float)
        same = np.isclose(a, r, equal_nan=True, rtol=1e-9, atol=1e-9)
        if not same.all():
            cols = [c for c, ok in zip(part.columns, same.all(axis=0)) if not ok]
            raise AssertionError(f"LEAK in {fn.__name__} at origin {o}: columns {cols}")
    print(f"leakcheck OK: {fn.__name__} ({full.shape[1]} features, {n} origins)")


def threads(n: int = 2) -> None:
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        os.environ.setdefault(k, str(n))
