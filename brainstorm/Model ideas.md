---
tags: [brainstorm, model]
owner: Pavel
created: 2026-11-06
status: draft
---

# Model ideas

Ideas for the models role (PLAN §5, role 2). Back to [[00 Brainstorm Hub]]. Related: [[Data layer ideas]], [[Risks and checks]].

## Step-by-step comparison table (also the jury story)

Each row has to beat the one above it on validation (models trained up to 6 Sep):

| # | Model | Expected MAE | Notes |
|---|---|---|---|
| 0 | Persistence (≈ baseline) | ~65 | From PLAN finding 1 |
| 1 | p50 = spot | 46.5 | ✔ PLAN |
| 2 | spot − 7.7 | 44.2 | ✔ PLAN |
| 3 | 💡 spot + median gap per (local hour × wind quintile) | ? | 24 × 5 lookup table, about 30 min |
| 4 | LightGBM on package features | ? | |
| 5 | + recent-conditions features | ? | |
| 6 | + Open-Meteo revision | ? | |
| 7 | + Fingrid real-time | ? | |

Do the same for pinball and both Brier scores, not only MAE. The table *is* the reasoning chain worth 20 jury points.

## Recent-conditions features

The conditions shift (PLAN finding 9): spike shares rose from 9 / 7 % in training to 12 / 13 % in validation, and the up share dropped toward the end. Recency weights help, but the model is still fixed after 4 Oct.

💡 **Let the model see the current conditions through features** computed from data that is already usable at the origin:

- `roll_absgap_7d`: mean |gap| over the last 7 days of usable quarters
- `roll_spike_hi_7d`, `roll_spike_lo_7d`: spike shares over the last 7 days
- `roll_up_share_7d`: share of up-regulation

These follow the data rule (every row has `first_usable_origin_utc ≤ t`), so they are **not** retraining on test data. They're ordinary lagged features. During the test period they update by themselves as the conditions change.

⚠ **Caveat:** training has only ~4 months, so these features take few distinct values, and the model may not trust them. Compare against simply raising the spike base rates. Keep them only if validation improves.

⚠ This is different from the open question in PLAN §12 ("recalibrate on test-period prices"). That question is about refitting; this is just features. Ask the organisers anyway if unsure.

## Calibration after the final retrain

**The problem:** the plan calibrates P10/P90 (and the probabilities) on validation, then retrains on everything up to 4 Oct for the test run. A model refit on the validation weeks fits them better than it would fit new data, so calibration measured there would make the band **too narrow** on the test.

**Options:**
1. **Carry the offsets over:** learn the calibration on validation with the model trained up to 6 Sep, then apply the same per-step-band offsets to the retrained model. Simple. It assumes the retrained model is about as wide as the old one.
2. **Rolling time-split:** e.g. train up to 9 Aug → predict 10 Aug – 6 Sep; train up to 6 Sep → predict 7 Sep – 4 Oct. Fit the calibration on all out-of-sample predictions together. More robust; costs one more training run (seconds with LightGBM).
3. **Don't retrain:** use the model trained up to 6 Sep for the test. This gives up 4 weeks of the most recent data, which is bad given the drift.

My recommendation is **2**, with 1 as the fallback. Pinball loss punishes too-narrow bands more than too-wide ones, so if unsure, widen.

## Spike probabilities

✔ Keep P(spike_high) = P(up) × P(gap > 50 | up), as in PLAN finding 11.

💡 Add a **final calibration on the product** (isotonic or Platt), fitted on out-of-sample predictions from option 2 above. Errors in the two parts multiply, and the Brier score only sees the product.

💡 Compare against **always predicting the base rate per (local hour × wind quintile)** as a cheap spike baseline. With the shares drifting, a well-calibrated simple model can beat a sharp but miscalibrated one.

## Direction

- Binary up vs down + `p_none = 0.002` (never 0).
- ☐ Check in `score.py` whether direction Brier is a 3-class sum (0.4509 suggests so).
- 💡 Make the direction and price forecasts agree: if `p_up > 0.5` but P50 < spot, that's a "conflicting signals" flag for the dashboard (PLAN §6 panel 6). Don't force them to agree in the model, but count how often it happens on validation.

## Quantiles

- ✔ LightGBM quantile on the gap, step as a feature, then sort.
- 💡 If the pinball score lags: try a **mixture approach**. Use P(up) together with the gap distribution for up quarters and for down quarters (both learned on similar hours/wind), and read P10/P50/P90 from the combined distribution. The gap distribution has two humps (+25 up, −17 down, PLAN §1), which this handles directly.
- 💡 **Recency weights:** tune the half-life (e.g. 14 / 28 / 56 days) on validation. Don't guess it.

## Pre-June history (from Frank's E1)

💡 Frank suggests training on Fingrid history from Mar 2025 onwards ([[Comparison with Frank's branch]]). Oct–Nov 2025 is the same season as the test. That's the best fix for the drift problem that we have.

- **Ask first.** Keep it out of the pipeline until the organisers say yes in writing in `#turku-energia`.
- **Direction model first.** When the grid goes up or down shouldn't depend on the 1 Jun pricing change. Gap sizes and spike tails do: since 1 Jun, the imbalance price can be a mix of mFRR and aFRR prices. Add pre-June rows to the quantile and spike-tail models only if validation agrees.
- **Down-weight it:** e.g. pre-June rows at 0.3–0.5 weight, tuned on validation. Or add an `is_pre_june_rule` flag so the model can tell the two periods apart.
- **Gap needs spot:** pre-June FI spot isn't in the package. It would come from Energinet, which has the same licence question as Frank's E3.
- **Bonus:** 2025 includes the 26 Oct DST change, so local-hour features can be checked against a real clock change.

## Things not to spend time on

- Deep learning or sequence models: ~4 months of data, 36 hours, and LightGBM trains in seconds.
- Pretrained time-series models (Frank's E6, Chronos-2 / TimesFM): Frank himself expects it to lose. Feeding it the history before each origin has to go through the availability filter, a new leakage risk. It also adds a model to the licence list. Do it only if everything else is done on Sunday morning, and drop it otherwise.
- Per-step separate models: the step feature in one model shares data better.
- Hyperparameter search beyond a small grid: the gains are small next to features and calibration.
