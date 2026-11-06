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
| 6 Nov | **`gbm_cal_product_norecency`**: same, without recency weights | package | 43.22 | **12.44** | **0.802** | **0.0939** | **0.4148** | **Current best**: best on 3 of 4 metrics. |

**Best vs baseline:** MAE −35 % (66.20 → 43.22), pinball −49 % (24.18 → 12.44), spike Brier −17 % (0.1132 → 0.0939), direction Brier −8 % (0.4509 → 0.4148).

⚠ Choosing the best of six variants on the validation period makes these numbers slightly optimistic. The test period will tell.

## Takeaways so far

- **Anchoring on spot** is worth a third of the error, at no cost.
- **The model barely improves MAE beyond the anchor** (44.3 → 43.2). Package features tell us little about the size of the gap. Error grows only from 41.6 (hour 1) to 43.7 (hour 10), so recent state adds little. Better MAE needs new information (PLAN §0: E1 winter history, E2 frequency, E3 price spread), not a fancier model.
- **Calibration is where the points are.** It took the probability scores from a tie with the baseline to −17 % / −8 %, and coverage from 0.53 to 0.80.
- **Recency weighting helps MAE but hurts the probabilities.** It shrinks the effective training set, so the probability models get noisier.
- ⚠ **Calibration risk on the test run:** the 14-day holdout before the test (20 Sep – 4 Oct) was volatile, so the learned P90 offset is +28 to +36 €/MWh vs +14 to +21 for validation. That's either a correct adaptation to the autumn regime or overfitting to two noisy weeks. Next: a longer holdout or shrinking the offsets, checked week by week.
- **`top_drivers`** (from LightGBM's SHAP) is mostly consumption forecast, wind forecast and spot, consistent with findings 3–4.
