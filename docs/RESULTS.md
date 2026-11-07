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
| 7 Nov | `split_all_rt`: `split_all` + live-imbalance features (Fingrid 198/186 surplus/deficit, production vs BRP plan, hydro change) in the short model only | + Fingrid 198/186/192/242/191 | 42.52 | 12.07 | 0.815 | 0.0918 | 0.4005 | Fold A. Small, consistent gain, all at steps 1-8 (long model identical). Hour 1: MAE 38.46 (was 38.52), direction 0.3431 (0.3471), spikes 0.0816 (0.0837). Hour 2: 41.05 / 0.3875 (41.07 / 0.3892). |
| 7 Nov | `split_all_rt_lean`: same, only `rt_sd_mean4`, `rt_plan_err`, `rt_plan_err_mean4`, `rt_hydro_change_1h` | same | 42.52 | 12.07 | 0.816 | 0.0920 | 0.4007 | Fold A. Same overall as `split_all_rt`; hour 1 slightly worse (direction 0.3469), hour 2 slightly better (MAE 40.97, direction 0.3848). No reason to prefer it. |
| 7 Nov | `split_all_icon`: `split_all` + ICON-EU wind index, ICON revision vs. day-ahead run, ECMWF-vs-ICON wind spread (both models, short and long) | + Fingrid RT + 2 weather models | **42.14** | **12.06** | 0.807 | 0.0923 | **0.3995** | Fold A: MAE −0.39, pinball −0.03, direction −0.012 vs `split_all`; spike Brier +0.0002 (noise). Small, consistent gain; coverage −0.007. |
| 7 Nov | `split_all_pcal`: `split_all` with pooled calibration (3 rolling 14-day holdouts) | + Fingrid RT + weather | 42.34 | 12.01 | 0.765 | 0.0907 | 0.3969 | Code removed when Frank's branch was merged (his calibration kept). Fold A: better on all four metrics, but coverage drops to 0.765. Fold B (row in the August table below): **worse** MAE, pinball and direction. **Rejected** (must beat the reference on both folds). |
| 7 Nov | **`split_all_rt_icon`**: ICON-EU in both models + live imbalance in the short model (`split_all_icon` + `split_all_rt`) | + Fingrid RT + 198/186/192/242/191 + 2 weather models | **42.14** | 12.06 | 0.808 | 0.0922 | **0.3978** | Fold A. vs `split_all`: MAE −0.39, pinball −0.03, direction −0.0033, spikes +0.0001 (noise). vs `split_all_icon`: same MAE and pinball, direction −0.0017. |
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
| 7 Nov | **`v6_hf`**: `v6_h` + a pricing-rule flag (`regime_2026` = 1 for deliveries from 1 Jun 2026, the package period) | + pre-June history | **40.67** | **11.19** | 0.771 | **0.0856** | **0.3892** | **Submitted model.** vs `v6_h`: +0.03 % (Sep; MAE better 4/4 weeks) and +0.15 % (Aug; spikes 5/5), with pinball slightly worse. A near tie, kept because it wins both months and encodes the rule change the organisers asked teams to account for. vs `v4_n50`: +2.29 % (Sep), +3.10 % (Aug). Coverage 0.77 is a little under the 80 % target, but the scored pinball loss is 5.8 % better. |
| 7 Nov | `split_all` **after merging Frank's code (feature order changed)**, rerun on `e22354b` | + Fingrid RT + weather | 42.71 | 12.17 | 0.810 | 0.0915 | 0.4011 | Fold A, exact: 42.7091 / 12.1718 / 0.8102 / 0.0915 / 0.4011. Before the merge: 42.53 / 12.09 / 0.814 / 0.0921 / 0.4011 (MAE +0.18, pinball +0.08, spikes −0.0006, direction unchanged). Passes `validate_submission.py`. Reference for the next row. |
| 7 Nov | `split_all_rt_icon` **after merging Frank's code (feature order changed)**, rerun on `e22354b` | + Fingrid RT + 198/186/192/242/191 + 2 weather models | 42.41 | 12.07 | 0.816 | 0.0916 | 0.3977 | Fold A, exact: 42.4092 / 12.0671 / 0.8162 / 0.0916 / 0.3977. Before the merge: 42.14 / 12.06 / 0.808 / 0.0922 / 0.3978 (MAE +0.27, pinball +0.01, coverage +0.008, spikes −0.0006). Passes `validate_submission.py`. Still better than the rerun `split_all` on every metric except coverage (MAE −0.30, pinball −0.10, spikes +0.0001, direction −0.0034). |

**History rows (round 6):** a package-format table built by Abdo's `experiments/lab/build_history.py` (`brainstorming-abdo`):
- **Inputs:** Fingrid's package series, the spot price from Elering and the calendar.
- **Target:** the imbalance price recomputed with the 1 June 2026 volume-weighted rule. It matches the official price on 99.5 % of Jun–Oct 2026 quarters (his `SOURCES.md` §11).
- **Leak safety:** `src/data/load.py` (`load_history`) makes every measured row usable no earlier than the package's own rule for that minute of the hour. A truncation leak test covers history origins (`tests/test_availability.py`).
- **Missing before June:** ENTSO-E neighbour series, weather runs and Fingrid real-time data. Their features are empty on history rows.
- **P(none)** is still taken from June onwards only.

**Final vs baseline:** MAE −39 % (66.20 → 40.67), pinball −54 % (24.18 → 11.19), spike Brier −24 % (0.1132 → 0.0856), direction Brier −14 % (0.4509 → 0.3892). **Weighted by points (30/20/20/10): 35.7 % better** (`v4_n50`: 34.4 %, `final_capw`: 32.8 %). Better than the baseline in all 4 weeks on all four metrics.

⚠ About 37 variants were compared on this one validation month, so expect the test period to come in somewhat worse. Since round 3, every change also had to win on August (below).

## Second check: August

The same pipeline trained on June–July only (`--period fold_b`), forecasting every hour of August. Scored with the organisers' `score.py` against actuals rebuilt from the package (`src/backtest/actuals.py`; `tests/test_actuals.py` checks that the builder reproduces the official validation actuals exactly). Weeks from `weekly.py --period fold_b`.

| Model | MAE | Pinball | Coverage | Brier spikes | Brier direction |
|---|---|---|---|---|---|
| `split_all` (Frank's run) | 28.39 | 7.10 | 0.764 | **0.0731** | 0.4461 |
| `split_all` (Pavlo's run, reference for the rows below) | 28.41 | 7.10 | 0.766 | 0.0750 | 0.4491 |
| `split_all_rt` (Pavlo) | 28.41 | 7.10 | 0.765 | 0.0732 | 0.4480 |
| `split_all_icon` (Pavlo) | 28.11 | 6.99 | 0.758 | 0.0738 | 0.4445 |
| `split_all_rt_icon` (Pavlo) | 28.02 | 6.97 | 0.760 | 0.0741 | 0.4443 |
| `split_all_rt_icon` (Pavlo), **after merging Frank's code (feature order changed)** | 27.99 | 7.03 | 0.748 | 0.0749 | 0.4441 |
| `split_all_pcal` (Pavlo, rejected) | 28.67 | 7.14 | 0.782 | 0.0738 | 0.4559 |
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
| **`v6_hf` (submitted)** | **27.74** | 6.59 | 0.770 | **0.0680** | **0.4388** |

- **Pavlo's August runs** (rows marked Pavlo; run 7 Nov before Frank's rounds 3–6 were merged, cutoff 1 Aug, trained on Jun–Jul only):
  - **`split_all` (reference):** the fold-B reference for every later comparison of Pavlo's variants.
  - **`split_all_rt`** (+ Fingrid 198/186/192/242/191 in the short model): spikes −0.0018 and direction −0.0011 vs the reference (same sign as September), MAE and pinball unchanged. Hour 1: MAE 25.04, spikes 0.0628, direction 0.3895; hour 2: 26.66, 0.0658, 0.4289.
  - **`split_all_icon`** (+ ICON-EU, both models; + Fingrid RT + 2 weather models): better than the reference on MAE, pinball and both Briers; coverage −0.008. Same sign as September, so the ICON gain is not a one-window fluke, though small.
  - **`split_all_rt_icon`** (ICON-EU in both models + live imbalance in the short model): better than the reference on all four metrics (MAE −0.39, pinball −0.13, spikes −0.0009, direction −0.0048); vs `split_all_icon`: MAE −0.09, pinball −0.02. **Best of Pavlo's branch** (`v6_hf` is better on both folds).
  - **`split_all_rt_icon` after the merge** (rerun on `e22354b`, exact: 27.9925 / 7.0325 / 0.7476 / 0.0749 / 0.4441): MAE −0.03, spikes +0.0008 and coverage −0.012 against the row above; pinball +0.065. Passes `validate_submission.py`.
  - **`split_all_pcal`** (pooled calibration over 3 rolling 14-day holdouts): better on every September metric but **worse** on August MAE, pinball and direction, so rejected (a change must beat the reference on both folds).
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
- **Live imbalance adds little on top of the Fingrid real-time set.** The measured surplus/deficit (dataset 198/186) has near-zero rank correlation with the next hour's gap (|rho| below 0.05) and a non-monotone link to the up-regulation share (training data, steps 1-4); the sign convention is unverified, so the briefing states only its size. Production vs the BRP plan is similarly weak. Hydro output change over 1 h is the one clear signal (up-regulation share 0.26 in the lowest quintile, 0.54 in the highest; rho +0.19), and it carries most of the small fold-A gain.
- Fold A gain of `split_all_rt` over `split_all` is about 0.01 MAE, 0.012 pinball, 0.0003 spike Brier and 0.0006 direction Brier overall, and 0.04 / 0.004 in hour-1 direction: consistent in sign across all metrics, but small enough to be noise (no seed repeats were run), so confirm on fold B before relying on it.
- Coverage of all seven new features is 100 % in the training, validation and test windows (the series have no gaps).
- **A second weather model helps a little.** ICON-EU (runs 25 May - 2 Nov, usable 5 h after init) added to ECMWF: fold A MAE 42.53 -> 42.14, direction Brier 0.4011 -> 0.3995, pinball 12.09 -> 12.06. The gain is small (about 1 %), spike Brier is unchanged and coverage drops 0.007, so the model-spread idea (wider band when the models disagree) is only weakly visible in pinball.
- Fold B confirms the direction of the fold-A result: the live-imbalance features leave MAE and pinball unchanged and improve the spike Brier (0.0750 to 0.0732) and the direction Brier (0.4491 to 0.4480) slightly. Real, but small; it is not the reason to expect a big jump on the test period.
- **Pooled calibration is not robust.** Averaging the calibration over three rolling 14-day holdouts improved every fold-A metric but made fold B worse on MAE, pinball and direction, and pulled fold-A coverage down to 0.765. The single last-14-days holdout stays.
- **Best of Pavlo's branch: `split_all_rt_icon`.** Superseded by Frank's `v6_hf`. Among the `split_all` variants it is the only one that beats `split_all` on both folds on MAE, pinball and direction (spike Brier is flat on fold A, better on fold B). Each added group gives about 1 %; together they compound only slightly, which fits the picture that the package already captures most of what is predictable.
- **Merging Frank's code moved our scores a little (feature order changed).** On `e22354b`, `split_all` on fold A is 42.71 MAE (was 42.53) and `split_all_rt_icon` is 42.41 / 12.07 on fold A (was 42.14 / 12.06) and 27.99 / 7.03 on fold B (was 28.02 / 6.97). The ranking inside our branch holds (`split_all_rt_icon` still beats `split_all` on fold A), and the direction Brier is unchanged to the third decimal, but the MAE gain over `split_all` shrank from 0.39 to 0.30 and fold-B pinball got worse. LightGBM column sampling depends on the column order, which Frank's code changed; we did not check other causes. The earlier rows above are the pre-merge numbers.
- **Test run of `split_all_rt_icon`** (trained on everything published by 5 Oct 00:00): passes `validate_submission.py`, 26,920 rows, every `data_cutoff_utc` at or before its origin. The learned P90 offsets are +18 €/MWh (short model) and +38 to +44 (long model), wider than on validation, so the calibration risk above still applies.
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
