"""v2 features: spot shape, capacity-weighted wind, calendar interactions, net-position shape, ICON-vs-IFS."""
from __future__ import annotations

import json
import numpy as np
import pandas as pd

from ..data import ROOT, U, Data, at_delivery, nwp_latest

Q = pd.Timedelta(minutes=15)
S = lambda d, sid: d.series("pkg", sid)
TZ = "Europe/Helsinki"


def _day_matrix(series, base):
    """(n_rows, 100) matrix of the series over the delivery's local day (NaN if outside the day or unpublished)."""
    loc = base["delivery"].dt.tz_convert(TZ)
    d0 = loc.dt.normalize()
    start = d0.dt.tz_convert("UTC")
    nxt = (d0 + pd.Timedelta(days=1, hours=3)).dt.normalize().dt.tz_convert("UTC")   # robust next local midnight
    off0 = ((start - base["delivery"]) / Q).round().astype(int).to_numpy()
    nq = ((nxt - start) / Q).round().astype(int).to_numpy()
    cols = []
    for k in range(100):
        v = at_delivery(series, base, 0).to_numpy() * np.nan   # placeholder shape
        v = _at_off(series, base, off0 + k)
        v = np.where(k < nq, v, np.nan)
        cols.append(v)
    return np.stack(cols, axis=1), -off0   # position of delivery within day


def _at_off(s, base, off):
    v = s.drop_duplicates("ts").set_index("ts")
    t = base["delivery"] + pd.to_timedelta(off * 15, unit="min")
    val = v["value"].reindex(t).to_numpy()
    fu = U(v["fu"].reindex(t).to_numpy())
    ok = pd.notna(fu) & (fu <= U(base["origin"]))
    return np.where(ok, val, np.nan)


def spot_shape(base, data):
    s = S(data, "fi_spot_price")
    M, pos = _day_matrix(s, base)
    cur = at_delivery(s, base).to_numpy()
    f = pd.DataFrame(index=base.index)
    with np.errstate(all="ignore"):
        mx, mn = np.nanmax(M, axis=1), np.nanmin(M, axis=1)
        f["sp_rank"] = np.nansum(M < cur[:, None], axis=1) / np.maximum(np.sum(~np.isnan(M), axis=1), 1)
        f["sp_dmax"] = cur - mx
        f["sp_dmin"] = cur - mn
        f["sp_spread"] = mx - mn
    f.loc[np.isnan(cur), :] = np.nan
    nxt4, prv4 = at_delivery(s, base, 4), at_delivery(s, base, -4)
    f["sp_ramp_next"] = nxt4 - cur
    f["sp_ramp_prev"] = cur - prv4
    f["sp_ramp_dir"] = np.sign(nxt4 - prv4)
    f["sp_ramp_abs"] = (nxt4 - prv4).abs()
    return f


def netpos_shape(base, data):
    cons, wind, sol = (S(data, k) for k in ("fi_consumption_fc_da", "fi_wind_fc_da", "fi_solar_fc_da"))
    C, _ = _day_matrix(cons, base)
    W, _ = _day_matrix(wind, base)
    So, _ = _day_matrix(sol, base)
    N = C - W - So
    cur = (at_delivery(cons, base) - at_delivery(wind, base) - at_delivery(sol, base)).to_numpy()
    f = pd.DataFrame(index=base.index)
    with np.errstate(all="ignore"):
        f["np_rel_mean"] = cur - np.nanmean(N, axis=1)
        f["np_rel_max"] = cur - np.nanmax(N, axis=1)
        f["np_rel_min"] = cur - np.nanmin(N, axis=1)
        f["np_day_range"] = np.nanmax(N, axis=1) - np.nanmin(N, axis=1)
        f["wind_rel_mean"] = at_delivery(wind, base).to_numpy() - np.nanmean(W, axis=1)
    return f


def calendar2(base, data):
    loc = base["delivery"].dt.tz_convert(TZ)
    f = pd.DataFrame(index=base.index)
    wk = (loc.dt.dayofweek >= 5).astype(float)
    f["wkend"] = wk
    f["wkend_hour"] = wk * (loc.dt.hour + 1) + (1 - wk) * 0      # 0 on weekdays, 1..24 on weekends
    d0 = loc.dt.normalize()
    n = ((d0 + pd.Timedelta(days=1, hours=3)).dt.normalize().dt.tz_convert("UTC") - d0.dt.tz_convert("UTC")) / pd.Timedelta("1h")
    f["dst_day"] = (n.round() != 24).astype(float)
    return f


_FARMS = None


def _weights():
    """Capacity share per IFS point: each OSM wind farm is assigned to the nearest cluster point."""
    from src.data.external.common import POINTS
    F = json.load(open(ROOT / "external_data/osm/farms.json"))["wind"]
    pts = [p for p in POINTS if p != "helsinki" and p in ("kristiinankaupunki", "vaasa", "kokkola", "lestijarvi", "kalajoki", "raahe_pyhajoki", "ii_simo")]
    w = dict.fromkeys(pts, 0.0)
    for x in F:
        cap = x["capacity_mw"] if x.get("capacity_mw") else 3.0 * (x.get("turbines") or 1)
        d = {p: (POINTS[p][0] - x["lat"]) ** 2 + ((POINTS[p][1] - x["lon"]) * 0.45) ** 2 for p in pts}
        w[min(d, key=d.get)] += cap
    tot = sum(w.values())
    return {p: v / tot for p, v in w.items()}


def cap_wind(base, data):
    global _FARMS
    if _FARMS is None:
        _FARMS = _weights()
    nwp = data["ifs"]
    v = {p: nwp_latest(nwp, base, "wind_speed_100m", point=p).to_numpy() for p in _FARMS}
    eq = np.mean(list(v.values()), axis=0)
    cw = sum(_FARMS[p] * v[p] for p in _FARMS)
    cw3 = sum(_FARMS[p] * np.clip(v[p], 0, 14) ** 3 for p in _FARMS) ** (1 / 3)
    f = pd.DataFrame(index=base.index)
    f["capw_ws"], f["capw_ws3"], f["capw_minus_eq"] = cw, cw3, cw - eq
    return f


def icon_ifs(base, data):
    a, b = data["icon"], data["ifs"]
    pts = [p for p in a.point.unique() if p != "helsinki"]
    ia = nwp_latest(a[a.point.isin(pts)], base, "wind_speed_100m")
    ib = nwp_latest(b[b.point.isin(pts)], base, "wind_speed_100m")
    f = pd.DataFrame(index=base.index)
    f["icon_ws"], f["icon_minus_ifs"], f["icon_ifs_abs"] = ia, ia - ib, (ia - ib).abs()
    return f
