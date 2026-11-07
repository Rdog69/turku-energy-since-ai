# Results log

Validation period 7 Sep – 4 Oct 2026 (672 origins, 26,700 scored rows), scored with the organisers' `score.py` 0.1.1, spike margin 50. Lower is better everywhere. Each row is one model run. This log becomes the step-by-step comparison (ablation table) in the evaluation report.

| Date | Model | Data | MAE | Pinball (p10/p90 mean) | Coverage | Brier spikes | Brier direction | Notes |
|---|---|---|---|---|---|---|---|---|
| 6 Nov | Organisers' baseline (persistence) | package | 66.20 | 24.18 | 0.683 | 0.1132 | 0.4509 | Reproduced exactly with `baseline.ipynb` |
| 6 Nov | `spot_anchor`: spot + constant gap quantiles; training shares for the probabilities | package | 44.29 | 14.99 | 0.675 | 0.1132 | 0.4508 | Accuracy −33 %, calibration −38 % vs baseline. Probabilities **tie the baseline**, so they would earn 0 points. |
| 6 Nov | `gbm`: LightGBM quantiles on the gap + up classifier + direct spike classifiers | package | 43.23 | 13.30 | 0.527 | 0.1063 | 0.4225 | Intervals far too narrow (coverage 0.53). |
| 6 Nov | `gbm_recency`: + recency weights (τ = 30 days) | package | 42.96 | 13.70 | 0.509 | 0.1078 | 0.4401 | Slightly better MAE; worse everything else. |
| 6 Nov | `gbm_cal`: + calibration on the last 14 training days (Platt for probabilities, offsets per step band for quantiles) | package | **42.89** | 12.76 | 0.790 | 0.0971 | 0.4256 | Calibration fixes coverage and the spike score. |
| 6 Nov | `gbm_cal_product`: + spikes = P(direction) × P(tail \| direction) | package | **42.89** | 12.76 | 0.790 | 0.0945 | 0.4256 | Product form beats direct spike models (finding 11 holds). |
| 6 Nov | `gbm_cal_product_norecency`: same, without recency weights | package | 43.22 | 12.44 | 0.802 | 0.0939 | 0.4148 | Best package-only model. |
| 6 Nov | `gbm_fingrid`: + Fingrid real-time wind, nuclear, frequency, consumption, at every step | + Fingrid RT | 43.43 | 12.52 | 0.773 | 0.0944 | 0.4204 | **Worse.** Helps hour 1 (direction 0.4076 → 0.3904), hurts hours 3–10: the model fits noise on a stale signal. |
| 6 Nov | `gbm_fingrid_early`: same, real-time features hidden after step 8 | + Fingrid RT | 42.86 | 12.38 | 0.810 | 0.0947 | 0.4154 | Better MAE; direction still worse after hour 2. |
| 6 Nov | `split_fingrid`: separate models, steps 1–8 with Fingrid RT, steps 9–40 package-only | + Fingrid RT | 42.95 | 12.31 | 0.797 | 0.0927 | 0.4058 | Hour 1: MAE 41.5 → 39.4, direction 0.408 → 0.342, spikes 0.091 → 0.082. |
| 6 Nov | `gbm_weather`: package + ECMWF weather runs (wind index, revision vs. the day-ahead run, temperature, icing) | + weather | 43.08 | 12.19 | 0.816 | 0.0932 | 0.4088 | Weather helps every metric. |
| 6 Nov | `split_all`: steps 1–8 with Fingrid RT + weather, steps 9–40 with weather | + Fingrid RT + weather | 42.53 | 12.09 | 0.814 | 0.0921 | 0.4011 | Best on all four metrics at the time. |
| 7 Nov | `split_all_rt2`: + 10 more Fingrid RT series in the short model (hydro, electric boilers, net import, flows, CHP) | + Fingrid RT2 | 42.62 | 12.12 | 0.815 | 0.0912 | 0.4000 | Better spikes and direction, slightly worse MAE. |
| 7 Nov | `split_all_seeds`: `split_all` with 5-seed averaging | same | 42.44 | 12.14 | 0.810 | 0.0917 | 0.3998 | |
| 7 Nov | `split_all_rt2_seeds`: both | + Fingrid RT2 | 42.37 | 12.09 | 0.813 | 0.0913 | 0.3983 | Beats `split_all` in 3/4 weeks on MAE, 4/4 spikes, 3/4 direction, 2/4 pinball. |
| 7 Nov | `split_all_h21` / `split_all_h28`: `split_all` re-tuned on the last 21 / 28 days instead of 14 | same | 42.56 / 42.54 | 12.15 / 12.07 | 0.845 / 0.813 | 0.0918 / 0.0904 | 0.3961 / 0.3961 | 28 days is better and steadier: the test-period P90 offset is +27…+30 instead of +28…+36. |
| 7 Nov | `final`: `split_all_rt2_seeds` + 28-day re-tuning | + Fingrid RT2 | 42.38 | **12.01** | 0.817 | 0.0905 | 0.3938 | |
| 7 Nov | `final_capw`: `final` + weather averaged over 14 points weighted by installed wind capacity (OpenStreetMap turbines) | + OSM farms, 6 more weather points | 42.34 | 12.06 | 0.814 | 0.0900 | 0.3908 | Submitted model until round 3. vs `final`: direction better in 3/4 weeks, MAE and spikes 2/4, pinball slightly worse every week (+0.04). Weighted by points it comes out ahead. |
| 7 Nov | `final_tuned`: `final_capw` with smaller, slower trees (15 leaves, ≥ 800 rows per leaf, learning rate 0.03, 300 trees, 60 % of features per tree), picked on 3 training-only folds (26 Jul – 6 Sep, `src/models/tune.py`) | same | 41.82 | 11.90 | 0.802 | 0.0886 | 0.3899 | vs `final_capw`: MAE better 4/4 weeks, pinball 3/4, spikes 3/4, direction 2/4. |
| 7 Nov | `final_tuned_long`: tuned settings in the long model only | same | 41.82 | 11.89 | 0.804 | 0.0886 | 0.3910 | Same accuracy; direction 2/4 weeks. |
| 7 Nov | `v3_xm`: `final_capw` + 4-hour memory (mean gap and direction over the last 16 usable quarters) | same | 42.48 | 12.08 | 0.812 | 0.0894 | 0.3895 | Untuned: MAE and pinball slightly worse, probabilities slightly better. |
| 7 Nov | `v3_bm`: tuned trees in both models + 4-hour memory | same | 41.68 | 11.90 | 0.800 | 0.0880 | 0.3888 | vs `final_tuned`: spikes better 4/4 weeks, direction 3/4, MAE 2/4. Memory pays off once the trees are regularised. |
| 7 Nov | `v3_lm`: tuned long model + memory | same | 41.67 | 11.89 | 0.803 | 0.0882 | 0.3902 | Ties `v3_bm`; `v3_bm` is slightly better on spikes and direction. |
| 7 Nov | `v3_bmn` / `v3_lmn`: + wind at 12 points in Sweden, Norway, Denmark and Estonia (ECMWF) | + Nordic weather | 41.52 / 41.49 | 12.04 / 12.04 | 0.803 / 0.805 | 0.0888 / 0.0887 | 0.3883 / 0.3889 | **Rejected.** vs `v3_bm`: MAE better in 2/4 weeks, but pinball and spikes worse in 3/4. About 0.35 % worse weighted by points. |
| 7 Nov | `v3_bmi`: `v3_bm` + a second weather model, DWD ICON-EU (wind index, its revision since the day-ahead forecast, ECMWF–ICON disagreement), ported from Pavlo's `split_all_icon` | + ICON-EU | 41.31 | **11.88** | 0.796 | **0.0873** | 0.3902 | vs `v3_bm`: MAE better 4/4 weeks, spikes 3/4, pinball 2/4, direction 1/4. About 0.5 % better weighted by points; also better on all four metrics in August (below). |
| 7 Nov | `v3_bmni`: `v3_bmi` + Nordic weather | + ICON-EU + Nordic | 41.21 | 12.02 | 0.801 | 0.0879 | 0.3885 | Not used as a whole. vs `v3_bmi`: MAE better in 2/4 weeks, pinball worse in all 4, spikes worse 3/4. About 0.3 % worse weighted by points here, 1.1 % better in August. |
| 7 Nov | `v3_bmi_n50`: `v3_bmi` with the median (P50) and its drivers taken from `v3_bmni` | + ICON-EU + Nordic (median only) | 41.21 | 11.88 | 0.796 | 0.0873 | 0.3902 | Submitted model in round 3. Nordic wind improved the median in both September and August and made the band worse in both, so it's used for the median only. vs `v3_bmi`: +0.09 % weighted by points (Sep), +0.45 % (Aug); band and probabilities unchanged. |
| 7 Nov | `v4_eb`: `v3_bmi` with the spike calibration shrunk toward the uncalibrated model when the calibration window holds few spike quarters (s = m / (m + 50); idea from Abdo's `calib_eb.py`) | same | 41.31 | 11.88 | 0.796 | 0.0869 | 0.3902 | **Kept.** Only the spike probabilities change: better in 4/4 weeks (Sep, +0.12 % weighted) and 5/5 (Aug, spike Brier −6 %, +1.49 %). In August the plain calibration, learned on a quiet July, had cut the high-spike probability to 2.3 % against 10.5 % observed. |
| 7 Nov | `v4_b4`: a separate model for steps 1–4 inside the short model | same | 41.32 | 11.89 | 0.794 | 0.0871 | 0.3893 | Dropped. +0.05 % (Sep) and +0.08 % (Aug) weighted, but MAE and pinball slightly worse in most weeks. A tie, so the simpler model stays. |
| 7 Nov | `v4_wh`: + learned wind production: non-negative weights for 22 weather points (ECMWF and ICON) fitted to Fingrid's measured wind (dataset 181, data published before the cutoff only). Features: the predicted production, its gap to the day-ahead forecast, and its revision since then | + Fingrid 181 for the fit | 41.26 | 11.88 | 0.797 | 0.0874 | 0.3899 | **Kept.** MAE better in 3/4 weeks (Sep) and 4/5 (Aug); +0.02 % and +0.66 % weighted. On its own the learned map is cruder than Fingrid's day-ahead forecast (564 vs 321 MW error 5 h ahead in September), but it adds information next to it. |
| 7 Nov | **`v4_n50`**: `v3_bmi_n50` with both kept changes in both of its models | + learned wind production | **41.08** | **11.88** | 0.797 | **0.0871** | **0.3899** | **Submitted model.** vs `v3_bmi_n50`: +0.19 % weighted (Sep; MAE better 3/4 weeks), +1.58 % (Aug; spikes better 5/5 weeks). |
| 7 Nov | `v5_sol`: `v4_n50` + solar revision at 8 towns (ECMWF shortwave radiation vs the run behind Fingrid's day-ahead solar forecast, also scaled to MW) | + town weather | 41.08 | 11.91 | 0.795 | 0.0872 | 0.3903 | Not kept. −0.08 % (Sep) and −0.01 % (Aug) weighted by points: no effect, even in sunny August. |
| 7 Nov | `v5_tmp`: `v4_n50` + town temperature and its revision since the day-ahead consumption forecast (heating demand) | + town weather | 41.05 | 11.87 | 0.794 | 0.0870 | 0.3866 | Not kept. +0.20 % (Sep; direction better in 3/4 weeks) but −0.20 % (Aug). See the August section. |
| 7 Nov | `v5_st`: both | + town weather | 41.03 | 11.90 | 0.795 | 0.0868 | 0.3865 | Not kept. +0.21 % (Sep) but −0.16 % (Aug). |
| 7 Nov | `v6_h`: `v4_n50` also trained on 15 months before the package (5 Mar 2025 – 31 May 2026, every 3rd hourly origin; 238k training rows instead of 94k). The organisers allowed pre-June data on 7 Nov (`QUESTIONS.md` Q1) | + pre-June history | 40.74 | 11.19 | 0.770 | 0.0855 | 0.3890 | vs `v4_n50`: +2.26 % weighted by points (Sep; pinball better 4/4 weeks, MAE 3/4), +2.96 % (Aug; pinball 5/5, direction 5/5, MAE 4/5, spikes 4/5). |
| 7 Nov | `v6_hf`: `v6_h` + a pricing-rule flag (`regime_2026` = 1 for deliveries from 1 Jun 2026, the package period) | + pre-June history | 40.67 | 11.19 | 0.771 | 0.0856 | 0.3892 | Submitted model in round 6. vs `v6_h`: +0.03 % (Sep; MAE better 4/4 weeks) and +0.15 % (Aug; spikes 5/5), with pinball slightly worse. A near tie, kept because it wins both months and encodes the rule change the organisers asked teams to account for. vs `v4_n50`: +2.29 % (Sep), +3.10 % (Aug). Coverage 0.77 is a little under the 80 % target, but the scored pinball loss is 5.8 % better. |

**History rows (round 6):** a package-format table built by Abdo's `experiments/lab/build_history.py` (`brainstorming-abdo`):
- **Inputs:** Fingrid's package series, the spot price from Elering and the calendar.
- **Target:** the imbalance price recomputed with the 1 June 2026 volume-weighted rule. It matches the official price on 99.5 % of Jun–Oct 2026 quarters (his `SOURCES.md` §11).
- **Leak safety:** `src/data/load.py` (`load_history`) makes every measured row usable no earlier than the package's own rule for that minute of the hour. A truncation leak test covers history origins (`tests/test_availability.py`).
- **Missing before June:** ENTSO-E neighbour series, weather runs and Fingrid real-time data. Their features are empty on history rows.
- **P(none)** is still taken from June onwards only.

**Round 7 (7 Nov), each change on top of `v6_hf`, weighted by points (Sep / Aug):**

| Model | Change | MAE | Pinball | Coverage | Spikes | Direction | Verdict |
|---|---|---|---|---|---|---|---|
| `v7_runs` | Direction runs, 24-hour shares, same quarter yesterday (after Abdo's "runs") | 40.82 | 11.30 | – | 0.0861 | 0.3907 | Dropped: −0.57 % / +0.35 %, worse on all four in September. |
| `v7_w` | History rows at half weight | 40.64 | 11.25 | – | 0.0864 | 0.3888 | Dropped: −0.33 % / −0.98 %. |
| `v7_all` | Every hourly history origin (3× the history rows) | 40.64 | 11.15 | – | 0.0846 | 0.3858 | Dropped: +0.51 % / −0.68 %; August spikes 3.2 % worse. |
| **`v7_rt`** | Fingrid real-time series on the history rows too (all 14 ids, Mar 2025 – May 2026, same 30-min rule) | **40.64** | 11.20 | 0.787 | **0.0855** | 0.3892 | **Submitted model.** +0.02 % / +0.19 %: a near tie that wins both months (MAE better in 3/4 and 3/5 weeks). |

**Round 8 (7 Nov), on top of `v7_rt`, weighted by points (Sep / Aug):**
- **`v8_imb`, Fingrid real-time surplus/deficit (198, 186) in the hours 1–2 model** (30-min rule, history rows included): +0.01 % / −0.01 %. No effect; our other real-time series already carry the signal. Dropped.
- **`v8_thr`, distance from the newest mFRR up/down prices to the spike thresholds (spot ± 50)**: −0.03 % / −0.80 %. August spikes got 2.8 % worse. Dropped.
- **`v8_both`**: −0.03 % / −0.79 %. Dropped.

**Team candidate (7 Nov evening): ½ `v7_rt` + ½ Abdo's `h_int4ss`**, equal weights on all eight outputs. Officially scored: Sep 40.19 / 11.07 / 0.0840 / 0.3799, Aug 27.05 / 6.22 / 0.0648 / 0.4202. That is 36.7 % / 29.0 % better than the baseline (average 32.8 %, the best on the team scoreboard). Files and checksums are in `submissions/MANIFEST.md`.

**Final vs baseline (`v7_rt` alone):** MAE −39 % (66.20 → 40.64), pinball −54 % (24.18 → 11.20), spike Brier −24 % (0.1132 → 0.0855), direction Brier −14 % (0.4509 → 0.3892). **Weighted by points (30/20/20/10): 35.7 % better** (`v4_n50`: 34.4 %, `final_capw`: 32.8 %).

⚠ About 41 variants were compared on this one validation month, so expect the test period to come in somewhat worse. Since round 3, every change also had to win on August (below).

## Second check: August

The same pipeline trained on June–July only (`--period fold_b`), forecasting every hour of August. Scored with the organisers' `score.py` against actuals rebuilt from the package (`src/backtest/actuals.py`; `tests/test_actuals.py` checks that the builder reproduces the official validation actuals exactly). Weeks from `weekly.py --period fold_b`.

| Model | MAE | Pinball | Coverage | Brier spikes | Brier direction |
|---|---|---|---|---|---|
| `split_all` | 28.39 | 7.10 | 0.764 | **0.0731** | 0.4461 |
| `final_capw` | 29.53 | 7.34 | 0.761 | 0.0882 | 0.4562 |
| `v3_bm` | 28.38 | 7.11 | 0.738 | 0.0768 | 0.4492 |
| `v3_bmi` | 28.32 | **7.01** | 0.732 | 0.0758 | 0.4458 |
| `v3_bmni` | **27.99** | 7.08 | 0.736 | **0.0730** | **0.4453** |
| `v3_bmi_n50` | **27.99** | 7.01 | 0.732 | 0.0758 | 0.4458 |
| `v4_eb` | 28.32 | 7.01 | 0.732 | 0.0713 | 0.4458 |
| `v4_b4` | 28.33 | 7.02 | 0.731 | 0.0755 | **0.4450** |
| `v4_wh` | 28.19 | **7.00** | 0.738 | 0.0744 | 0.4466 |
| `v4_n50` (round 4) | 27.99 | 7.00 | 0.738 | 0.0710 | 0.4466 |
| `v5_sol` | 27.94 | 7.01 | 0.732 | 0.0712 | 0.4464 |
| `v5_tmp` | 28.08 | 7.03 | 0.734 | 0.0709 | 0.4473 |
| `v5_st` | 27.98 | 7.05 | 0.736 | 0.0710 | 0.4470 |
| `v6_h` | 27.77 | **6.57** | 0.771 | 0.0684 | 0.4390 |
| `v6_hf` | 27.74 | 6.59 | 0.770 | **0.0680** | 0.4388 |
| `v7_runs` | 27.93 | **6.47** | – | 0.0678 | 0.4364 |
| `v7_w` | 27.95 | 6.69 | – | 0.0686 | 0.4410 |
| `v7_all` | 27.78 | 6.58 | – | 0.0702 | **0.4336** |
| **`v7_rt` (submitted)** | **27.67** | 6.56 | 0.769 | **0.0680** | 0.4378 |

- **Same fold as the teammates:** `final_capw` reproduces Abdo's August numbers exactly (29.53 / 7.34 / 0.0882 / 0.4562), and `split_all` is within 0.02 MAE of Pavlo's (28.41).
- **ICON holds:** `v3_bmi` vs `v3_bm` is better on all four metrics (+0.8 % weighted by points). ICON was chosen on September only, so this is a clean check.
- **Round 3 holds against `final_capw`:** better in all 5 weeks on all four metrics (+6.9 % weighted). Not fully independent: the tuning folds (26 Jul – 6 Sep) overlap August.
- **Nordic wind:** better median in 4 of 5 weeks; the band is worse overall because of one bad day (31 Aug). Same pattern as September, hence median only.
- **The submitted model vs `final_capw`:** better in all 5 weeks on all four metrics (+8.2 % weighted by points).
- **Town weather (round 5) doesn't pass:**
  - **Solar revision:** no effect in either month.
  - **Temperature revision:** helps September (+0.20 %, mostly direction; the coldest week gains most) but hurts every August week (−0.20 %), so it isn't kept.
  - **The heating mechanism isn't visible in the training data yet.** A colder-than-planned forecast doesn't line up with higher-than-planned consumption from June to September (correlation +0.10 in September, the wrong sign for heating). Only the first four days of October show the heating pattern (−0.32), too little to rely on.
  - The switch (`town_temp=True` in `make_final`) is ready if the heating season makes it worth a bet.
- **Pre-June history (round 6) passes clearly:** +3.1 % weighted by points on August against +2.3 % on September. The band improves in all 5 August weeks, and direction does too. August gains more because its own training window is only June–July, so 15 more months matter most there.
- ⚠ **The older `split_all` stays close on August.** Before the round-4 spike fix it was level with our model (`v3_bmi_n50`: −0.1 % weighted, worse spikes). The submitted `v4_n50` beats it by +1.5 % (better MAE, band and spikes), but that's far below September's gap. Part of the September gain since `split_all` is probably specific to September, so expect a smaller gain on the test month.
- Every model's error is lower in August (MAE about 28 vs 41 in September): it was a calmer month.

### What each step added (for the reasoning chain)

| Step | MAE | Pinball | Spikes | Direction |
|---|---|---|---|---|
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

## Takeaways so far

- **Anchoring on spot** is worth a third of the error, at no cost.
- **The model barely improves MAE beyond the anchor** (44.3 → 43.2). Package features tell us little about the size of the gap. Error grows only from 41.6 (hour 1) to 43.7 (hour 10), so recent state adds little. Better MAE needs new information (PLAN §0: E1 winter history, E2 frequency, E3 price spread), not a fancier model.
- **Calibration is where the points are.** It took the probability scores from a tie with the baseline to −17 % / −8 %, and coverage from 0.53 to 0.80.
- **Recency weighting helps MAE but hurts the probabilities.** It shrinks the effective training set, so the probability models get noisier.
- ⚠ **Calibration risk on the test run:** the 14-day holdout before the test (20 Sep – 4 Oct) was volatile, so the learned P90 offset is +28 to +36 €/MWh vs +14 to +21 for validation. That's either a correct adaptation to the autumn regime or overfitting to two noisy weeks. Next: a longer holdout or shrinking the offsets, checked week by week.
- **`top_drivers`** (from LightGBM's SHAP) is mostly consumption forecast, wind forecast and spot, consistent with findings 3–4.
- **Fresh data only helps where it's fresh.** Fingrid's real-time series (usable 30 min after each quarter, the organisers' own rule for measured data) transform hour 1 but are noise by hour 3. Giving them to a separate short-horizon model is what made them pay off.
- **Weather adds a little everywhere.** The day-ahead wind forecast in the package already captures most of the weather, and the revision since then is the extra information.
- **Smaller, slower trees are a consistent accuracy win** (MAE better in all 4 weeks). The settings were picked on training-only folds, not on the validation month.
- **A second weather model helps everywhere.** ICON-EU next to ECMWF improved MAE in every September week and all four metrics in August.
- **Neighbouring countries' wind helps the median, not the band.** In both September and August it improved MAE but made the P10–P90 band worse. Extra inputs barely move the median, which has lots of data behind it, but give the tail models more noise to chase. So the final model uses it for the median only.
- **A calibration window with few events needs shrinking.** Platt scaling learned on a quiet month can switch spike warnings almost off for the next, busier one. Shrinking the correction by how many spike quarters the window actually held fixed August (−6 % spike Brier) and still helped September.
- **Learned wind production helps a little, even though it's cruder than Fingrid's own day-ahead forecast.** It adds information next to that forecast rather than replacing it.
- **Solar adds nothing beyond Fingrid's day-ahead solar forecast, and temperature is a bet on the heating season.** Solar is small next to wind (85 MW vs 3,787 MW on average in October, by Fingrid's day-ahead forecasts in the starter package), and radiation revisions didn't help even in August. Temperature revisions helped only in September.
- **History is the biggest single gain since round 3, and it lands mostly on the band.** Pinball improved about 6 % in both months; MAE, spikes and direction gained less.

## Abdo's models on the same footing (7 Nov)

Abdo's committed validation files (`brainstorming-abdo`, `submissions/`), scored with the organisers' `score.py` here. His model also trains on pre-June history (`hist_blend` 0.6), which the organisers now allow. August numbers are from his lab scorer; it reproduces our official August scores for `v4_n50` exactly. His August forecasts aren't in git, so we couldn't rescore them.

| Model | Sep: MAE / pinball / spikes / direction | vs `v6_hf`, weighted (Sep) | vs `v6_hf`, weighted (Aug) |
|---|---|---|---|
| **`v6_hf` (ours)** | **40.67 / 11.19 / 0.0856 / 0.3892** | – | – |
| His best single model `P2 INT4+ss lgb7` | 41.52 / 11.65 / 0.0888 / 0.3874 | −2.7 % | +1.5 % |
| `team5050`: ½ `v4_n50` + ½ his model | 40.97 / 11.63 / 0.0861 / 0.3803 | −1.1 % | +1.1 % |
| ½ `v6_h` + ½ his model | 40.72 / 11.26 / 0.0851 / 0.3797 | +0.3 % (vs `v6_h`) | not checked |

+ = better than `v6_hf`.
- **Each side wins one month.**
  - **September, ours:** better MAE, band and spikes, with the band better in all 4 weeks against both of his files.
  - **August, his:** better MAE, spikes and direction; the band is a tie.
- **A 50/50 blend with `v6_h` adds little on September** (+0.3 %): direction improves, the band gets worse. August is the open question. His model is stronger there, so a blend might help, but it can't be checked without his August forecasts.
- **Later on 7 Nov, Abdo's `team_hist`** (half `v4_n50`, half his history-mode model) reported 40.19 / 11.26 / 0.0846 / 0.3789 (Sep) and 27.12 / 6.29 / 0.0657 / 0.4243 (Aug) from his lab scorer, commit d85191f. That would be 36.4 % and 28.4 % better than the baseline, against 35.7 % and 26.2 % for `v7_rt`. Not rescored: only its test file is committed. The team scoreboard (`scoreboard/` on main) ranks every model on both months.
