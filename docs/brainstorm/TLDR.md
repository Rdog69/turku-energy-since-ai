# Brainstorm TL;DR

> 🆕 Round 2 with measured results: [COMPARISON_1.1.md](COMPARISON_1.1.md). This page is the short version of round 1, [COMPARISON.md](COMPARISON.md). Five models were each asked how to beat a plain LightGBM-on-gap model: Kimi K3.1 Pro, Kimi K3, DeepSeek V4.1 Flash, GLM-5.3 and Claude Opus 5.5. ✔ = checked on training data.

## The answer all five gave

**Model the price the way it's formed, as one distribution per quarter-hour:**

> P(up) × the gap distribution given up + P(down) × the gap distribution given down (+ a tiny "none" mass at spot)

All eight submitted numbers are read off this one distribution, so the quantiles, the direction and the spikes never contradict each other.

**Feed it the wind forecast error:** Fingrid real-time wind production minus the day-ahead wind forecast.

Five independent votes means this is the right core. Our edge is executing it well, plus the extras below.

## The numbers behind it (✔)

- Fresh data is worth a lot: step-1 MAE would be **26** with 1-quarter-old data vs **44** with the 5-quarter-old data we get.
- Up-regulation gaps grow with mFRR volume (median +8 → +61 across quintiles). Down-regulation gaps stay flat at about −17.
- The day-ahead net position (consumption − wind − solar) moves the up-regulation share from 21 % to 49 % across quintiles.

## Keep / skip

| ✅ Adopt | ❌ Skip |
|---|---|
| A plain LightGBM challenger, choosing the **best model per column** | GLM's "price persistence" (✔ identical to gap persistence) |
| Calibration aimed at **pinball and Brier**, per step band | Trailing up-share as a drift defence (✔ worse than a constant) |
| Wind error as its **own prediction target** (Kimi K3.1 Pro) | HMM smoothing across steps (double-counts information) |
| Blend a day-ahead-only model with a recent-state model by horizon | Rebuilding the June VWAP price rule (aFRR volumes aren't in the package) |
| Validate on Jun–Aug → Sep too, and choose settings that win both | |
| 🧪 Test: Fingrid history before June for the direction model | |

## Build order

1. Leak-safe harness; reproduce the baseline exactly.
2. **Safety submission** with package data only, by Sat noon.
3. Mixture distribution, choosing the best model per column.
4. Calibration.
5. Fingrid real-time wind error.
6. Fingrid history before June.
7. Open-Meteo weather runs.

Steps 1–4 need only the package. If time runs out, cut from the bottom.

## Ask the organisers tonight

- Fingrid real-time data: allowed, and with what delay? We assume 30 min.
- Fingrid history before June: allowed for training?
- Test-period prices that are already usable at the origin: allowed for calibration?

*The models' gain estimates are guesses. Re-check them once the safety model gives real numbers.*
