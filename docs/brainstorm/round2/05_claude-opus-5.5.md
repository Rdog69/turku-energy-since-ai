# Round 2: Claude Opus 5.5, the empirical lab

*Angle: instead of estimating gains, **measure** them on the package data. Everything here was run on real origins (train: targets before 7 Sep; validation: origins 7 Sep – 4 Oct, 26,700 rows) with availability lags asserted against `first_usable_origin_utc`. The scripts are in [`experiments/brainstorm_round2/`](../../../experiments/brainstorm_round2/). The model is scikit-learn HistGradientBoosting (the LightGBM family) with 28 package-only features.*

## 1. Thesis

The mixture design is **measurably** better than the crowd's direct model on three of the four metrics. The largest gain is on **spike Brier (−10 %)**, which is also the most point-dense metric. Calibration on the most recent weeks adds a second clear step. The real gap to "first" is in the **probability columns** (spikes and direction), where the distance between baseline and best is tiny, so every 0.001 counts. MAE is the most crowded metric and the hardest to move with package data.

## 2. Measured results (validation, all 40 steps)

| Model | MAE | Pinball | Coverage | Spike Brier | Direction Brier |
|---|---:|---:|---:|---:|---:|
| Official baseline | 66.20 | 24.18 | 0.68 | 0.1132 | 0.4509 |
| Spot + constant quantiles | 44.28 | 15.00 | 0.67 | 0.1133 | 0.4508 |
| **Crowd proxy** (direct quantiles + 3 classifiers) | 43.98–44.39 ¹ | 13.37–13.47 | 0.54 | 0.1073 | 0.4388 |
| **Mixture** (P(up) × conditional quantile grids, CDF inversion) | **43.39–43.46** | **12.77–12.84** | 0.60 | **0.0960–0.0966** | 0.4388 ² |
| Mixture + recent calibration ³ | 43.41 | **12.45** | **0.78** | **0.0941** | **0.4289** |
| Mixture, 21-day recency half-life | 43.36 | 13.17 | 0.59 | 0.0984 | 0.4530 |

¹ The range comes from the random early-stopping split in two runs; treat about ±0.4 MAE as noise.
² The same direction classifier is used in both.
³ Two-fold calibration inside validation: fit on 7–20 Sep, score on 21 Sep – 4 Oct and vice versa, then average. It uses per-band additive quantile offsets and Platt scaling for the probabilities. This simulates "calibrate on the most recent weeks before the test".

**Takeaways:**

1. **Mixture vs direct:** spike Brier −10 %, pinball −4 %, MAE −1 to −2 %. The spike gain is the biggest single win we have measured.
2. **Calibration on the most recent weeks** adds pinball −2.6 %, spikes −2 % and direction −2.2 %, and fixes coverage from 0.60 to 0.78.
3. **Recency weighting with a 21-day half-life hurts** pinball, spikes and direction (direction gets *worse than the baseline*). Don't use aggressive recency weights. If any, use a long half-life, and only after an ablation.
4. **Predicting the price instead of the gap** (DeepSeek's idea) improves the direct p50 MAE from 44.34 to 43.93, winning on both folds. Worth testing inside the mixture.
5. **Package-only models barely beat spot + constant on MAE** (44.0 vs 44.3). The MAE battle is won with fresher or external information, not with more package features.

## 3. Where the points are

Points = weight × (B − T) / (B − best). With a **guess** of what the best team reaches (☐), the value of one unit of improvement is:

| Metric | B | Assumed best ☐ | B − best | Value of a 1 % relative improvement at our level |
|---|---:|---:|---:|---|
| MAE (30) | 66.2 | ~40 | ~26 | 0.43 € → ~0.5 pts |
| Pinball (20) | 24.18 | ~12 | ~12 | 0.12 → ~0.2 pts |
| Spike Brier (20) | 0.1132 | ~0.090 | ~0.023 | 0.00094 → **~0.8 pts** |
| Direction Brier (10) | 0.4509 | ~0.425 | ~0.026 | 0.0043 → **~1.7 pts** |

The **probability metrics are the most point-dense per relative improvement**, because baseline and best sit close together. Our direction is 0.4289 calibrated, already near our guess for the best. Each further −0.003 there is worth about a point. **Prioritise the spike and direction probabilities.**

## 4. Kill-checks of the other round-2 ideas (training data)

| Idea (from) | Check | Result | Verdict |
|---|---|---|---|
| Import saturation → spikes (Kimi K3) | High-spike rate in up quarters, saturated vs not | 0.281 vs 0.249; at a usable lag of 3 quarters, 0.099 vs 0.087 | ❌ Below its own 2× kill bar |
| FI–SE1 price decoupling marks the spike regime (Kimi K3) | Median \|FI mFRR up − SE1\| by \|gap\| decile | Not monotone (0.5, 2.7, 3.0, 2.1, 0, 0, 0, 0, 0, 7.0) | ❌ |
| Snap quantiles to round bids (Kimi K3) | Share of up prices on round values | 14 % whole euros, 7 % multiples of 5 | ❌ Not atomic |
| Spike risk vs spot threshold (DeepSeek) | Spike rate by spot quintile within direction | **Low spikes \| down: 0.3 % → 58 %**; high spikes \| up: 12 % → 30–37 % (rising, not falling as DeepSeek said) | ✅ Strong: add `lo_dist`/`hi_dist` features; spot level drives the spike base rate |
| Price-space target (DeepSeek) | Direct p50, same features | 43.93 vs 44.34, both folds | ✅ Modest |
| No package-only nowcast: production, consumption and flows close as an identity (DeepSeek) | Residual of production − consumption − net exports | std 61 MW, mean −1 | ✅ Mostly true: package flows carry no hidden imbalance |
| September is unusually wide (GLM) | Down-regulation P10 gap by month | Jun −53, Jul −29, Aug −52, **Sep −82** | ✅ Real: don't calibrate widths on September alone |
| Blend direct + mixture p50 (Kimi K3.1 Pro) | Error correlation; weight grid | Correlation 0.993; best weight 0.75–1.0 on the mixture | ⚠️ Small gain; use the mixture's p50 |
| Effective sample size (Kimi K3.1 Pro) | Distinct validation quarters | 2,688 under 26,700 rows | ✅ Use day-block bootstrap for decisions |

## 5. Corrections to round 1 (including mine)

- **The freshness prize was overstated.** I quoted MAE 26.4 at lag 1. As GLM points out, an honest 30-min delay plus rounding up to the hour gives complete quarters only at **lag 3 (39.4)**, or lag 2 (33.9) at best with a 15-min delay. And that's for the *gap itself*: real-time wind error is only a proxy. Fingrid real-time is still worth testing, but it's a few €/MWh at steps 1–8, not a moat.
- **"October is calmer"** (DeepSeek, GLM) rests on **1–4 Oct only** (384 quarters), the last rows of training. I labelled the month table poorly. Don't treat it as the test month. The principled fix still holds: condition on context known at each origin (spot level, net position) rather than on a month.

## 6. Recommended next steps (all package-only)

1. Mixture as the main model, with recent-weeks calibration (per-band offsets + Platt). ✔ Measured.
2. Add spike threshold-distance features: `spot − 50 − last usable down price` and `last usable up price − (spot + 50)`, plus spot level. ✔ Strongly supported.
3. Test a price-space target inside the mixture's conditional models.
4. Validate on a second fold with a different regime (GLM's "July" fold) and day-block bootstrap before adopting anything.
5. Then add external data (Fingrid real-time and Open-Meteo), each behind a measured gate.
