## First, a flag from the leaderboard

`brier_dir` is **identical to 5 decimals between the `direct` and `mixture` rows on both folds** (0.43691 / 0.45278). Two different model families cannot produce the same direction Brier unless the direction column is not actually model-driven. Reading `models.py` explains it: `p_none` is `float(np.mean(d==0))` — a **constant** — and `calibrate()` only Platt-maps the up/down ratio conditional on non-zero. So direction skill enters only through a binary classifier on ~30% of rows. That is the cheapest win on the board; everything below is ordered by that.

---

### 1. Model `p_none` instead of hard-coding it (dir Brier)

**(a) Hypothesis.** P(no mFRR activation) depends strongly on horizon band and hour block (long steps → the TSO has already balanced; peak hours → activation more likely), but the code uses one train-wide constant. Mechanism: `p_up+p_down` is rescaled to `1−p_none`; a wrong constant injects a fixed bias into all three classes, and Brier is quadratic in it. Fold-A/B base rates also differ, so the constant is fold-specific and drifts.

**(b) Sketch** — a lookup table fitted only on deliveries < 2026‑07‑31T21:00Z (allowed by rule 2, and leakcheck-safe because it reads no sources):

```python
import numpy as np, pandas as pd
from experiments.lab.data import build_base, U
CUT = pd.Timestamp("2026-07-31T21:00Z")

def _prior():
    b = build_base(); b = b[(b.delivery < CUT) & b.dir.notna()].copy()
    b["hb"] = U(b.delivery).dt.hour // 6
    b["band"] = np.select([b.step <= 4, b.step <= 12, b.step <= 24], [0, 1, 2], 3)
    return b.groupby(["hb", "band"])["dir"].apply(lambda s: float((s == 0).mean()))
PRIOR = _prior()

def dir_prior(base, data):
    idx = pd.MultiIndex.from_arrays([(U(base.delivery).dt.hour // 6).to_numpy(),
        np.select([base.step <= 4, base.step <= 12, base.step <= 24], [0, 1, 2], 3)])
    return pd.DataFrame({"p_none_prior": PRIOR.reindex(idx).to_numpy()}, index=base.index)

def fix_none(pred, va, X):
    pn = np.clip(X["p_none_prior"].to_numpy(), .30, .90)
    u, d = pred["p_up"], pred["p_down"]; t = np.maximum(u + d, 1e-6)
    pred["p_none"] = pn; pred["p_up"] = (1 - pn) * u / t; pred["p_down"] = (1 - pn) * d / t
    return pred

run_experiment("dir prior p_none", agent="prob", feature_fns=[package_features, dir_prior],
               model="mixture", calibrate=True, post=fix_none, notes="post runs after calibrate")
```

Also print, as a one-liner diagnostic, `base.groupby(["foldA","foldB"])["dir"].value_counts(normalize=True)` — if the September base rate differs from June–July, that alone sets a floor on achievable Brier.

**(c)** `brier_dir`, all steps; expect the largest gain on steps 13–40 (where p_none is far from the constant).
**(d)** Kill if `brier_dir` improves < 0.005 on either fold. Report the per-band base rates regardless.

---

### 2. Direction-specific featues for the up/down classifier (dir Brier)

**(a)** The classifier sees only the package features, which are level/weather-centric. Direction is a *sign* problem: recent gap sign persistence, the ramp of the spot curve, cross-border flow sign, and the up/down activation asymmetry carry the sign. Mechanism: the mixture's up/down grids are already decent; the 30% non-zero mass is where the classification error lives.

**(b)**

```python
def dir_feats(base, data):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    S  = lambda sid: data.series("pkg", sid)
    g  = asof(S("fi_imbalance_price"), o, lags=tuple(range(8))); g.index = U(o)
    sp = S("fi_spot_price").drop_duplicates("ts").set_index("ts")["value"]
    oi = pd.DatetimeIndex(U(o))
    last = oi - pd.to_timedelta(g["age_q"].to_numpy() * 15, unit="min")
    gaps = g[[f"lag{i}" for i in range(8)]].to_numpy() - np.stack(
        [sp.reindex(last - i * pd.Timedelta(minutes=15)).to_numpy() for i in range(8)], 1)
    rs = pd.DataFrame(index=U(o))
    rs["gap_sign_frac"] = np.nanmean(np.sign(gaps), axis=1)           # signed persistence
    rs["gap_last4_sd"]  = np.nanstd(gaps[:, :4], axis=1)
    rs["flow_se1"]      = asof(S("fi_se1_flow"), o)["lag0"].to_numpy()
    rs["flow_ee"]       = asof(S("fi_ee_flow"), o)["lag0"].to_numpy()
    rs["act_asym"]      = (asof_window(S("fi_mfrr_up_activated"), o, 4) -
                           asof_window(S("fi_mfrr_down_activated"), o, 4)).to_numpy()
    return per_origin(base, rs.add_prefix("dir_"))
```
Variants: `hgb={"min_samples_leaf": 80, "max_iter": 400}` (the shared `min_samples_leaf=200` is coarse for a 70/30 classifier) — note this also loosens the regressors, so judge it on pinball too.

**(c)** `brier_dir`, steps 1–12 mainly. **(d)** Kill if `brier_dir` gain < 0.005 on fold B (fold A is 28 days, noisier).

---

### 3. Real-time reserve-price distances for the spike heads (spike Brier)

**(a)** `hi_dist/lo_dist` use the package's `fi_mfrr_up_price` (lagged). `fg_extra` carries *real-time* last up/down bid prices and bid depth with much shorter `fu`. Mechanism: imbalance spikes happen when the marginal activation price crosses spot ± 50; a fresher activation price and the bid stack depth are near-sufficient statistics. Add cumulative surplus/deficit and BRP plan deviation to catch the sustained-imbalance regime.

**(b)**

```python
def spike_feats(base, data):
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    a  = asof(data.series("fg_extra", "fg22_mfrr_last_up_bid_price"),  o, lags=(0, 4)); a.index = U(o)
    b  = asof(data.series("fg_extra", "fg251_mfrr_last_down_bid_price"), o, lags=(0,)); b.index = U(o)
    dp = asof(data.series("fg_extra", "fg243_mfrr_up_bids_sum"),       o, lags=(0,)); dp.index = U(o)
    cu = asof(data.series("fg_rt",    "fg186_surplus_deficit_cum_rt"), o, lags=(0, 1)); cu.index = U(o)
    spot = at_delivery(data.series("pkg", "fi_spot_price"), base)
    f = pd.DataFrame(index=base.index)
    f["hi_dist_rt"] = per_origin(base, a)["lag0"] - (spot + 50)
    f["lo_dist_rt"] = (spot - 50) - per_origin(base, b)["lag0"]
    f["up_dist_rt4"] = per_origin(base, a)["lag4"] - (spot + 50)
    f["up_depth"]   = per_origin(base, dp)["lag0"]
    C = per_origin(base, cu)
    f["cum_sd"], f["cum_sd_d"] = C["lag0"], C["lag0"] - C["lag1"]
    f["plan_dev"] = (at_delivery(data.series("fg_extra", "fg242_production_plan_da"), base)
                     - at_delivery(data.series("pkg", "fi_consumption_fc_da"), base))
    return f
```

**(c)** `brier_spike` at all steps; check `pinball` doesn't degrade (the same features feed the conditional grids). **(d)** Require ≥ 0.004 improvement on **both** folds; otherwise ablate to just `hi_dist_rt/lo_dist_rt` once before dropping.

---

### 4. Shrink spike probabilities toward the pre-cutoff base rate (spike Brier)

**(a)** After Platt on a 14-day window with few positives, `p_hi/p_lo` are overconfident at the row level; Brier is quadratic, so a shrunk forecast beats a sharp one unless it is genuinely well-calibrated. Also protects against the September/Fold-B base-rate drift seen in MAE (43.9 vs 29.3).

**(b)** Two a-priori variants, `ALPHA = 0.85, 0.70`:
```python
RATE = 0.08   # fold-train spike base rate, hard-coded, pre-cutoff
def shrink(pred, va, X, A=0.85):
    for c in ("p_hi", "p_lo"):
        pred[c] = A * pred[c] + (1 - A) * RATE
    s = pred["p_hi"] + pred["p_lo"]; m = s > 1
    pred["p_hi"][m] /= s[m]; pred["p_lo"][m] /= s[m]
    return pred
```
Decide with a reliability table (predicted vs realised spike rate per decile, computed on the saved `_cache/preds` npz), not by tuning α on validation.

**(c)** `brier_spike`. **(d)** Kill if both α lose on fold A, or if the reliabity table shows the unshrunk forecast is already flat (then the problem is the features, not the calibration).

---

### 5. `target="price"` and per-column selection (MAE / pinball)

**(a)** The mixture models `gap = imb − spot`, so a spike to 500 during a high-spot hour is a small gap. In price space the model can learn level-dependent tails. Direct-vs-mixture already differ by column (mixture wins pinball on A and B; direct wins MAE on B by 0.1).

**(b)** `run_experiment("price target mixture", feature_fns=[package_features], model="mixture", target="price")` and `target="price", model="direct"`. Then a small script that loads the four saved npz per fold and evaluates `p50` from one and `p10/p90` from the other with `models.metrics`, appending via `experiments.lab.run._append`. Only blend saved, already leak-checked predictions.

**(c)** `pinball` (tails) and `MAE_s13_40`. **(d)** Kill if no variant beats the reference on both `MAE` and `pinball` on fold A.

---

### 6. Recency weighting under drift (all four)

**(a)** Fold A validation is September, trained on June–Sept 6; the reference `pinball` is 75% worse on A than B while coverage is similar — a volatility/regime effect, not just bias. Exponential decay plus dropping the earliest weeks may transfer better; conversely fold B trains on only 62 days, so aggressive decay can hurt.

**(b)**
```python
def wt(tr):
    age = (tr.delivery.max() - tr.delivery) / pd.Timedelta(days=10)
    return np.exp(-np.log(2) * age).to_numpy()
```
Variants: halflife 7, 10, 21 days, and "drop first 21 days of train".

**(c)** `MAE`/`pinball` on A (should improve if drift dominates), watch B for degradation. **(d)** Kill any variant that loses on MAE or pinball on either fold.

---

**Recommended for the final model:** #1 + #2 unconditionally (direction is currently unmodelled), #3 if the ablation holds, then re-check #4 on the shrunken probabilities. Everything above is cheap: 1–4 `run_experiment` calls each, all under ~3 min at 2 threads.