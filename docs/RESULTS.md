# Results log

Validation period 7 Sep – 4 Oct 2026 (672 origins, 26,700 scored rows), scored with the organisers' `score.py` 0.1.1, spike margin 50. Lower is better everywhere. Each row is one model run. This log becomes the step-by-step comparison (ablation table) in the evaluation report.

| Date | Model | Data | MAE | Pinball (p10/p90 mean) | Coverage | Brier spikes | Brier direction | Notes |
|---|---|---|---|---|---|---|---|---|
| 6 Nov | Organisers' baseline (persistence) | package | 66.20 | 24.18 | 0.683 | 0.1132 | 0.4509 | Reproduced exactly with `baseline.ipynb` |
| 6 Nov | `spot_anchor`: spot + constant gap quantiles; training shares for the probabilities | package | **44.29** | **14.99** | 0.675 | 0.1132 | 0.4508 | Accuracy −33 %, calibration −38 % vs baseline. Probabilities **tie the baseline**, so they would earn 0 points; they need real models (PLAN §0, E4). |

## Takeaways so far

- Anchoring on spot is worth a third of the error, at no cost.
- The probability columns (spikes and direction, 30 of the 80 automatic points) don't improve from a constant: the training shares (spikes 7.9 % / 5.7 %) are far below what validation shows (12.1 % / 13.0 %). Next: conditional models plus calibration on recent data.
- Coverage is 0.68, below the 0.80 target, for the same reason: the validation period is more volatile than training (PLAN finding 9).
