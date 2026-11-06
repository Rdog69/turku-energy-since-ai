## Read of the board first

Two observations drive my ranking: (1) `brier_dir` is **bit-identical across model families** on both folds (0.43691 / 0.45278) — the direction predictions look like base rates, so direction is the biggest headroom, and direction is weather-driven. (2) None of the 35 reference features touch `fg_rt`, any NWP source, or ERA5 — my whole area is greenfield. Precondition (10 min, do first): list `data["ifs"].columns`, `.point.unique()`, run cadence, and June–Oct coverage; check whether `icon`, `metno`, `fg_hist` finished downloading.

All code goes in `experiments/lab/features/weather.py` + `exp_weather.py`; every idea runs as its own leaderboard row via `run_experiment(..., agent="weather", sources=(...))` so leakcheck covers the extra sources. Run with `OMP_NUM_THREADS=2 .venv/bin/python -W ignore`.

## 1. Wind-forecast-error nowcast: `fg181_wind_rt` vs `fi_wind_fc_da`

**(a)** The sign of the live wind forecast error persists for hours; imbalance direction follows realised-minus-planned wind. The reference set has the DA forecast at delivery but never compares it to what actually happened. Newest usable rt quarter is 3 quarters before step 1, so signal peaks at steps 1–8.
**(b)**

```python
def wind_err_features(base, data):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True); oi = U(o)
    w = asof(data.series("fg_rt", "fg181_wind_rt"), o, lags=tuple(range(5))); w.index = oi
    fc = data.series("pkg", "fi_wind_fc_da").drop_duplicates("ts").set_index("ts")["value"]
    ts0 = oi - pd.to_timedelta(w["age_q"].to_numpy() * 15, unit="min")   # DA fc of a past quarter is long usable
    E = w[[f"lag{i}" for i in range(5)]].to_numpy() - np.stack(
        [fc.reindex(ts0 - i * pd.Timedelta(minutes=15)).to_numpy() for i in range(5)], axis=1)
    cap = asof(data.series("fg_extra", "fg268_wind_capacity"), o, lags=(0,))["lag0"].to_numpy()
    rs = pd.DataFrame(index=oi)
    rs["werr_L"], rs["werr_L4"] = E[:, 0], np.nanmean(E[:, :4], axis=1)
    rs["werr_rel"] = E[:, 0] / np.where(cap > 1, cap, np.nan)
    rs["werr_slope"] = np.nanmean(E[:, :3], axis=1) - np.nanmean(E[:, 2:], axis=1)
    return per_origin(base, rs)
```
**(c)** `brier_dir` and `MAE_s1_4` first; `brier_spike` at short steps.
**(d)** Kill if fold A `brier_dir` isn't ≥0.01 under REF mixture (0.4369) or fold B `MAE_s1_4` worsens.

## 2. Newest IFS run at delivery + run-to-run revision

**(a)** At steps 13–40 (3.25–10 h) there is no rt information; the newest run's wind at the delivery hour, and its revision vs the previous run(s), is the only intraday news. The DA wind forecast was built on a D-1 run, so `nth=1/2` revisions approximate "news since day-ahead".
**(b)**

```python
def nwp_wind_features(base, data):
    ifs = data["ifs"]; f = pd.DataFrame(index=base.index)
    f["nwp_w"] = nwp_latest(ifs, base, "wind_speed_100m")
    f["nwp_w_rev1"] = f["nwp_w"] - nwp_latest(ifs, base, "wind_speed_100m", nth=1)
    f["nwp_w_rev2"] = f["nwp_w"] - nwp_latest(ifs, base, "wind_speed_100m", nth=2)
    pre = nwp_latest(ifs, base.assign(delivery=base["delivery"] - pd.Timedelta(hours=3)), "wind_speed_100m")
    f["nwp_w_ramp3h"] = f["nwp_w"] - pre        # intra-run ramp into delivery
    return f
```
**(c)** MAE / pinball on steps 13–40; `brier_dir` mid steps.
**(d)** Kill if `nwp_latest` returns >20% NaN on usable origins, or fold A `MAE_s13_40` doesn't improve ≥0.5.

## 3. Power-curve mapping (ERA5 → Fingrid wind MW), then MW-unit revisions

**(a)** m/s deltas ignore the curve's nonlinearity: +2 m/s at 4 m/s ≈ nothing, at 9 m/s ≈ hundreds of MW. Mapping wind speed through an empirical curve makes revisions comparable to the DA forecast (MW) and to mFRR bid features.
**(b)**

```python
CUT = pd.Timestamp("2026-07-31T21:00Z"); _PC = None
def _pc(data):                                  # binned median curve m/s -> MW, rule-2 cutoff
    global _PC
    if _PC is None:
        e = data["era5"].groupby("valid_utc")["wind_speed_100m"].mean()   # fu = valid + 6d
        w = data.series("fg_rt", "fg181_wind_rt")
        wh = w.assign(h=w.ts.dt.floor("h")).groupby("h")["value"].mean()
        df = pd.DataFrame({"spd": e, "mw": wh}).dropna()
        df = df[df.index < CUT - pd.Timedelta(days=6)]
        df["b"] = np.digitize(df.spd, np.arange(0, 26, 0.5))
        _PC = df.groupby("b")["mw"].median()
    return _PC

def wpc_features(base, data):
    pc = _pc(data); c, mw = pc.index.values * 0.5 + 0.25, pc.values
    f = pd.DataFrame(index=base.index)
    f["wpc_new"] = np.interp(nwp_latest(data["ifs"], base, "wind_speed_100m"), c, mw)
    f["wpc_prev"] = np.interp(nwp_latest(data["ifs"], base, "wind_speed_100m", nth=1), c, mw)
    f["wpc_rev"] = f.wpc_new - f.wpc_prev
    f["wpc_vs_da"] = f.wpc_new - at_delivery(data.series("pkg", "fi_wind_fc_da"), base)
    return f
```
**(c)** MAE, pinball all steps; should subsume experiment 2's raw features.
**(d)** Kill if the curve is non-monotone over 3+ consecutive bins, or fold A MAE doesn't beat the experiment-2 row.

## 4. Inter-model spread (IFS / ICON-EU / MET Nordic)

**(a)** Disagreement between models at the wind points proxies wind uncertainty and ramp risk: where spread is large the p10–p90 band should widen (pinball, coverage); where the newest runs agree on a big revision vs DA, spike probability should rise.
**(b)**

```python
def nwp_spread_features(base, data):
    f = pd.DataFrame(index=base.index)
    for src in ("ifs", "icon", "metno"):
        if src in data: f[f"{src}_w"] = nwp_latest(data[src], base, "wind_speed_100m")
    w = [c for c in f.columns if c.endswith("_w")]
    if len(w) >= 2:
        f["nwp_spread"] = f[w].max(axis=1) - f[w].min(axis=1)
        f["nwp_sd"] = f[w].std(axis=1)
    return f
```
**(c)** `pinball` / `coverage` and `brier_spike`; minor MAE effect.
**(d)** Kill if ICON or METno is missing over either window, or fold A pinball doesn't improve vs REF (12.463).

## 5. Autumn direction prior from `fg_hist` (fitted pre-cutoff)

**(a)** Fold B trains on June–July only; fold A's training window contains no full autumn. Direction base rates vary by (month, local hour); a shrunk prior fitted on Mar 2025–May 2026 history (hard cutoff) gives fold A's model seasonal knowledge its window lacks. This directly targets the suspiciously flat 0.4369. Note the reference set already uses lagged `fi_imbalance_price`, so lagged/historical target series are established practice.
**(b)**

```python
def hist_dir_features(base, data):
    d = data.series("fg_hist", "fi_mfrr_direction"); df = d[d.ts < pd.Timestamp("2026-07-31T21:00Z")]
    loc = df.ts.dt.tz_convert("Europe/Helsinki")
    k = pd.DataFrame({"m": loc.dt.month, "h": loc.dt.hour, "up": (df.value == 1).astype(float),
                      "nz": (df.value != 0).astype(float)})
    up, nz = k.groupby(["m", "h"]).up.mean(), k.groupby(["m", "h"]).nz.mean()   # shrink toward global mean by n/(n+200)
    dl = base.delivery.dt.tz_convert("Europe/Helsinki")
    f = pd.DataFrame(index=base.index)
    f["dir_prior_up"] = list(map(up.get, zip(dl.dt.month, dl.dt.hour)))
    f["dir_prior_nz"] = list(map(nz.get, zip(dl.dt.month, dl.dt.hour)))
    return f
```
**(c)** `brier_dir`, fold A mainly; should be ~neutral on fold B.
**(d)** Kill if fold A `brier_dir` unchanged or fold B degrades >0.005.

## 6. Cold-weather derate (icing proxy) + temperature anomaly

**(a)** Near 0 °C with precipitation, iced blades cut output well below the power curve → surprise wind shortfall → up-regulation spikes. Fit a (temp, precip) → realised/curve-expected wind ratio table on `era5` + `fg181_wind_rt` (last autumn gives cold hours), apply to NWP temp/precip at delivery. Add heating-demand surprise: NWP temp vs an ERA5 hour-of-year climatology (fitted pre-cutoff). Honest caveat: fold B is August — expected effect there is ~null; the test is "helps A, harmless B". Exact NWP variable names beyond `wind_speed_100m` must be confirmed from `data["ifs"].columns` before coding.
**(b)** Skeleton: fit ratio table on deliveries < cutoff; then `f["icing_risk"] = ((t > -3) & (t < 2) & (pr > 0)) * wpc_new`, `f["temp_dev"] = nwp temp − climatology(hour_of_year)`.
**(c)** fold A MAE / pinball / `brier_spike` on cold hours.
**(d)** Kill if <100 fitted cold-hours, or fold A spike Brier unchanged, or fold B MAE worsens >0.2.

## Recommendation and notes

If 1–4 land, the final stack is `package_features + wind_err + wpc + spread`. Suspicious items for the report: the identical `brier_dir` across model families (check whether `calibrate`'s Platt maps are flattening direction probabilities — worth one experiment with `calibrate=False`), and ICON/METno/`fg_hist` download completeness before trusting experiments 4–5.