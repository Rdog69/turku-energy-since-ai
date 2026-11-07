# Submission manifest: `v7_rt`

The exact files behind every number we report, so anyone can check them.

| | |
|---|---|
| Model | `v7_rt` (`src/backtest/run.py`): `v6_hf` + Fingrid real-time series on the pre-June history rows |
| Code | branch `brainstorming-frank`, commit `18ca9f6` |
| Training data | everything published before each period's first origin; pre-June history 5 Mar 2025 – 31 May 2026 (organisers' Q&A answer, 7 Nov 2026, `QUESTIONS.md` Q1) |
| Calibration | last 28 days before the cutoff |
| External data | Fingrid real-time (30-min rule), Open-Meteo ECMWF/ICON runs (8 h / 5 h), OpenStreetMap turbines, pre-June history (`SOURCES.md`) |
| Run | `python -m src.backtest.run --model v7_rt --period <validation\|fold_b\|test>` |

| File | Period | SHA-256 | Score (organisers' `score.py` 0.1.1): MAE / pinball / spike Brier / direction Brier |
|---|---|---|---|
| `v7_rt_validation.csv` | 7 Sep – 4 Oct 2026 | `f64553ccf17ba40dd31fc9a378187d4a3d0c336a44d5281c9dec99e85222b1d1` | 40.6399 / 11.1991 / 0.0855 / 0.3892 (coverage 0.787) |
| `v7_rt_august.csv` | August 2026 | `98187e2c224deab01020676087e317893ec85c894d35a73f3e6db3bb873ab935` | 27.6704 / 6.5641 / 0.0680 / 0.4378 (coverage 0.769), against `scoreboard/make_actuals.py` |
| `v7_rt_test.csv` | 5 Oct – 1 Nov 2026 (the submission) | `5b6a4432485a8aacbed5c77bca23c596864c9703c249c7484efd0df8b67db2e2` | Not scored by us. `validate_submission.py`: 26,920 rows, 0 errors, 0 warnings |

To submit, rename `v7_rt_test.csv` to `forecast_backtest.csv`; the bytes must keep the hash above.

The files hold forecasts only (no spot column). The repository is private; don't publish them until the organisers say spot-derived outputs may be shared.
