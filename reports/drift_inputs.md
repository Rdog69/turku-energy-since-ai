# Test-period input drift (inputs only, no targets)

Quantiles of model inputs at test origins (5 Oct 00:00 - 1 Nov 23:00 local, 673 hourly origins x 40 steps) against the training rows (origins before 5 Oct 00:00 local, 120,720 rows) and against the last 14 days of training (the window the single-holdout calibration learns from). Features built with `with_targets=False` through the normal availability-aware pipeline; no test targets were read. Units: MW for `wind_fc`, `cons_fc`, `rt_wind_err` (Fingrid real-time wind minus day-ahead forecast); `om_wind_rev` is the ECMWF wind-index revision; `spot_abs_ramp` is a price ramp (aggregate quantiles only). `rt_sd_last` does not exist in the current feature set.

| Feature | Training (<= 4 Oct) q05/25/50/75/95 | Last 14 days of training | Test origins (5 Oct - 1 Nov) | Test rows outside training 5-95 % range | NaN share train / test |
|---|---|---|---|---|---|
| `wind_fc` | 303 / 890 / 1.77e+03 / 3.08e+03 / 4.73e+03 | 240 / 1.32e+03 / 2.55e+03 / 3.46e+03 / 4.44e+03 | 1.01e+03 / 2.42e+03 / 3.94e+03 / 5.54e+03 / 6.92e+03 | 34% | 0.0% / 0.0% |
| `cons_fc` | 7.48e+03 / 8.02e+03 / 8.55e+03 / 8.92e+03 / 9.24e+03 | 7.78e+03 / 8.25e+03 / 8.74e+03 / 8.94e+03 / 9.1e+03 | 8.71e+03 / 9.29e+03 / 9.66e+03 / 1.01e+04 / 1.04e+04 | 78% | 0.0% / 0.0% |
| `spot_abs_ramp` | 0.06 / 0.99 / 3.98 / 10.3 / 29.1 | 0.39 / 1.91 / 5.63 / 13.3 / 34.8 | 0.03 / 0.86 / 3.29 / 8.31 / 30 | 12% | 0.0% / 0.0% |
| `rt_wind_err` | -840 / -354 / -123 / 95.8 / 498 | -506 / -233 / -16.7 / 193 / 604 | -1.01e+03 / -274 / 36.4 / 346 / 1.03e+03 | 25% | 0.0% / 0.0% |
| `om_wind_rev` | -0.0504 / -0.0124 / 0.000331 / 0.0151 / 0.0607 | -0.0417 / -0.0105 / 0.000556 / 0.015 / 0.0618 | -0.0599 / -0.0157 / 0.00153 / 0.017 / 0.0507 | 11% | 0.0% / 0.0% |

## What it means for calibration

- The test period is a different regime: median day-ahead wind is 3.9 GW (training 1.8 GW), median consumption forecast 9.7 GW (training 8.6 GW), and 78 % of test rows have a consumption forecast above the training 95th percentile. Tree models cannot extrapolate, so predictions for those rows rely on the highest training leaves, and the quantile offsets and Platt maps learned on summer data may not carry over.
- The real-time wind error is much wider in the test period (5th-95th percentile -1.0 to +1.0 GW against -0.8 to +0.5 GW in training), while the spot price ramps look similar (median 3.3 against 4.0). Wider intervals for October are plausible, but the 14-day holdout covers the wind and consumption range only partly (its median wind of 2.6 GW and consumption of 8.7 GW are still well below the test medians). Pooled or longer calibration windows would not fix this either; they only add more summer data.
