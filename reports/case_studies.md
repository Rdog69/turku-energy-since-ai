# Spike case studies (split_all, validation only)

The three largest realised spikes between 7 Sep and 4 Oct 2026 (by absolute gap to spot, at least 6 hours apart), and what the forecast said 1.5, 3.5 and 6.5 hours before. Hourly origins mean the lead times are not round numbers. All price numbers are **gaps to spot** (imbalance price minus spot), never spot levels. Source: `results/split_all/validation/forecast_backtest.csv` and `actuals_validation.csv`; no test-period targets.

### Case 1: Wed 09 Sep 2026, quarter starting 20:30 local

Realised: gap to spot **+3800 EUR/MWh**, direction up. (Spot-relative numbers only.)

| Forecast made | Step | P50 gap | P10 to P90 gap | P(spike high) | P(spike low) | P(up) | Top drivers |
|---|---|---|---|---|---|---|---|
| 1.50 h before (Wed 19:00) | 7 | +3 | -91 to +67 | 0.27 | 0.41 | 0.59 | last_gap;rt_freq_dev;spot |
| 3.50 h before (Wed 17:00) | 15 | -5 | -92 to +58 | 0.05 | 0.36 | 0.63 | spot;om_wind_idx;solar_fc |
| 6.50 h before (Wed 14:00) | 27 | -5 | -87 to +52 | 0.04 | 0.39 | 0.55 | spot;om_wind_idx;solar_fc |

### Case 2: Tue 15 Sep 2026, quarter starting 06:30 local

Realised: gap to spot **+1768 EUR/MWh**, direction up. (Spot-relative numbers only.)

| Forecast made | Step | P50 gap | P10 to P90 gap | P(spike high) | P(spike low) | P(up) | Top drivers |
|---|---|---|---|---|---|---|---|
| 1.50 h before (Tue 05:00) | 7 | -42 | -109 to +23 | 0.02 | 0.62 | 0.44 | spot;mean_gap_last8;last_gap |
| 3.50 h before (Tue 03:00) | 15 | -11 | -104 to +46 | 0.04 | 0.49 | 0.44 | om_temp;spot;residual_load_fc |
| 6.50 h before (Tue 00:00) | 27 | -26 | -110 to +26 | 0.03 | 0.55 | 0.29 | om_temp;spot;mean_gap_last8 |

### Case 3: Fri 02 Oct 2026, quarter starting 13:30 local

Realised: gap to spot **+865 EUR/MWh**, direction up. (Spot-relative numbers only.)

| Forecast made | Step | P50 gap | P10 to P90 gap | P(spike high) | P(spike low) | P(up) | Top drivers |
|---|---|---|---|---|---|---|---|
| 1.50 h before (Fri 12:00) | 7 | +15 | -46 to +94 | 0.32 | 0.15 | 0.41 | last_gap;om_wind_rev_mw;mean_gap_last8 |
| 3.50 h before (Fri 10:00) | 15 | -9 | -57 to +54 | 0.26 | 0.21 | 0.31 | mean_gap_last8;cons_fc;mean_gap_last4 |
| 6.50 h before (Fri 07:00) | 27 | -5 | -56 to +62 | 0.21 | 0.19 | 0.28 | mean_gap_last8;cons_fc;mean_gap_last4 |

## What a trader should take from these

- **All three were up-regulation spikes far beyond the interval.** The realised gaps (+3800, +1768, +865 EUR/MWh) are roughly 10 to 80 times the P90 gap (+23 to +94 across the rows shown). The 99th percentile of the absolute gap over the whole validation period is 277 and only 13 quarters exceeded 500. These are extreme tail events, and a model trained on the gap to spot, with a P90 at about +60, cannot size them.
- **The spike probability gave a partial warning in two of the three.** Case 1: P(spike high) went from 0.05 at 3.5 h to 0.27 at 1.5 h (drivers: last gap, frequency deviation), but the P50 stayed at spot. Case 3: 0.21 at 6.5 h, 0.26 at 3.5 h and 0.32 at 1.5 h, against a base rate of 12 % for high-spike quarters. Case 2 (06:30, early morning) was **missed**: P(spike high) was 0.02 to 0.04 and the model leaned toward a low spike (0.49 to 0.62).
- **Effect on the score.** The three quarters carry 5.7 % of the total absolute error of the P50 (MAE 42.53 overall, 40.15 without them). No threshold on these forecasts would have said "expect more than 800 above spot"; a flag that the high-spike risk is elevated is the most the forecast offers.
- **Honest framing for the demo:** the system raises the probability of a spike a few hours ahead in some cases, but it does not predict the size, and some spikes are not flagged at all.
