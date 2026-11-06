# Evaluation report: Finnish imbalance price forecast, 10 h ahead

Team entry for the Turku Energia challenge, Since AI 2026. Marks: ✔ checked in the data or code, ☐ assumption. `TODO(final)` marks text or numbers that will change before the 8 Nov 10:00 deadline.

> TODO(final): this draft uses the validation window 7 Sep – 4 Oct 2026 and the model `split_all`. Work in progress may change the numbers: a second validation fold (August), pooled calibration, real-time imbalance features (Fingrid 198/186, BRP plan error) and an ECMWF-vs-ICON spread feature. The final model and the test-run details are not chosen yet.

## 1. The problem and our framing

We forecast the Finnish imbalance price for 40 quarter-hours (10 h) from every full-hour origin. We also give an 80 % interval (P10, P50, P90), the probabilities of up- and down-regulation, and the probabilities of a spike (more than 50 €/MWh from spot).

**We forecast the gap to spot, not the price.** The imbalance price is the day-ahead spot price plus a jump up or down. Spot is known for all 40 steps at every origin (✔ PLAN finding 10, checked at every hourly origin 2 Jun – 1 Nov). Everything that spot already contains (gas, weather outlook, the Nordic fleet) is "priced in". The gap is what the day-ahead plan missed in Finland. This single choice gave the largest gain: a constant gap on top of spot beats the organisers' persistence baseline by a third (finding 1).

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

The Open-Meteo Historical Forecast API is not used, because it leaks. Fingrid's updated forecasts (245, 241) are not used for the same reason. Data from before 1 Jun 2026 is fetched but **not used** until the organisers approve it. ☐

## 3. Factors that affect the forecast

All findings below come from training data up to 4 Oct only (✔ PLAN §2).

| Factor | Evidence | How the model uses it |
|---|---|---|
| **Day-ahead wind forecast level** | Top vs bottom wind quintile: mean \|gap\| 13.6 vs 40.0 €/MWh; up-regulation share 21 % vs 43 % | `wind_fc`, `wind_share`, `wind_fc_ramp_1h` |
| **Spot ramps** | \|gap\| rises from 18.5 to 50.4 between the lowest and highest quintile of quarter-to-quarter spot change | `spot_ramp_in/out`, `spot_abs_ramp`, spot shape over the horizon |
| **Time of day** | Evening peak around 20:00 local (\|gap\| 52.6 vs about 23 at night); morning ramp 06–09 | local hour, weekday, holiday, quarter |
| **Stale recent state** | The newest imbalance price is 5 quarters old at step 1. Its pull fades: direction agreement falls from 0.70 to 0.57 (chance 0.54) over the horizon | last gap and direction, trailing means, age; the model learns the weight |
| **Season drift** | September was the most volatile month. Spike shares: 9.0 % / 7.3 % in training, 12.1 % / 13.0 % in validation | calibration on the most recent 14 training days |
| **Spikes only in the matching direction** | Of about 12,000 training quarters, 7 high spikes fall outside up-regulation and 18 low spikes outside down-regulation | spikes = P(direction) × P(tail given direction) |
| **Wind forecast revision** | Newer ECMWF run vs the run behind the day-ahead forecast | `om_wind_rev`, `om_wind_rev_mw`, icing proxy, temperature |
| **Fresh system state** | Measured wind vs forecast, frequency, nuclear output, consumption vs forecast, usable 30 min after each quarter | `rt_*` features, steps 1–8 only |
| Weak factors | Neighbour imbalance prices (corr. with the gap about 0.1), consumption error (about −0.04) | cheap features, little gain |

**Per-row explanations.** `top_drivers` lists the top 3 features by |SHAP| of the P50 model (LightGBM's built-in TreeSHAP), not text from an LLM. They are mostly the consumption forecast, the wind forecast and spot, consistent with the table above. ☐ TODO(final): re-read `top_drivers` on the final test forecast and update this sentence.

## 4. The model

All models are LightGBM trained from scratch (`src/models/gbm.py`); no pretrained forecasting model is used.

- **Price:** quantile regression (q = 0.1, 0.5, 0.9) on the gap, with the step as a feature. We add spot back and sort the quantiles.
- **Direction:** a binary "up" classifier. `p_none` is a constant (the training share, about 0.2 %), because "no dominating direction" almost never happens (✔ finding 8). `p_down = 1 − p_none − p_up`.
- **Spikes:** `P(spike high) = P(up) × P(gap > 50 | up)`, and `P(spike low) = P(down) × P(gap < −50 | down)`. The two sum to at most 1 and stay consistent with the direction forecast.
- **Calibration:** we hold out the last 14 days of the training window, fit the models on the earlier data, and learn (a) Platt scaling for the three probabilities and (b) offsets for P10, P50, P90 in three step bands (1–8, 9–20, 21–40). Then we refit on the full window and apply the maps. This takes coverage from 0.53 to about 0.80.
- **Horizon split (`split_all`):** steps 1–8 come from a model that gets the Fingrid real-time features plus weather. Steps 9–40 come from a model with weather but no real-time features. The first model is trained on steps 1–8 only. Reason: real-time signals are stale after a few hours, and giving them to every step made results worse (section 5).
- **No recency weights** in the final variant: they helped MAE but hurt the probabilities.
- Order of work: package → weather → Fingrid real-time. We kept a source only if validation improved.

TODO(final): the final model may change (pooled calibration over several folds, extra real-time features, ECMWF-vs-ICON spread). Update this section and the tables below.

## 5. The reasoning chain: step by step

Validation 7 Sep – 4 Oct 2026: 672 origins, 26,700 scored rows, organisers' `score.py` 0.1.1, spike margin 50. Lower is better in every column.

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

Reading the chain:

1. **Spot anchoring is worth a third of the error, for free.**
2. **The model barely improves MAE beyond the anchor** (44.3 → 43.2). Package features say little about the size of the gap. Error grows only from 41.6 (hour 1) to 43.7 (hour 10), so recent state adds little.
3. **Calibration is where the points are.** It took the probability scores from a tie with the baseline to −17 % (spikes) and −8 % (direction), and coverage from 0.53 to 0.80.
4. **Fresh data only helps where it is fresh.** Real-time series transform hour 1 and are noise by hour 3. A separate short-horizon model made them pay off.
5. **Weather adds a little everywhere.** The day-ahead wind forecast already holds most of the weather; the revision since then is the extra information.

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

## 7. Limitations

- **The numbers are optimistic.** We picked the best of 11 variants on one validation window (7 Sep – 4 Oct). Selection on one window inflates the result. The test period will tell. TODO(final): a second fold (August) is being added to check this.
- **The real-time delay is our assumption.** We use 30 min after each quarter, the organisers' own delay for measured Fingrid data. ☐ We have not asked the organisers whether real-time series with our own delay are accepted. If they are not, the model falls back to the package-plus-weather variant (MAE 43.08 on validation).
- **Calibration drift into October and November.** The 14-day holdout before the test (20 Sep – 4 Oct) was volatile. The learned P90 offset is +28 to +36 €/MWh there, against +14 to +21 for validation. It is either a correct adaptation to the autumn regime or overfitting to two noisy weeks. TODO(final): pooled calibration over several folds, or shrunk offsets, checked week by week.
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
