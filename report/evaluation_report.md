# Evaluation report

> Skeleton. Jim's draft (`brainstorming-jim`: `reports/evaluation_report.md`) is the starting point; merge it here. The jury scores the **reasoning chain** from this report, the slides and the video (20 % of Level 1): clarity, consistency, inventiveness.

## 1. The problem in one paragraph

TODO: the imbalance price = spot + a gap that depends on the balancing direction. Forecast 40 quarter-hours every hour, with an interval, the direction, and spike probabilities.

## 2. Reasoning chain

TODO, one line each, with the evidence:

1. **Direction first.** The price follows the dominant mFRR direction. Model P(up), P(down) and P(none), then the price gap given each direction; every output (median, band, spikes, direction) comes from that one mixture, so they are consistent.
2. **Data known at the forecast time only.** Every row is used from its `first_usable_origin_utc`. The leak tests rebuild every feature with all later rows deleted and require identical values.
3. **What moves the gap:**
   - recent imbalance and direction (the last published quarters);
   - real-time Fingrid data (surplus/deficit, wind against its forecast, frequency);
   - weather-forecast revisions after the day-ahead forecast (ECMWF, ICON, a wind map weighted by installed capacity);
   - the spot price's shape.
4. **More history (Mar 2025 →), with the June 2026 price rule rebuilt.** Before June, the imbalance price used a different formula. Rebuilding it with the new rule from mFRR/aFRR prices and volumes reproduces the official price on 99.5 % of Jun–Oct 2026 quarters. Training on 19 months instead of 4 improved every score in September and August.
5. **Calibration.** Probabilities and widths are calibrated on the last 14 days before each forecast period, shrunk toward no change.
6. **Two independent models, blended 50/50.** Each is strong where the other is weak.

## 3. Factors that drive the forecast

TODO: TreeSHAP drivers (`top_drivers` column), with plain-language names. Examples: wind in Sweden/Finland against the forecast, the consumption forecast, the latest gap to spot, grid frequency.

## 4. Validation metrics

Organisers' `score.py` 0.1.1; MAE / pinball / spike Brier / direction Brier.

| Model | September (organisers' validation) | August (trained before 1 Aug) |
|---|---|---|
| Organisers' baseline | 66.20 / 24.18 / 0.1132 / 0.4509 | 38.67 / 11.65 / 0.0792 / 0.4792 |
| Frank `v7_rt` | 40.64 / 11.20 / 0.0855 / 0.3892 | 27.67 / 6.56 / 0.0680 / 0.4378 |
| Abdo `h_int4ss` | 40.55 / 11.28 / 0.0865 / 0.3844 | 27.15 / 6.16 / 0.0639 / 0.4219 |
| **Submitted blend** | **40.19 / 11.07 / 0.0840 / 0.3799** | **27.05 / 6.22 / 0.0648 / 0.4202** |

TODO:
- week-by-week consistency;
- what did not work (the list in `brainstorming-abdo` `docs/EXPERIMENTS.md` §4);
- how we avoided overfitting (both months, cross-fitting, no tuning on the test month).

## 5. Limitations and next steps

TODO: rare event days dominate the error. Open data cannot see Turku Energia's own position, so suggestions say "check", never "trade".
