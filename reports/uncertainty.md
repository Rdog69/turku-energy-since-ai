# Uncertainty on the model differences (job U1)

Method: paired day-block bootstrap on the September validation window (7 Sep - 4 Oct, 26,880 rows, 29 Europe/Helsinki delivery days). Both models are scored on the same resampled days, 2,000 resamples, seed 1, 90 % interval (5th to 95th percentile). Metric definitions are copied from `starter_package/score.py`. Lower is better for the four metrics, so a negative difference favours A. The gain row is the points-weighted % (30/20/20/10) by which A beats B; positive favours A. Reproduce with `python tools/paired_bootstrap.py A.csv B.csv`.

Files: `split_all` and `split_all_rt_icon` from `results/*/validation/forecast_backtest.csv`; `team5050` from `submissions/validation_team5050.csv`; the baseline was regenerated with `scoreboard/baseline.py --period validation` (MAE 66.20 and pinball 24.18, matching the organisers' figures).

## Pairs

Format: difference (90 % interval). Intervals that exclude 0 are in bold.

| Pair (A vs B) | MAE | Pinball p10/p90 | Spike Brier | Direction Brier | Points-weighted gain of A |
|---|---|---|---|---|---|
| split_all_rt_icon vs split_all | -0.39 (-0.86, +0.06) | -0.026 (-0.106, +0.054) | +0.0001 (-0.0013, +0.0014) | -0.0033 (-0.0106, +0.0037) | +0.47 % (-0.44, +1.33) |
| team5050 vs split_all_rt_icon | **-1.17 (-1.83, -0.43)** | **-0.424 (-0.550, -0.298)** | **-0.0061 (-0.0094, -0.0033)** | **-0.0175 (-0.0263, -0.0094)** | **+4.13 % (+2.77, +5.77)** |
| split_all vs baseline | **-23.68 (-33.97, -14.99)** | **-12.09 (-17.07, -7.92)** | **-0.0211 (-0.0331, -0.0106)** | **-0.0498 (-0.0787, -0.0219)** | **+31.95 % (+26.23, +37.68)** |
| split_all_rt_icon vs baseline | **-24.06 (-34.63, -15.15)** | **-12.12 (-17.14, -7.89)** | **-0.0210 (-0.0337, -0.0100)** | **-0.0531 (-0.0827, -0.0247)** | **+32.26 % (+26.27, +38.38)** |
| team5050 vs baseline | **-25.23 (-35.76, -16.21)** | **-12.54 (-17.50, -8.36)** | **-0.0271 (-0.0385, -0.0170)** | **-0.0706 (-0.0967, -0.0454)** | **+35.20 % (+29.42, +41.22)** |

Scores behind the table (MAE / pinball / spike / direction): baseline 66.20 / 24.18 / 0.1132 / 0.4509; split_all 42.53 / 12.09 / 0.0921 / 0.4011; split_all_rt_icon 42.14 / 12.06 / 0.0922 / 0.3978; team5050 40.97 / 11.63 / 0.0861 / 0.3803.

## Reading

- Every model beats the baseline by 32-35 % points-weighted, with intervals far from zero; that gain is not noise.
- split_all_rt_icon vs split_all (+0.5 %, interval -0.4 to +1.3) cannot be told apart from noise on this window, and differences of about 1 % between variants should be read the same way.
- team5050 vs split_all_rt_icon (+4.1 %, +2.8 to +5.8) is clearly distinguishable on all four metrics, but both the variants and team5050 were tuned on this same month, so the interval understates the real uncertainty on the test period.
- The intervals resample days only, so they do not cover the tuning (selection) effect. Day blocks keep within-day autocorrelation, but week-level regimes (29 days, about 4 weeks) are few.
