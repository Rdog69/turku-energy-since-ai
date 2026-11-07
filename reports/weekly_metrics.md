# Week-by-week stability, validation period (7 Sep - 4 Oct 2026)

Per local week (Mon-Sun, Europe/Helsinki) of delivery quarter-hours, all 40 steps pooled. Definitions as in the organisers' `score.py` (MAE of p50; pinball = mean of p10 and p90 pinball; coverage of [p10, p90]; spike Brier = mean of high/low Brier with margin 50; three-class direction Brier). `spike_high_rate`/`spike_low_rate` are the observed shares. Computed by a script that reads `results/<model>/validation/forecast_backtest.csv`; only aggregates are shown.

## split_all

| Week (local) | rows | MAE | pinball | coverage | brier_spike | brier_dir | spike_high_rate | spike_low_rate |
|---|---|---|---|---|---|---|---|---|
| W1 (07 Sep-13 Sep) | 6540 | 49.61 | 15.95 | 0.847 | 0.0903 | 0.4237 | 0.107 | 0.087 |
| W2 (14 Sep-20 Sep) | 6720 | 41.45 | 12.61 | 0.834 | 0.0621 | 0.3431 | 0.062 | 0.138 |
| W3 (21 Sep-27 Sep) | 6720 | 47.83 | 11.47 | 0.731 | 0.1375 | 0.4811 | 0.217 | 0.144 |
| W4 (28 Sep-04 Oct) | 6720 | 31.41 | 8.42 | 0.845 | 0.0785 | 0.3572 | 0.098 | 0.147 |
| All | 26700 | 42.53 | 12.09 | 0.814 | 0.0921 | 0.4011 | 0.121 | 0.130 |

The spot-anchor run is not available as a results folder, so only split_all is shown. The `All` row reproduces the organisers' scorer output for split_all (42.53 / 12.09 / 0.814 / 0.0921 / 0.4011).

## Interpretation

- Week 3 (21-27 Sep) is the outlier. It had the most spikes (21.7 % high, 14.4 % low), the worst spike Brier (0.1375) and direction Brier (0.481), and the worst coverage (0.731, against 0.83-0.85 in the other weeks). The models underestimated that week's tail risk.
- Week 4 (28 Sep - 4 Oct) is the best week on MAE (31.4) and pinball (8.4), and it is the last week before the test run. The test-run calibration holdout (20 Sep - 4 Oct) spans the volatile week 3 and the calm week 4.
- Week-to-week swings (MAE 31-50, spike Brier 0.062-0.138) are large compared with the differences between model variants (a few tenths of MAE, about 0.001 spike Brier). Single-window comparisons between close variants are within noise.
