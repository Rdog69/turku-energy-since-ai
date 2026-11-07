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
| 6 Nov | **`split_all`**: steps 1–8 with Fingrid RT + weather, steps 9–40 with weather | + Fingrid RT + weather | **42.53** | **12.09** | 0.814 | **0.0921** | **0.4011** | **Current best on all four metrics.** |
| 7 Nov | `split_all_rt`: `split_all` + live-imbalance features (Fingrid 198/186 surplus/deficit, production vs BRP plan, hydro change) in the short model only | + Fingrid 198/186/192/242/191 | 42.52 | 12.07 | 0.815 | 0.0918 | 0.4005 | Fold A. Small, consistent gain, all at steps 1-8 (long model identical). Hour 1: MAE 38.46 (was 38.52), direction 0.3431 (0.3471), spikes 0.0816 (0.0837). Hour 2: 41.05 / 0.3875 (41.07 / 0.3892). |
| 7 Nov | `split_all_rt_lean`: same, only `rt_sd_mean4`, `rt_plan_err`, `rt_plan_err_mean4`, `rt_hydro_change_1h` | same | 42.52 | 12.07 | 0.816 | 0.0920 | 0.4007 | Fold A. Same overall as `split_all_rt`; hour 1 slightly worse (direction 0.3469), hour 2 slightly better (MAE 40.97, direction 0.3848). No reason to prefer it. |
| 7 Nov | `split_all_icon`: `split_all` + ICON-EU wind index, ICON revision vs. day-ahead run, ECMWF-vs-ICON wind spread (both models, short and long) | + Fingrid RT + 2 weather models | **42.14** | **12.06** | 0.807 | 0.0923 | **0.3995** | Fold A: MAE −0.39, pinball −0.03, direction −0.012 vs `split_all`; spike Brier +0.0002 (noise). Small, consistent gain; coverage −0.007. |
| 7 Nov | `split_all_icon` (**fold B**, August, cutoff 1 Aug) | + Fingrid RT + 2 weather models | **28.11** | **6.99** | 0.758 | **0.0738** | **0.4445** | Fold B vs `split_all` (28.41 / 7.10 / 0.766 / 0.0750 / 0.4491): better on MAE, pinball, both Briers; coverage −0.008. Same sign as fold A, so the ICON gain is not a one-window fluke, though small. |
| 7 Nov | `split_all_rt` on **fold B** (August, trained on Jun-Jul only) | + Fingrid 198/186/192/242/191 | 28.41 | 7.10 | 0.765 | 0.0732 | 0.4480 | Fold B. `split_all` reference: 28.41 / 7.10 / 0.766 / 0.0750 / 0.4491. Spikes -0.0018 and direction -0.0011 (same sign as fold A), MAE and pinball unchanged. Hour 1: MAE 25.04, spikes 0.0628, direction 0.3895; hour 2: 26.66, 0.0658, 0.4289. |

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
- **Live imbalance adds little on top of the Fingrid real-time set.** The measured surplus/deficit (dataset 198/186) has near-zero rank correlation with the next hour's gap (|rho| below 0.05) and a non-monotone link to the up-regulation share (training data, steps 1-4); the sign convention is unverified, so the briefing states only its size. Production vs the BRP plan is similarly weak. Hydro output change over 1 h is the one clear signal (up-regulation share 0.26 in the lowest quintile, 0.54 in the highest; rho +0.19), and it carries most of the small fold-A gain.
- Fold A gain of `split_all_rt` over `split_all` is about 0.01 MAE, 0.012 pinball, 0.0003 spike Brier and 0.0006 direction Brier overall, and 0.04 / 0.004 in hour-1 direction: consistent in sign across all metrics, but small enough to be noise (no seed repeats were run), so confirm on fold B before relying on it.
- Coverage of all seven new features is 100 % in the training, validation and test windows (the series have no gaps).
- **A second weather model helps a little.** ICON-EU (runs 25 May - 2 Nov, usable 5 h after init) added to ECMWF: fold A MAE 42.53 -> 42.14, direction Brier 0.4011 -> 0.3995, pinball 12.09 -> 12.06. The gain is small (about 1 %), spike Brier is unchanged and coverage drops 0.007, so the model-spread idea (wider band when the models disagree) is only weakly visible in pinball.
- Fold B confirms the direction of the fold-A result: the live-imbalance features leave MAE and pinball unchanged and improve the spike Brier (0.0750 to 0.0732) and the direction Brier (0.4491 to 0.4480) slightly. Real, but small; it is not the reason to expect a big jump on the test period.
