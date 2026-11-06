# 1. Thesis

Submit a **generative mixture model of the price-formation rule**, not three regression outputs: a direction classifier (up/down/none) feeding direction-conditional gap distributions, assembled into one per-row predictive CDF from which all eight scored columns are read off (point mass at gap = 0 for "none"; VWAP-damped tails). Second, make the system **drift-immune by running the test month as a live simulation**: every origin gets trailing-state features (realised gap quantiles, direction share, our own residual pinball) computed only from data usable at that origin — no retraining on test, no leakage grey zone. The crowd's three independent LightGBM quantile models cannot encode the mechanical rule, will bleed pinball on the mass at gap ≈ 0, and will be mis-scaled in October's regime (Sep σ=141 vs Jul 25; validation spike shares already flipped 9.0/7.3 → 12.1/13.0). Because scoring is winner-take-all per metric (clip at 1), we concentrate on being #1 on Calibration + Spikes (40 pts, thin competition) while holding a floor under MAE. The price-rule story plus disciplined availability handling is also the strongest reasoning-chain narrative (20 jury points).

# 2. Method

**Targets.** Work in `gap = imbalance − spot` (spot known for all 40 steps per origin, verified). Training rows: every hourly origin Jun 1–Oct 4 × 40 steps (≈120k rows), features built strictly under the availability rule.

**Stage A — direction model.** One LightGBM multiclass (3 classes; effectively binary since none = 0.17 %), log-loss, step index as feature. Outputs `p_up, p_down, p_none`. Recalibrate with isotonic per horizon band (steps 1–4 / 5–12 / 13–24 / 25–40) fitted via blocked time-series CV inside training; final fit uses all data through 4 Oct with exponential recency weighting (half-life ~6–8 wks, tuned on the Aug→Sep stress test). Keep `p_none` near its tiny empirical rate — non-zero is a Brier freebie.

**Stage B — direction-conditional gap distributions.** Two LightGBM quantile model families: one trained only on up-regulated quarters (`gap | up`, support roughly [0, +3800] with ~10 % slightly negative — this is real structure, not noise), one on down quarters (`gap | down`, support (−∞, ~0]). Fit a quantile grid q ∈ {0.02, 0.05, 0.1, …, 0.95, 0.98} (~14 levels each; 28 models total, cheap). Monotonicity enforced by sorting the predicted quantile ladder.

**Assembly — the per-row CDF.** For each (origin, step): `F(z) = p_none·1{z≥0} + p_up·F_up(z) + p_down·F_down(z)`, with F_up/F_down piecewise-linear in (z, F) space over the predicted ladder.
- `p10/p50/p90` = z solving F(z) ∈ {0.1, 0.5, 0.9} (monotone by construction → no crossing, ever).
- `p_spike_high = 1 − F(50)`, `p_spike_low = F(−50)`. These automatically include the rare off-direction spikes (7/18 observed cases) via the conditional tails, and automatically satisfy `p_spike_high + p_spike_low ≤ 1`.
- Consistency is structural, e.g. `p90 < 50 ⇒ p_spike_high ≤ 0.1` — independent spike classifiers (the crowd's plan) violate this regularly, and each violation costs Brier.

**Calibration for Brier, not for coverage.** After assembly, isotonic-recalibrate `p_spike_high/low` and direction probs per horizon band on validation-fold predictions, shrunk 50/50 toward the raw values (validation is only ~4 weeks; overconfident isotonic → test-month blow-up). Pinball-side: additive per-band offsets to p10/p90 fitted to minimise validation pinball, same 50 % shrinkage. We optimise pinball (sharpness), not nominal coverage — the metric rewards it.

**Features.** (a) Known-for-all-steps: spot level, |Δspot| and spot ramp shape around target quarter (fact 5), hour-of-day × the 18–21 h evening block (fact 6), weekday/holiday, DA wind/consumption/solar forecasts with wind quintile interactions (fact 4), solar downweighted for Oct (fact 9). (b) Recent-state (decay-weighted by step): last usable gap, shrunk-persistence gap, last usable direction with horizon-dependent agreement (0.70@lag5 → 0.57@lag44 — fit this blending, don't hard-code), mFRR up/down marginal − spot spreads (last usable), mFRR activated volumes, aFRR prices where present, cross-border flows, SE1/SE3/EE imbalance at lag 9 (weak but Nordic-common mFRR marginal). (c) **Trailing-state features refreshed per origin** (the drift defence): realised gap P10/P50/P90 over trailing 48 h and 7 d at usable lags, trailing up-share, trailing |gap| mean per hour-of-day, trailing spike rates, and our own per-band residual pinball from predictions already issued at earlier origins (deterministic function of allowed data).

**Final fit protocol.** Tune and calibrate with end = 4 Sep, validate on 7 Sep–4 Oct (organiser window); then retrain everything through 4 Oct with frozen hyperparameters and CV-fitted calibration maps.

# 3. Expected gain per score component

Estimates vs a *well-tuned* LightGBM-on-gap crowd-proxy on validation-scale numbers; marked confidence is honest.

| Metric (weight) | Crowd proxy (est.) | Us (est.) | Δ | Confidence |
|---|---|---|---|---|
| MAE of p50 (30) | ~44–46 (spot anchor alone: 46.5) | ~43–44.5 | −2–4 % | Medium that we ≥ tie; low that we're clearly #1 — crowded metric |
| Pinball p10/p90 (20) | ~19–20 (static quantiles under drift) | ~17.5–18.5 | −6–10 % | Medium-high: mixture tails + mass-at-0 + trailing-state widths |
| Spike Brier (20) | ~0.090–0.095 | ~0.082–0.088 | −5–10 % | Medium-high: CDF-coherent spikes + Brier-tuned isotonic |
| Direction Brier (10) | ~0.435 | ~0.428–0.435 | ~0–2 % | Low stakes; cheap calibration decides a coin-flip |

The dominant term in our favour isn't visible on validation: October regime shift. A static crowd model degrades on test while our trailing-state features and recency weighting adapt. We proxy this with a **stress test** (train Jun–Aug → score Sep) and optimise `min(validation, stress)`, not the mean. Verification needed before we promise anything: reproduce the four baseline numbers (66.20 / 24.18 / 0.1132 / 0.4509) exactly with the local scorer.

# 4. Data

**Open-Meteo Single Runs (yes, gated on a 1-h fetch test).** ECMWF IFS inits 00/06/12/18 UTC; honest availability = init + ~6 h (verify empirically with the archive's timestamping; never use an init whose availability post-dates the origin). Fetch for every training day and the test window: hub-height wind speed (~100–120 m, exact variable names to verify) on a coarse grid of ~6–8 points over the Ostrobothnia capacity cluster, plus surface wind as fallback. Features: (i) **init-to-init disagreement** for the target quarter (a poor-man's ensemble → conditional width); (ii) **revision vs the Fingrid DA wind forecast** (our usable later run minus the DA forecast → median shift and tail widening); (iii) an icing-risk proxy from temperature at hub height (unverified, low priority). Traps: do not touch the Historical Forecast API; do not use "latest run" convenience endpoints for training rows; pin exact init times in the feature table.

**Fingrid Open Data real-time (yes, cheap).** 3-min actual wind production, nuclear, total production/consumption. Feature: realised wind minus DA wind forecast (the current forecast-error state, informative for roughly steps 1–8). Honest delay: assume 30 min until organisers confirm (the package's own production series use 30 min — take the conservative analog). Trap: real-time series can be revised; if the API offers point-in-time snapshots, use them, else log the assumed delay and buffer it.

**Skip (negative expected value in 34 h):** Nord Pool UMM (versioned, correct, but nuclear/CSP outages are rare-event features and 673 origins give no statistical power to fit them — last-priority nicety at best), intraday prices (not in package, licence friction), Elering EE balance (weak measured correlation), FMI observations (dominated by NWP revisions), per-type production (unavailable).

**Already in package, underused:** mFRR marginal prices and aFRR prices — verification task: reconstruct the post-June VWAP rule on training data (activated mFRR + aFRR demand same direction ⇒ price = VWAP). If it reconstructs on >80 % of qualifying quarters, engineer the **damping feature** (typical price − mFRR-marginal spread given joint activation) — nobody else will have this, and it feeds straight into the reasoning-chain score. If reconstruction fails, use raw mFRR marginal − spot spreads as plain features and move on.

# 5. Experiment plan (~34 h, 5 people)

Ordered by expected value per hour. Slots overlap across people; the numbers are start–end hours from now.

0. **Hrs 0–3 (2 ppl): scaffolding and leakage spine.** Row-join with hard asserts (`first_usable_origin_utc ≤ t` on every joined row; external series get explicit buffer), DST unit test on 25–26 Oct (local hour-mapping, 25-hour day), submission validator (monotonicity, sums, no NaNs, ≥ baseline margin on validation). Reproduce all four baseline metrics exactly. **No-go:** any baseline mismatch → stop, our scoring understanding is wrong.
1. **Hrs 2–7 (2 ppl): crowd-proxy LightGBM-on-gap** = the bar we must beat per metric. **No-go:** MAE > 46.5 → debug features before anything else.
2. **Hrs 4–12 (2 ppl): mixture-CDF v1** (Stage A+B+assembly, recency weighting). **Go:** pinball ≥3 % better than proxy on validation *and* on the Aug→Sep stress window, with MAE no more than 1 % worse. If it fails, ship improved proxy + our calibration stack instead.
3. **Hrs 4–14 (1 pers): external data.** Hour 0: fetch test (10 training days of IFS runs). If archive incomplete or >30 min/day → drop weather, keep Fingrid RT wind-error only. **Go:** revision/spread feature in top-10 importance *and* ≥1.5 % pinball gain on validation+stress; else drop without regret.
4. **Hrs 10–16 (1 pers): mechanics** — VWAP reconstruction + damping feature + mFRR/aFRR features. **Go** on the 80 % reconstruction rule above.
5. **Hrs 12–18 (1 pers): per-metric calibration** (band-wise isotonic + shrunk pinball offsets). **Go:** stress-window Brier and pinball don't degrade vs raw (protects against validation overfit).
6. **Hrs 16–22 (1–2 ppl): final blend/selection** choosing config by `min(validation, stress)`; retrain through 4 Oct; full sequential test-run generation; validator.
7. **Hrs 8–34 (1 pers, ~60 %): report, slides, video, dashboard.** The reasoning chain is 20 jury points plus Level 2 is 20 % of total — under-investing here is the classic losing move. Log per-batch `top_drivers` attributions from the fitted models; they make the reasoning story concrete.
8. **Hrs 22–34 (all):** dry-run the organiser scoring script, sanity-compare our validation metrics vs baseline floors, freeze, submit, polish talk. Keep 3 h real buffer.

**Cut order if time runs short:** weather ensemble (3) → VWAP damping (4) → blend tuning (6). **Never cut:** scaffolding/leakage tests (0), calibration sanity (5), submission validation (8) — a leak or malformed file zeros 34 h of work.

# 6. The idea others won't think of

1. **The submission is one distribution, not eight numbers.** Reading every column off a single per-row CDF that embeds the legal price-formation rule (zero mass for "none", damped-mFRR tails, support asymmetries) gives coherence the crowd can't match: their independent spike classifiers routinely contradict their own p90, and their quantile models smear the gap≈0 mass and pay for it in pinball. It's also the only approach that turns "how the price is formed" into submitted numbers — the jury-visible inventiveness is computational, not rhetorical.
2. **Run October as a live system inside a static model.** Most teams will batch-predict the 673 origins with fixed features. We generate the file sequentially, origin by origin, feeding trailing realised gap quantiles, trailing direction share (the up-share fell 35 % → 25 % by 4 Oct — this signal is free at test time), and our own residual pinball into a model that learned to use them on training data. It's fully legal (features only, availability-respecting), it's the only drift defence that works on a regime the training set has never seen, and it sidesteps the "is adaptive conformal training on test?" grey zone entirely. (If organisers explicitly bless adaptive conformal, bolt it on in <2 h as a bonus.)

# 7. Risks and what to verify first

**Verify in the first 3 hours, before committing:**
- *Price-rule checks:* none-direction ⇒ gap exactly 0 (matches 0.17 % claim); up-gaps' P10 ≈ 0 with ~10 % negative (drives CDF assembly); VWAP reconstruction rate (gates the damping feature).
- *Baseline reproduction* of all four metrics with the local scorer — if we can't reproduce 66.20/24.18/0.1132/0.4509, every estimate above is built on sand.
- *DST integrity:* quarter counts and local-hour mapping across 25–26 Oct 2026; this bug will silently hit several teams, and must not hit us.
- *Open-Meteo archive:* confirm Jun–Oct 2026 IFS inits are fetchable now at acceptable speed, and pin availability delays empirically (or the whole weather workstream is dropped by lunch).
- *Trailing-feature coverage:* no NaN deserts early in training; windows bounded so step-1 rows aren't degenerate.

**Main failure modes:**
1. **Validation ≠ test regime** (the big one): validation sits in Sep, test in cooling, windier October. Anything tuned hard to validation — isotonic maps, pinball offsets, con­formal widths — is suspect; hence 50 % shrinkage, the Aug→Sep stress test as the real decision metric, and `min()`-selection. Residual risk: October could still be wilder than anything since June; trailing-state features are the only mitigation, and they only help if past-within-test informs future-within-test (true for regime persistence, false for single shocks).
2. **Overclaim from small samples:** spike Brier differences of ~0.005 are within validation noise; we will not re-architect chasing them. Decisions between close configs go to the stress window.
3. **Leakage via subtleties:** publication-rounding of external series, revised real-time values, accidentally-valid Open-Meteo inits. Mitigation: single choke-point availability assert, conservative buffers, and a written data-cutoff log per batch (`data_cutoff_utc` column doubles as our audit trail).
4. **Adaptive-calibration legality:** we assumed "features under the availability rule" covers trailing statistics of realised targets; our design deliberately needs nothing stronger. If organisers rule otherwise, nothing changes — we never retrain on test.
5. **Winner-take-all variance:** we may simply not be #1 on MAE; the plan accepts that and buys its edge where the field is weakest (calibration, spikes, reasoning). The irreducible risk is another team having the same idea — the mix of price-rule fidelity plus live-simulation discipline is, in our assessment, the least likely thing five tired teams will independently build this weekend.