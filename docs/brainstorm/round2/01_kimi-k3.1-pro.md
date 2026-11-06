## 1. Thesis

My edge would be **low-variance, decision-optimal post-processing measured on exact origin × step predictions**, not another feature group. If the leading models are similar, the transferable gains come from blending diverse errors, avoiding validation-driven model selection, and tuning each submitted column for its actual loss. Treat the coherent mixture CDF as a useful candidate—not as a requirement that all eight columns must share one calibration.

## Evaluation protocol for everything below

Use two genuinely temporal experiments:

- **D — development:** origins 3 Aug–6 Sep, trained only on earlier data.
- **V — validation:** origins 7 Sep–4 Oct, trained only on earlier data.
- Purge at least 10 hours at each boundary. Features remain strictly as-of; fitting any blend or calibration rule uses only predictions available before the fold being scored.
- After selection, refit using out-of-fold predictions through 4 Oct and freeze everything before test generation.

Evaluate the **final processed columns**, preferably through `score.py::compute_metrics`, not intermediate model diagnostics. For uncertainty, use paired moving blocks of delivery days: `actuals_validation.csv` has only **2,688 distinct quarter-hours** (`data_samples.md`, quality report), each repeated across many origins. Treating roughly 26,000 scored rows as independent will severely overstate significance.

All gain ranges below are ☐ judgement estimates relative to the best single round-1 core model, not measurements.

---

## 2. Top five ideas, ranked by expected points per hour

### 1. Replace per-column source selection with small simplex stacks

**What.** Cache one row per `(forecast_origin_utc, step)` for every candidate: direct gap model, mixture CDF, fundamentals-only model, full-state model, and simple anchors. For each scored output, fit a constrained convex blend:

```python
# Two candidates; fit w only on earlier OOF predictions.
ws = np.linspace(0, 1, 41)
loss = {
    w: np.mean(np.abs(d.y - (w * d.p50_mix + (1 - w) * d.p50_direct)))
    for w in ws
}
w_star = min(loss, key=loss.get)
```

Use the same grid for p10/p90 pinball and probability Brier scores. Start globally; permit at most the bands `1–4 / 5–12 / 13–24 / 25–40` when the weights are stable across D and V. Blend first, then apply any calibration, then enforce validity and score.

This exploits a mathematical fact: **MAE, pinball loss and Brier score are convex in the submitted value**. Consequently, a blend cannot be worse than the *average* candidate loss, and with diverse errors it can beat both candidates. Model averaging is therefore safer than selecting a winner on one volatile month.

Importantly:

- Do **not** average the up- and down-conditional medians and call that the mixture median. Invert the mixture CDF, or use the direct p50 candidate.
- The direction probability used inside the price CDF need not equal submitted `p_up`. Calibration optimal for direction Brier may be wrong for price quantiles; maintain separate `pi_price` and `p_up_submission`.

**Evidence.** `score.py` implements the four losses independently; README §6 and `criterion_points()` contain no reward for cross-column coherence. Round 1 already plans per-column selection; blending is the lower-variance extension.

**Metrics and rough size.** ☐ MAE 0.3–1.0%, pinball 0.5–2%, Briers 0.5–3%; medium-low confidence, but cheap and downside-protected.

**Cost.** 3–4 person-hours once OOF predictions exist.

**Leak traps.** Blend weights must be fitted on earlier OOF rows, never on the fold used to report the gain. Do not include test-period predictions when estimating feature scaling or weights.

**Go/no-go.** Adopt a blend only if it beats both endpoints on D and V for the relevant metric. Otherwise ship the simpler global model or constant anchor. Reject per-band weights if their signs or optimal endpoints flip between folds.

---

### 2. Use Brier-optimal shrinkage toward a recent prior, not flexible isotonic by default

**What.** For each probability family, test:

\[
p'=(1-\lambda)p_{\mathrm{raw}}+\lambda\pi_{\mathrm{recent}},
\qquad 0\leq\lambda\leq1 .
\]

Fit `lambda` by Brier score on earlier OOF predictions. Estimate `pi_recent` using only pre-fold labels; test one or two prespecified recent windows rather than searching many. Apply separately to:

- `p_up`, then convert with constant `p_none`;
- `p_spike_high`;
- `p_spike_low`.

A slightly richer alternative is one global temperature plus intercept on logits, still fitted for **Brier**, not log loss. Avoid independent isotonic maps per horizon band unless event counts are substantial.

For direction, use the simple binary decomposition:

```text
p_none = small pre-fold empirical constant
p_up   = (1 - p_none) * calibrated_up_probability
p_down = 1 - p_none - p_up
```

Clip only after calibration, renormalise direction, and score the result. There is little justification for fitting a flexible three-class model for a class occurring around 0.17% of quarter-hours.

**Evidence.** `PLAN.md` finding 9 reports material base-rate movement: spike shares 9.0%/7.3% in training versus 12.1%/13.0% in validation, and up share falling to 25% on 1–4 Oct. Flexible calibration fitted to September is therefore a drift risk. The three-class Brier in `score.py` rewards calibrated probabilities, not confident classifications.

**Metrics and rough size.** ☐ 1–4% reduction in spike/direction Brier where raw models are overconfident or stale; medium confidence on sign, low on magnitude.

**Cost.** 1.5–2 hours.

**Leak traps.** `pi_recent` must be computed independently inside each temporal fold. No test-period intercept or probability recalibration unless the organisers explicitly approve it.

**Go/no-go.** Require lower final Brier on both D and V and no materially worse late-September/October slice. If `lambda` is unstable, use the global unshrunk model; do not choose a window from the best-looking validation result.

---

### 3. Train direct spike probabilities; use the mixture tail as a feature, not a constraint

**What.** Train two binary candidates using the exact labels:

```python
high = (df.imbalance_price > df.spot_price + 50).astype(int)
low  = (df.imbalance_price < df.spot_price - 50).astype(int)
```

Use origin × step features so horizon-dependent uncertainty is represented. Include the mixture’s tail probability, `pi_price`, recent state and net-position features. Do **not** use balanced class weights or `scale_pos_weight` when the desired output is a probability.

Compare three candidates for each of high and low:

1. Direct classifier.
2. Mixture-CDF tail probability.
3. Convex blend of the two, followed by the shrinkage in idea 2.

The scorer rewards no extra points for enforcing `p_spike_high <= p_up` or agreement with p90. Only validity sums matter. Direct classifiers also learn the rare off-direction events instead of structurally assigning them nearly zero probability.

**Evidence.** The strict definitions are in `score.py::compute_metrics`; exceptional prices carry **20 points**, equal to calibration. The round-2 facts report 43% of directional prices within ±0.5 €/MWh of the relevant mFRR marginal and only 7 high/18 low off-direction spikes. That supports conditional tails as useful information, but not as an inflexible output rule.

**Metrics and rough size.** ☐ 2–6% spike-Brier improvement over an uncalibrated quantile-grid tail; low-medium confidence because events are concentrated in a few days.

**Cost.** 2–3 hours.

**Leak traps.** Spike labels use the delivery quarter’s own spot price, already known at the origin, and its actual imbalance price only as a training label. Preserve the strict `>` and `<` comparisons.

**Go/no-go.** Choose direct, mixture or blend separately for high and low only when it wins on both folds. A gain produced by one September spike day is insufficient; inspect delivery-day block contributions.

---

### 4. Add a two-parameter, uncertainty-conditioned interval-width correction

**What.** Go beyond a constant per-band conformal offset, but keep the model tiny. For each side and horizon band, adjust widths around the chosen p50:

\[
p10'=p50-s_{10}(u)(p50-p10),\qquad
p90'=p50+s_{90}(u)(p90-p50),
\]

where

\[
s_q(u)=\exp(a_q+b_q u)
\]

and `u` is **one** predeclared uncertainty signal, such as standardised direct-versus-mixture disagreement or `abs(pi_price - 0.5)`. Fit `a_q,b_q` to minimise the corresponding pinball loss on earlier OOF rows. Shrink `b_q` toward zero, or drop it unless stable.

If this is too costly, the mandatory simpler version remains: additive correction equal to the empirical q-quantile of `y - raw_quantile`, with p50 corrected by the median residual. Do not optimise interval width to hit exactly 80% coverage.

**Evidence.** Pinball loss is the scored objective in `score.py::pinball`; coverage is explicitly only supporting information. Mixture and direct models will disagree most where regime or direction is uncertain, providing a potential conditional-width signal.

**Metrics and rough size.** ☐ Additional 0.5–2% pinball reduction beyond constant per-band corrections; low-medium confidence.

**Cost.** 2–3 hours.

**Leak traps.** Disagreement features must be computed from predictions available at that origin. Do not fit dozens of direction × wind × horizon cells on four weeks of data.

**Go/no-go.** Keep `b_q` only if the conditional rule beats the constant correction on both D and V. Otherwise retain the constant correction; if that also fails, submit raw blended quantiles.

---

### 5. Test causal averaging across successive forecast origins

**What.** At origin `t`, a previous forecast for the same delivery quarter is legitimately available. For a selected output:

\[
z_{\mathrm{final}}(t,d)=(1-a)z(t,d)+a z(t-1h,d).
\]

The older prediction simply has a step index four greater. Fit one small `a`, initially only for long-horizon probabilities and quantiles where successive origins share almost all day-ahead information. This can reduce model jitter without using future information.

Do not confuse this with smoothing across the 40 delivery steps. Direction runs are short—median down/up runs of 3/2 quarters—so HMM-like temporal smoothing can erase genuine transitions.

**Evidence.** Brier and pinball convexity favours variance reduction. Conversely, the measured direction decay and short runs limit how much stale predictions should contribute; this is why it is a small experiment, not a pillar.

**Metrics and rough size.** ☐ 0.5–2% probability-metric improvement and below 1% on price metrics; low confidence.

**Cost.** 1.5–2 hours using cached sequential predictions.

**Leak traps.** Generate predictions strictly in origin order. Never average with a later origin, and do not recursively smooth in a way that accidentally imports a revised future model state.

**Go/no-go.** Adopt only for outputs where the same positive gain appears on D and V. Otherwise delete it; a zero-weight result is a perfectly acceptable outcome.

---

## 3. What to change or drop in the round-1 core

- **Drop “one coherent distribution for all eight columns” as an objective.** It is a useful model, but the scorer has four independent objectives. Price-CDF direction probabilities, submitted direction probabilities and spike probabilities may need different calibration.
- **Replace per-column winner selection with blend-versus-endpoints selection.** Forty independent per-step choices would be validation mining. Use global weights or four broad bands with shrinkage.
- **Keep p50 explicitly median-oriented.** The mean of two conditional prices is not the median of a bimodal mixture. Likewise, do not let quantile-crossing repair silently replace a strong p50; preserve it where possible and score the final validity projection.
- **Do not chase 80% coverage.** Correct p10 and p90 separately for pinball loss; coverage may remain instrumentally useful but is not the target.
- **Timebox additional nowcast work using the actual row weights.** The supplied lag experiment improves step-1 MAE from 43.8 to 26.4, a 17.4 €/MWh gain. Even perfectly realising that gain at step 1 alone changes overall MAE by only **17.4/40 = 0.435 €/MWh**. Valuable, but not worth endangering the whole pipeline.
- Under relative scoring, while between best and baseline, a metric improvement `δ` earns approximately `weight × δ / (B − best)`. Since `best` is unknown, prioritise robust improvements with a credible chance of leading rather than promising precise points. Calibration and spikes total 40 points; direction totals only 10, so direction work should be strongly timeboxed.

## 4. Three quick package-data checks for the top idea

1. **Does origin × step weighting change model rankings?**

   Merge candidates with validation actuals and compare ordinary scoring with inverse-repetition weighting:

   ```python
   n = pred.groupby(["model", "delivery_start_utc"])["step"].transform("size")
   pred["unique_qh_weight"] = 1 / n
   # Compare weighted and unweighted MAE/pinball/Brier by model.
   ```

   If rankings differ, all subsequent selection must use exact origin × step rows.

2. **Is there real blend headroom and error diversity?**

   For direct and mixture p50, compute residual correlation overall and by step band, then run the 41-point weight grid on D. Evaluate D’s chosen weight unchanged on V. Repeat for p10/p90 pinball. Kill per-band blending if optima jump between 0 and 1 or V favours an endpoint.

3. **Is the apparent gain just day-level selection noise?**

   Add `delivery_day = delivery_start_utc.dt.floor("D")` and calculate paired candidate loss differences by day. Recompute the chosen source/weight by week and by 3–7-day moving blocks. If the winner changes across weeks, or the mean gain is smaller than block variability, select the simpler global configuration rather than trusting the full-validation optimum.

These checks require no external data and will quickly show whether stacking offers transferable gains or merely another way to overfit September.