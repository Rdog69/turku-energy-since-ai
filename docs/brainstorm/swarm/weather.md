# Weather agent: wind-forecast revisions, FMI nowcast, temperature

Code: `experiments/lab/features/weather.py`, `experiments/lab/exp_weather.py`
(`OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_weather "<name>"`). All rows use `mixture` / `gap` / `calibrate=True`, with `sources=("pkg","ifs","fg_rt","fg_extra","fmi")`, so `leakcheck` covers every source.

## Results (leaderboard; mixture / gap / calibrate unless noted)

| name | fold | MAE | pinball | cov | brier_spike | brier_dir | MAE s1-4 | s5-12 | s13-40 |
|---|---|---|---|---|---|---|---|---|---|
| REF package mixture | A | 43.576 | 12.463 | 0.794 | 0.0949 | 0.4369 | 41.81 | 43.09 | 43.97 |
| W0 rt wind err (fg181 vs DA, no NWP) | A | 43.238 | 12.276 | 0.793 | 0.0930 | 0.4263 | 40.85 | 42.44 | 43.81 |
| W1 ifs rev | A | 43.442 | 12.381 | 0.791 | 0.0966 | 0.4324 | 42.31 | 43.08 | 43.71 |
| W2 ifs rev + rt err | A | 43.267 | 12.291 | 0.785 | 0.0938 | 0.4302 | 41.71 | 42.59 | 43.69 |
| **W6 W2 + wind_err_hat** | A | **42.956** | 12.281 | 0.788 | 0.0943 | 0.4244 | 41.12 | 42.13 | 43.46 |
| W3 W6 + fmi | A | 43.183 | 12.221 | 0.790 | 0.0941 | 0.4338 | 41.48 | 42.47 | 43.63 |
| W4 W6 + temp/icing | A | 42.819 | 12.271 | 0.785 | 0.0938 | 0.4168 | 40.84 | 42.09 | 43.31 |
| **W6 regHGB** (leaf15/msl400/iter150) | A | **42.268** | **11.996** | 0.790 | 0.0931 | 0.4266 | 40.51 | 41.52 | 42.74 |
| REF package mixture | B | 29.402 | 7.014 | 0.806 | 0.0788 | 0.4528 | 28.49 | 29.07 | 29.63 |
| W0 rt wind err | B | 29.482 | 6.946 | 0.796 | 0.0753 | 0.4517 | 28.35 | 28.93 | 29.80 |
| W1 ifs rev | B | 28.654 | 6.777 | 0.804 | 0.0765 | 0.4441 | 28.21 | 28.25 | 28.83 |
| W2 ifs rev + rt err | B | 28.567 | 6.804 | 0.796 | 0.0762 | 0.4439 | 27.65 | 28.13 | 28.82 |
| **W6 W2 + wind_err_hat** | B | **28.257** | 6.700 | 0.806 | 0.0760 | 0.4408 | 27.11 | 27.59 | 28.61 |
| W3 W6 + fmi | B | 28.009 | 6.695 | 0.806 | 0.0759 | 0.4390 | 27.05 | 27.40 | 28.32 |
| W4 W6 + temp/icing | B | 28.184 | 6.857 | 0.804 | 0.0769 | 0.4463 | 27.28 | 27.83 | 28.42 |
| **W6 regHGB** | B | **27.381** | **6.684** | 0.807 | **0.0738** | **0.4360** | 26.32 | 26.84 | 27.69 |

For comparison, structure's "S final" (REF features, HGB G and bands) scores A 42.24 / 12.05 / 0.0923 / 0.4193 and B 27.58 / 6.81 / 0.0729 / 0.4375. W6 regHGB uses no bands and is as good or better on MAE/pinball on B and on pinball on A. No plain "REF mixture + HGB G" row exists, so the weather gain under HGB G is measured only against S-direct-G (A 43.02, B 28.16).

## What helped on both folds

- **IFS revision (W1)** is the main weather signal: B MAE −0.75, all bands better, direction Brier better on both folds. On A it is −0.13 MAE, mostly at steps 13–40 (−0.26), and spike Brier is slightly worse.
- **`wind_err_hat`** (pre-cutoff OLS combination per step band) is the best addition: W6 is better than W2 on every MAE band on both folds (A −0.31, B −0.31) and better on direction Brier.
- **Regularised HGB** on W6 gains another −0.69 (A) and −0.88 (B) MAE, plus better pinball and spike Brier on both folds.
- **FMI (W3)**: mixed. It helps B (MAE −0.25) and pinball on both folds, but A MAE is +0.23 and direction Brier is worse. **Not recommended.**
- **Temperature/icing (W4)**: A MAE −0.14 and direction Brier 0.4244 → 0.4168, but B pinball +0.16 and direction Brier worse. Not consistent on both folds. Icing is constant 0 on both folds, so it is untested.

## Recommended

`ifs_rev` + `wind_err_features` + `ifs_now_features` + `wind_hat_features` (12 features), with regularised HGB. ICON was not tested because it was still downloading.

## Suspicious

- The seasonal curve bias (CF −0.04 in Oct 2026) means the test month will see a shifted raw `ifs_rev`. `ifs_rev_dc` and `wind_err_hat` (which uses `ifs_rev_dc`) are protected by the trailing 7-day debias. If the model leans on raw `ifs_rev`/`ifs_mw`, consider dropping those two.
- Coverage drops about 0.01 on A with the rt features (0.79 → 0.785).
- nwp_latest NaN: 0.3–0.9% on all fold windows. One missing run (2026-06-10 12z).

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

