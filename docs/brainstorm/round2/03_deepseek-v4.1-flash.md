# Round 2 — Data detective

## 1. Thesis

The core is right about *what* to model (a direction mixture) and wrong about *what quantity* to model: the package's target is the imbalance price, but four of the eight columns are defined **relative to the delivery quarter's spot price** (`score.py`: spike iff `imb > spot ± 50`), and the imbalance price in a directional quarter equals the mFRR marginal price in that direction (±0.5 €/MWh in 43 % of quarters, median |diff| 1.0). So predict the *price level* (anchored on the last usable mFRR marginal price) and subtract spot, instead of predicting the gap where the model must discover a −1 slope in spot. Second edge: the spike label is a **known, per-step threshold**, so spike probabilities are tail probabilities evaluated at `spot + 50` — and the validation month's spot regime (Sep mean 57.0, P90 145.8) is nearly 2× the test month's (Oct mean 33.6, P90 61.2), so validation-tuned spike base rates will *not* transfer, and a July fold (spot mean 15.4) is a better stress test than September.

Nothing here needs new data — it is all refactoring and checking, which is what 32 hours allows.

## 2. Top five ideas, ranked by expected points per hour

### #1. Anchor on the mFRR marginal price; target the price, not the gap

**What.** For every (origin `t`, step `k`), delivery `q = t + 15k min`, take the **newest usable** (not fixed-lag) up/down marginal prices and build mechanical anchors:

```python
def newest_usable(sid, t):
    s = inp.query("series_id == @sid and first_usable_origin_utc <= @t")
    s = s.sort_values("timestamp_utc").iloc[-1]
    return float(s.value), s.timestamp_utc, int((t - s.timestamp_utc) / pd.Timedelta("15min"))

up, up_ts, up_age = newest_usable("fi_mfrr_up_price",  t)   # age 5 in sample
dn, dn_ts, dn_age = newest_usable("fi_mfrr_down_price", t)   # age 5 (7 if sparse)
sp = wide.at[q, "fi_spot_price"]                             # known for all 40 steps
f["up_price_last"], f["up_age"] = up, up_age
f["dn_price_last"], f["dn_age"] = dn, dn_age
f["up_anchor_gap"] = up - sp          # mechanical up-gap point forecast
f["dn_anchor_gap"] = dn - sp          # mechanical down-gap point forecast
f["up_upgrade"]   = up - dn           # offer-ladder spread = width signal
```

Then train the two conditional models on **price at delivery**, not gap (`F_up(p)`, `F_down(p)`), and re-attach spot only when writing columns: `p10/p50/p90 = spot + F⁻¹(q)`, `p_spike_high = P(up)·(1 − F_up(spot+50)) + P(down)·(1 − F_down(spot+50))`. Optionally also fit a challenger in gap-space on the residual `gap − up_anchor_gap` / `gap − dn_anchor_gap`.

**Evidence.** Up price median 21 / P90 122 / P99 232, down price median 10.3 / P90 89.3 (per-series stats); imbalance price = mFRR marginal in direction 43 % of quarters, median |diff| 1.0; down gap is flat across activated-volume quintiles (−18 → −15, rank corr 0.10) while up gap climbs (+8 → +61, corr 0.58) — the down price is a near-constant level, so `dn − spot` is a strong anchor for the 65 % majority class and the −1 spot slope comes for free. Sept spot P90 145.8 vs Oct 61.2 means the same up price maps to a very different gap in the test month; price-space is invariant to that.

**Metric.** MAE (30) and pinball (20) primarily; spikes secondarily. Rough guess: MAE −1 to −2 %, pinball −3 to −6 % vs gap-space. Confidence medium.

**Cost.** 4–6 person-hours (a target/assembly refactor, no new fetching).

**Leak traps.** `up_age`/`dn_age` must come from the **row's own** `first_usable_origin_utc`, never `shift(5)` — aFRR gaps up to 29 quarters mean fixed shifts silently read the future or the wrong row. Never touch delivery-quarter mFRR/aFRR values.

**Go/no-go.** Validation: pinball ≤ 0.97 × gap-space and MAE ≤ 0.99 ×. Second fold: train ≤ 31 Jul, validate Aug (or Jul). If only one of the two folds wins, keep per-column selection and don't refactor the whole thing.

### #2. Spikes as a threshold-distance logistic, not per-band isotonic

**What.** One small model per side, or two features in the existing tail model, in the *distance* space:

```python
f["hi_dist"] = f["up_price_last"] - (sp + 50)    # < 0 ⇒ a spike needs a higher up price than last seen
f["lo_dist"] = (sp - 50) - f["dn_price_last"]    # < 0 ⇒ a low spike needs a lower down price than last seen
f["sp_hi"]  = logistic(f["hi_dist"], hour, net_position)
```

**Evidence.** The spike definition compares against the delivery quarter's own spot, which is known at every step (`data_samples.md` §2: spot usable 119 quarters ahead). Up price P10 is 1.9 and its median is 21, so at spot 20 an up spike needs up price > 70 (common); at spot 145 it needs > 195 (P99 territory). Conversely a low spike needs down price < spot − 50, i.e. spot > 60 for a down price of 10 — so **lower spot ⇒ more high spikes, fewer low spikes**. The observed train→validation flip (9.0/7.3 → 12.1/13.0) is consistent with September's high spot. A per-band isotonic map fitted on September would bake in the wrong base rate for a low-spot October.

**Metric.** Exceptional prices (20 points) — the thinnest competition, since most teams will ship two independent binary classifiers with raw spot as a feature.

**Cost.** 3–4 hours.

**Leak traps.** Use `p_spike_high + p_spike_low ≤ 1` by construction (subtract the overlap). Never calibrate on the *validation* month's base rate — calibrate on `hi_dist`/`lo_dist`, which is regime-free.

**Go/no-go.** Validation `brier_spike_mean ≤ core − 0.004` **and** both components improve; repeat on the August fold. Verify the sign first: high-spike rate must fall across spot quintiles *within up quarters*.

### #3. Replace "add a July fold" for every calibration decision

**What.** Folds: A = 7 Sep–4 Oct (official), B = July (low spot, mean 15.4) and/or August (mean 41.3). Choose the shrinkage factors, per-band corrections and spike calibration by `min(A, B)`, not A.

**Evidence.** Spot monthly means: Jun 45.3, Jul 15.4, Aug 41.3, Sep 57.0, Oct 33.6; P90: Jul 30.1, Aug 112.8, Sep 145.8, Oct 61.2. October (the scored month) sits between July and August, *not* September. Every round-1 plan proposes shrinkage/`min(validation, stress)` with the stress window = Aug→Sep — i.e. two high-spot months, which does not stress the low-spot regime at all.

**Metric.** Protects pinball (20) + spikes (20). Expected effect: avoids a several-point loss rather than gaining points. Confidence medium-high (this is a variance play, and the round-1 plans are exposed here).

**Cost.** 2–3 hours (fold plumbing is a `make_templates.py` call plus a loop; the scorer already exists).

**Leak traps.** Purge 10 h around fold boundaries; per-fold calibration only on that fold's OOF predictions.

**Go/no-go.** No gate needed — this is the decision rule, not a model.

### #4. Flow saturation / import headroom at lag 3 (fresher than the price block)

**What.** The measured block (production, consumption, flows) is at **−3 quarters**; the price block is at −5. Use it:

```python
fl = inp.query("series_id in ['fi_se1_flow','fi_se3_flow','fi_no4_flow','fi_ee_flow']")
u  = fl[fl.first_usable_origin_utc <= t].pivot(index="timestamp_utc", columns="series_id", values="value")
ts = u.index[-1]                                   # age 3
hist = u[u.index > ts - pd.Timedelta("30D")]       # only rows usable at t
lo = hist.min()                                    # trailing import extreme per border
f["sat"] = ((u.loc[ts] - lo) / (-lo)).clip(0, 1)   # 1 = at the historical import maximum
f["imp_headroom"] = -(u.loc[ts].sum()) / (-lo.sum())
f["ee_cong"] = (abs(u.loc[ts, "fi_ee_flow"]) / wide.at[q, "fi_ee_capacity_da"]).clip(0, 1)
```

**Evidence.** On the volatile day, the 17:00–17:45 spike (797, 2640, 4000, 2664 €/MWh) coincides with `fi_se1_flow = −1990.85` (1st pct −1995, min −2379.8) and `fi_se3_flow = −1192.28` (10th pct −1193.5, min −1197.1) — both borders pinned at their import extreme. On the calm day the same borders are exporting (+148 … +1400). `fi_ee_capacity_da` reaches 0 (P1 358), so an isolated Finland is a discrete state known ahead.

**Metric.** Up-side spike Brier and p90 pinball; MAE at short steps. Confidence medium-low (two rows is an anecdote; the mechanism is sound).

**Cost.** 3 hours.

**Leak traps.** The trailing extreme must be computed only from rows with `first_usable_origin_utc ≤ t` and a trailing window; a full-sample percentile is leakage.

**Go/no-go.** On validation, quarters with `imp_headroom` in the top quintile must have a materially higher up-spike rate *conditional on net position*; `brier_spike_mean` down ≥ 0.002 on fold A and not worse on fold B.

### #5. As-of online recalibration during the backtest (gated on a written answer)

**What.** At origin `t`, recompute the p10/p90 offsets and the spike intercept from realised residuals of deliveries already published (`first_usable_origin_utc ≤ t`), trailing 3 days, shrunk 0.5 toward the static fit. This is exactly what the baseline notebook already does with persistence, so the *feature* use is clearly legal; ask `#turku-energia` whether recalibration counts as "training on test data" (PLAN §12 already lists the question).

**Evidence.** October's drift is real (up share 35 % → 25 % on 1–4 Oct); spikes and quantiles are base-rate sensitive; adaptive conformal only needs realised values that are already published.

**Metric.** Pinball + spikes. Confidence low-medium; **gated** — if the answer is no, ship the static fit.

**Cost.** 3 hours behind a flag.

**Leak traps.** Only rows with `fu ≤ t`; never reuse the forecast's own error before its actual is published.

## 3. What to change or drop in the round-1 core

- **Shrink the "recent state" block.** The freshness table (MAE 26.4 @ lag 1 … 43.8 @ lag 5) cannot be reproduced from package data at lag 5. With down/up runs of median 3/2 quarters, a lag-5 direction agrees 0.70 with step 1 — barely above the 65 % down base rate. So drop the HMM smoothing, the persistence blend at steps 1–4 (already shown to be a no-op) and the elaborate "horizon bridge" built on 75-minute-old data; spend those hours on the external fetch that gets you to lag 1–2, and on ideas #1–#4.
- **Keep** the anchored gap level: `spot + c + w·(gap@lag5 − c)` still gives 43.0 vs 44.2 at step 1 — the *level* is worth something, the *direction* is not.
- **Do not transfer September's spike base rates** to October (see #2). Also do not add within-quarter position features (30.9/31.1/32.3/31.4 by quarter — dead).
- **Drop the package-only "physical nowcast".** Production/consumption/flows is a closed identity: at 2026-09-15T15:00Z, `7090.54 − 7994.98 + 1438.03 + 303.04 + 50.01 − 889.22 = −2.46 MW`. There is no hidden imbalance residual; only the external fetch gives you plan error.
- **Negative result worth an hour:** the aFRR `missingness` and the SE1/SE3 neighbour prices (lag 9, 0.10 corr with gap) are not the edge; document them as tested-and-rejected — that is cheap jury credit on the reasoning chain.

## 4. Three quick checks, in pandas

1. **The identity** (kills a plan): on the training quarter-hours, `resid = fi_production − fi_consumption + (fi_se1_flow + fi_se3_flow + fi_no4_flow + fi_ee_flow)`; report `resid.std()`. If ≲ 30 MW, no package-only nowcast exists.

2. **Anchor quality** (decides #1): for each origin, join `newest_usable(up/dn price)` to the delivery value on the same quarter; on up quarters compute `MAE(up_price_q − up_price_last)` and the share within ±1 €/MWh; same for down. Also report `corr(dn_price_q, spot_q)` vs `corr(gap_q, spot_q)` on down quarters — if the first is much lower, the price-space target wins.

3. **Threshold monotonicity** (decides #2), straight on training data: within up quarters, tabulate high-spike rate by spot quintile; within down quarters, low-spike rate by spot quintile. If monotone (high falling with spot, low rising), the `hi_dist`/`lo_dist` model is safe and the September base rate is unusable for October.

**Best idea outside my angle:** one person spends 45 minutes writing the *negative-results appendix* (identity, quarter-position null, SE1 lag-9 weakness, persistence no-op). The reasoning chain is 20 jury points of Level 1 for hours of work — the best points-per-hour left on the table.