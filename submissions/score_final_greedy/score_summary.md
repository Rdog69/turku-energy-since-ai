# Score summary

- Scorer version: 0.1.1
- Schema version: 1.0
- Submission: validation_final_greedy.csv
- Actuals: actuals_validation.csv
- Spike margin: 50.00 EUR/MWh
- Rows in submission: 26880
- Rows scored (price metrics): 26700; skipped (no actual): 180
- Rows scored (exceptional prices): 26700
- Rows scored (direction): 26700

## Overall results

| Metric | Value | Use |
|---|---|---|
| MAE (p50) | 41.3986 | Level 1: accuracy |
| Pinball loss p10 | 6.8205 | |
| Pinball loss p90 | 16.0432 | |
| Mean pinball loss p10 and p90 | 11.4318 | Level 1: calibration |
| P10-P90 coverage | 0.8161 | supporting metric (target about 0.80) |
| Brier p_spike_high | 0.0944 | |
| Brier p_spike_low | 0.0814 | |
| Mean Brier, exceptional prices | 0.0879 | Level 1: exceptional prices |
| Three-class Brier, direction | 0.3843 | Level 1: direction |
| Pinball loss p50 | 20.6993 | for information |
| Observed share of high / low quarter-hours | 0.1213 / 0.1296 | for information |
| Baseline MAE (p50) | 66.2033 | for information |
| MAE difference vs baseline (team - baseline) | -24.8047 | for information |
| MAE ratio vs baseline (team / baseline) | 0.6253 | for information |

## Results by forecast horizon

| Hour | Steps | Rows | MAE | Pinball p10/p90 mean | Coverage | Brier spikes | Brier direction |
|---|---|---|---|---|---|---|---|
| 1 | 1-4 | 2688 | 36.5275 | 10.7290 | 0.8062 | 0.0753 | 0.3249 |
| 2 | 5-8 | 2684 | 39.5090 | 11.0760 | 0.8104 | 0.0794 | 0.3679 |
| 3 | 9-12 | 2680 | 40.7826 | 11.2882 | 0.8056 | 0.0847 | 0.3857 |
| 4 | 13-16 | 2676 | 41.2307 | 11.3383 | 0.8079 | 0.0864 | 0.3882 |
| 5 | 17-20 | 2672 | 41.8197 | 11.4539 | 0.8271 | 0.0894 | 0.3914 |
| 6 | 21-24 | 2668 | 42.0522 | 11.5019 | 0.8227 | 0.0901 | 0.3915 |
| 7 | 25-28 | 2664 | 42.5537 | 11.5671 | 0.8221 | 0.0914 | 0.3933 |
| 8 | 29-32 | 2660 | 42.9050 | 11.6831 | 0.8203 | 0.0934 | 0.3974 |
| 9 | 33-36 | 2656 | 43.2688 | 11.8123 | 0.8219 | 0.0946 | 0.4009 |
| 10 | 37-40 | 2652 | 43.4141 | 11.8822 | 0.8171 | 0.0951 | 0.4026 |

Lower is better for MAE, pinball loss and Brier scores. Points are calculated with `score.py --points` after all submissions have been scored.
