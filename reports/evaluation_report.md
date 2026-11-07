# Evaluation report: Finnish imbalance price forecast, 10 h ahead

Team entry for the Turku Energia challenge, Since AI 2026. Marks: ✔ checked in the data or code, ☐ assumption. `TODO(final)` marks text or numbers that will change before the 8 Nov 10:00 deadline.

> TODO(final): this draft uses the validation window 7 Sep – 4 Oct 2026 and the model `split_all`. Work in progress may change the numbers: a second validation fold (August), pooled calibration, real-time imbalance features (Fingrid 198/186, BRP plan error) and an ECMWF-vs-ICON spread feature. The final model and the test-run details are not chosen yet.

## 1. The problem and our framing

We forecast the Finnish imbalance price for 40 quarter-hours (10 h) from every full-hour origin. We also give an 80 % interval (P10, P50, P90), the probabilities of up- and down-regulation, and the probabilities of a spike (more than 50 €/MWh from spot).

**We forecast the gap to spot, not the price.** The imbalance price is the day-ahead spot price plus a jump up or down. Spot is known for all 40 steps at every origin (✔ PLAN finding 10, checked at every hourly origin 2 Jun – 1 Nov). Spot is a strong anchor: it already reflects gas, the weather outlook and the Nordic fleet. The gap measures what remains after using spot. It is a modelling target, not a pure causal measure of Finland's forecast error, because it also contains balancing-market rules, activation and pricing effects. This single choice gave the largest gain: on validation, a constant gap on top of spot reduced MAE by 33 % against the organisers' persistence baseline (finding 1).

## 2. Data and the availability rule

Data: the organisers' package (Fingrid, ENTSO-E, Nord Pool spot, calendar), plus two external sources we added: Fingrid real-time series and ECMWF weather-model runs from Open-Meteo. Full list with licences and delays: `SOURCES.md`.

**The rule:** at origin `t`, a row may be used only if `first_usable_origin_utc ≤ t`. Breaking it scores 0. We enforce it in one place and test it.

- Every feature is read through `SeriesIndex` lookups (`src/data/availability.py`): `value_at` returns a value only if its row is usable at that origin, and `latest` returns the newest usable row. No feature uses a fixed shift.
- **Truncation leakage test** (`tests/test_availability.py`): for sampled origins (edge cases such as data start, spot publication hours, the DST change, period boundaries, plus random hours), we build the features from the full data and again from data where every row with `first_usable_origin_utc > t` was deleted. The two must be identical. A feature that peeks at the future would change. The same test covers the weather features (runs not yet usable are removed).
- A second test compares the fast lookups with the slow reference filter (the organisers' `rows_available_at` logic). Further tests check that `data_cutoff_utc` is before the origin, that targets are never features, and that training rows were published before the training cut-off.
- Training: for the validation run we train only on rows whose targets were published before 7 Sep; for the test run, before 5 Oct.

**Delays we assumed for external data (all conservative, rounded up to the next full hour):**

| Source | Rule | Basis |
|---|---|---|
| Fingrid real-time (wind, nuclear, frequency, consumption) | quarter end + 30 min | The organisers' own delay for measured Fingrid data. Fingrid publishes every 1–3 min. ☐ |
| ECMWF IFS runs (Open-Meteo) | run start + 8 h | Measured about 7.1 h on 6 Nov. ☐ |

The Open-Meteo Historical Forecast API is not used, because it does not give the point-in-time run vintages our availability rule requires. Fingrid's updated forecasts (245, 241) are not used for the same reason. Data from before 1 Jun 2026 is fetched but **not used** until the organisers approve it. ☐

TODO(timestamp: one worked availability example). At a chosen origin, show the newest Fingrid quarter used (its end, its assumed publication time and its first usable origin after rounding up to the full hour), and the ECMWF run used (its initialisation time and the selection rule: newest run with `first_usable_origin_utc` at or before the origin). TODO(number: leakage-test counts, i.e. origins sampled, series checked and result).

## 3. Factors that affect the forecast

All findings below come from training data up to 4 Oct only (✔ PLAN §2).

| Factor | Evidence | How the model uses it |
|---|---|---|
| **Day-ahead wind forecast level** | Top vs bottom wind quintile: mean \|gap\| 13.6 vs 40.0 €/MWh; up-regulation share 21 % vs 43 % | `wind_fc`, `wind_share`, `wind_fc_ramp_1h` |
| **Spot ramps** | \|gap\| rises from 18.5 to 50.4 between the lowest and highest quintile of quarter-to-quarter spot change | `spot_ramp_in/out`, `spot_abs_ramp`, spot shape over the horizon |
| **Time of day** | Evening peak around 20:00 local (\|gap\| 52.6 vs about 23 at night); morning ramp 06–09 | local hour, weekday, holiday, quarter |
| **Stale recent state** | The newest imbalance price is 5 quarters old at step 1. Its pull fades: direction agreement falls from 0.70 to 0.57 (chance 0.54) over the horizon | last gap and direction, trailing means, age; the model learns the weight |
| **Observed distribution shift** | September was the most volatile month. Spike shares (high / low): 9.0 % / 7.3 % in training, 12.1 % / 13.0 % in validation. Two samples, so this shows a shift between them, not a stable seasonal pattern. TODO(number: spike and direction rates by week, with sample sizes) | calibration on the most recent 14 training days |
| **Spikes only in the matching direction** | Of about 12,000 training quarters, 7 high spikes fall outside up-regulation and 18 low spikes outside down-regulation | spikes = P(direction) × P(tail given direction) |
| **Wind forecast revision** | Newer ECMWF run vs an older run used as a proxy for the vintage behind the day-ahead forecast (the package does not say which run produced it) | `om_wind_rev`, `om_wind_rev_mw`, icing proxy, temperature |
| **Fresh system state** | Measured wind vs forecast, frequency, nuclear output, consumption vs forecast, usable 30 min after each quarter | `rt_*` features, steps 1–8 only |
| Weak factors | Neighbour imbalance prices (corr. with the gap about 0.1), consumption error (about −0.04) | cheap features, little gain |

**Per-row explanations.** `top_drivers` lists the top 3 features by |SHAP| of the P50 model (LightGBM's built-in TreeSHAP), not text from an LLM. These are model attributions: they describe what drives the fitted model's output, not physical causes of the gap. In the rows we looked at, the consumption forecast, the wind forecast and spot appear often. TODO(number: share of scored rows in which each feature appears in `top_drivers`, aggregated over all rows of the run). ☐ TODO(final): re-read `top_drivers` on the final test forecast.

## 4. The model

All models are LightGBM trained from scratch (`src/models/gbm.py`); no pretrained forecasting model is used.

- **Price:** quantile regression (q = 0.1, 0.5, 0.9) on the gap, with the step as a feature. We add spot back and sort the quantiles.
- **Direction:** a binary "up" classifier. `p_none` is a constant (the training share, about 0.2 %), because "no dominating direction" almost never happens (✔ finding 8). `p_down = 1 − p_none − p_up`.
- **Spikes:** `P(spike high) = P(up) × P(gap > 50 | up)`, and `P(spike low) = P(down) × P(gap < −50 | down)`. The two sum to at most 1 and stay consistent with the direction forecast.
- **Calibration:** we hold out the last 14 days of the training window, fit the models on the earlier data, and learn (a) Platt scaling for the three probabilities and (b) offsets for P10, P50, P90 in three step bands (1–8, 9–20, 21–40). Then we refit on the full window and apply the maps. In the ablation below this takes coverage from 0.51 to 0.79 (with recency weights) and from 0.53 to about 0.80 for the package-only chain.
- **Horizon split (`split_all`):** steps 1–8 come from a model that gets the Fingrid real-time features plus weather. Steps 9–40 come from a model with weather but no real-time features. The first model is trained on steps 1–8 only. Reason: real-time signals are stale after a few hours, and giving them to every step made results worse (section 5).
- **No recency weights** in the final variant: they helped MAE but hurt the probabilities.
- Order of work: package → weather → Fingrid real-time. We kept a source only if validation improved.

TODO(final): the final model may change (pooled calibration over several folds, extra real-time features, ECMWF-vs-ICON spread). Update this section and the tables below.

## 5. The reasoning chain: step by step

Validation protocol:

| Run | Origins (local dates) | Training rows | Calibration holdout | Selection |
|---|---|---|---|---|
| Fold A (validation) | 7 Sep - 4 Oct, 672 origins | targets published by 7 Sep 00:00 | last 14 days of the training window (24 Aug - 6 Sep) | all variants below were compared on this window |
| Fold B (August) | 1 - 31 Aug, 744 origins | targets published by 1 Aug 00:00 | 18 - 31 Jul | `split_all` and pooled calibration only (section 6) |
| Test | 5 Oct - 1 Nov, 673 origins | targets published by 5 Oct 00:00 | 21 Sep - 4 Oct | not used for selection |

Fold A results below: organisers' `score.py` 0.1.1, spike margin 50. Lower is better in every column. Scored rows: 672 origins x 40 steps is 26,880 forecast rows, and 26,700 are scored. The 180 rows missing are quarter-hours after 4 Oct 23:45 local (36 + 32 + 28 + ... + 4 rows over the last nine origins), for which the actuals file has no price, so the scorer skips them. All 26,880 rows are in the submitted file. Direction Brier is the three-class score of `p_up`, `p_down`, `p_none` (range 0-2).

| Model | MAE | Pinball | Coverage | Brier spikes | Brier direction | What we learned |
|---|---:|---:|---:|---:|---:|---|
| Organisers' baseline (persistence) | 66.20 | 24.18 | 0.683 | 0.1132 | 0.4509 | Ignores spot |
| Spot anchor (spot + constant gap quantiles) | 44.29 | 14.99 | 0.675 | 0.1132 | 0.4508 | Gap framing: MAE −33 %. Probabilities only tie the baseline. |
| LightGBM quantiles + classifiers | 43.23 | 13.30 | 0.527 | 0.1063 | 0.4225 | Intervals far too narrow |
| + recency weights (30-day τ) | 42.96 | 13.70 | 0.509 | 0.1078 | 0.4401 | Better MAE, worse everything else |
| + calibration (14-day holdout) | 42.89 | 12.76 | 0.790 | 0.0971 | 0.4256 | Calibration fixes coverage and spikes |
| + spikes = P(dir) × P(tail \| dir) | 42.89 | 12.76 | 0.790 | 0.0945 | 0.4256 | Product form beats direct spike models |
| same, without recency weights | 43.22 | 12.44 | 0.802 | 0.0939 | 0.4148 | Best package-only model |
| + Fingrid real-time at every step | 43.43 | 12.52 | 0.773 | 0.0944 | 0.4204 | **Worse**: helps hour 1, fits noise in hours 3–10 |
| same, real-time hidden after step 8 | 42.86 | 12.38 | 0.810 | 0.0947 | 0.4154 | Better MAE, direction still worse |
| separate models: steps 1–8 with real-time | 42.95 | 12.31 | 0.797 | 0.0927 | 0.4058 | Hour 1: MAE 41.5 → 39.4, direction 0.408 → 0.342 |
| package + ECMWF weather runs | 43.08 | 12.19 | 0.816 | 0.0932 | 0.4088 | Weather helps every metric |
| **`split_all`: split + real-time + weather** | **42.53** | **12.09** | 0.814 | **0.0921** | **0.4011** | Best on all four metrics |

**What each step added** (change in the metric; negative is better):

| Step | MAE | Pinball | Spikes | Direction |
|---|---:|---:|---:|---:|
| Baseline → spot anchor | −21.9 | −9.2 | 0 | 0 |
| → LightGBM + calibration + product spikes (package only) | −1.1 | −2.6 | −0.0193 | −0.0360 |
| → + weather runs | −0.1 | −0.3 | −0.0007 | −0.0060 |
| → + Fingrid real-time, first 2 h only | −0.6 | −0.1 | −0.0011 | −0.0077 |

Reading the chain (each step changes one thing, except where noted):

1. **Spot anchoring is worth a third of the MAE, for free** (66.20 to 44.29).
2. **The model barely improves MAE beyond the anchor** (44.3 to 43.2). Error grows only from 41.6 (hour 1) to 43.7 (hour 10). We have not run a feature-group ablation, so we do not claim recent-state features add little. TODO(number: MAE and pinball with and without recent-state features, by forecast hour).
3. **Calibration, product spikes and dropping recency weights are three separate effects.** From the rows above:
   - Calibration alone (recency variant, direct spike classifiers): coverage 0.509 to 0.790, pinball 13.70 to 12.76, spike Brier 0.1078 to 0.0971, direction Brier 0.4401 to 0.4256.
   - Product-form spikes on top: spike Brier 0.0971 to 0.0945 (pinball and direction unchanged).
   - Dropping the recency weights on top: pinball 12.76 to 12.44, spike Brier 0.0945 to 0.0939, direction 0.4256 to 0.4148, MAE 42.89 to 43.22 (worse).
   - Most of the direction gain over the baseline (0.4509 to 0.4225) comes from the LightGBM classifier itself, before any calibration. About half of the spike gain (0.1132 to 0.0939) comes from calibration (0.1078 to 0.0971). The probabilities tied the baseline only for the spot anchor.
4. **Real-time features improved hour 1 in this run.** Using them at every horizon worsened the aggregate scores (MAE 43.22 to 43.43); restricting them to steps 1-8 worked better, and a separate short-horizon model better still. Hour 1 numbers: MAE 41.5 to 39.4, direction Brier 0.408 to 0.342. TODO(number: per-hour MAE, pinball and Brier with and without real-time features).
5. **Weather improved every reported aggregate metric in this validation run**, by small amounts (for example MAE 43.22 to 43.08 against the package-only model). The differences are not accompanied by uncertainty estimates. TODO(number: paired-origin uncertainty intervals for the weather deltas, and separate wind-level, revision, temperature and icing ablations).

TODO(final): add the August fold (second validation window) to this table, and a per-week breakdown.

## 6. Validation metrics against the baseline

| Metric (7 Sep – 4 Oct) | Baseline | `split_all` | Change |
|---|---:|---:|---:|
| MAE of P50 (€/MWh) | 66.20 | 42.53 | −36 % |
| Mean pinball loss of P10/P90 | 24.18 | 12.09 | −50 % |
| P10–P90 coverage (target 0.80) | 0.683 | 0.814 | closer to target |
| Brier, exceptional prices | 0.1132 | 0.0921 | −19 % |
| Brier, direction | 0.4509 | 0.4011 | −11 % |

The baseline row is reproduced exactly with the organisers' `baseline.ipynb`. The forecast file passes `validate_submission.py` (✔ for the safety submission; ☐ TODO(final): re-run for the final model). TODO(final): test-run results, if the organisers publish them before the deadline.

### Second fold (August)

`split_all`, trained on rows published by 1 Aug 00:00 (June and July only), scored on 1 - 31 Aug (29,580 scored rows; the organisers' scorer, actuals rebuilt from the package data with `src/backtest/actuals.py`, which reproduces `actuals_validation.csv` byte for byte on fold A):

| Fold | MAE | Pinball | Coverage | Brier spikes | Brier direction |
|---|---:|---:|---:|---:|---:|
| A (7 Sep - 4 Oct) | 42.53 | 12.09 | 0.814 | 0.0921 | 0.4011 |
| B (August) | 28.41 | 7.10 | 0.766 | 0.0750 | 0.4491 |

August is calmer (lower MAE and pinball), the intervals under-cover slightly (0.766), and the direction score is worse than on fold A (0.4491 against 0.4011), with only two months of training data. No organisers' baseline exists for August, so we do not report improvement percentages there. TODO(number: the other variants on fold B, and `split_all_pcal` on both folds, from `docs/RESULTS.md`).

### Diagnostics on the validation forecasts

- **Week-by-week stability** (`reports/weekly_metrics.md`). The four validation weeks differ a lot: MAE 31.4 to 49.6, spike Brier 0.062 to 0.138. Week 3 (21–27 Sep) is the outlier, with 21.7 % high-spike quarters, the worst spike (0.1375) and direction (0.481) Brier scores, and coverage of 0.731 against 0.83–0.85 in the other weeks. Differences between our model variants (tenths of an MAE point) are small next to this weekly swing, so close variants cannot be ranked reliably on one window.
- **Reliability of the probabilities** (`reports/calibration_check.md`). The high-spike probability is close to calibrated (mean forecast 0.114, observed 0.121): forecasts of 0.07 realised 0.11, forecasts of 0.38 realised 0.32, and forecasts of 0.58 realised 0.47 (533 rows in that top bin, strongly autocorrelated). The low-spike probability is over-forecast (mean 0.183 against 0.130 observed), and forecasts of 0.03–0.12 almost never happened. `p_up` is reliable in the middle but over-confident at both ends (forecast 0.11 realised 0.18; forecast 0.74 realised 0.64). Bin tables with counts are in the detail file.
- **Alert thresholds** (`reports/alerts_tuning.md`). Comparing each origin with the previous one, an alert when a block's `p_spike_high` rises by at least 0.20 to a level of at least 0.30 fires about 1.8 times a day, and 64–67 % of those alerts were followed by a high spike in that hour (base rate 19.6 %). A P50 move of at least 40 €/MWh fires about 1.8 times a day with 84 % precision for a spike in either direction (base rate 40 %). Thresholds were tuned on the same four weeks, and recall was not measured.
- **Input drift into the test period** (`reports/drift_inputs.md`, inputs only, no test targets). Median day-ahead wind is 3.9 GW in the test origins against 1.8 GW in training, and median consumption forecast 9.7 GW against 8.6 GW; 78 % of test rows have a consumption forecast above the training 95th percentile. Tree models cannot extrapolate, so the summer-trained calibration may not carry over to October.

TODO(final): add the August fold and the pooled-versus-single calibration comparison here once T1's `docs/RESULTS.md` rows are merged.

## 7. Limitations

- **The numbers are optimistic.** We picked the best of 11 variants on one validation window (7 Sep – 4 Oct). Selection on one window inflates the result, and the weekly results swing a lot (MAE 31 to 50 between weeks, `reports/weekly_metrics.md`). The August fold exists for `split_all` only so far (section 6). The test period will tell. No confidence intervals are reported. TODO(number: paired-origin uncertainty intervals).
- **Fingrid real-time history was downloaded after the fact.** If Fingrid corrected or revised values after first publication, the backtest saw the corrected values, not what was available at the origin. We cannot verify vintages. ☐ This is a question for the organisers, together with the delay rule below.
- **The real-time delay is our assumption.** We use 30 min after each quarter, the organisers' own delay for measured Fingrid data. ☐ We have not asked the organisers whether real-time series with our own delay are accepted. If they are not, the model falls back to the package-plus-weather variant (MAE 43.08 on validation).
- **Calibration drift into October and November.** The 14-day holdout before the test (20 Sep – 4 Oct) was volatile. The learned P90 offset is +28 to +36 €/MWh there, against +14 to +21 for validation. It is either a correct adaptation to the autumn regime or overfitting to two noisy weeks. The input drift in `reports/drift_inputs.md` shows the test period has much more wind and higher consumption than even the last 14 training days, so the holdout covers that regime only partly, and the week-by-week table (`reports/weekly_metrics.md`) shows how much one window can swing. TODO(final): pooled calibration over several folds, or shrunk offsets, checked week by week.
- **Daylight saving change on 25 Oct** falls inside the test period (a 25-hour local day). Features use the package's local calendar (`cal_hour_local`, `cal_weekday_local`, `cal_is_dst`), which the organisers computed from local Finnish time, so the hour of day should stay correct. ✔ the leakage test includes origins around the change. ☐ We have not checked forecast quality separately on that day. The submission has 673 origins, one more than 28 × 24, because of the extra hour.
- **The weather power curve is generic** (hand-set, not fitted), and the 8 weather points are approximate wind-cluster centres. A better mapping could help.
- **Few spikes and short history.** The training data has only about four months. The test period is autumn into November, a season the training data covers little of. Icing and winter effects are barely represented.
- **No plant or position data.** We do not know Turku Energia's capacity, marginal costs, contracts or trading position. The dashboard therefore gives **suggestions to review** ("check the Naantali plan for 16–18"), never instructions.
- **LLM text is explanation only.** It cannot change the forecast and is checked against a fact sheet, but it can still be wrong in tone or emphasis.

## 8. Next steps

- Second validation fold and week-by-week error; pooled calibration (TODO(final)).
- Real-time imbalance features: Fingrid 198 (surplus/deficit against the confirmed exchange plan) and 186, and the BRP production-plan error (dataset 242). These measure the deviation from the plan directly (TODO(final)).
- ECMWF-vs-ICON spread as a measure of weather uncertainty (TODO(final)).
- Outage messages from Nord Pool UMM: large fresh trips (above 800 MW) preceded the strongest spikes in training, but only 20 quarters (fetched, not used yet).
- Pre-June Fingrid history (last autumn and winter) once the organisers approve it.
- With plant data from Turku Energia: move from "suggestions to review" to capacity-aware recommendations.
