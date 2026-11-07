"""Agent `history`: direction run structure, neighbour real-time data, and direction priors
fitted on the Fingrid package history (Mar 2025 - May 2026, key `fg_hist`).

Leak safety
  * run / spike / day-lag features read the package only through asof / at_delivery.
  * neighbour features convert elering / energinet to long form and read them through asof.
  * history models are fitted ONLY on `fg_hist`, whose rows are all usable before the first
    origin (2026-06-02) and before the fitting cutoff 2026-07-31T21:00Z (asserted). They are applied
    to features computed through the same leak-safe helpers, so leakcheck still verifies them.
"""
from __future__ import annotations

import hashlib
import pickle

import numpy as np
import pandas as pd

from ..data import CACHE, Q, U, Data, asof, at_delivery, per_origin

CUTOFF = pd.Timestamp("2026-07-31T21:00Z")
TZ = "Europe/Helsinki"
S = lambda d, sid: d.series("pkg", sid)

# fg_hist series -> package names (same Fingrid datasets as the package)
HIST_MAP = {
    "fg319_imbalance_price": "fi_imbalance_price", "fg369_mfrr_direction": "fi_mfrr_direction",
    "fg244_mfrr_up_price": "fi_mfrr_up_price", "fg106_mfrr_down_price": "fi_mfrr_down_price",
    "fg375_mfrr_up_activated": "fi_mfrr_up_activated", "fg376_mfrr_down_activated": "fi_mfrr_down_activated",
    "fg347_afrr_up_price": "fi_afrr_up_price", "fg348_afrr_down_price": "fi_afrr_down_price",
    "fg124_consumption": "fi_consumption", "fg74_production": "fi_production",
    "fg61_se3_flow": "fi_se3_flow", "fg57_no4_flow": "fi_no4_flow", "fg60_se1_flow": "fi_se1_flow",
    "fg55_ee_flow": "fi_ee_flow", "fg165_consumption_fc_da": "fi_consumption_fc_da",
    "fg246_wind_fc_da": "fi_wind_fc_da", "fg247_solar_fc_da": "fi_solar_fc_da",
}


def _uo(base):
    return base["origin"].drop_duplicates().sort_values().reset_index(drop=True)


def _local(ts: pd.Series):
    loc = ts.dt.tz_convert(TZ)
    return loc.dt.hour.to_numpy(), loc.dt.weekday.to_numpy()


# ----------------------------------------------------------------------------- 1. run structure
def _run_stats(D: np.ndarray) -> dict:
    """D: (n, L) directions, column 0 = newest usable quarter. NaN = missing."""
    n, L = D.shape
    first = D[:, :1]
    same = (D == first)
    run = np.cumprod(same, axis=1).sum(axis=1).astype(float)
    run[np.isnan(D[:, 0])] = np.nan
    prev = np.full(n, np.nan)
    for i in range(n):
        r = run[i]
        if np.isnan(r) or r >= L:
            continue
        r = int(r)
        v = D[i, r]
        if np.isnan(v):
            continue
        k = r
        while k < L and D[i, k] == v:
            k += 1
        prev[i] = k - r
    nz = np.where(D == 0, np.nan, D)
    sw16 = np.nansum((nz[:, :15] * nz[:, 1:16]) == -1, axis=1).astype(float)
    with np.errstate(all="ignore"):
        out = dict(run_len=run, prev_run_len=prev, n_switch16=sw16,
                   up8=np.nanmean(D[:, :8] == 1, axis=1), up32=np.nanmean(D[:, :32] == 1, axis=1),
                   up96=np.nanmean(D[:, :96] == 1, axis=1))
    return out


def runs_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Direction run structure + spike regime counts + same-quarter-yesterday direction."""
    o = _uo(base)
    L = 96
    a = asof(S(data, "fi_mfrr_direction"), o, lags=tuple(range(L)))
    D = a[[f"lag{i}" for i in range(L)]].to_numpy(float)
    rs = pd.DataFrame(_run_stats(D), index=U(o))
    # spike regime: share of |gap| > 50 among last 96 usable quarters (spot of a past quarter is known)
    g = asof(S(data, "fi_imbalance_price"), o, lags=tuple(range(L)))
    oi = pd.DatetimeIndex(U(o))
    last = oi - pd.to_timedelta(g["age_q"].to_numpy() * 15, unit="min")
    spot_at = S(data, "fi_spot_price").drop_duplicates("ts").set_index("ts")["value"]
    sp = np.stack([spot_at.reindex(last - i * Q).to_numpy() for i in range(L)], axis=1)
    gaps = g[[f"lag{i}" for i in range(L)]].to_numpy(float) - sp
    with np.errstate(all="ignore"):
        ok = ~np.isnan(gaps)
        rs["hi96"] = np.nansum(gaps > 50, axis=1) / np.maximum(ok.sum(axis=1), 1)
        rs["lo96"] = np.nansum(gaps < -50, axis=1) / np.maximum(ok.sum(axis=1), 1)
        rs["hi16"] = np.nansum(gaps[:, :16] > 50, axis=1) / np.maximum(ok[:, :16].sum(axis=1), 1)
        rs["lo16"] = np.nansum(gaps[:, :16] < -50, axis=1) / np.maximum(ok[:, :16].sum(axis=1), 1)
        rs["gapmax16"] = np.nanmax(gaps[:, :16], axis=1)
        rs["gapmin16"] = np.nanmin(gaps[:, :16], axis=1)
    f = per_origin(base, rs)
    # delivery-aligned: same quarter on previous days (always published: >= 24 h old)
    ds = S(data, "fi_mfrr_direction")
    dl = np.stack([at_delivery(ds, base, -96 * k).to_numpy() for k in range(1, 8)], axis=1)
    f["dir_d1"] = dl[:, 0]
    with np.errstate(all="ignore"):
        f["up_sameq7"] = np.nanmean(np.where(np.isnan(dl), np.nan, dl == 1), axis=1)
    return f


# ----------------------------------------------------------------------------- 2. neighbours
def _long_from_wide(df: pd.DataFrame, cols, prefix: str) -> dict:
    out = {}
    for c in cols:
        out[c] = pd.DataFrame({"ts": U(df["timestamp_utc"]), "value": pd.to_numeric(df[c], errors="coerce"),
                               "fu": U(df["fu"])}).dropna(subset=["value"]).sort_values("ts")
    return out


def neighbour_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    o = _uo(base)
    rs = pd.DataFrame(index=U(o))
    srcs = [("elering", ["system_balance", "ac_balance"], "ee"),
            ("energinet", ["aFRR_ActivatedDK1", "aFRR_ActivatedDK2", "Exchange_DK2_SE", "Exchange_DK1_SE"], "dk")]
    for key, cols, p in srcs:
        for c, s in _long_from_wide(data[key], cols, p).items():
            a = asof(s, o, lags=(0, 1, 2, 3, 4, 5, 6, 7))
            v = a[[f"lag{i}" for i in range(8)]].to_numpy(float)
            with np.errstate(all="ignore"):
                rs[f"{p}_{c}_L"] = v[:, 0]
                rs[f"{p}_{c}_L4"] = np.nanmean(v[:, :4], axis=1)
                rs[f"{p}_{c}_d4"] = v[:, 0] - np.nanmean(v[:, 4:8], axis=1)
    return per_origin(base, rs)


# ----------------------------------------------------------------------------- 3. history models
def hist_as_pkg(data: Data) -> pd.DataFrame:
    h = data["fg_hist"]
    h = h[h.series_id.isin(HIST_MAP)].copy()
    assert h["fu"].max() <= CUTOFF, "fg_hist must end before the fitting cutoff"
    h["series_id"] = h["series_id"].map(HIST_MAP)
    return h


def _da_frame(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Day-ahead inputs at the delivery quarter (+ calendar from the delivery timestamp)."""
    f = pd.DataFrame(index=base.index)
    hr, wd = _local(base["delivery"])
    f["h_hour"], f["h_wday"] = hr, wd
    w, c, s = (at_delivery(S(data, k), base) for k in ("fi_wind_fc_da", "fi_consumption_fc_da", "fi_solar_fc_da"))
    w4, c4, s4 = (at_delivery(S(data, k), base, -4) for k in ("fi_wind_fc_da", "fi_consumption_fc_da", "fi_solar_fc_da"))
    f["h_wind"], f["h_cons"], f["h_solar"] = w, c, s
    f["h_net"] = c - w - s
    f["h_dnet4"] = f["h_net"] - (c4 - w4 - s4)
    f["h_dwind4"] = w - w4
    return f


def _origin_frame(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Per-origin state that exists in both the history and the package (no spot needed)."""
    o = _uo(base)
    L = 32
    a = asof(S(data, "fi_mfrr_direction"), o, lags=tuple(range(L)))
    D = a[[f"lag{i}" for i in range(L)]].to_numpy(float)
    st = _run_stats(D)
    rs = pd.DataFrame(index=U(o))
    rs["h_dirL"] = D[:, 0]
    rs["h_age"] = a["age_q"].to_numpy()
    rs["h_run"] = st["run_len"]
    rs["h_up8"], rs["h_up32"], rs["h_sw16"] = st["up8"], st["up32"], st["n_switch16"]
    for sid, nm in (("fi_mfrr_up_activated", "h_upmw"), ("fi_mfrr_down_activated", "h_dnmw")):
        v = asof(S(data, sid), o, lags=(0, 1, 2, 3))
        rs[nm] = v[["lag0", "lag1", "lag2", "lag3"]].mean(axis=1).to_numpy()
    c = asof(S(data, "fi_consumption"), o)
    oi = pd.DatetimeIndex(U(o))
    cts = oi - pd.to_timedelta(c["age_q"].to_numpy() * 15, unit="min")
    cfc = S(data, "fi_consumption_fc_da").drop_duplicates("ts").set_index("ts")["value"]
    rs["h_conserr"] = c["lag0"].to_numpy() - cfc.reindex(cts).to_numpy()
    rs["h_prodcons"] = asof(S(data, "fi_production"), o)["lag0"].to_numpy() - c["lag0"].to_numpy()
    f = per_origin(base, rs)
    f["h_step"] = base["step"].to_numpy()
    return f


DA_COLS = ["h_hour", "h_wday", "h_wind", "h_cons", "h_solar", "h_net", "h_dnet4", "h_dwind4"]
OR_COLS = ["h_step", "h_dirL", "h_age", "h_run", "h_up8", "h_up32", "h_sw16", "h_upmw", "h_dnmw", "h_conserr", "h_prodcons"]


def _hist_base(h: pd.DataFrame) -> pd.DataFrame:
    d = h[h.series_id == "fi_mfrr_direction"].drop_duplicates("ts").set_index("ts")["value"]
    t0, t1 = d.index.min().ceil("h") + pd.Timedelta(days=2), d.index.max().floor("h") - pd.Timedelta(hours=10)
    origins = pd.date_range(t0, t1, freq="h")
    b = pd.DataFrame({"origin": np.repeat(origins, 40), "step": np.tile(np.arange(1, 41), len(origins))})
    b["origin"] = U(b["origin"])
    b["delivery"] = b.origin + (b.step - 1) * Q
    b["y"] = d.reindex(b.delivery).to_numpy()
    return b


_MODELS: dict = {}


def _key(h: pd.DataFrame, tag: str) -> str:
    s = f"{tag}|{len(h)}|{h['fu'].max()}|{h['ts'].max()}|{np.nansum(h['value'].to_numpy()):.6f}"
    return hashlib.md5(s.encode()).hexdigest()[:16]


def _fit_hist(data: Data, tag: str, cols: list[str]):
    """Fit P(up | cols) on history (directions != 0). Cached by a fingerprint of the training data."""
    from sklearn.ensemble import HistGradientBoostingClassifier as HGC
    h = hist_as_pkg(data)
    k = _key(h, tag + "|" + ",".join(cols))
    if k in _MODELS:
        return _MODELS[k]
    p = CACHE / f"history_{k}.pkl"
    if p.exists():
        _MODELS[k] = pickle.loads(p.read_bytes())
        return _MODELS[k]
    hd = Data({"pkg": h})
    hb = _hist_base(h)
    if not any(c in OR_COLS for c in cols):      # DA-only: one row per delivery quarter is enough
        hb = hb[hb.step == 1].reset_index(drop=True)
    X = _da_frame(hb, hd)
    if any(c in OR_COLS for c in cols):
        X = X.join(_origin_frame(hb, hd))
    m = hb["y"].notna().to_numpy() & (hb["y"] != 0).to_numpy()
    assert hb.loc[m, "delivery"].max() < CUTOFF
    clf = HGC(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=300, l2_regularization=1.0,
              early_stopping=False, random_state=0).fit(X.loc[m, cols], (hb.loc[m, "y"] == 1).astype(int))
    p.write_bytes(pickle.dumps(clf))
    _MODELS[k] = clf
    return clf


def _logit(p):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def hist_da_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Origin-independent prior P(up | day-ahead net position, wind, hour, ...) fitted on history."""
    clf = _fit_hist(data, "da", DA_COLS)
    X = _da_frame(base, data)
    f = pd.DataFrame(index=base.index)
    f["hda_lpup"] = _logit(clf.predict_proba(X[DA_COLS])[:, 1])
    return f


def hist_full_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Persistence-aware P(up) fitted on history with simulated hourly origins (steps 1-40)."""
    cols = DA_COLS + OR_COLS
    clf = _fit_hist(data, "full", cols)
    X = _da_frame(base, data).join(_origin_frame(base, data))
    f = pd.DataFrame(index=base.index)
    f["hfull_lpup"] = _logit(clf.predict_proba(X[cols])[:, 1])
    return f


def hist_both_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    return hist_da_features(base, data).join(hist_full_features(base, data))


def hist_prior_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Month x local-hour P(up) and P(none) from fg_hist (featherless idea 5), shrunk to the month mean."""
    h = hist_as_pkg(data)
    d = h[(h.series_id == "fi_mfrr_direction") & (h.ts < CUTOFF)].drop_duplicates("ts")
    loc = d["ts"].dt.tz_convert(TZ)
    k = pd.DataFrame({"m": loc.dt.month.to_numpy(), "h": loc.dt.hour.to_numpy(),
                      "up": (d["value"] == 1).to_numpy(float), "nz": (d["value"] != 0).to_numpy(float)})
    kz = k[k.nz == 1]
    g = kz.groupby(["m", "h"]).up.agg(["sum", "count"])
    mm = kz.groupby("m").up.mean()
    lam = 200.0
    pr = (g["sum"] + lam * mm.reindex(g.index.get_level_values(0)).to_numpy()) / (g["count"] + lam)
    pn = k.groupby(["m", "h"]).nz.mean()
    dl = base["delivery"].dt.tz_convert(TZ)
    ix = pd.MultiIndex.from_arrays([dl.dt.month.to_numpy(), dl.dt.hour.to_numpy()])
    f = pd.DataFrame(index=base.index)
    f["hp_up"] = pr.reindex(ix).to_numpy()
    f["hp_up_m"] = mm.reindex(dl.dt.month.to_numpy()).to_numpy()
    f["hp_none"] = 1 - pn.reindex(ix).to_numpy()
    return f


def _origin_frame2(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Extra state for hfull2: longer run structure, same quarter on previous days, mFRR price spread."""
    o = _uo(base)
    L = 96
    a = asof(S(data, "fi_mfrr_direction"), o, lags=tuple(range(L)))
    st = _run_stats(a[[f"lag{i}" for i in range(L)]].to_numpy(float))
    rs = pd.DataFrame(index=U(o))
    rs["h_prevrun"], rs["h_up96"] = st["prev_run_len"], st["up96"]
    up = asof(S(data, "fi_mfrr_up_price"), o, lags=(0,))["lag0"].to_numpy()
    dn = asof(S(data, "fi_mfrr_down_price"), o, lags=(0,))["lag0"].to_numpy()
    rs["h_spread"] = up - dn
    f = per_origin(base, rs)
    ds = S(data, "fi_mfrr_direction")
    dl = np.stack([at_delivery(ds, base, -96 * k).to_numpy() for k in range(1, 8)], axis=1)
    f["h_dird1"] = dl[:, 0]
    with np.errstate(all="ignore"):
        f["h_upq7"] = np.nanmean(np.where(np.isnan(dl), np.nan, dl == 1), axis=1)
    return f


OR2_COLS = ["h_prevrun", "h_up96", "h_spread", "h_dird1", "h_upq7"]


def hist_full2_features(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """hfull + longer run structure, same-quarter previous days and mFRR spread, fitted on fg_hist."""
    from sklearn.ensemble import HistGradientBoostingClassifier as HGC
    cols = DA_COLS + OR_COLS + OR2_COLS
    h = hist_as_pkg(data)
    k = _key(h, "full2|" + ",".join(cols))
    clf = _MODELS.get(k)
    p = CACHE / f"history_{k}.pkl"
    if clf is None and p.exists():
        clf = _MODELS[k] = pickle.loads(p.read_bytes())
    if clf is None:
        hd = Data({"pkg": h})
        hb = _hist_base(h)
        X = _da_frame(hb, hd).join(_origin_frame(hb, hd)).join(_origin_frame2(hb, hd))
        m = hb["y"].notna().to_numpy() & (hb["y"] != 0).to_numpy()
        assert hb.loc[m, "delivery"].max() < CUTOFF
        clf = HGC(max_iter=300, learning_rate=0.05, max_leaf_nodes=31, min_samples_leaf=300, l2_regularization=1.0,
                  early_stopping=False, random_state=0).fit(X.loc[m, cols], (hb.loc[m, "y"] == 1).astype(int))
        p.write_bytes(pickle.dumps(clf))
        _MODELS[k] = clf
    X = _da_frame(base, data).join(_origin_frame(base, data)).join(_origin_frame2(base, data))
    f = pd.DataFrame(index=base.index)
    f["hfull2_lpup"] = _logit(clf.predict_proba(X[cols])[:, 1])
    return f
