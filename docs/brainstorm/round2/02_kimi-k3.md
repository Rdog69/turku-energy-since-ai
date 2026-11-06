# Round 2 — Nordic balancing-market insider

## 1. Thesis

Finland's imbalance price is the **Nordic mFRR marginal price** — until the interconnectors from Sweden are saturated, at which point Finland clears on its own steep merit order and prices decouple into the 500–4000 €/MWh tail (Sep 9 in `data_samples.md` is this exact signature). Every round-1 variant treats congestion as just another LightGBM feature; modelling **flow saturation and FI↔SE1 decoupling as an explicit regime** is the highest-value thing the shared core misses, and it lands directly on the two tail metrics (spikes, pinball). Second: the price *is* the activated bid (equal to the marginal in 43 % of quarters, median |Δ| 1.0), and bids live on a round-number ladder — snapping predictive quantiles to that ladder is cheap, surgical, and untried by pure-ML teams. These two get us from tied to first on 40–50 of the 80 automatic points.

## 2. Mechanisms in one page (cited, then reused below)

- **Nordic mFRR EAM.** One shared Nordic bid list, 15-min products, bids lock ≈45 min before the quarter (☐ exact GCT), scheduled activation at quarter start for the forecast system imbalance, direct activation within the quarter for acute events (trips, forecast errors). When transmission isn't congested, one Nordic marginal price results. That's why SE1's imbalance price equals Finland's mFRR marginal **75 % of quarters** — and why it does *not* during Finnish spikes: Sep 9 17:15–17:45, FI 2640/4000/2664 while SE1 sits at 136/68/40. **Decoupling = congestion → local clearing.** This is the spike mechanism.
- **Flow ceilings.** Training extremes look like ATC limits: SE3 ±1197, SE1 −2380/+2099, EE ±1032 (☐ treat as empirical capacities, fit on training only). On Sep 9, `fi_se3_flow` is pinned at ≈−1193 continuously from 06:00 to 20:45 while FI spikes; on the calm wind day (Sep 19) it floats freely. Saturation is slow-moving (hours), which makes it a **lead indicator of the congestion regime**, usable from lag-3 flow data.
- **Bid ladder.** Up-marginal prices in the samples are round: 5, 10, 35, 40, 150, 500, 750, 1500, 4000. The price distribution is *atomic*, not smooth.
- **June-2026 VWAP rule.** Price = volume-weighted average of co-directional mFRR and aFRR prices ⇒ usually ≈ marginal, with a damping term when aFRR demand is present. We have no aFRR volumes, so damping is inferred from aFRR-price *presence* and spread.
- **Run structure.** Median direction runs of 2–3 quarters mean shock episodes (direct activations) persist only a few quarters — but within those quarters the tail regime is near-certain.

## 3. Top 5 ideas, ranked by expected points per hour

### Idea 1 — Congestion/decoupling regime: flow saturation + SE1 anchor divergence (top pick)

**What.** Per border, normalized import/export utilization from lag-3-usable flows; saturation flags and spell duration; plus an ex-post depeg meter built only from lag-9 pairs (FI marginal and SE1 price at the same quarter, both usable). Feed as features to the direction model, the F_up/F_down tail models, and a high-spike classifier; optionally split F_up into uncongested/congested regimes with regime probability as a feature.

```python
CAP = {'se1': {'imp': 2380, 'exp': 2100}, 'se3': {'imp': 1197, 'exp': 1198},
       'ee':  {'imp': 1000, 'exp': 1032}}            # ☐ training extremes, fit ≤ 4 Oct
for b, caps in CAP.items():
    f = w[f'fi_{b}_flow']
    w[f'imp_util_{b}'] = (-f).clip(lower=0) / caps['imp']
    w[f'exp_util_{b}'] = ( f).clip(lower=0) / caps['exp']
w['sat_imp_nordic'] = (w[['imp_util_se1','imp_util_se3']].max(axis=1) > 0.97)
w['sat_imp_dur']    = spell_length(w['sat_imp_nordic'])          # from usable lag-3 history
# depeg, same-quarter pairs, only at lag >= 9 so both sides are usable at origin
w['depeg_abs'] = (w.fi_mfrr_up_price - w.se1_imbalance_price_long).abs()
feat['depeg_ewm_lag9'] = w['depeg_abs'].ewm(halflife=8).mean().shift(9)
feat['scarcity'] = feat['sat_imp_nordic_lag3'] * feat['net_position_da']  # from PLAN finding
```

**Evidence.** Mechanism above; `data_samples.md` Sep 9 (SE3 pinned −1193 through every spike hour; SE1 decouples exactly at the 1500–4000 quarters); Sep 19 counterexample (no saturation, gap ≈ −7 all day); net-position quintile table (|gap| 13→49). The interaction "high residual load *and* no import relief" is the textbook scarcity condition.
**Metrics.** Spike Brier: −3 to −6 % relative (medium confidence; high for mechanism, low for size — few events). Pinball p90: −1 to −3 %. MAE: −0 to −1 %. 
**Cost.** 4–5 person-hours.
**Leak traps.** Capacities and thresholds fitted on training only (no November flows); SE1/FI same-quarter comparisons only at lag ≥ 9; flows at lag ≥ 3 via `first_usable_origin_utc`, never fixed shifts.
**Go/no-go.** Ex-ante kill test (§4) on training: saturation × direction must separate spike shares roughly as strongly as net position does; then feature set must improve spike Brier on **both** validation folds (Fold A 7–20 Sep, Fold B 21 Sep–4 Oct). Kill if SE1/FI depeg doesn't co-occur with large |gap|.

### Idea 2 — Snap quantiles to the bid ladder (atomic price structure)

**What.** Build per-direction atom sets from rounded mFRR marginal prices (frequency > 0.5 % in training; rounding: 1 € below 100, 5–10 € below 1000, 50–100 € above). Snap mixture p10/p50/p90 (in **price** space, then re-derive everything gap-wise) to the nearest atom if within ~1.5 %, using a monotone map so ordering survives. For p90 in high-volume up regimes, prefer tail atoms (500/750/1500/4000) over interpolated values.

```python
atoms_up = atom_set(train.fi_mfrr_up_price)   # fitted <= 2026-10-04 only
snap = lambda x: nearest_atom(x, atoms_up, tol=0.015 * max(abs(x), 1))
p10, p50, p90 = np.sort([snap(p10), snap(p50), snap(p90)])   # per row, monotone
```

**Evidence.** Price equals the marginal in 43 % of directional quarters (median |Δ| 1.0); sample rows show repeated exact round values (4000.00, 1500.00, 750.00, 40.00, 5.00).
**Metrics.** Pinball: −1 to −3 % (medium confidence — quantile loss rewards landing on mass points). MAE: −0.5 to −1.5 % (median snap). Spikes: small (±50 thresholds rarely sit near atoms).
**Cost.** 3–4 h.
**Leak traps.** Atoms and tolerances fitted ≤ 4 Oct and held fixed; snap in absolute price (spot is known per row — internal use only, never exported); re-check p10 ≤ p50 ≤ p90 after snapping.
**Go/no-go.** Count share of prices within ±1 % of an atom on training (expect > 50 % of directional quarters); adopt only if pinball improves on both folds, and the Aug→Sep stress test doesn't degrade.

### Idea 3 — Explicit up-merit-order: predicted activation volume → tail regime

**What.** Train a LightGBM quantile model for `fi_mfrr_up_activated` (q 0.5, 0.9). For the up-conditional gap model, add the predicted volume percentile as a feature and — the structural part — replace the LightGBM tail with an empirical, isotonic-smoothed mapping volume-percentile-bin → gap quantiles fitted on training; when predicted volume exceeds an elbow (☐ ~300–400 MW, visible on Sep 9 where prices explode only once activations pass 400 MW), switch F_up to a "capacity-segment" empirical tail (atoms 500–4000). Blend with the direct challenger per column per fold.

**Evidence.** Rank corr 0.58; median up-gap +8→+61 across volume quintiles; Sep 9: 226 MW → 187 €, 428 → 467, 659 → 4000 — volume walks up the merit order an hour before prices go. Down side is flat (0.10), so this is **up-only**; don't waste it on F_down. Round 1 deprioritized GLM's merit-order idea; the measured numbers justify resurrecting it as a *tail structure*, not a separate model.
**Metrics.** Spike Brier: −3 to −8 % if it beats the flat classifier (low-medium confidence). Pinball tails: −2 to −5 %. MAE: small.
**Cost.** 5–7 h.
**Leak traps.** Volume model trained out-of-fold before fitting the bin map (else optimistic tails); isotonic map fit ≤ 4 Oct.
**Go/no-go.** Volume-conditioned spike probabilities beat the direct spike classifier's Brier on both folds; kill otherwise, keep plain features.

### Idea 4 — aFRR damping term (model the June-2026 VWAP, don't let LightGBM rediscover it)

**What.** Feature block: aFRR-price presence (usable at lag ≥ 5), rolling presence share, and last usable (mFRR marginal − aFRR price) spread per direction. Add `damp_hat = P(aFRR present | context) × E[marginal − actual | context]` as a feature and as an optional negative correction on F_up quantiles.

**Evidence.** README §5.2 states the VWAP rule; samples show the residual: 14:45 467.39 vs 500 marginal (damping 32.6), 16:45 288.55 vs 300 — always non-positive in up regime. Median |Δ| is only 1.0, so this is a small, systematic correction, exactly the kind LightGBM wastes depth approximating.
**Metrics.** MAE: −0.3 to −1 % (low-medium confidence). Pinball p50-side: similar.
**Cost.** 2–3 h.
**Leak traps.** aFRR series have 60-min lag (lag ≥ 5); presence for future quarters predicted from persistence only.
**Go/no-go.** In training, regress (price − marginal) on presence × spread: R² > 0.2 and correct sign, else drop; then MAE on directional quarters must improve on both folds.

### Idea 5 — Episode memory: shock-state with explicit survival decay, steps 1–8

**What.** Define episode state from usable lag-5 data (|gap| above its 75th percentile or an activation jump > 300 MW in the last 1–3 usable quarters). Estimate survival S_k = P(episode alive at origin + k | episode at t−5) from training run statistics. For steps 1–8, form F_k = S_k·F_episode + (1−S_k)·F_normal per direction, rather than letting `step` alone figure out decay inside the trees.

**Evidence.** Freshness curve (MAE 26.4 at lag 1 vs 43.8 at lag 5) quantifies the value of the recent state; run stats (median 2–3, mean 4.3/7.9) set realistic S_k; Sep 9 spike cores last 2–4 quarters.
**Metrics.** Steps 1–8 MAE: −5 to −10 % there → −1 to −2 % overall (medium confidence); early-step pinball similar.
**Cost.** 3–4 h.
**Leak traps.** State and survival from training-usable lags only.
**Go/no-go.** Use the scorer's by-horizon output: hours 1–2 MAE must improve on both folds.

## 4. What to change or drop in the round-1 core

- **Merge, don't stack:** Ideas 1–3 are changes *inside* the agreed mixture, not extra models. F_up gains a congestion-regime split and a volume→tail mapping; F_down stays simple (down-merit is flat, rank corr 0.10 — put no effort there).
- **Snap the final quantiles (Idea 2) as a last pipeline step**, after per-column challenger selection; it's model-agnostic.
- **Drop/**deprioritize: UMM for the model (already low; congestion carries the same physical signal hours earlier), HMM smoothing (already agreed dead), any Elering/Statnett work — Idea 1 uses package flows and is strictly fresher.
- **Keep unchanged:** per-column challenger selection, freshness-first feature discipline (train with exactly the missingness pattern each origin will have — simulate it in training rows, not just in inference), pinball/Brier band calibration.
- **Narrative note:** Ideas 1–3 *are* the reasoning chain — wind error → residual load → import headroom exhausted → local merit order → price. Write this into the report; it's worth jury points.

## 5. Three quick pandas checks (confirm or kill Idea 1, run first)

```python
t = train  # <= 2026-10-04 only; spot used internally, never exported

# Check 1: does import saturation separate high-spike risk by direction?
t['sat_imp'] = (t['fi_se3_flow'] < -1170) | (t['fi_se1_flow'] < -2000)
t['spike_hi'] = t['fi_imbalance_price'] - spot_le(t) > 50     # join spot internally
print(t.assign(up=t['fi_mfrr_direction'] > 0)
        .groupby(['sat_imp', 'up'])['spike_hi'].agg(['mean', 'count']))
# KILL if saturated+up is not clearly >2x unsaturated+up; same test for export saturation vs low spikes.

# Check 2: does FI-SE1 depeg co-occur with large |gap| (i.e., it marks the congestion regime)?
t['depeg'] = t['fi_mfrr_up_price'] - t['se1_imbalance_price_long']
print(t.groupby(pd.qcut((t['fi_imbalance_price'] - spot_le(t)).abs(), 10))
        ['depeg'].apply(lambda s: s.abs().median()))
# KILL if not monotone increasing.

# Check 3: how persistent is saturation? (sizes the horizon reach of the feature)
sat = t['sat_imp'].astype(int)
print({k: (sat.shift(-k) > 0)[sat > 0].mean() for k in [1, 4, 8, 16, 24, 32]})
# KILL (or demote to a steps-1-4 feature) if P(sat at +k | sat now) falls below ~0.6 before k=8.
```

If any check fails, demote Idea 1 to "plain features" and reallocate its hours to Ideas 2 and 3. Honest caveat: my effect sizes are judgement calls from the spike mechanics and the measured separation tables — with ~330 spike events in validation, gains below ~2 % on spike Brier won't be statistically separable, so treat fold-level ties as "kill".