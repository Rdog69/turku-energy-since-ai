# Claude Opus 5.5: proposal

*Written before reading the other four answers. Every number marked ✔ was computed on training data (≤ 4 Oct) for this proposal; ☐ marks something unverified.*

## 1. Thesis

The imbalance price is set by one hidden quantity: **how wrong the day-ahead plan is in Finland right now and over the next hours**. Its sign gives the direction, and its size, through the steep up-regulation merit order, gives the gap. A LightGBM-on-gap team sees that quantity only through data that is 75 minutes old and through day-ahead forecasts that, by construction, contain no plan error. Our edge is to **estimate the plan error directly**: a *nowcast* of the current state from fresh real-time data (worth up to ~17 €/MWh of MAE at step 1, ✔), a *re-forecast* of wind from the latest weather runs (the plan error over hours 2–10), and **longer history** for the classifiers. All of this feeds a **structured mixture output** that turns one coherent belief into all eight submitted numbers, each tuned to its own metric.

## 2. Method

### 2.1 Decomposition (the output layer)

For each (origin, step), model:

- `π = P(up)` (and `p_none`, a constant ≈ 0.002 ✔);
- `F_up(g)`: the distribution of the gap given up-regulation;
- `F_down(g)`: the distribution of the gap given down-regulation.

Then the gap distribution is the mixture `F(g) = π·F_up(g) + (1 − π)·F_down(g)`, plus the point mass at 0 for none. Every column comes from it:

| Column | From the mixture | Metric it is tuned for |
|---|---|---|
| `p50` | spot + mixture median (solve F(g) = 0.5 numerically) | MAE |
| `p10`, `p90` | spot + mixture 10 % and 90 % quantiles | pinball |
| `p_up`, `p_down`, `p_none` | π, 1 − π − p_none, p_none | 3-class Brier |
| `p_spike_high` | π · (1 − F_up(50)) | Brier |
| `p_spike_low` | (1 − π) · F_down(−50) | Brier |

Why this beats direct quantile regression:

- **The distribution is bimodal** (up: median +25, down: median −17 ✔). The median and outer quantiles jump between the modes as π crosses thresholds. A mixture represents that exactly; a single quantile model must learn the jump from the features.
- **One belief, eight numbers.** The outputs are consistent by construction (spike ≤ direction ✔ finding 8), which also helps the dashboard and the jury's "consistency" criterion.
- **Each piece is easier to learn.** ✔ Down-regulation magnitude barely moves: the median is −18 → −15 across activated-volume quintiles. So `F_down` is a narrow, nearly stable distribution, mostly hour-dependent. ✔ Up-regulation magnitude rises steeply with volume (median +8 → +61 across quintiles, rank correlation 0.58). So `F_up` is a function of the **expected up-regulation volume**. Nearly all the difficulty sits in π and in the size of the up-regulation.

Implementation:

- **π:** LightGBM binary classifier with log loss, isotonic-calibrated per step band (1–4, 5–12, 13–40) on the last 3 training weeks.
- **`F_up` and `F_down`:** LightGBM quantile models on a grid (q = 0.05, 0.1, …, 0.95) trained only on rows of that direction, with monotone sorting. Interpolate to get CDFs. `F_up` gets volume-related features (see 2.2).
- **Keep a direct LightGBM quantile model as a challenger.** For each metric, ship whichever of mixture or direct wins on validation, or a blend tuned on validation. This is cheap and removes the risk.

### 2.2 Features that measure plan error

1. **Day-ahead net position:** consumption forecast − wind forecast − solar forecast (Fingrid 165, 246, 247). ✔ It separates outcomes better than wind alone: up share 21 % → 49 %, mean |gap| 13 → 49, high-spike share 3 % → 14 %, low-spike share 0.3 % → 16 % across quintiles. This is cheap and in the package.
2. **Nowcast block (steps 1–12):**
   - Real-time wind production − DA wind forecast: the *current* wind plan error.
   - Real-time consumption − DA consumption forecast.
   - Real-time net import vs. the scheduled position.
   - Grid frequency deviation (Nordic-wide, but an instantaneous imbalance signal).

   Source: Fingrid 3-minute real-time datasets ☐ (IDs to confirm with the key), each aggregated to the quarter and lagged by an honest publication delay (☐ 15 min). These go into a **nowcast sub-model** trained on Jun–Sep: it predicts the *current* (lag-1) gap and direction from the fresh proxies. Its output feeds the main models as features.
3. **Wind re-forecast (steps 5–40):** from Open-Meteo Single Runs (ECMWF IFS and ICON, 100 m wind at ~10 west-coast points), fit a simple power curve on Jun–Sep (realised wind from Fingrid vs. forecast wind speed). Use the latest available run at the origin minus the DA forecast. That gives a predicted wind plan error per future quarter, which is exactly the quantity the market will have to balance.
4. Keep the standard features: spot level and ramps, hour × wind interactions (✔ evening low-wind |gap| 54 vs 24 high-wind), step, recent state.

### 2.3 Calibration and drift

- Recency weights (half-life ~3 weeks) for every model.
- **Probabilities:** isotonic calibration on the last 3 training weeks, per step band. Brier scores are dominated by calibration when the signal is weak, as it is at long steps.
- **Quantiles:** conformalised quantile regression per step band, fitted on the last 3 training weeks, to hit coverage of 10 % / 90 % on each side separately. Pinball is asymmetric, so fit each side on its own.

## 3. Expected gain per score component

The reference is a well-tuned LightGBM-on-gap model with package features only.

| Metric | Main source of gain | Rough estimate | Confidence |
|---|---|---|---|
| MAE (30) | The nowcast at steps 1–8, plus the wind re-forecast at steps 5–40 | ✔ The upper bound at step 1 is 43.8 → 26.4 (lag-5 vs lag-1 information). If the nowcast recovers a third of that on steps 1–8 and the wind re-forecast gives 1–3 % at longer steps, overall MAE improves by **~2–4 %** | Medium-low: depends on how well the real-time proxies track the gap |
| Pinball (20) | Mixture quantiles that follow π across the bimodal gap; separate conformal adjustment per side | **3–8 %** | Medium |
| Spike Brier (20) | π × tail decomposition, net position, nowcast at short steps, recency calibration of base rates (✔ 9/7 % in training vs 12/13 % in validation) | **3–6 %** | Medium |
| Direction Brier (10) | Longer history (§4), nowcast (✔ agreement 0.85 at lag 1 vs 0.71 at lag 5), calibration | **3–7 %** | Medium |

Because points are relative to the best team, a few percent on each metric is worth a lot. The gap between "good" and "best" teams will be small.

## 4. Data

| Source | Use | Honest delay | Fetch | Trap |
|---|---|---|---|---|
| Fingrid real-time 3-min (wind, consumption, production, frequency, net import ☐ IDs) | Nowcast | ☐ ask the organisers; assume 15 min + round up to the hour | API with key; ~5 months × a few series is a few dozen paged requests | Use measurement timestamps + delay, **never** "latest value" endpoints |
| Fingrid history **before June 2026**: direction (369), DA forecasts (165, 246, 247), wind production | Train π on ~18 months including last autumn and winter ☐ (does 369 go back to the Nordic mFRR market start in Mar 2025?) | none needed for training | Same API | The price formula changed in June, but the **direction** logic did not ☐. Use it for π only, never for `F_up` / `F_down`. Compute features from those same Fingrid series, since spot isn't needed for π, or treat spot as missing. |
| Open-Meteo Single Runs (ECMWF IFS, ICON) | Wind re-forecast | init + 7 h (IFS), + 4 h (ICON), rounded up | One call per run per point batch | Never use the Historical Forecast API; filter by init time + delay |
| UMM | Dashboard "why" only | publication date per version | – | Skip for the model: rare events, low score value |

## 5. Experiment plan (5 people, ~34 h)

| # | Experiment | Hours | Go/no-go on validation |
|---|---|---|---|
| 0 | Package-only LightGBM-on-gap (direct quantiles + classifiers) + availability layer + validator | 4 | Beats the baseline on all 4 metrics. This is the safety net, shipped by Sat noon whatever else happens. |
| 1 | Net-position + hour × wind features, recency weights, per-step-band calibration | 2 | Any gain on ≥ 2 metrics |
| 2 | Mixture output layer vs direct quantiles (same features) | 3 | Keep per metric whichever wins |
| 3 | Fingrid real-time fetch + nowcast sub-model | 6 | Nowcast lag-1 direction accuracy > 0.75 on validation, and MAE gain at steps 1–8 |
| 4 | Fingrid pre-June history for π | 3 | Direction Brier gain ≥ 2 % |
| 5 | Open-Meteo wind re-forecast | 6 | Gain at steps 5–40 |
| 6 | Blending (mixture + direct), final conformal + isotonic on the last 3 weeks, retrain to 4 Oct | 2 | – |

**Cut order if time runs short:** 5 → 4 → 3. Items 0–2 need only the package.

## 6. Ideas others won't think of

1. **The nowcast as a "virtual fresh price".** Everyone feeds the 75-minute-old gap as a lag feature. Instead, train a model that *predicts what the gap is right now* from real-time physics, and use that as the anchor for the first hours. ✔ The prize is large: lag-1 information halves step-1 error.
2. **Train the direction model on the old regime.** The package starts in June because the *price* formula changed, and everyone will assume all earlier data is useless. Direction comes from mFRR activations, which didn't change ☐, and last October–November is the closest analogue to the test period.

## 7. Risks and what to verify first

- ☐ **Organisers reject the Fingrid real-time delays,** which kills experiment 3. Ask tonight. Fallback: experiments 1, 2, 4 and 5.
- ☐ **Dataset 369 history may not start before June 2026,** or its definition may have changed. Check with one API call.
- **The mixture's median can flip sharply when π ≈ 0.5,** which risks large MAE swings. Mitigate with a blend with the direct p50, tuned on validation.
- **The October drift** (up share 25 % on 1–4 Oct ✔) may make calibration on the last 3 weeks of September wrong. Validate week by week, and prefer calibration on the most recent 2 weeks if it is stable.
- **Leakage review:** each external source gets a `first_usable_origin_utc` column and goes through the same `available_at()`. A unit test samples origins and asserts no row exceeds the origin.
