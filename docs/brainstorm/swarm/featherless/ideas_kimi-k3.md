Priors that shaped the ranking: RT data is usable 30 min after quarter end, so `lag0` = the quarter starting `origin−3Q` — genuinely fresh for steps 1–12 but **stale beyond ~step 16**, so expect gains concentrated in `MAE_s1_4`/`s5_12`, and let `step` modulate the effect (HGB interacts, no need for manual decay). All sketches below assume `sources=("pkg","fg_rt","fg_extra","umm")` is passed to `run_experiment` so leakcheck actually truncates them.

---

## 1. RT deficit stack: fg198 + fg186 + fg209 (+ fg176 netted imbalance)

**(a) Hypothesis.** `fg198` is the running system energy surplus/deficit — nearly the same physical quantity the mFRR market is pricing this hour. It persists over 1–3 h, so the newest usable value hard-shifts the gap for steps 1–12. `fg186` (cumulative) captures "stuck in deficit all day", `fg209` (system state) flags scarcity regimes, `fg176` (FI–SE netted imbalance power) corroborates volume.

**(b)**
```python
def rt_deficit(base, data):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    r = pd.DataFrame(index=U(o))
    a = asof(data.series("fg_rt","fg198_surplus_deficit_rt"), o, lags=(0,1,2,3,8)); a.index = U(o)
    r["def_L"], r["def_L1"], r["def_L4"] = a["lag0"], a["lag1"], a["lag3"]
    r["def_d45"] = a["lag0"] - a["lag3"]; r["def_d2h"] = a["lag0"] - a["lag8"]
    r["def_age_q"] = a["age_q"]
    c = asof(data.series("fg_rt","fg186_surplus_deficit_cum_rt"), o, lags=(0,)); c.index = U(o)
    r["def_cum"] = c["lag0"]
    st = asof(data.series("fg_rt","fg209_power_system_state_rt"), o); st.index = U(o)
    r["sys_state"] = st["lag0"]
    n = asof(data.series("fg_extra","fg176_imbalance_power_fi_se"), o, lags=(0,4)); n.index = U(o)
    r["imbnet_L"], r["imbnet_d1h"] = n["lag0"], n["lag0"] - n["lag4"]
    return per_origin(base, r)

run_experiment("rt deficit stack", agent="nowcast",
    feature_fns=[package_features, rt_deficit], model="mixture",
    sources=("pkg","fg_rt","fg_extra"), notes="198/186/209/176 nowcast")
```
**(c) Moves:** `MAE_s1_4` and `MAE_s5_12` (A: hoping 5–10% on s1_4), `brier_dir` on A (sign of `def_L` predicts direction), some `brier_spike`. **(d) Kill:** <2% relative `MAE_s1_4` gain on *either* fold → drop (means the package imb-lag features already carry it).

## 2. Forecast-error persistence: fg181 − `fi_wind_fc_da`, fg193 − `fi_consumption_fc_da`

**(a) Hypothesis.** Package features use day-ahead wind/solar/consumption forecasts at delivery, but D-A error is highly autocorrelated within a day (weather regime). The error measurable at origin ≈ error at delivery, so correcting the forecast the model already sees should help *all* steps, incl. 13–40.

**(b)**
```python
def fc_err(base, data):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    oi = pd.DatetimeIndex(U(o)); r = pd.DataFrame(index=oi)
    wfc = data.series("pkg","fi_wind_fc_da").drop_duplicates("ts").set_index("ts")["value"]
    cfc = data.series("pkg","fi_consumption_fc_da").drop_duplicates("ts").set_index("ts")["value"]
    w = asof(data.series("fg_rt","fg181_wind_rt"), o, lags=(0,16)); w.index = oi
    wt = U(oi) - pd.to_timedelta(w["age_q"]*15, unit="min")     # ts of newest usable quarter
    e0 = w["lag0"] - wfc.reindex(wt).to_numpy()
    e4 = w["lag16"] - wfc.reindex(wt - pd.Timedelta(hours=4)).to_numpy()
    r["werr_L"], r["werr_L4"], r["werr_tr"] = e0, e4, e0 - e4
    cn = asof(data.series("fg_rt","fg193_consumption_rt"), o); cn.index = oi
    ct = U(oi) - pd.to_timedelta(cn["age_q"]*15, unit="min")
    r["cerr_L4h"] = cn["lag0"] - cfc.reindex(ct).to_numpy()
    r["neterr_L"] = r["cerr_L4h"] - e0                          # load-minus-wind error ≈ deficit driver
    return per_origin(base, r)
```
Same `reindex`-on-past-ts pattern as `package.py` uses for spot (fu of D-A forecasts ≪ ts ≤ origin, so truncation-safe; leakcheck verifies). Optionally normalise `werr_L` by `fg268_wind_capacity` (latest value per origin, fu ≤ origin).

**(c) Moves:** `MAE_s5_12`, `MAE_s13_40`, `pinball` (asymmetric tails when wind busts), both folds. **(d) Kill:** no `pinball` gain on fold B (August, wind-exposed) → drop.

## 3. Frequency nowcast (fg177)

**(a) Hypothesis.** Quarter-mean frequency deviation < 50 Hz is the sub-quarter fingerprint of an active deficit *right now*, leading mFRR activation by minutes. Adds sign information not in `fg198` (which is 30–45 min older) for steps 1–4 and direction tails.

**(b)**
```python
def freq_dev(base, data):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    a = asof(data.series("fg_rt","fg177_frequency_rt"), o, lags=(0,1,2,3)); a.index = U(o)
    r = pd.DataFrame(index=U(o))
    r["fdev_L"] = a["lag0"] - 50.0
    r["fdev_min4"] = a[["lag0","lag1","lag2","lag3"]].min(axis=1) - 50.0
    r["fdev_slope"] = a["lag0"] - a["lag3"]
    r["fdev_abs3"] = (a[["lag0","lag1","lag2"]] - 50.0).abs().mean(axis=1)  # volatility → tail risk
    return per_origin(base, r)
```
**(c) Moves:** `brier_dir` (A), `MAE_s1_4`, maybe `brier_spike` up-side. Cheap: ~30 min. **(d) Kill:** `brier_dir` gain <0.003 on both folds and no `MAE_s1_4` gain → drop (fg198 already subsumes it).

## 4. Production-plan deviation + nuclear flag (fg192 vs fg242, fg188)

**(a) Hypothesis.** `fg242` (BRP production plans, D-1 18:00) vs `fg192` actual RT production isolates *unplanned* generation shortfalls — trips and deviations that force up-regulation for hours. A nuclear-specific feature (`fg188` dip vs its own 8-lag level) catches big-unit events correlated with scarcity prices.

**(b)**
```python
def plan_dev(base, data):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    oi = pd.DatetimeIndex(U(o)); r = pd.DataFrame(index=oi)
    plan = data.series("fg_extra","fg242_production_plan_da").drop_duplicates("ts").set_index("ts")["value"]
    p = asof(data.series("fg_rt","fg192_production_rt"), o, lags=(0,4)); p.index = oi
    pt = U(oi) - pd.to_timedelta(p["age_q"]*15, unit="min")
    d0 = p["lag0"] - plan.reindex(pt).to_numpy()
    d4 = p["lag4"] - plan.reindex(pt - pd.Timedelta(hours=1)).to_numpy()
    r["proddev_L"], r["proddev_d"] = d0, d0 - d4
    r["short_now"] = np.clip(-d0, 0, None)                     # only shortfalls bite
    nuc = asof(data.series("fg_rt","fg188_nuclear_rt"), o, lags=(0,8)); nuc.index = oi
    r["nuc_dip"] = nuc["lag8"] - nuc["lag0"]
    return per_origin(base, r)
```
**(c) Moves:** `brier_spike` (up-spikes), `MAE_s1_4`/`s5_12` on A (September, tighter margin). **(d) Kill:** no `brier_spike` gain on either fold → drop (partial collinearity with `def_L` is expected; keep whichever of #1/#4 wins per-fold).

## 5. mFRR bid-stack scarcity (fg243, fg22, fg251)

**(a) Hypothesis.** Spikes happen when activations climb the bid curve. Thin up-bid volume (`fg243`) + high last up-bid price (`fg22`) *at origin* raise P(gap > 50) regardless of the deficit level; down side symmetric (`fg251`). Complements (not duplicates) the package's `up_last`/`dn_last`, which are *activation* prices.

**(b)**
```python
def bid_stack(base, data):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    r = pd.DataFrame(index=U(o))
    for sid, n in [("fg243_mfrr_up_bids_sum","upbids"), ("fg22_mfrr_last_up_bid_price","upbidp"),
                   ("fg251_mfrr_last_down_bid_price","dnbidp")]:
        a = asof(data.series("fg_extra", sid), o, lags=(0,4)); a.index = U(o)
        r[n+"_L"], r[n+"_d"] = a["lag0"], a["lag0"] - a["lag4"]
    spot = data.series("pkg","fi_spot_price").drop_duplicates("ts").set_index("ts")["value"]
    st = at_delivery(data.series("pkg","fi_spot_price"), base.assign(delivery=base["origin"]))
    r = r.assign(upbidp_marg=(r["upbidp_L"] - st.to_numpy()), dnbidp_marg=(st.to_numpy() - r["dnbidp_L"]))
    return per_origin(base, r.drop(columns=["upbids_d"].__class__([])) )
```
(Simplify: keep the spread columns, spot at origin via `at_delivery` as in package.py; `spot` lookup import line isn't needed.) **(c) Moves:** `brier_spike` both folds. **(d) Kill:** <0.002 absolute `brier_spike` gain on both folds → drop.

## 6. UMM unplanned-outage freshness deltas

**(a) Hypothesis.** Newly published unplanned outages (type 1, FI area) remove cheap capacity and precede price-spike episodes; *planned* outages known at origin for the delivery quarter shift the level. The exploitable edge vs the crowd is the **delta vs what was known 6 h ago** — the crowd baseline has no UMM at all. Highest ceiling on `brier_spike`, but the most engineering (version dedup + per-origin `fu` filter), hence ranked last on gain/hour.

**(b)**
```python
def umm_now(base, data):
    u = data["umm"].copy()
    u = u.sort_values("fu")                     # newest version per unit×period wins downstream
    idc = [c for c in ("unit_kind","area","fuel_type","event_start_utc") if c in u]  # verify real unit key!
    u = u.drop_duplicates(subset=idc, keep="last")
    un = u[(u.unavailabilityType == 1) & (u.area == "FI")]
    out = pd.DataFrame(index=base.index)
    for name, hrs in (("now", 0), ("d6h", 6)):
        cut = base["origin"] - pd.Timedelta(hours=hrs)
        m = un.merge(base[["origin","delivery"]].assign(k=cut), how="cross")  # replace with grouped loop in practice
    # practical implementation: loop over ~3k unique origins with
    # sel = un[(un.fu <= o) & (un.event_start_utc <= t) & (un.event_stop_utc > t)]
    # features: unplan_mw_origin (t=origin), unplan_mw_deliv (t=delivery), unplan_mw_d6h = difference of the two sums
```

Also emit `plan_mw_deliv` (type 2). Everything is `fu ≤ origin` (or ≤ origin−6h) filtered → passes leakcheck once sources include `"umm"`. Fit nothing; no cutoff issue. **(c) Moves:** `brier_spike`, and `MAE_s13_40` via planned outages. **(d) Kill:** <1% relative `brier_spike` gain on both folds, or unplanned-FI volume coverage turns out sparse in Jun–Oct → drop and report null.

---

**Sequencing advice:** run 1 alone first (fastest, establishes how much of the package's imb-lag block is redundant — afterwards try `drop=["gap_L4","gap_L16"]` as a free variant). Then 2 and 3 in parallel; 4 only if 1 leaves `brier_spike` unmoved. Merge whatever survives into one combined run before reporting, since leaderboard comparability requires the identical feature set on both folds.