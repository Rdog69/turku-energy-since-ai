# Weather agent: wind-forecast revisions, FMI nowcast, temperature

Code: `experiments/lab/features/weather.py`, `experiments/lab/exp_weather.py`
(`OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_weather "<name>"`). All rows use `mixture` / `gap` / `calibrate=True`, with `sources=("pkg","ifs","fg_rt","fg_extra","fmi")`, so `leakcheck` covers every source.

**Status: incomplete.** The IFS main-period file (`runs_ecmwf_ifs_main.csv.gz`) had not landed when this run was stopped (download at 401/648 runs, 01:15). That means **no IFS experiment has run on the leaderboard yet.** Only W0 (no NWP) is measured. The IFS rows W1–W6 are coded and leak-checked (on a scratch copy of the cached runs), ready to run.

## Results (leaderboard)

| name | fold | MAE | pinball | coverage | brier_spike | brier_dir | MAE s1-4 | s5-12 | s13-40 |
|---|---|---|---|---|---|---|---|---|---|
| REF package mixture | A | 43.576 | 12.463 | 0.794 | 0.0949 | 0.4369 | 41.81 | 43.09 | 43.97 |
| W0 rt wind err | A | **43.238** | **12.276** | 0.793 | **0.0930** | **0.4263** | **40.85** | **42.44** | **43.81** |
| REF package mixture | B | 29.402 | 7.014 | 0.806 | 0.0788 | 0.4528 | 28.49 | 29.07 | 29.63 |
| W0 rt wind err | B | 29.482 | **6.946** | 0.796 | **0.0753** | **0.4517** | **28.35** | **28.93** | 29.80 |

W0 = REF + `wind_rt`, `wind_err_now` (fg181 − fi_wind_fc_da at the newest usable quarter), `wind_err_now4`, `wind_rt_d4`. It improves pinball, spike Brier and direction Brier on both folds. MAE improves on A (−0.34), but on B it is +0.08 overall, driven by steps 13–40 (+0.17); steps 1–12 improve on both folds.

## Power curve (step 1)

- CF = Σᵢ wᵢ · sigmoid((v100ᵢ − a)/b) over the 7 cluster points, with CF = fg75 / fg268. It is fitted with scipy `least_squares` on deliveries < 2026-07-31T21:00Z only, and the parameters are hard-coded in `weather.py`. It is monotone by construction (non-negative weights, CF(25 m/s) = 0.65).
- **Input chosen: IFS short lead (8–20 h)** (last autumn 2025 + 25 May – 31 Jul 2026): a=7.00, b=1.39. The ERA5 fit is almost identical (a=7.13, b=1.39). Fit on data before July and tested on IFS-input July, both give MAE_CF ≈ 0.035, with r 0.962 (IFS) against 0.959 (ERA5). A monotone HGB was worse out of sample (0.046 against 0.042).
- Jun–Jul 2026: IFS short-lead MW MAE is 332 MW against 343 MW for fi_wind_fc_da, and their average is 308 MW. corr(actual − fc_da, IFS − fc_da) = 0.42.
- **Suspicious / important:** the curve's bias drifts by season. CF bias is about +0.02 in Jun–Jul (summer curtailment or stability?), −0.006 in Oct 2025 and **−0.04 in Oct 2026** (about −380 MW). The raw revision `ifs_rev` therefore shifts between train and the test month. `ifs_rev_dc` removes this by subtracting the trailing 7-day mean of (newest-run MW − fc_da), computed on a base-independent hourly grid.

## Pre-cutoff diagnostics (Jun–Jul, not leaderboard)

corr with gap, by step band 1–4 / 5–12 / 13–40:

| feature | DA wind error | gap |
|---|---|---|
| `ifs_rev_dc` (debiased revision) | 0.43 / 0.42 / 0.37 | **−0.20 / −0.19 / −0.15** (best gap correlation in every band) |
| `ifs_rev` | 0.44 / 0.44 / 0.39 | −0.17 / −0.16 / −0.12 |
| `ifs_rev_da` (newest run − run usable at DA publication) | 0.42 / 0.41 / 0.36 | −0.17 / −0.16 / −0.12 |
| `ifs_corr_rev` (IFS + current IFS error − fc_da) | 0.81 / 0.61 / **0.40** | −0.21 / −0.14 / −0.13 |
| `wind_err_now` (fg181) | **0.84 / 0.61** / 0.28 | −0.18 / −0.12 / −0.09 |
| `ifs_runchg` (nth0 − nth1) | 0.12 / 0.13 / 0.11 | −0.10 / −0.08 / −0.02 |
| FMI `fmi_err` / `fmi_err_dc` | ~0.13 / 0.10 | ~0 (weak) |
| `t_hel`, `t_hel_rev` | weak | ±0.05 |
| `icing_frac` | constant 0 in summer, so it can't be validated on A/B | n/a |

`wind_err_hat` is a per-step-band OLS fitted pre-cutoff on [wind_err_now, ifs_rev_dc, ifs_corr_rev, ifs_runchg]. Fitted on June and tested on July, R² is 0.75 / 0.49 / 0.30 / 0.17 for steps 1–4 / 5–12 / 13–24 / 25–40, against 0.71 / 0.39 / 0.24 / 0.14 for the best single feature.

Kill criteria from the ideas doc: the curve is monotone, so it passes. nwp_latest NaN is 0.4–2% pre-cutoff, so it passes too; this still needs rechecking on the final file with `scratchpad/cov.py`.

## Recommended (pending the IFS runs)

1. Keep the W0 fg181 error features: they help on both folds except fold B MAE at steps 13–40.
2. Run in this order: **W1** (REF + `ifs_rev`), **W2** (+ W0 + `ifs_now_features`), **W6** (W2 + `wind_err_hat`), then W3 (FMI) and W4 (temp/icing). Diagnostics suggest `ifs_rev_dc` and `ifs_corr_rev` should fix W0's weak band (steps 13–40). Expect little from FMI and temperature in Aug–Sep. Icing only matters for late October, so include it only if it is neutral.
3. ICON (`icon_rev`, W5) and the IFS–ICON spread are not tested yet because the file is not downloaded.
