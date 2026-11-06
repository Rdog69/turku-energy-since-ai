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
| 7 Nov | **`final_capw`**: `final` + weather averaged over 14 points weighted by installed wind capacity (OpenStreetMap turbines) | + OSM farms, 6 more weather points | **42.34** | 12.06 | 0.814 | **0.0900** | **0.3908** | **Submitted model.** vs `final`: direction better in 3/4 weeks, MAE and spikes 2/4, pinball slightly worse every week (+0.04). Weighted by points it comes out ahead. |

**Final vs baseline:** MAE −36 % (66.20 → 42.34), pinball −50 % (24.18 → 12.06), spike Brier −20 % (0.1132 → 0.0900), direction Brier −13 % (0.4509 → 0.3908).

⚠ About 20 variants were compared on this one validation month, so expect the test period to come in somewhat worse.

**Best vs baseline:** MAE −36 % (66.20 → 42.53), pinball −50 % (24.18 → 12.09), spike Brier −19 % (0.1132 → 0.0921), direction Brier −11 % (0.4509 → 0.4011).

⚠ Choosing the best of 11 variants on the validation period makes these numbers somewhat optimistic. The test period will tell.

### What each step added (for the reasoning chain)

| Step | MAE | Pinball | Spikes | Direction |
|---|---|---|---|---|
| Baseline → spot anchor | −21.9 | −9.2 | 0 | 0 |
| → LightGBM + calibration + product spikes (package) | −1.1 | −2.6 | −0.0193 | −0.0360 |
| → + weather runs | −0.1 | −0.3 | −0.0007 | −0.0060 |
| → + Fingrid real-time, first 2 h only | −0.6 | −0.1 | −0.0011 | −0.0077 |

## Takeaways so far

- **Anchoring on spot** is worth a third of the error, at no cost.
- **The model barely improves MAE beyond the anchor** (44.3 → 43.2). Package features tell us little about the size of the gap. Error grows only from 41.6 (hour 1) to 43.7 (hour 10), so recent state adds little. Better MAE needs new information (PLAN §0: E1 winter history, E2 frequency, E3 price spread), not a fancier model.
- **Calibration is where the points are.** It took the probability scores from a tie with the baseline to −17 % / −8 %, and coverage from 0.53 to 0.80.
- **Recency weighting helps MAE but hurts the probabilities.** It shrinks the effective training set, so the probability models get noisier.
- ⚠ **Calibration risk on the test run:** the 14-day holdout before the test (20 Sep – 4 Oct) was volatile, so the learned P90 offset is +28 to +36 €/MWh vs +14 to +21 for validation. That's either a correct adaptation to the autumn regime or overfitting to two noisy weeks. Next: a longer holdout or shrinking the offsets, checked week by week.
- **`top_drivers`** (from LightGBM's SHAP) is mostly consumption forecast, wind forecast and spot, consistent with findings 3–4.
- **Fresh data only helps where it's fresh.** Fingrid's real-time series (usable 30 min after each quarter, the organisers' own rule for measured data) transform hour 1 but are noise by hour 3. Giving them to a separate short-horizon model is what made them pay off.
- **Weather adds a little everywhere.** The day-ahead wind forecast in the package already captures most of the weather, and the revision since then is the extra information.
