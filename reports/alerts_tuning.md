# Alert threshold analysis (split_all, validation 7 Sep - 4 Oct 2026)

> Analyses `split_all` on the validation period (7 Sep – 4 Oct 2026), written before the merge. The pipeline model is now `v6_hf`; the thresholds below were not re-tuned on it.

Analysis only: nothing in `src/export/` was changed. Aggregates only, no spot values.

## Method

- Source: `results/split_all/validation/forecast_full.parquet` (672 hourly origins) and the organisers' `actuals_validation.csv`.
- An **alert unit** is an (origin, delivery hour) pair. The 10 hourly blocks of an origin are steps 1-4, 5-8, ..., 37-40. Block risk is the **maximum** `p_spike_high` (or `p_spike_low`, or the larger of the two, "any") over the block's four quarter-hours. The block P50 is the mean of the four P50s.
- Each block is compared with the **previous origin's forecast of the same delivery hour** (one hour earlier, so block b is compared with block b+1 of the previous origin). Block 10 has no previous forecast and is not compared. That gives 6,003 comparable pairs.
- An alert **rule** is "rise in block risk >= delta and risk >= level", or "|change in block P50| >= X EUR/MWh".
- **Precision** is the share of alerts followed by an actual spike in that delivery hour (high: imbalance price > spot + 50; any: above spot + 50 or below spot - 50). Base rates over all pairs: an hour contains a high spike 19.6 % of the time and any spike 40.2 % of the time.
- Two ways of counting alerts per day (28 days): **every origin** (the same delivery hour can alert again at the next origin) and **first per delivery hour** (a notification only when that hour is first flagged, which is what a user would see if repeats are suppressed).
- Precision only. Recall (share of spikes that had an alert) was not computed here.

## Results

| Type | Rule | Alerts/day (every origin) | Alerts/day (first per hour) | Precision (every) | Precision (first) |
|---|---|---|---|---|---|
| high-spike rise | rise >= 0.10, level >= 0.2 | 7.1 | 5.8 | 0.50 | 0.44 |
| high-spike rise | rise >= 0.15, level >= 0.2 | 3.9 | 3.6 | 0.56 | 0.53 |
| high-spike rise | rise >= 0.20, level >= 0.2 | 2.0 | 1.9 | 0.64 | 0.62 |
| high-spike rise | rise >= 0.10, level >= 0.3 | 5.9 | 4.9 | 0.55 | 0.49 |
| high-spike rise | rise >= 0.15, level >= 0.3 | 3.4 | 3.1 | 0.61 | 0.58 |
| high-spike rise | rise >= 0.20, level >= 0.3 | 1.9 | 1.8 | 0.67 | 0.64 |
| high-spike rise | rise >= 0.15, level >= 0.4 | 2.5 | 2.3 | 0.62 | 0.59 |
| high-spike rise | rise >= 0.20, level >= 0.4 | 1.8 | 1.6 | 0.65 | 0.63 |
| high-spike rise | rise >= 0.10, level >= 0.5 | 2.5 | 2.1 | 0.65 | 0.62 |
| high-spike rise | rise >= 0.15, level >= 0.5 | 1.5 | 1.4 | 0.72 | 0.70 |
| high-spike rise | rise >= 0.20, level >= 0.5 | 1.1 | 1.0 | 0.75 | 0.72 |
| any-spike rise | rise >= 0.10, level >= 0.4 | 7.4 | 6.5 | 0.76 | 0.75 |
| any-spike rise | rise >= 0.20, level >= 0.3 | 1.6 | 1.5 | 0.77 | 0.77 |
| any-spike rise | rise >= 0.20, level >= 0.5 | 1.4 | 1.3 | 0.87 | 0.86 |
| P50 move | abs(change) >= 25 EUR/MWh | 7.3 | 5.8 | 0.73 | 0.73 |
| P50 move | abs(change) >= 40 EUR/MWh | 1.9 | 1.8 | 0.83 | 0.84 |
| P50 move | abs(change) >= 60 EUR/MWh | 0.2 | 0.2 | 0.67 | 0.67 |
| high-spike level only (no rise) | risk >= 0.5 | 10.1 | 3.1 | 0.66 | 0.58 |
| high-spike level only (no rise) | risk >= 0.6 | 3.9 | 1.5 | 0.75 | 0.72 |

The grid also covered other delta and level combinations; only the rows near 1-3 alerts per day and some contrasting ones are shown.

## Recommendation (about 1-3 alerts per day)

1. **High-spike risk alert:** rise in block `p_spike_high` of at least 0.20 versus the previous origin, with the new level at least 0.30. About 1.8 alerts a day, precision 0.64-0.67, which is 3.3x the 0.196 base rate. For a more sensitive setting, use rise >= 0.15 with level >= 0.4 (2.3-2.5 a day, precision 0.59-0.62).
2. **Price alert:** change of at least 40 EUR/MWh in the block P50 versus the previous origin, about 1.8 alerts a day, precision 0.84 for "a spike in either direction follows" (base rate 0.40). Use 25 EUR/MWh for a "watch" tier, but it fires 6-7 times a day.
3. Suppress repeat alerts for the same delivery hour. It removes 5-40 % of the volume (most at the sensitive settings) and lowers precision slightly.

## Caveats

- Thresholds were chosen on the same four weeks they are evaluated on. Week 3 (21-27 Sep) had far more spikes than the others (`reports/weekly_metrics.md`), so precision will move with the regime. Expect alert rates and precision to differ in other regimes.
- Because the p_spike_low calibration is over-confident (`reports/calibration_check.md`), rules that use low-spike risk or the "any" risk alert more often than the stated probabilities imply.
- Precision ignores how early the alert came. A rise at step 37-40 is a 9-10 hour warning; a rise at steps 1-4 is nearly nowcasting.
