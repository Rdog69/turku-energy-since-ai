## 1. Thesis

My bet is **driver-first, regime-conditional forecasting**, not a larger booster: forecast realised wind-minus-day-ahead-wind error using strictly as-of measurements and archived NWP runs, then feed that into separate up/down gap distributions. A single gap-LGBM tends to blur the discontinuous direction mixture and average away the recent-state signal as horizon grows. I would explicitly blend recent-state and fundamentals-only models by horizon, with weights learned out of fold. Finally, I would select and calibrate each submitted column for its own scored loss rather than forcing one model to win everywhere. The likely edge is a few percent, not a breakthrough; every addition needs a validation gate and a simple fallback.

## 2. Method

**Common setup.** Build origin-based training rows in UTC, with every feature’s `first_usable_origin_utc <= origin`. Purge ten hours around temporal fold boundaries. Keep a well-tuned direct gap-LGBM as the challenger for every output.

**1. Predict the physical driver.** For historical quarter \(q\), define:

\[
e_q=\text{realised FI wind}_q-\text{Fingrid DA wind forecast}_q .
\]

This is an auxiliary **label**, never a future feature. Train horizon-aware models for signed \(e_q\), absolute error, and preferably q10/q50/q90 of \(e_q\), using:

- Latest eligible NWP run’s west-coast wind forecast for \(q\).
- Same-valid-time revision versus older NWP runs.
- Latest usable realised wind errors, their EWMA, slope and recent ramp.
- DA wind level/ramp, consumption, solar, spot ramps, calendar and horizon.

Generate out-of-fold auxiliary predictions for training the price models. At inference, everything is computable at the origin. Signed predicted error should help direction; predicted absolute error and interval width should help spikes and quantile width. Verify the expected sign—more wind than forecast should generally favour down-regulation—rather than hard-coding it.

**2. Direction.** Train two binary up/down models:

- **Fundamentals:** DA forecasts, spot shape/ramps, calendar, auxiliary wind-error predictions.
- **Full state:** additionally recent direction/run length, gaps, mFRR prices/volumes, aFRR prices with missingness indicators, flows and measurements.

Combine their out-of-fold logits or probabilities with horizon-band weights, constraining recent-state weight to be non-increasing with horizon. This directly exploits the observed decay from 0.70 agreement at lag 5 to 0.57 at lag 44. Estimate a small rolling `p_none`, then set `p_up=(1-p_none)*r`, `p_down=(1-p_none)*(1-r)`. Calibrate on recent out-of-fold predictions using Platt/temperature scaling; select by three-class Brier, not log loss.

**3. Price quantiles.** Fit conditional quantile models for `gap | up` and `gap | down`, plus the direct unconditional gap models. About 17–19 quantiles per conditional model are enough to approximate each CDF; include the rare wrong-signed gaps rather than truncating at zero. Mix the conditional CDFs using the calibrated direction probabilities, with `p_none` mass at gap zero, and invert the mixture to obtain p10/p50/p90. Add known spot only after predicting the gap.

This is a structural approximation, **not** an exact reconstruction of the mFRR/aFRR volume-weighted price. Compare mixture p50 against direct-median p50 and a validation-weighted blend.

**4. Spikes.** Train conditional tail classifiers, for example `P(gap>50 | up)` and the small complementary probability under down, and similarly for low spikes. Combine them with direction probabilities. Also train direct all-row spike classifiers; retain whichever has better temporally out-of-fold Brier. Conditional models exploit the near-deterministic spike/direction relationship; direct models are the lower-variance fallback.

**5. Calibration and validity.** Use rolling recent calibration windows, testing 21/28/42 days and recency weighting. For each horizon band, correct a raw quantile by the empirical \(q\)-quantile of \(y-\hat y_q\): this directly reduces pinball loss, unlike merely chasing 80% coverage. Shrink band corrections toward the global correction. Finally sort p10/p50/p90, clip probabilities, renormalise direction, and enforce spike sum ≤1. Select columns separately by their own metric.

## 3. Expected gain per score component

These are **planning estimates, not measured results**, versus a strong direct gap-LGBM with conventional classifiers:

| Metric | Source of improvement | Plausible relative reduction | Confidence |
|---|---|---:|---|
| p50 MAE | Wind-error target, direction-conditional median, horizon stacking | **1–3%** | Medium-low |
| p10/p90 pinball | Conditional tails, wind-error uncertainty, recent pinball-optimal corrections | **3–7%** | Medium |
| Spike Brier | Direction gating, absolute-wind-error signal, recent probability calibration | **3–8%** | Low-medium; few events |
| Direction Brier | Fundamentals/state horizon bridge and calibration | **2–5%** | Medium |

The median may improve least because spot is already a strong anchor and distant errors are irreducible. Calibration and spikes offer more differentiation, but September’s exceptional volatility makes validation estimates noisy. Do not extrapolate these percentages into promised points: the best-team denominator is unknown.

## 4. Data

**Fingrid real-time wind — first priority.** Fetch quarter aggregates of realised wind for the full training period; optionally add nuclear and total production changes later. Join to the packaged DA wind forecast and construct recent forecast-error features without using Open-Meteo. Until organisers confirm otherwise, assume **30 minutes after measurement/quarter end**, then round publication up to the next hourly origin. Cache raw responses and record assumed publication timestamps. Check units, timezone, missing quarters and whether historical values can be revised.

**Open-Meteo Single Runs — second priority, in parallel.** Start with ECMWF 00/12 UTC runs at two or three Ostrobothnia/west-coast locations and wind speed at turbine-relevant height. Use only runs available by `init + a conservative seven-hour delay`, rounded up to an hourly origin, unless organisers approve a tighter reconstruction. Cache each run and construct same-valid-time revisions against older runs; never request a forecast origin later than the allowed run. Expand models/locations only after a measurable gain.

**Skip initially:** UMM parsing, FMI observations, Elering and additional neighbour prices. They have higher integration cost or weak demonstrated signal. Never use Historical Forecast/latest-version forecast archives. Keep licensed spot entirely local; send only coordinates and timestamps to external services.

## 5. Experiment plan

Evaluation should use the supplied validation period plus at least three rolling temporal folds, with weekly breakdowns. Suggested adoption gates: ≥1% improvement for MAE, pinball or direction Brier, ≥2% for spike Brier, and no severe degradation in late-September/October slices. These are safeguards against noise, not guarantees.

1. **Hours 0–3 — P1:** reproducible metrics, UTC/DST joins, availability assertions and a valid persistence submission. **P2:** strong direct-LGBM challenger. No external experiment starts without this.
2. **Hours 3–8 — P2/P3:** horizon-stacked direction model, conditional/direct spike comparison, recent probability and pinball calibration. Adopt each output independently; otherwise retain the challenger.
3. **Hours 3–10 — P4:** Fingrid wind history and latest-error features. Go/no-go: clean >95% usable coverage and ≥1% validation MAE or direction-Brier gain.
4. **Hours 6–14 — P4/P5:** Single Runs feasibility and revision matrix. If an auditable as-of history is not ready by hour 12–14, drop it rather than risk leakage. Otherwise build the auxiliary wind-error model and require incremental improvement beyond Fingrid-only features.
5. **Hours 10–18 — P2:** direction-conditional gap mixture. Require ≥1% MAE or ≥2% pinball improvement; otherwise use it only where it wins.
6. **Hours 18–25:** frozen ablation, recency choice, final refit using labels only through 4 October, and complete test generation. Test inputs must not influence fitting, scaling or calibration.
7. **Hours 25–34:** independent leak/code review, schema checks, report/dashboard/video and buffer. **P5** should document the economic reasoning chain throughout, not start at hour 25.

Cut first: UMM/FMI/Elering, extra weather models/locations, elaborate SHAP/dashboard work, then Open-Meteo if its gate fails. Never cut availability tests, a valid fallback submission or final local scoring.

## 6. The idea others won’t think of

**Predict wind forecast error as a target, not weather as just another feature.** Raw wind-speed revisions have a noisy, nonlinear relationship with price; the auxiliary MW-error target aligns learning with the actual Finnish driver and produces separate signed and uncertainty signals for direction, median and tails. It is also leakage-safe when its predictions are out of fold.

**Build an explicit bridge from nowcast to fundamentals.** Instead of hoping `step` learns this inside a tree, let recent mFRR/wind state dominate early horizons and smoothly hand over to DA fundamentals. The supplied direction-agreement decay is direct evidence that this transition exists.

## 7. Risks and what to verify first

- **Availability misunderstanding causes automatic zero.** Obtain written confirmation for Fingrid and Open-Meteo delays; assert cutoffs row by row and inspect maximum usable timestamps.
- **The auxiliary model leaks realised future wind.** Confirm realised error appears only as an auxiliary label or historically usable lag; price training receives only out-of-fold predictions.
- **DST/spot alignment silently corrupts labels.** Check quarter counts around 25 October, UTC uniqueness and that every target uses its own known spot.
- **Conditional models overfit sparse tails.** Inspect event counts by fold and week, compare against direct models, and avoid aggressive per-hour calibration.
- **Regime drift invalidates calibration.** Report June–July, August, September and 1–4 Oct separately; do not learn a linear “month trend” into winter.
- **Coverage looks better while pinball worsens.** Score the exact submitted columns after every correction.
- **Wind data adds nothing at longer horizons.** Inspect gains by horizon band; if benefits are confined to steps 1–8, retain the fundamentals-only model thereafter.