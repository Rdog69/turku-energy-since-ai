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
| 7 Nov | **`v3_bmi_n50`**: `v3_bmi` with the median (P50) and its drivers taken from `v3_bmni` | + ICON-EU + Nordic (median only) | **41.21** | **11.88** | 0.796 | **0.0873** | 0.3902 | **Submitted model.** Nordic wind improved the median in both September and August and made the band worse in both, so it's used for the median only. vs `v3_bmi`: +0.09 % weighted by points (Sep), +0.45 % (Aug); band and probabilities unchanged. |

**Final vs baseline:** MAE −38 % (66.20 → 41.21), pinball −51 % (24.18 → 11.88), spike Brier −23 % (0.1132 → 0.0873), direction Brier −13 % (0.4509 → 0.3902). **Weighted by points (30/20/20/10): 34.3 % better** (`final_capw`: 32.8 %). Better than the baseline in all 4 weeks on all four metrics.

⚠ About 30 variants were compared on this one validation month, so expect the test period to come in somewhat worse.

## Second check: August

The same pipeline trained on June–July only (`--period fold_b`), forecasting every hour of August. Scored with the organisers' `score.py` against actuals rebuilt from the package (`src/backtest/actuals.py`; `tests/test_actuals.py` checks that the builder reproduces the official validation actuals exactly). Weeks from `weekly.py --period fold_b`.

| Model | MAE | Pinball | Coverage | Brier spikes | Brier direction |
|---|---|---|---|---|---|
| `split_all` | 28.39 | 7.10 | 0.764 | **0.0731** | 0.4461 |
| `final_capw` | 29.53 | 7.34 | 0.761 | 0.0882 | 0.4562 |
| `v3_bm` | 28.38 | 7.11 | 0.738 | 0.0768 | 0.4492 |
| `v3_bmi` | 28.32 | **7.01** | 0.732 | 0.0758 | 0.4458 |
| `v3_bmni` | **27.99** | 7.08 | 0.736 | **0.0730** | **0.4453** |
| **`v3_bmi_n50` (submitted)** | **27.99** | **7.01** | 0.732 | 0.0758 | 0.4458 |

- **Same fold as the teammates:** `final_capw` reproduces Abdo's August numbers exactly (29.53 / 7.34 / 0.0882 / 0.4562), and `split_all` is within 0.02 MAE of Pavlo's (28.41).
- **ICON holds:** `v3_bmi` vs `v3_bm` is better on all four metrics (+0.8 % weighted by points). ICON was chosen on September only, so this is a clean check.
- **Round 3 holds against `final_capw`:** better in all 5 weeks on all four metrics (+6.9 % weighted). Not fully independent: the tuning folds (26 Jul – 6 Sep) overlap August.
- **Nordic wind:** better median in 4 of 5 weeks; the band is worse overall because of one bad day (31 Aug). Same pattern as September, hence median only.
- ⚠ **The older `split_all` is about level with the final model on August** (−0.1 % weighted: better MAE and band, worse spikes). Part of the September gain since `split_all` is probably specific to September, so expect a smaller gain on the test month.
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
- **Not used: blending with a teammate's model.** A 50/50 blend of `v3_bm` with Abdo's best lab model (`brainstorming-abdo`, CAL INT4) scored about 41.2 / 11.75 / 0.0870 / 0.3800 (`weekly.py`). But that model trains part of its direction forecast on Fingrid history from Mar 2025 – May 2026, and the organisers' README says to train only on 1 Jun – 4 Oct 2026. It stays out unless the organisers approve. His history-free reference model made the blend worse in every week.
