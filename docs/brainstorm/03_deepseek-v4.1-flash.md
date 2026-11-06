## 1. Thesis
We will not treat the imbalance price as one continuous gap regression. We will model it as a **mixture over the three mFRR directions**, with direction probabilities driven by a physical **wind-forecast-error nowcast** and the latest NWP revision, and with **direction-conditional gap quantiles**. All submitted columns will be derived from that single mixture CDF, so `p10/p50/p90`, direction probabilities and spike probabilities are mutually consistent. We will also sequence-smooth direction probabilities across the 40 steps, because direction is strongly autocorrelated and step-independent classifiers are noisy. The edge is structural correctness plus better tails/calibration, not just more LightGBM features.

## 2. Method

**Targets.** Work in UTC. For each row: `gap = imbalance_price - spot`. For direction, use Fingrid 369. Train only on available history; test features only via the availability join.

**1. Direction model.**
- Train a LightGBM multiclass model for `up/down/none` with `objective='multiclass'`, sample weights with ~30-day half-life. If `none` is <0.5 % in validation, fall back to binary up/down plus a small constant `p_none` (e.g. 0.002–0.005), tuned on validation.
- Features: spot level/ramp/daily shape; Fingrid DA wind/consumption/solar forecasts; hour/weekday/holiday/DST/step; last usable direction, mFRR up/down MW, marginal prices, aFRR indicator/price spread; real-time wind error and frequency features below; Open-Meteo wind revision features below.
- Calibrate on out-of-fold (OOF) predictions: temperature scaling for multiclass, or isotonic per class with clipping. Validate with three-class Brier, not logloss.
- **Sequence smoothing:** estimate a 3×3 transition matrix from training. For each origin, treat the per-step model probabilities as emissions and run forward-backward to get smoothed marginals. Tune a blend weight `λ` on validation: `P_final = (1-λ)P_model + λP_HMM`. Use only if direction Brier improves.

**2. Direction-conditional gap models.**
- Train separate LightGBM quantile regressors on rows where the realised direction is up, and separately on down rows. Use `gap` directly, quantile grid `q = {0.05, 0.1, 0.25, 0.5, 0.75, 0.9, 0.95}`. That is ~14 models total, with `step` as a feature.
- For `none`, gap = 0 exactly.
- At inference, apply both conditional models to every row. Build the mixture CDF:
  `F(x) = p_none·1(spot ≤ x) + p_up·F_up(x-spot) + p_down·F_down(x-spot)`.
  Interpolate `F_up`/`F_down` from the predicted quantiles.
- `p10`, `p50`, `p90` = numerical inverses of `F` at 0.1, 0.5, 0.9. Enforce `p10 ≤ p50 ≤ p90`.
- Spike probabilities from the same CDF:
  `p_spike_high = p_up · (1 - F_up(50))`,
  `p_spike_low = p_down · F_down(-50)`.
  Optionally apply a simple multiplicative tail correction fitted on OOF validation, but keep `p_spike_high ≤ p_up`, `p_spike_low ≤ p_down`, and sum ≤ 1.

**3. Calibration.**
- Split OOF residuals by step band (`1–4`, `5–12`, `13–24`, `25–40`), predicted direction, and predicted wind regime (e.g. low/mid/high wind-error quintile).
- Fit separate multiplicative half-width scalars for lower and upper intervals to minimise pinball loss on OOF. Apply to test. This is conditional conformal calibration rather than one global per-step factor.
- Use recency weighting in training; do not fit scalers on test features.

**Key extra features.**
- **Wind revision:** latest available Open-Meteo NWP 100 m wind (ECMWF IFS and ICON) minus Fingrid DA wind forecast (dataset 246) for each step, at 2–3 Ostrobothnian points; also ensemble/model spread and revision ramp.
- **Real-time wind error:** latest Fingrid real-time wind production minus the DA wind forecast for the same quarter; trend over the last 4 usable quarters; decay this error with horizon.
- **Frequency:** latest 3-min frequency deviation from 50 Hz, 15-min mean, and trend; interaction with last mFRR direction.
- **mFRR/aFRR state:** last marginal prices, activated MW, price spread, time since activation, aFRR activation indicator and aFRR-vs-mFRR price spread.

**Why this beats LGBM-on-gap.** A single gap quantile model blurs the bimodal up/down distribution. The mixture respects the price formula, widens intervals when direction is uncertain, and makes spikes a tail of the same distribution rather than an independent classifier.

## 3. Expected gain per score component

These are rough, honest guesses; validation decides.

| Component | What improves | Rough vs well-tuned LGBM-on-gap | Confidence |
|---|---|---|---|
| Accuracy (MAE of p50) | Mixture median captures bimodality; direction smoothing; wind-error nowcast | 2–6 % lower MAE, e.g. 35 → 33–34 | Medium |
| Calibration (pinball p10/p90) | Mixture CDF + conditional conformal by direction/wind/step | 5–12 % lower pinball, e.g. 19 → 17–18; coverage closer to 0.8 | Medium-high |
| Exceptional prices (Brier) | Spikes derived as `P(direction)·P(tail|direction)`; wind-error and frequency features | 5–10 % lower Brier, e.g. 0.085 → 0.077–0.081 | Medium |
| Direction (Brier) | Brier calibration, sequence smoothing, physical wind/frequency features | 3–8 % lower Brier, e.g. 0.37 → 0.34–0.36 | Medium |

The biggest risk is that a strong LGBM-on-gap already captures most of this. The mixture and smoothing should still help calibration and tails, which are 40 of the 80 automatic points.

## 4. Data

**Add:**
- **Open-Meteo Single Runs API** for ECMWF IFS and ICON, 100 m wind at 2–3 west-coast points. Honest delay: use 7 h for ECMWF IFS and 4 h for ICON unless docs/organisers confirm otherwise. At origin `t`, only use runs with `init + delay ≤ t`. Fetch history run-by-run in parallel and cache; do not use the Historical Forecast API.
- **Fingrid Open Data real-time series**: wind production, nuclear, hydro, total production/consumption, frequency. Assume 30 min delay unless organisers confirm 15 min. Use only timestamps `≤ t - 30 min`. This is fresher than the package’s 45-min lag and gives a physical imbalance nowcast.
- **Nord Pool UMM** (optional): Finnish outages published after D-1 14:00 and before `t`. Use publication timestamp, not event start. Add MW, fuel, direction, and time since publication. Skip if API access is slow.

**Skip unless time:** FMI observations, Elering, detailed icing proxies. They are unlikely to pay off versus the wind/frequency work.

**Leakage traps:** run initialisation plus availability delay; publication timestamps for UMM; no test actuals or test-fitted scalers; spot licence — never send spot data to external APIs. Verify the real-time Fingrid delay with organisers in writing.

## 5. Experiment plan

Ordered by expected value/hour, for 5 people over ~34 h.

1. **0–3 h: validation harness and leakage audit.** Reproduce baseline and scoring script. Build availability join for every series. Check that no feature timestamp exceeds `t`. Go/no-go: all joins pass; baseline numbers match.
2. **3–9 h: mixture model.** Direction classifier + conditional gap quantiles + CDF inversion. Compare against direct LGBM-on-gap on validation. Go/no-go: mixture improves MAE by ≥1 % and pinball by ≥2 %; otherwise keep direct model for p50 but use mixture for spikes/direction.
3. **9–15 h: wind revision features.** Fetch Open-Meteo Single Runs, compute latest NWP minus Fingrid DA wind. Add to direction and gap models. Go/no-go: direction Brier improves by ≥0.01 absolute or spike Brier by ≥0.003.
4. **15–20 h: real-time wind error + frequency nowcast.** Fetch Fingrid real-time series, compute latest error/trend/frequency. Go/no-go: MAE at steps 1–8 improves by ≥2 %.
5. **20–25 h: conditional conformal calibration.** Fit half-width scalars by step band, direction, wind regime. Go/no-go: pinball improves by ≥1 % over global per-step conformal.
6. **25–30 h: sequence smoothing.** HMM forward-backward on direction probabilities. Go/no-go: direction Brier improves by ≥0.005 absolute.
7. **30–34 h: spike calibration, report, submission.** Sanity checks: monotonicity, probabilities sum to 1, no NaNs, DST handling.

**Cut first:** UMM, icing proxy, aFRR/mFRR full mixture, sequence smoothing if it does not validate. Do not cut the mixture or calibration.

## 6. The idea others won't think of

**A latent net-imbalance state from frequency + real-time wind error, projected forward with a calibrated decay.** Frequency deviation is a direct physical signal of Nordic imbalance, and real-time wind minus the DA wind forecast is a direct signal of the Finnish forecast error already materialising. Combine them into a scalar “imbalance nowcast” at the latest usable quarter, then let LightGBM learn how that state decays over steps 1–40. Most teams will use last gap and NWP revisions, but not a physical nowcast of the current imbalance state.

**A second non-obvious idea:** derive spike probabilities as `P(direction) × P(tail | direction)` from the same conditional CDF used for p10/p90. This enforces that high spikes only occur in up-regulation and low spikes only in down-regulation, which matches the data (only 7 high spikes outside up and 18 low outside down out of ~12,000 quarters). It also prevents the common inconsistency where `p_spike_high` exceeds `p_up`.

## 7. Risks and what to verify first

- **Open-Meteo Single Runs API throughput.** Verify you can fetch enough runs for 1 Jun–4 Oct in <6 h. If not, use only ECMWF IFS 00Z/12Z and two points.
- **Real-time Fingrid publication delay.** If organisers say 30 min, use 30 min; if unsure, use 45 min. A leak means zero.
- **Mixture inversion instability.** Check quantile crossing and CDF monotonicity. If unstable, fall back to direct quantile models for p10/p90 and use the mixture only for spikes/direction.
- **Validation shift.** Validation is 7 Sep–4 Oct, including a very volatile September; test is October. Use recency weighting and conditional calibration, but do not overfit to validation strata.
- **Weak direction model.** If direction Brier does not beat a simple Markov/persistence baseline, the mixture will not pay off. Run that baseline first.
- **Quick data checks before committing:** verify `first_usable_origin_utc` joins; verify Open-Meteo run init timestamps; verify Fingrid real-time timestamp delay; check direction autocorrelation and spike-direction contingency; compare mixture vs direct LGBM on the validation scorer.