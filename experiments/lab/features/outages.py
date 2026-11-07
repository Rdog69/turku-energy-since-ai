"""Outage features from Nord Pool UMM + Fingrid real-time nuclear (agent: outages).

Leak safety
-----------
* A UMM message version is usable at origin o iff fu <= o (fu = ceil_hour(publicationDate)).
* At each origin we use, per messageId, the newest version among the usable ones
  ("state" intervals [fu_v, fu_next_v) per message). Versions sharing the same fu: highest wins.
* `isOutdated` is a fetch-time attribute (knows the future) and is NEVER used.
* eventStatus 3 (dismissed) rows contribute 0 MW.
* Nothing is fitted.

Dedup
-----
The same physical outage is often reported twice (production unit "Olkiluoto 3" and
generation unit "B3"; "Metsä Fibre Kemi" by two publishers). Per delivery quarter we take the
max MW per unit key (normalised name + installed MW) and sum over units.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data import U, Data, asof, asof_window, per_origin

Q = pd.Timedelta(minutes=15)
H = pd.Timedelta(hours=1)
NSTEP = 40
_ALIAS = {"Olkiluoto 3": "B3", "Olkiluoto 1": "B1", "Olkiluoto 2": "B2"}


def _state_intervals(u: pd.DataFrame) -> pd.DataFrame:
    """Rows of u annotated with [vf, vt): the origins at which their version is the newest usable one."""
    if u.empty:
        return u.assign(vf=pd.Series(dtype="datetime64[ns, UTC]"), vt=pd.Series(dtype="datetime64[ns, UTC]"))
    v = (u.groupby(["messageId", "version", "fu"], as_index=False)["publicationDate"].min()
         .sort_values(["messageId", "fu", "version"]))
    v["vmax"] = v.groupby("messageId")["version"].cummax()
    v["pub0"] = v.groupby("messageId")["publicationDate"].cummin()   # first publication among usable versions
    v = v.groupby(["messageId", "fu"], as_index=False)[["vmax", "pub0"]].last()   # version in force from fu on
    v["vt"] = v.groupby("messageId")["fu"].shift(-1)
    v = v.rename(columns={"fu": "vf", "vmax": "version"})
    out = u.drop(columns=["fu"]).merge(v, on=["messageId", "version"], how="inner")
    out["vt"] = out["vt"].fillna(pd.Timestamp("2100-01-01", tz="UTC"))
    out["event_stop_utc"] = out["event_stop_utc"].fillna(pd.Timestamp("2100-01-01", tz="UTC"))
    out = out[out["event_start_utc"].notna()]
    return out.reset_index(drop=True)


def _ns(x) -> np.ndarray:
    return U(pd.Series(x)).to_numpy().astype("datetime64[ns]").astype(np.int64) if len(x) else np.zeros(0, np.int64)


class _Block:
    """Numpy arrays of one UMM subset for fast per-origin evaluation."""

    def __init__(self, df: pd.DataFrame, key: str | None = None):
        st = _state_intervals(df)
        self.n = len(st)
        self.vf, self.vt = _ns(st["vf"]), _ns(st["vt"])
        self.es, self.ee = _ns(st["event_start_utc"]), _ns(st["event_stop_utc"])
        self.pub0 = _ns(st["pub0"])
        mw = pd.to_numeric(st["unavailable_mw"], errors="coerce").fillna(0).to_numpy(float)
        self.mw = np.where(st["eventStatus"].to_numpy() == 3, 0.0, mw)
        if key is None:
            k = st["unit_name"].map(lambda s: _ALIAS.get(s, s)).astype(str) + "|" + st["installed_mw"].astype(str)
        else:
            k = st[key].astype(str)
        self.key = pd.factorize(k)[0] if self.n else np.zeros(0, int)
        self.nkey = int(self.key.max()) + 1 if self.n else 0
        self.extra = st

    def current(self, o: int) -> np.ndarray:
        return np.nonzero((self.vf <= o) & (o < self.vt))[0]

    def active_mw(self, idx: np.ndarray, dts: np.ndarray, extra_mask: np.ndarray | None = None,
                  how: str = "sum") -> np.ndarray:
        """MW active during each delivery quarter [d, d+15min): per unit key max, then sum (or max) over units."""
        if extra_mask is not None:
            idx = idx[extra_mask]
        if len(idx) == 0:
            return np.zeros(len(dts))
        q = Q.value
        act = (self.es[idx, None] < dts[None, :] + q) & (self.ee[idx, None] > dts[None, :])
        m = np.where(act, self.mw[idx, None], 0.0)
        per_unit = np.zeros((self.nkey, len(dts)))
        np.maximum.at(per_unit, self.key[idx], m)
        return per_unit.sum(axis=0) if how == "sum" else per_unit.max(axis=0)


def _umm_blocks(data: Data):
    u = data["umm"]
    u = u[u["publicationDate"].notna()]
    gen = u[(u["messageType"] == 1) & (u["area"] == "FI")]
    cons = u[(u["messageType"] == 2) & (u["area"] == "FI")]
    nb = u[(u["messageType"] == 1) & (u["area"].isin(["SE1", "SE3", "EE"]))]
    tr = u[(u["messageType"] == 3) & ((u["in_area"] == "FI") | (u["out_area"] == "FI"))]
    tr_key = tr["unit_name"].astype(str)
    return gen, cons, nb, tr, tr_key


def umm_features(base: pd.DataFrame, data: Data, fresh_h=(1, 3, 6), big_mw: float = 250.0,
                 with_tr: bool = True, with_nb: bool = True) -> pd.DataFrame:
    gen, cons, nb, tr, tr_key = _umm_blocks(data)
    B = {}
    for name, df in (("g_unpl", gen[gen.unavailabilityType == 1]), ("g_pl", gen[gen.unavailabilityType == 2]),
                     ("c_unpl", cons[cons.unavailabilityType == 1]), ("nb_unpl", nb[nb.unavailabilityType == 1])):
        B[name] = _Block(df)
    trb = _Block(tr, key="unit_name") if with_tr else None
    if trb is not None and trb.n:
        nm = trb.extra["unit_name"].astype(str).to_numpy()
        tr_imp = np.char.endswith(nm.astype(str), "→ FI")
        tr_exp = np.char.startswith(nm.astype(str), "FI →")
        tr_unpl = trb.extra["unavailabilityType"].to_numpy() == 1
    nuc_pl = (B["g_pl"].extra["fuel_type"].to_numpy() == 14) if B["g_pl"].n else np.zeros(0, bool)

    origins = U(base["origin"].drop_duplicates().sort_values())
    steps = np.arange(NSTEP)
    cols = ["unpl_mw", "unpl_max", *[f"unpl_fresh{h}" for h in fresh_h], "fresh_big",
            "pl_mw", "pl_nuc", "pl_chg", "cons_unpl", "hrs_since_big", "hrs_since_trip_start",
            "unpl_delta6", "pl_delta6"]
    if with_nb:
        cols += ["nb_fresh3", "nb_unpl"]
    if with_tr:
        cols += ["tr_imp_red", "tr_exp_red", "tr_unpl"]
    res = {c: np.full((len(origins), NSTEP), np.nan) for c in cols}
    o_ns = _ns(origins)
    g = B["g_unpl"]
    for i, o in enumerate(o_ns):
        dts = o + steps * Q.value
        cur = g.current(o)
        res["unpl_mw"][i] = g.active_mw(cur, dts)
        res["unpl_max"][i] = g.active_mw(cur, dts, how="max")
        # delta vs. what was known 6 h earlier (versions usable at origin - 6 h), same delivery quarter
        res["unpl_delta6"][i] = res["unpl_mw"][i] - g.active_mw(g.current(o - 6 * H.value), dts)
        for h in fresh_h:
            fm = (g.es[cur] >= o - h * H.value) & (g.es[cur] <= o)
            res[f"unpl_fresh{h}"][i] = g.active_mw(cur, dts, fm)
        fm3 = (g.es[cur] >= o - 3 * H.value) & (g.es[cur] <= o)
        res["fresh_big"][i] = (g.active_mw(cur, dts, fm3, how="max") >= 800).astype(float)
        # hours since the newest large unplanned message (by first publication) / large trip start
        big = cur[g.mw[cur] >= big_mw]
        hs = (o - g.pub0[big].max()) / H.value if len(big) else 999.0
        res["hrs_since_big"][i] = min(hs, 168.0)
        bs = big[g.es[big] <= o]
        hs2 = (o - g.es[bs].max()) / H.value if len(bs) else 999.0
        res["hrs_since_trip_start"][i] = min(hs2, 168.0)
        p = B["g_pl"]
        pc = p.current(o)
        pm = p.active_mw(pc, dts)
        res["pl_mw"][i] = pm
        res["pl_nuc"][i] = p.active_mw(pc, dts, nuc_pl[pc]) if len(pc) else 0.0
        res["pl_chg"][i] = pm - p.active_mw(pc, np.array([o - Q.value]))[0]
        res["pl_delta6"][i] = pm - p.active_mw(p.current(o - 6 * H.value), dts)
        c = B["c_unpl"]
        res["cons_unpl"][i] = c.active_mw(c.current(o), dts)
        if with_nb:
            n_ = B["nb_unpl"]
            nc = n_.current(o)
            res["nb_unpl"][i] = n_.active_mw(nc, dts)
            fmn = (n_.es[nc] >= o - 3 * H.value) & (n_.es[nc] <= o)
            res["nb_fresh3"][i] = n_.active_mw(nc, dts, fmn)
        if with_tr:
            if trb.n:
                tc = trb.current(o)
                res["tr_imp_red"][i] = trb.active_mw(tc, dts, tr_imp[tc])
                res["tr_exp_red"][i] = trb.active_mw(tc, dts, tr_exp[tc])
                res["tr_unpl"][i] = trb.active_mw(tc, dts, tr_unpl[tc])
            else:
                res["tr_imp_red"][i] = res["tr_exp_red"][i] = res["tr_unpl"][i] = 0.0
    # map (origin, step) -> row
    pos = pd.Series(np.arange(len(origins)), index=origins)
    oi = pos.reindex(U(base["origin"])).to_numpy()
    si = base["step"].to_numpy() - 1
    f = pd.DataFrame(index=base.index)
    for c in cols:
        f["o_" + c] = res[c][oi, si]
    return f


def umm_core(base, data):
    """FI generation/consumption outage features only (no transmission, no neighbours)."""
    return umm_features(base, data, with_tr=False, with_nb=False)


def umm_all(base, data):
    return umm_features(base, data, with_tr=True, with_nb=True)


def rt_nuclear(base: pd.DataFrame, data: Data) -> pd.DataFrame:
    """Real-time nuclear output vs its own 24 h max and 1 h ago: a trip detector."""
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    s = data.series("fg_rt", "fg188_nuclear_rt")
    a = asof(s, o, lags=(0, 4))
    mx = asof_window(s, o, 96, "max")
    rs = pd.DataFrame(index=U(o))
    rs["rt_nuc"] = a["lag0"].to_numpy()
    rs["rt_nuc_drop24"] = mx.to_numpy() - a["lag0"].to_numpy()
    rs["rt_nuc_drop1h"] = a["lag4"].to_numpy() - a["lag0"].to_numpy()
    return per_origin(base, rs)


FRESH_COLS = ["o_unpl_mw", "o_unpl_max", "o_unpl_fresh1", "o_unpl_fresh3", "o_unpl_fresh6", "o_fresh_big",
              "o_hrs_since_big", "o_hrs_since_trip_start", "o_unpl_delta6"]


def umm_delta(base, data):
    """Coordinator idea: unplanned MW known now minus known 6 h ago (same delivery) + planned MW at delivery."""
    return umm_core(base, data)[["o_unpl_delta6", "o_pl_delta6", "o_pl_mw"]]


def umm_fresh(base, data):
    """Only the 'fresh unplanned FI generation' features (no slow regime variables)."""
    return umm_core(base, data)[FRESH_COLS]


def umm_regime(base, data):
    """Slow regime variables: planned MW, consumption outages, neighbour + border transmission outages."""
    f = umm_all(base, data)
    return f[[c for c in f.columns if c not in FRESH_COLS]]


TRIP_COLS = ["o_unpl_fresh1", "o_unpl_fresh3", "o_unpl_fresh6", "o_unpl_delta6", "o_hrs_since_big"]


def umm_trip(base, data):
    """Only shock (fresh) features - no slow level variables that can act as date proxies."""
    return umm_core(base, data)[TRIP_COLS]
