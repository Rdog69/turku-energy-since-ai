# Submission manifest

The exact files behind every number we report, so anyone can check them.

## Team candidate: ½ `v7_rt` + ½ Abdo's `h_int4ss`, P90 stretched ×1.15

The best model on the team scoreboard: 32.9 % better than the organisers' baseline, weighted by points and averaged over September (36.7 %) and August (29.1 %).

| | |
|---|---|
| Recipe | The equal-weight blend below, then `p90 = p50 + 1.15 × (p90 − p50)`; every other column unchanged (`submissions/tools/stretch_p90.py`; the blend itself: `submissions/tools/blend_period.py`) |
| Why | In both months too many prices land above the blend's P90 (11–13 % instead of 10 %), while P10 is fine. Factor chosen by cross-fit: fitted on August (best 1.15) it improves September pinball by 0.34 %; fitted on September (best 1.125) it improves August by 0.98 %. The test month was never used |
| Effect | Pinball 11.065 → 11.027 (Sep), 6.217 → 6.153 (Aug). MAE, spike and direction identical. Coverage of P10–P90 rises to 0.835 / 0.853 (not scored) |

| File | Period | SHA-256 | Score (organisers' `score.py` 0.1.1): MAE / pinball / spike Brier / direction Brier |
|---|---|---|---|
| `blend_hi15_validation.csv` | 7 Sep – 4 Oct 2026 | `4aa95884edc0de2d0b3d5b4e0b4aa00adb222ea2e978b4bbdb20f487c6e609d2` | 40.1938 / 11.0270 / 0.0840 / 0.3799 (coverage 0.835) |
| `blend_hi15_august.csv` | August 2026 | `7ccabb306f01f4fdc7a71edd124f093cf63cd8aa3dba584d58cb1bae90c9a2ff` | 27.0461 / 6.1530 / 0.0648 / 0.4202 (coverage 0.853) |
| `blend_hi15_test.csv` | 5 Oct – 1 Nov 2026 (the submission) | `cfc5066113e107a7387f52073a93e1eeb99a09de5c6649f087212c7cd792779c` | Not scored by us. `validate_submission.py`: 26,920 rows, 0 errors, 0 warnings |

To submit, rename `blend_hi15_test.csv` to `forecast_backtest.csv`; the bytes must keep the hash above.

## Previous candidate: ½ `v7_rt` + ½ Abdo's `h_int4ss` (no stretch)

32.8 % better than the baseline (September 36.7 %, August 29.0 %).

| | |
|---|---|
| Recipe | Equal-weight average of all eight forecast columns of the two files below; quantiles re-sorted, direction probabilities renormalised, spikes capped so they sum to at most 1; `data_cutoff_utc` = the later of the two |
| Our half | `v7_rt`, files below, commit `18ca9f6` |
| Abdo's half | `h_int4ss`, `brainstorming-abdo` commit `2b4e84e`: `submissions/validation_h_int4ss.csv`, `foldb_h_int4ss.csv`, `forecast_backtest_h_int4ss.csv` |

| File | Period | SHA-256 | Score (organisers' `score.py` 0.1.1): MAE / pinball / spike Brier / direction Brier |
|---|---|---|---|
| `blend_v7_rt_h_int4ss_validation.csv` | 7 Sep – 4 Oct 2026 | `cd13c752e831c094dddcfc82b79377215817c788b3f1e221ad31e09d4bb6a067` | 40.1938 / 11.0651 / 0.0840 / 0.3799 (coverage 0.814) |
| `blend_v7_rt_h_int4ss_august.csv` | August 2026 | `e2b035f62842d0a3f40fe48bf0f3434f49602ee7a123e8accea2ac1e009a5236` | 27.0461 / 6.2166 / 0.0648 / 0.4202 (coverage 0.824) |
| `blend_v7_rt_h_int4ss_test.csv` | 5 Oct – 1 Nov 2026 (the submission) | `923d508ef1738ecd7daf8b10caf1abfd1ec47c240269d3a636ffcba097ae30eb` | Not scored by us. `validate_submission.py`: 26,920 rows, 0 errors, 0 warnings |

To submit, rename `blend_v7_rt_h_int4ss_test.csv` to `forecast_backtest.csv`; the bytes must keep the hash above.

## Second fallback: `v7_rt` alone

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
