# Error breakdown of split_all on validation (7 Sep - 4 Oct 2026)

> Analyses `split_all` on the validation period (7 Sep – 4 Oct 2026), written before the merge. The pipeline model is now `v6_hf`; the numbers below are not its errors.

Source: `results/split_all/validation/forecast_backtest.csv` against the organisers' `actuals_validation.csv`, 26,700 scored rows. Overall MAE 42.53 and mean pinball 12.09 (matches the scorer). Pinball is the mean of the P10 and P90 pinball losses, as in `score.py`. A quarter is a **high spike** if the imbalance price is more than 50 EUR/MWh above spot, a **low spike** if more than 50 below. Hours are Europe/Helsinki local time of the delivery quarter. "Share" columns say how much of the total loss a slice carries; compare with its share of rows. Only gaps to spot are shown, no spot levels.

| Step band | rows | share of rows | MAE | pinball | coverage | share of abs. error | share of pinball |
|---|---|---|---|---|---|---|---|
| 1-8 | 5372 | 20.1% | 39.8 | 11.5 | 0.79 | 18.8% | 19.1% |
| 9-20 | 8028 | 30.1% | 43.2 | 12.2 | 0.82 | 30.5% | 30.3% |
| 21-40 | 13300 | 49.8% | 43.2 | 12.3 | 0.82 | 50.6% | 50.5% |

| Local hour of delivery | rows | share of rows | MAE | pinball | coverage | share of abs. error | share of pinball |
|---|---|---|---|---|---|---|---|
| 00-05 | 6564 | 24.6% | 27.7 | 6.6 | 0.85 | 16.0% | 13.5% |
| 06-09 | 4456 | 16.7% | 45.7 | 13.0 | 0.80 | 17.9% | 17.9% |
| 10-15 | 6720 | 25.2% | 35.9 | 8.7 | 0.82 | 21.3% | 18.2% |
| 16-19 | 4480 | 16.8% | 50.4 | 14.2 | 0.78 | 19.9% | 19.7% |
| 20-23 | 4480 | 16.8% | 63.1 | 22.1 | 0.81 | 24.9% | 30.7% |

| Realised direction | rows | share of rows | MAE | pinball | coverage | share of abs. error | share of pinball |
|---|---|---|---|---|---|---|---|
| down | 17638 | 66.1% | 23.4 | 6.3 | 0.90 | 36.4% | 34.3% |
| none | 80 | 0.3% | 17.0 | 5.3 | 1.00 | 0.1% | 0.1% |
| up | 8982 | 33.6% | 80.3 | 23.6 | 0.64 | 63.5% | 65.6% |

| Quarter type | rows | share of rows | MAE | pinball | coverage | share of abs. error | share of pinball |
|---|---|---|---|---|---|---|---|
| high spike | 3240 | 12.1% | 162.6 | 54.3 | 0.23 | 46.4% | 54.5% |
| low spike | 3460 | 13.0% | 72.9 | 16.0 | 0.53 | 22.2% | 17.1% |
| no spike | 20000 | 74.9% | 17.8 | 4.6 | 0.96 | 31.4% | 28.4% |

Signed P50 error (forecast - actual, EUR/MWh) by quarter type:

| Quarter type | mean (P50 - actual) | mean abs. gap to spot |
|---|---|---|
| high spike | -162.5 | 157.4 |
| low spike | +72.8 | 97.0 |
| no spike | -5.2 | 20.0 |

## Where the loss sits

- **Spikes carry most of the loss.** High spikes are 12 % of the quarters but 46 % of the absolute error and 55 % of the pinball loss. The P10-P90 interval covers only 23 % of them, and the P50 sits on average 162 EUR/MWh below the realised price, about equal to the whole spike gap (157). Low spikes (13 % of quarters) are covered 53 % of the time. The 75 % of quarters without a spike have MAE 17.8 and coverage 0.96.
- **Up-regulation quarters are the hard half.** They are 34 % of the rows but 64 % of the error (MAE 80 against 23 for down-regulation), with coverage of 0.64. Down-regulation quarters are over-covered (0.90).
- **Evenings dominate.** Delivery 20:00-23:59 local has MAE 63 and 31 % of the pinball loss in 17 % of the rows. Night (00-05) is easy: MAE 28.
- **The horizon barely matters.** Steps 1-8 have MAE 39.8, steps 9-40 about 43.2, and the shares of loss track the shares of rows. Better long-horizon models would not help much; the loss is about the spike quarters themselves.
- **Where the next gain would come from:** earlier or sharper signals for evening up-regulation spikes (a direction and tail model that reacts to real-time imbalance, plan error and outages), and wider upper tails in the evening hours rather than a general interval widening. Down-regulation quarters have room to tighten the P90.
