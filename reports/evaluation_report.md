# Evaluation report: Finnish imbalance price forecast, 10 h ahead

Team entry for the Turku Energia challenge, Since AI 2026. Marks: ✔ checked in the data or code, ☐ assumption. `TODO(number)` marks analyses we have not run.

> **Pipeline model: `v6_hf`** (Frank's branch, section 4). It is the model in the repo's submission pipeline. Fold A (7 Sep – 4 Oct, the organisers' validation window): MAE 40.67, pinball 11.19, spike Brier 0.0856, direction Brier 0.3892, 35.7 % better than the baseline weighted by points. Fold B (August): 27.74 / 6.59 / 0.0680 / 0.4388. Our own `split_all_rt_icon` (Pavlo) is now one ablation row, not the final model. Abdo's `team5050` (½ `v4_n50` + ½ his model) leads the team scoreboard (31.1 % average against 30.9 % for `v6_hf`). TODO(team): v6_hf or team5050 — which file is submitted. Numbers are for fold A unless marked fold B.

## 1. The problem and our framing

We forecast the Finnish imbalance price for 40 quarter-hours (10 h) from every full-hour origin. We also give an 80 % interval (P10, P50, P90), the probabilities of up- and down-regulation, and the probabilities of a spike (more than 50 €/MWh from spot).

**We forecast the gap to spot, not the price.** The imbalance price is the day-ahead spot price plus a jump up or down. Spot is known for all 40 steps at every origin (✔ PLAN finding 10, checked at every hourly origin 2 Jun – 1 Nov). Spot is a strong anchor: it already reflects gas, the weather outlook and the Nordic fleet. The gap measures what remains after using spot. It is a modelling target, not a pure causal measure of Finland's forecast error, because it also contains balancing-market rules, activation and pricing effects. This single choice gave the largest gain: on validation, a constant gap on top of spot reduced MAE by 33 % against the organisers' persistence baseline (finding 1).

## 2. Data and the availability rule

Data: the organisers' package (Fingrid, ENTSO-E, Nord Pool spot, calendar), plus external sources we added: Fingrid real-time series (wind, nuclear, frequency, consumption, hydro, production, the live surplus/deficit) and the balance responsible parties' production plans, and two weather models' runs from Open-Meteo (ECMWF IFS and ICON-EU). Full list with licences and delays: `SOURCES.md`.

**The rule:** at origin `t`, a row may be used only if `first_usable_origin_utc ≤ t`. Breaking it scores 0. We enforce it in one place and test it.

- Every feature is read through `SeriesIndex` lookups (`src/data/availability.py`): `value_at` returns a value only if its row is usable at that origin, and `latest` returns the newest usable row. No feature uses a fixed shift.
- **Truncation leakage test** (`tests/test_availability.py`): for sampled origins (edge cases such as data start, spot publication hours, the DST change, period boundaries, plus random hours), we build the features from the full data and again from data where every row with `first_usable_origin_utc > t` was deleted. The two must be identical. A feature that peeks at the future would change. The same test covers the weather features (runs not yet usable are removed).
- A second test compares the fast lookups with the slow reference filter (the organisers' `rows_available_at` logic). Further tests check that `data_cutoff_utc` is before the origin, that targets are never features, and that training rows were published before the training cut-off.
- Training: for the validation run we train only on rows whose targets were published before 7 Sep; for the test run, before 5 Oct.

**Delays we assumed for external data (all conservative, rounded up to the next full hour):**

| Source | Rule | Basis |
|---|---|---|
| Fingrid real-time (wind, nuclear, frequency, consumption, hydro 191, production 192, surplus/deficit 198 and 186) | quarter end + 30 min | The organisers' own delay for measured Fingrid data. Fingrid publishes every 1–3 min. ☐ |
| BRP production plans (Fingrid 242) | 18:00 local on the day before delivery | Plans are due by 18:00 D-1 and are not revised. ☐ |
| ECMWF IFS runs (Open-Meteo) | run start + 8 h | Measured about 7.1 h on 6 Nov. ☐ |
| ICON-EU runs (Open-Meteo) | run start + 5 h | Measured about 3.9 h. ☐ |

The Open-Meteo Historical Forecast API is not used, because it does not give the point-in-time run vintages our availability rule requires. Fingrid's updated forecasts (245, 241) are not used for the same reason. Data from before 1 Jun 2026 is used by `v6_hf` only: the organisers allowed it on 7 Nov (`QUESTIONS.md` Q1). The `split_all` family and `split_all_rt_icon` do not use it. The Fingrid real-time and weather series do not reach before June, so those features are empty on history rows. ☐

**Worked example** (origin Fri 2 Oct 2026 09:00 UTC, 12:00 local; times in UTC, read from the same index the model uses):

| Data | Newest row used | Its first usable origin | Next row, not usable yet |
|---|---|---|---|
| Imbalance price (package) | quarter 07:45–08:00 | 09:00 (package rule) | 08:00–08:15, usable from 10:00 |
| Fingrid surplus/deficit (198) | quarter 08:15–08:30 | 08:30 + 30 min = 09:00 | 08:30–08:45: 08:45 + 30 min = 09:15, rounded up to 10:00 |
| ECMWF IFS run | 00 UTC run | 00:00 + 8 h = 08:00 | 06 UTC run, usable from 14:00 |
| ICON-EU run | 00 UTC run | 00:00 + 5 h = 05:00 | 06 UTC run, usable from 11:00 |

So the model sees the imbalance price up to one hour before the origin, the live surplus/deficit up to 30 minutes before, and weather runs that are 9 hours old. The `data_cutoff_utc` written for this origin is the newest measured quarter used.

**Leakage tests in numbers:** the main truncation test rebuilds 51 columns (36 package, 7 Fingrid real-time, 7 live-imbalance, plus `data_cutoff`) at 24 origins (12 fixed edge cases and 12 random hours, 40 steps each) and requires exact equality. The ECMWF and ICON-EU features have their own truncation tests at 20 origins, which remove every run not yet usable. A further test checks the newest-row lookup against the slow reference filter for every external series. All 66 tests in the suite pass.

## 3. Factors that affect the forecast

All findings below come from training data up to 4 Oct only (✔ PLAN §2).

| Factor | Evidence | How the model uses it |
|---|---|---|
| **Day-ahead wind forecast level** | Top vs bottom wind quintile: mean \|gap\| 13.6 vs 40.0 €/MWh; up-regulation share 21 % vs 43 % | `wind_fc`, `wind_share`, `wind_fc_ramp_1h` |
| **Spot ramps** | \|gap\| rises from 18.5 to 50.4 between the lowest and highest quintile of quarter-to-quarter spot change | `spot_ramp_in/out`, `spot_abs_ramp`, spot shape over the horizon |
| **Time of day** | Evening peak around 20:00 local (\|gap\| 52.6 vs about 23 at night); morning ramp 06–09 | local hour, weekday, holiday, quarter |
| **Stale recent state** | The newest imbalance price is 5 quarters old at step 1. Its pull fades: direction agreement falls from 0.70 to 0.57 (chance 0.54) over the horizon | last gap and direction, trailing means, age; the model learns the weight |
| **Observed distribution shift** | September was the most volatile month. Spike shares (high / low): 9.0 % / 7.3 % in training, 12.1 % / 13.0 % in validation. Two samples, so this shows a shift between them, not a stable seasonal pattern. By validation week (6,540–6,720 scored quarters each), the high-spike share was 10.7 %, 6.2 %, 21.7 % and 9.8 %, and the low-spike share 8.7 %, 13.8 %, 14.4 % and 14.7 % (`reports/weekly_metrics.md`). | calibration on the most recent 14 training days |
| **Spikes only in the matching direction** | Of about 12,000 training quarters, 7 high spikes fall outside up-regulation and 18 low spikes outside down-regulation | spikes = P(direction) × P(tail given direction) |
| **Wind forecast revision** | Newer ECMWF run vs an older run used as a proxy for the vintage behind the day-ahead forecast (the package does not say which run produced it) | `om_wind_rev`, `om_wind_rev_mw`, icing proxy, temperature |
| **Second weather model and model disagreement** | ICON-EU's wind index and its own revision, plus the gap between the ECMWF and ICON wind indices. The idea: when two models disagree, the weather is uncertain and the band should be wider. Adding them lowered MAE and direction Brier on both folds; the effect on the band is weak (section 5) | `om_icon_wind_idx`, `om_icon_wind_rev`, `om_model_spread`, all steps |
| **Fresh system state** | Measured wind vs forecast, frequency, nuclear output, consumption vs forecast, usable 30 min after each quarter | `rt_*` features, steps 1–8 only |
| **Live imbalance and plan error** | Fingrid's real-time surplus/deficit (datasets 198 and 186: measured net import against the confirmed exchange plan), production against the balance responsible parties' day-ahead plans, hydro output change over 1 h; usable about 45-75 min after the quarter. Hydro change is the clearest signal (up-regulation share 0.26 in the lowest quintile, 0.54 in the highest); the surplus/deficit series alone shows little relation to the next hour's gap (training data, steps 1–4) | `rt_sd_*`, `rt_plan_err*`, `rt_hydro_change_1h`, steps 1–8 only |
| Weak factors | Neighbour imbalance prices (corr. with the gap about 0.1), consumption error (about −0.04) | cheap features, little gain |

**Per-row explanations.** `top_drivers` lists the top 3 features by |SHAP| of the P50 model (LightGBM's built-in TreeSHAP), not text from an LLM. These are model attributions: they describe what drives the fitted model's output, not physical causes of the gap. Over all 26,920 rows of the `split_all_rt_icon` test forecast, the features that appear most often among the top 3 are spot (64 % of rows), the consumption forecast (52 %), ICON-EU's wind index (50 %), temperature (15 %), ICON's wind revision (15 %), the solar forecast (14 %), measured wind against its forecast (10 %) and the ECMWF-vs-ICON disagreement (10 %).

## 4. The model

All models are LightGBM trained from scratch (`src/models/gbm.py`); no pretrained forecasting model is used.

- **Price:** quantile regression (q = 0.1, 0.5, 0.9) on the gap, with the step as a feature. We add spot back and sort the quantiles.
- **Direction:** a binary "up" classifier. `p_none` is a constant (the training share, about 0.2 %), because "no dominating direction" almost never happens (✔ finding 8). `p_down = 1 − p_none − p_up`.
- **Spikes:** `P(spike high) = P(up) × P(gap > 50 | up)`, and `P(spike low) = P(down) × P(gap < −50 | down)`. The two sum to at most 1 and stay consistent with the direction forecast.
- **Calibration:** we hold out the last 14 days of the training window, fit the models on the earlier data, and learn (a) Platt scaling for the three probabilities and (b) offsets for P10, P50, P90 in three step bands (1–8, 9–20, 21–40). Then we refit on the full window and apply the maps. In the ablation below this takes coverage from 0.51 to 0.79 (with recency weights) and from 0.53 to about 0.80 for the package-only chain. Pooling the calibration over three rolling holdouts was tested and rejected (section 6).
- **Horizon split:** steps 1–8 come from a short model trained on steps 1–8 only, which gets the fresh real-time data. Steps 9–40 come from a long model without real-time features. Reason: real-time signals are stale after a few hours, and giving them to every step made results worse (section 5).
- **Pipeline model `v6_hf`** (details in `docs/RESULTS.md`). It builds on the horizon split above, with these parts:
  - **Horizon split:** a short model for steps 1–8 with fresh real-time data, a long model for steps 9–40.
  - **`MedianFrom`:** the P50 and its drivers come from a twin model that also sees wind in Sweden, Norway, Denmark and Estonia. The band and probabilities come from the model without it, because the neighbour wind improved the median but made the band worse in both September and August.
  - **5 seeds:** each model is trained five times and averaged.
  - **Tuned trees:** 15 leaves, at least 800 rows per leaf, learning rate 0.03, 300 trees, 60 % of features per tree, picked on three training-only folds (26 Jul – 6 Sep).
  - **4-hour memory:** mean gap and direction over the last 16 usable quarters.
  - **ICON-EU:** the second weather model (wind index, its revision, ECMWF–ICON disagreement), ported from our `split_all_icon`.
  - **Learned wind production:** non-negative weights for 22 weather points fitted to Fingrid's measured wind (dataset 181, data published before the cutoff only).
  - **Shrunk spike calibration:** the spike correction is shrunk toward the uncalibrated model when the calibration window holds few spike quarters (s = m / (m + 50)).
  - **Calibration window:** the last 28 days.
  - **Pre-June history:** also trained on 5 Mar 2025 – 31 May 2026 (every 3rd hourly origin), with a `regime_2026` flag (1 for deliveries from 1 Jun 2026). Older imbalance prices are recomputed under the June 2026 rule (99.5 % match, section 7).
- **Our branch's model `split_all_rt_icon`** (an ablation row in sections 5–6, not the pipeline model):
  - Short model (steps 1–8): package features, Fingrid real-time (wind, nuclear, frequency, consumption), the live surplus/deficit (198/186), production against the BRP plan (192 − 242), hydro change over 1 h (191), and both weather models.
  - Long model (steps 9–40): package features and both weather models.
  - Each group adds about 1 % or less; we kept a group only if it improved both validation folds (section 5).
  - Its ICON-EU features were ported into Frank's models from `v3_bmi` onward. Its live-imbalance features were not used by Frank.
- **No recency weights** in these variants: they helped MAE but hurt the probabilities.
- Order of work in our branch: package → ECMWF weather → Fingrid real-time → live imbalance and ICON-EU. Every step after `split_all` had to win on both folds.
- Which file is finally submitted is a team decision (see the note at the top of this report).

## 5. The reasoning chain: step by step

Validation protocol:

| Run | Origins (local dates) | Training rows | Calibration holdout | Selection |
|---|---|---|---|---|
| Fold A (validation) | 7 Sep - 4 Oct, 672 origins | targets published by 7 Sep 00:00 | last 14 days of the training window (24 Aug - 6 Sep) | all variants below were compared on this window |
| Fold B (August) | 1 - 31 Aug, 744 origins | targets published by 1 Aug 00:00 | 18 - 31 Jul | every change after `split_all` had to win here too (section 6) |
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
| `split_all`: split + real-time + weather | 42.53 | 12.09 | 0.814 | 0.0921 | 0.4011 | Best on all four metrics at this point |
| + live imbalance in the short model (`split_all_rt`) | 42.52 | 12.07 | 0.815 | 0.0918 | 0.4005 | Small gain, all at hours 1–2 |
| + ICON-EU weather in both models (`split_all_icon`) | 42.14 | 12.06 | 0.807 | 0.0923 | 0.3995 | MAE −0.39 |
| `split_all` with pooled calibration (`split_all_pcal`) | 42.34 | 12.01 | 0.765 | 0.0907 | 0.3969 | Better here, worse on fold B: **rejected** |
| Ablation: live imbalance + ICON-EU (`split_all_rt_icon`) | 42.14 | 12.06 | 0.808 | 0.0922 | 0.3978 | Better than `split_all` on both folds. Best of our branch. |
| Frank, round 3: `final_capw`, then smaller, slower trees (`final_tuned`) | 41.82 | 11.90 | 0.802 | 0.0886 | 0.3899 | MAE better in 4/4 weeks |
| + 4-hour memory (`v3_bm`) | 41.68 | 11.90 | 0.800 | 0.0880 | 0.3888 | Memory pays off once the trees are regularised |
| + ICON-EU, ported from `split_all_icon` (`v3_bmi`) | 41.31 | 11.88 | 0.796 | 0.0873 | 0.3902 | MAE better in 4/4 weeks |
| + neighbour wind for the median only (`v3_bmi_n50`) | 41.21 | 11.88 | 0.796 | 0.0873 | 0.3902 | Median better in Sep and Aug, band worse |
| + shrunk spike calibration (`v4_eb`) | 41.31 | 11.88 | 0.796 | 0.0869 | 0.3902 | Spikes better in 4/4 weeks (Sep), 5/5 (Aug) |
| + learned wind production, both models (`v4_n50`) | 41.08 | 11.88 | 0.797 | 0.0871 | 0.3899 | Earlier submitted model |
| + 15 months of pre-June history (`v6_h`) | 40.74 | 11.19 | 0.770 | 0.0855 | 0.3890 | Pinball better in 4/4 weeks |
| **+ `regime_2026` flag (`v6_hf`)** | **40.67** | **11.19** | 0.771 | 0.0856 | 0.3892 | **Pipeline model.** A near tie with `v6_h`; wins both months |
| Abdo, `team5050` (½ `v4_n50` + ½ his model) | 40.97 | 11.63 | 0.801 | 0.0861 | 0.3803 | Leads the team scoreboard; best direction Brier |

**What each step added** (change in the metric; negative is better):

| Step | MAE | Pinball | Spikes | Direction |
|---|---:|---:|---:|---:|
| Baseline → spot anchor | −21.9 | −9.2 | 0 | 0 |
| → LightGBM + calibration + product spikes (package only) | −1.1 | −2.6 | −0.0193 | −0.0360 |
| → + weather runs | −0.1 | −0.3 | −0.0007 | −0.0060 |
| → + Fingrid real-time, first 2 h only | −0.6 | −0.1 | −0.0011 | −0.0077 |
| → + ICON-EU weather + live imbalance (`split_all_rt_icon`, our branch, against `split_all`) | −0.39 | −0.03 | +0.0001 | −0.0033 |

Frank's steps, from `docs/RESULTS.md` (his chain also starts at the baseline, so the first rows repeat ours):

| Step | MAE | Pinball | Spikes | Direction |
|---|---:|---:|---:|---:|
| Baseline → spot anchor | −21.9 | −9.2 | 0 | 0 |
| → LightGBM + calibration + product spikes (package) | −1.1 | −2.6 | −0.0193 | −0.0360 |
| → + weather runs | −0.1 | −0.3 | −0.0007 | −0.0060 |
| → + Fingrid real-time, first 2 h only | −0.6 | −0.1 | −0.0011 | −0.0077 |
| → + more real-time series, 5 seeds, 28-day calibration, capacity-weighted weather | −0.2 | −0.03 | −0.0021 | −0.0103 |
| → + smaller, slower trees + 4-hour memory | −0.7 | −0.2 | −0.0020 | −0.0020 |
| → + second weather model (ICON-EU) | −0.4 | −0.02 | −0.0007 | +0.0014 |
| → + neighbour wind for the median only | −0.1 | 0 | 0 | 0 |
| → + steadier spike calibration and learned wind production | −0.1 | 0 | −0.0002 | −0.0003 |
| → + 15 months of pre-June history with a pricing-rule flag | −0.4 | −0.7 | −0.0015 | −0.0007 |

Reading the chain (each step changes one thing, except where noted):

1. **Spot anchoring is worth a third of the MAE, for free** (66.20 to 44.29).
2. **The model barely improves MAE beyond the anchor** (44.3 to 43.2). Error grows only from 41.6 (hour 1) to 43.7 (hour 10). We have not run a feature-group ablation, so we do not claim recent-state features add little. TODO(number: MAE and pinball with and without recent-state features, by forecast hour).
3. **Calibration, product spikes and dropping recency weights are three separate effects.** From the rows above:
   - Calibration alone (recency variant, direct spike classifiers): coverage 0.509 to 0.790, pinball 13.70 to 12.76, spike Brier 0.1078 to 0.0971, direction Brier 0.4401 to 0.4256.
   - Product-form spikes on top: spike Brier 0.0971 to 0.0945 (pinball and direction unchanged).
   - Dropping the recency weights on top: pinball 12.76 to 12.44, spike Brier 0.0945 to 0.0939, direction 0.4256 to 0.4148, MAE 42.89 to 43.22 (worse).
   - Most of the direction gain over the baseline (0.4509 to 0.4225) comes from the LightGBM classifier itself, before any calibration. About half of the spike gain (0.1132 to 0.0939) comes from calibration (0.1078 to 0.0971). The probabilities tied the baseline only for the spot anchor.
4. **Real-time features improved hour 1 in this run.** Using them at every horizon worsened the aggregate scores (MAE 43.22 to 43.43); restricting them to steps 1-8 worked better, and a separate short-horizon model better still. Hour 1 numbers: MAE 41.5 to 39.4, direction Brier 0.408 to 0.342. TODO(number: per-hour MAE, pinball and Brier with and without real-time features).
5. **Weather improved every reported aggregate metric in this validation run**, by small amounts (for example MAE 43.22 to 43.08 against the package-only model). Gains of this size are within noise on one month: a paired day-block bootstrap (`reports/uncertainty.md`) puts ICON-EU plus live imbalance over `split_all` at +0.5 % points-weighted, 90 % interval −0.4 to +1.3 %. TODO(number: separate wind-level, revision, temperature and icing ablations).

The August fold and the week-by-week breakdown are in section 6.

## 6. Validation metrics against the baseline

| Metric (7 Sep – 4 Oct) | Baseline | `v6_hf` | Change | `team5050` | `split_all_rt_icon` |
|---|---:|---:|---:|---:|---:|
| MAE of P50 (€/MWh) | 66.20 | 40.67 | −39 % | 40.97 | 42.14 |
| Mean pinball loss of P10/P90 | 24.18 | 11.19 | −54 % | 11.63 | 12.06 |
| P10–P90 coverage (target 0.80) | 0.683 | 0.771 | closer to target | 0.801 | 0.808 |
| Brier, exceptional prices | 0.1132 | 0.0856 | −24 % | 0.0861 | 0.0922 |
| Brier, direction | 0.4509 | 0.3892 | −14 % | 0.3803 | 0.3978 |

Weighted by points (30/20/20/10), the improvement over the baseline in September is 35.7 % for `v6_hf` and 35.2 % for `team5050`; in August it is 26.0 % and 26.9 %. Averaged over both months: `team5050` 31.1 %, `v6_hf` 30.9 %, `v4_n50` 29.1 %, `split_all_rt_icon` 27.6 % (team scoreboard). Abdo's August numbers come from his lab scorer; the others are scored officially.

The baseline row is reproduced exactly with the organisers' `baseline.ipynb`. The test forecast of `split_all_rt_icon` (673 origins, 26,920 rows) passes `validate_submission.py` ✔, and every `data_cutoff_utc` is at or before its origin ✔. The organisers have not published test-period scores.

### Second fold (August)

Every candidate after `split_all` was trained on rows published by 1 Aug 00:00 (June and July only) and scored on 1 - 31 Aug (29,580 scored rows; the organisers' scorer, actuals rebuilt from the package data with `src/backtest/actuals.py`, which reproduces `actuals_validation.csv` byte for byte on fold A):

| Model | Fold | MAE | Pinball | Coverage | Brier spikes | Brier direction |
|---|---|---:|---:|---:|---:|---:|
| `split_all` (reference) | A | 42.53 | 12.09 | 0.814 | 0.0921 | 0.4011 |
| | B | 28.41 | 7.10 | 0.766 | 0.0750 | 0.4491 |
| `split_all_pcal` (pooled calibration) | A | 42.34 | 12.01 | 0.765 | 0.0907 | 0.3969 |
| | B | 28.67 | 7.14 | 0.782 | 0.0738 | 0.4559 |
| `split_all_rt` (+ live imbalance) | A | 42.52 | 12.07 | 0.815 | 0.0918 | 0.4005 |
| | B | 28.41 | 7.10 | 0.765 | 0.0732 | 0.4480 |
| `split_all_icon` (+ ICON-EU) | A | 42.14 | 12.06 | 0.807 | 0.0923 | 0.3995 |
| | B | 28.11 | 6.99 | 0.758 | 0.0738 | 0.4445 |
| `split_all_rt_icon` | A | 42.14 | 12.06 | 0.808 | 0.0922 | 0.3978 |
| | B | 28.02 | 6.97 | 0.760 | 0.0741 | 0.4443 |
| `v4_n50` (Frank) | A | 41.08 | 11.88 | 0.797 | 0.0871 | 0.3899 |
| | B | 27.99 | 7.00 | 0.738 | 0.0710 | 0.4466 |
| **`v6_hf` (Frank, pipeline model)** | A | **40.67** | **11.19** | 0.771 | 0.0856 | 0.3892 |
| | B | **27.74** | 6.59 | 0.770 | 0.0680 | 0.4388 |
| `team5050` (Abdo) | A | 40.97 | 11.63 | 0.801 | 0.0861 | 0.3803 |
| | B (lab scorer) | 27.27 | 6.57 | | 0.0677 | 0.4281 |

August is calmer (lower MAE and pinball), the intervals under-cover slightly (0.76–0.78), and the direction score is worse than on fold A, with only two months of training data. No organisers' baseline exists for August, so we do not report improvement percentages there.

What fold B decided:
- **Pooled calibration** (three rolling 14-day holdouts instead of one) improved every fold-A metric but made fold B worse on MAE, pinball and direction, and pulled fold-A coverage down to 0.765. We kept the single holdout.
- **Live imbalance and ICON-EU** each improved fold B in the same direction as fold A. Together (`split_all_rt_icon`) they beat `split_all` on both folds on MAE, pinball and direction, so it is the best model of our branch. The spike Brier is flat on fold A (+0.0001) and better on fold B (−0.0009).
- Frank's later rounds (section 5) also had to win on August, and `v6_hf` does. The gains of our own variants are small (about 1 % of MAE) next to the week-to-week swing below, so the ranking of close variants rests on agreement across both folds, not on the size of any one gain.

### Diagnostics on the validation forecasts

- **Week-by-week stability** (`reports/weekly_metrics.md`). The four validation weeks differ a lot: MAE 31.4 to 49.6, spike Brier 0.062 to 0.138. Week 3 (21–27 Sep) is the outlier, with 21.7 % high-spike quarters, the worst spike (0.1375) and direction (0.481) Brier scores, and coverage of 0.731 against 0.83–0.85 in the other weeks. Differences between our model variants (tenths of an MAE point) are small next to this weekly swing, so close variants cannot be ranked reliably on one window.
- **Reliability of the probabilities** (`reports/calibration_check.md`). The high-spike probability is close to calibrated (mean forecast 0.114, observed 0.121): forecasts of 0.07 realised 0.11, forecasts of 0.38 realised 0.32, and forecasts of 0.58 realised 0.47 (533 rows in that top bin, strongly autocorrelated). The low-spike probability is over-forecast (mean 0.183 against 0.130 observed), and forecasts of 0.03–0.12 almost never happened. `p_up` is reliable in the middle but over-confident at both ends (forecast 0.11 realised 0.18; forecast 0.74 realised 0.64). Bin tables with counts are in the detail file.
- **Alert thresholds** (`reports/alerts_tuning.md`). Comparing each origin with the previous one, an alert when a block's `p_spike_high` rises by at least 0.20 to a level of at least 0.30 fires about 1.8 times a day, and 64–67 % of those alerts were followed by a high spike in that hour (base rate 19.6 %). A P50 move of at least 40 €/MWh fires about 1.8 times a day with 84 % precision for a spike in either direction (base rate 40 %). Thresholds were tuned on the same four weeks, and recall was not measured.
- **Input drift into the test period** (`reports/drift_inputs.md`, inputs only, no test targets). Median day-ahead wind is 3.9 GW in the test origins against 1.8 GW in training, and median consumption forecast 9.7 GW against 8.6 GW; 78 % of test rows have a consumption forecast above the training 95th percentile. Tree models cannot extrapolate, so the summer-trained calibration may not carry over to October.


## 7. Limitations

- **The numbers are optimistic.** About 37 variants were compared on the validation month (`docs/RESULTS.md`); we compared 16 of them on the validation window (7 Sep – 4 Oct). Selection on one window inflates the result, and the weekly results swing a lot (MAE 31 to 50 between weeks, `reports/weekly_metrics.md`). From `split_all` on, every change also had to win on the August fold (section 6), which limits this, but the earlier steps were chosen on fold A alone, and Frank's tuning folds (26 Jul – 6 Sep) overlap August. The test period will tell. Paired day-block bootstrap intervals (`reports/uncertainty.md`, 29 days, 2,000 resamples, 90 %): every model's gain over the baseline (32–35 % points-weighted) is far from zero, `team5050` beats `split_all_rt_icon` by +4.1 % (+2.8 to +5.8 %), and `split_all_rt_icon` vs `split_all` (+0.5 %, −0.4 to +1.3 %) can't be told from noise. Both sides of each comparison were tuned on this month, so the test-period uncertainty is larger.
- **Older imbalance prices were recomputed under the June 2026 rule.** The pre-June history used by `v6_hf` has a target rebuilt with the 1 June 2026 volume-weighted rule. It matches the official price on 99.5 % of Jun–Oct 2026 quarters. The `regime_2026` flag tells the model which rule a row was priced under. Pre-June rows have no ENTSO-E neighbour series, weather runs or Fingrid real-time data.
- **Fingrid real-time history was downloaded after the fact.** If Fingrid corrected or revised values after first publication, the backtest saw the corrected values, not what was available at the origin. We cannot verify vintages. ☐ This is a question for the organisers, together with the delay rule below.
- **The real-time delay is our assumption.** We use 30 min after each quarter, the organisers' own delay for measured Fingrid data. ☐ We have not asked the organisers whether real-time series with our own delay are accepted. If they are not, the model falls back to the package-plus-weather variant (MAE 43.08 on validation).
- **Calibration drift into October and November.** The 14-day holdout before the test (20 Sep – 4 Oct) was volatile. For the `split_all_rt_icon` test run, the learned P90 offset is +18 €/MWh in the short model and +38 to +44 €/MWh in the long model, against +14 to +21 for `split_all` on validation. It is either a correct adaptation to the autumn regime or overfitting to two noisy weeks. The input drift in `reports/drift_inputs.md` shows the test period has much more wind and higher consumption than even the last 14 training days, so the holdout covers that regime only partly, and the week-by-week table (`reports/weekly_metrics.md`) shows how much one window can swing. Pooled calibration over three holdouts was tested and rejected on fold B (section 6); shrinking the offsets is untested.
- **Daylight saving change on 25 Oct** falls inside the test period (a 25-hour local day). Features use the package's local calendar (`cal_hour_local`, `cal_weekday_local`, `cal_is_dst`), which the organisers computed from local Finnish time, so the hour of day should stay correct. ✔ the leakage test includes origins around the change. ☐ We have not checked forecast quality separately on that day. The submission has 673 origins, one more than 28 × 24, because of the extra hour.
- **The weather power curve is generic** (hand-set, not fitted), and the 8 weather points are approximate wind-cluster centres. A better mapping could help.
- **Few spikes and short history.** The package alone has only about four months; `v6_hf` adds 15 months of history. The test period is autumn into November, a season the training data covers little of. Icing and winter effects are barely represented.
- **No plant or position data.** We do not know Turku Energia's capacity, marginal costs, contracts or trading position. The dashboard therefore gives **suggestions to review** ("check the Naantali plan for 16–18"), never instructions.
- **LLM text is explanation only.** It cannot change the forecast and is checked against a fact sheet, but it can still be wrong in tone or emphasis.

## 8. Next steps

- **Evening up-regulation spikes.** High spikes are 12 % of the quarters but 46 % of the absolute error (`reports/error_breakdown.md`). Gains should come from sharper signals for these quarters and from a wider upper tail in the evening hours, not from a general widening of the band. Down-regulation quarters are over-covered (0.90), so their P90 can tighten.
- **Calibration that holds across regimes.** Pooling three holdouts did not help on fold B; shrinking the offsets towards a long-run value, or calibrating up and down quarters separately (the low-spike probability is over-forecast), are the next things to test, again on both folds.
- **Uncertainty on the deltas.** Paired intervals exist for the September forecasts we have (`reports/uncertainty.md`); add `v6_hf` and the August month, and repeat runs with different seeds.
- Outage messages from Nord Pool UMM: large fresh trips (above 800 MW) preceded the strongest spikes in training, but only 20 quarters (fetched, not used yet).
- Real-time Fingrid and weather data for the pre-June history rows, which are empty there now.
- With plant data from Turku Energia: move from "suggestions to review" to capacity-aware recommendations.
