# Forecast file

`forecast_backtest.csv`: 673 hourly forecast origins (5 Oct – 1 Nov 2026, Finnish time) × 40 quarter-hours = 26,920 rows. The organisers' `validate_submission.py`: **VALIDATION PASSED** (0 errors, 0 warnings).

**Model:** the equal-weight blend of Frank's `v7_rt` and Abdo's `h_int4ss` (see `report/evaluation_report.md`).
- All eight forecast columns averaged.
- Quantiles re-sorted.
- Direction probabilities renormalised.
- Spike probabilities capped so they sum to at most 1.
- `data_cutoff_utc` = the later of the two members'.
- `top_drivers` from `v7_rt`.

**SHA-256:** `923d508ef1738ecd7daf8b10caf1abfd1ec47c240269d3a636ffcba097ae30eb`

**Built from:**
- `brainstorming-frank`: `submissions/blend_v7_rt_h_int4ss_test.csv` (`submissions/MANIFEST.md`), from Frank's `v7_rt` and Abdo's `h_int4ss`;
- `brainstorming-abdo`: `submissions/forecast_backtest_h_int4ss.csv`.

The same model, run the same way on the validation months (organisers' `score.py`; MAE / pinball / spike Brier / direction Brier):

| Month | Score | vs baseline (points-weighted) |
|---|---|---|
| September (7 Sep – 4 Oct) | 40.19 / 11.07 / 0.0840 / 0.3799 | 36.7 % better |
| August (trained before 1 Aug) | 27.05 / 6.22 / 0.0648 / 0.4202 | 29.0 % better |

To submit: upload this file as `forecast_backtest.csv`.
