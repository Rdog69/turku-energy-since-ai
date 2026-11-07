# Forecast file

`forecast_backtest.csv`: 673 hourly origins (5 Oct – 1 Nov 2026) × 40 quarter-hours = 26,920 rows. `validate_submission.py`: **VALIDATION PASSED**.

**Current candidate:** an equal-weight blend of Frank's `v7_rt` and Abdo's history-trained `h_int4ss`. It averages all eight forecast columns, re-sorts the quantiles, renormalises the direction probabilities, caps spikes so they sum to at most 1, and uses the later `data_cutoff_utc` of the two.

- Built from: `brainstorming-frank` `submissions/blend_v7_rt_h_int4ss_test.csv` (Frank's `submissions/MANIFEST.md`, "Older candidate").
- SHA-256: `923d508ef1738ecd7daf8b10caf1abfd1ec47c240269d3a636ffcba097ae30eb`

Official validation scores (organisers' `score.py` 0.1.1; MAE / pinball / spike Brier / direction Brier):

| Month | Score | vs baseline (points-weighted) |
|---|---|---|
| September (7 Sep – 4 Oct) | 40.19 / 11.07 / 0.0840 / 0.3799 | 36.7 % better |
| August (trained before 1 Aug) | 27.05 / 6.22 / 0.0648 / 0.4202 | 29.0 % better |

**Open decision:** Frank's manifest proposes a P90 stretch (×1.15) plus a spike cap on top of this blend. On September and August it adds about 0.2 points. Choose one and replace this file, keeping the hash in this README up to date.

To submit: upload this file as `forecast_backtest.csv`.
