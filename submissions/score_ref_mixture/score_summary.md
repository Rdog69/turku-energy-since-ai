# Score summary

- Scorer version: 0.1.1
- Schema version: 1.0
- Submission: validation_ref_mixture.csv
- Actuals: actuals_validation.csv
- Spike margin: 50.00 EUR/MWh
- Rows in submission: 26880
- Rows scored (price metrics): 26700; skipped (no actual): 180
- Rows scored (exceptional prices): 26700
- Rows scored (direction): 26700

## Overall results

| Metric | Value | Use |
|---|---|---|
| MAE (p50) | 43.5406 | Level 1: accuracy |
| Pinball loss p10 | 7.8723 | |
| Pinball loss p90 | 16.7791 | |
| Mean pinball loss p10 and p90 | 12.3257 | Level 1: calibration |
| P10-P90 coverage | 0.7958 | supporting metric (target about 0.80) |
| Brier p_spike_high | 0.1016 | |
| Brier p_spike_low | 0.0873 | |
| Mean Brier, exceptional prices | 0.0945 | Level 1: exceptional prices |
| Three-class Brier, direction | 0.4294 | Level 1: direction |
| Pinball loss p50 | 21.7703 | for information |
| Observed share of high / low quarter-hours | 0.1213 / 0.1296 | for information |
| Baseline MAE (p50) | 66.2033 | for information |
| MAE difference vs baseline (team - baseline) | -22.6627 | for information |
| MAE ratio vs baseline (team / baseline) | 0.6577 | for information |

## Results by forecast horizon

| Hour | Steps | Rows | MAE | Pinball p10/p90 mean | Coverage | Brier spikes | Brier direction |
|---|---|---|---|---|---|---|---|
| 1 | 1-4 | 2688 | 41.9306 | 11.8070 | 0.8002 | 0.0885 | 0.4092 |
| 2 | 5-8 | 2684 | 42.8489 | 12.0247 | 0.7958 | 0.0903 | 0.4225 |
| 3 | 9-12 | 2680 | 43.1282 | 12.2224 | 0.7951 | 0.0919 | 0.4287 |
| 4 | 13-16 | 2676 | 43.2482 | 12.2626 | 0.8075 | 0.0938 | 0.4263 |
| 5 | 17-20 | 2672 | 43.5029 | 12.2853 | 0.8039 | 0.0946 | 0.4282 |
| 6 | 21-24 | 2668 | 43.6656 | 12.3617 | 0.7987 | 0.0953 | 0.4301 |
| 7 | 25-28 | 2664 | 43.9394 | 12.4845 | 0.7947 | 0.0961 | 0.4351 |
| 8 | 29-32 | 2660 | 44.2278 | 12.5034 | 0.7895 | 0.0965 | 0.4353 |
| 9 | 33-36 | 2656 | 44.2659 | 12.6144 | 0.7869 | 0.0979 | 0.4372 |
| 10 | 37-40 | 2652 | 44.6798 | 12.7013 | 0.7854 | 0.0998 | 0.4422 |

Lower is better for MAE, pinball loss and Brier scores. Points are calculated with `score.py --points` after all submissions have been scored.
