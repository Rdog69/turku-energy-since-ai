# Score summary

- Scorer version: 0.1.1
- Schema version: 1.0
- Submission: validation_team5050.csv
- Actuals: actuals_validation.csv
- Spike margin: 50.00 EUR/MWh
- Rows in submission: 26880
- Rows scored (price metrics): 26700; skipped (no actual): 180
- Rows scored (exceptional prices): 26700
- Rows scored (direction): 26700

## Overall results

| Metric | Value | Use |
|---|---|---|
| MAE (p50) | 40.9739 | Level 1: accuracy |
| Pinball loss p10 | 7.1980 | |
| Pinball loss p90 | 16.0712 | |
| Mean pinball loss p10 and p90 | 11.6346 | Level 1: calibration |
| P10-P90 coverage | 0.8006 | supporting metric (target about 0.80) |
| Brier p_spike_high | 0.0922 | |
| Brier p_spike_low | 0.0800 | |
| Mean Brier, exceptional prices | 0.0861 | Level 1: exceptional prices |
| Three-class Brier, direction | 0.3803 | Level 1: direction |
| Pinball loss p50 | 20.4869 | for information |
| Observed share of high / low quarter-hours | 0.1213 / 0.1296 | for information |
| Baseline MAE (p50) | 66.2033 | for information |
| MAE difference vs baseline (team - baseline) | -25.2294 | for information |
| MAE ratio vs baseline (team / baseline) | 0.6189 | for information |

## Results by forecast horizon

| Hour | Steps | Rows | MAE | Pinball p10/p90 mean | Coverage | Brier spikes | Brier direction |
|---|---|---|---|---|---|---|---|
| 1 | 1-4 | 2688 | 36.6409 | 10.9246 | 0.7935 | 0.0742 | 0.3246 |
| 2 | 5-8 | 2684 | 39.5837 | 11.3304 | 0.7813 | 0.0803 | 0.3660 |
| 3 | 9-12 | 2680 | 40.5597 | 11.5762 | 0.8000 | 0.0840 | 0.3840 |
| 4 | 13-16 | 2676 | 40.8552 | 11.6319 | 0.7971 | 0.0851 | 0.3845 |
| 5 | 17-20 | 2672 | 41.3324 | 11.6518 | 0.8035 | 0.0870 | 0.3863 |
| 6 | 21-24 | 2668 | 41.5294 | 11.6808 | 0.8047 | 0.0875 | 0.3864 |
| 7 | 25-28 | 2664 | 41.8787 | 11.7377 | 0.8071 | 0.0892 | 0.3880 |
| 8 | 29-32 | 2660 | 42.2154 | 11.8469 | 0.8105 | 0.0906 | 0.3921 |
| 9 | 33-36 | 2656 | 42.5441 | 11.9531 | 0.8046 | 0.0914 | 0.3954 |
| 10 | 37-40 | 2652 | 42.6644 | 12.0246 | 0.8039 | 0.0919 | 0.3969 |

Lower is better for MAE, pinball loss and Brier scores. Points are calculated with `score.py --points` after all submissions have been scored.
