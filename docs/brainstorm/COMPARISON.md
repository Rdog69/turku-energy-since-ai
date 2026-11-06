# Brainstorm: five proposals compared

📋 **Short version:** [TLDR.md](TLDR.md) · 🆕 **Round 2 (measured):** [COMPARISON_1.1.md](COMPARISON_1.1.md)

> Branch `brainstorming-abdo`, Fri 6 Nov evening. We asked the top open-weight models on the leaderboard (via Featherless) and Claude for "the solution you'd bet on to finish first", beyond a plain LightGBM-on-gap model. ✔ means checked on training data (≤ 4 Oct); everything else is a judgement call.

## How it was run

- **Same brief for everyone:** [`00_prompt.md`](00_prompt.md). It covers the task, the scoring, the availability rule, our verified findings (aggregates only, no spot data) and the current plan.
- **Models:**
  - [Kimi K3.1 Pro](01_kimi-k3.1-pro.md)
  - [Kimi K3](02_kimi-k3.md), standing in for MiMo-V2.6-Pro, which isn't on Featherless
  - [DeepSeek V4.1 Flash 1017](03_deepseek-v4.1-flash.md)
  - [GLM-5.3](04_glm-5.3.md)
  - [Claude Opus 5.5](05_claude-opus-5.5.md), written *before* reading the others
- **To reproduce:**

  ```bash
  .venv/bin/python tools/kimi.py ask docs/brainstorm/00_prompt.md -m <model> -o <out>.md
  ```

  ~12.5k prompt tokens and ~58k completion tokens in total.

## TL;DR

**All five converged on the same core, independently:** one **direction-mixture distribution**. Each row's price distribution is built as P(up) × gap distribution given up, plus P(down) × gap distribution given down, plus a small point mass at spot for "none". **All eight submitted numbers are read off that one distribution**, and the main new input is the **wind forecast error from Fingrid real-time data**. Five independent votes is strong evidence that this is the right architecture. It also means the edge comes from **executing it well**, plus a few ideas only one model had.

Recommended stack:

1. Mixture output layer, with a direct LightGBM challenger kept **per column**.
2. Fingrid real-time wind error, which doubles as a nowcast of the current state.
3. Pinball-optimal and Brier-optimal calibration per step band.
4. Open-Meteo wind re-forecast.
5. Cheap extras that pass validation.

## Where all five agree

| Idea | Kimi K3.1 Pro | Kimi K3 | DeepSeek | GLM-5.3 | Opus | Evidence |
|---|:-:|:-:|:-:|:-:|:-:|---|
| Mixture CDF: P(direction) × conditional gap quantiles, invert for p10/p50/p90 | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ Bimodal gap (up median +25, down −17) |
| Spikes from the same CDF (consistent with direction and p90) | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ Only 7 + 18 off-direction spikes in ~12k quarters |
| Keep a direct LightGBM-on-gap challenger; **pick the source per column** | ✔ | – | ✔ (fallback) | ✔ | ✔ | Metrics are scored independently, so this is free |
| Fingrid real-time wind − DA wind forecast as the key external feature | ✔ (priority 1) | ✔ | ✔ | ✔ ("the moat") | ✔ | ✔ Freshness is worth up to 43.8 → 26.4 MAE at step 1 (lag 5 vs lag 1 information) |
| Open-Meteo Single Runs revision vs the DA forecast, west-coast points | ✔ | ✔ | ✔ | ✔ | ✔ | ☐ Value unmeasured |
| Calibration per step band; optimise **pinball and Brier**, not coverage | ✔ | ✔ | ✔ | ✔ | ✔ | Baseline coverage 0.68 shows the headroom |
| Recency weighting against drift | ✔ | ✔ | ✔ | ✔ | ✔ | ✔ Sep std 141; up share 25 % on 1–4 Oct |
| Leak-safe harness + baseline reproduction **before** any modelling | ✔ | ✔ | ✔ | ✔ | ✔ | A leak scores 0 |
| UMM outages: skip or low priority for the model | skip | skip | optional | medium | dashboard only | Rare events, little statistical power |

**Assumed Fingrid real-time delay:** four say **30 min**, I said 15. Use **30 min** unless the organisers confirm something shorter, and get the answer in writing.

## Ideas only some proposed: verdicts

| Idea | From | Verdict | Why |
|---|---|---|---|
| **Wind error as an auxiliary target**: predict realised-minus-DA wind with its own model, then feed the out-of-fold prediction into the price models | Kimi K3.1 Pro | **Adopt (high)** | It aligns learning with the physical driver and turns noisy NWP wind speeds into MW of plan error. It's the natural way to use Open-Meteo. Must use out-of-fold predictions. |
| **Horizon bridge**: a fundamentals-only model and a full-state model, blended per step band with recent-state weight non-increasing in step | Kimi K3.1 Pro | **Adopt (medium)** | ✔ Direction agreement decays 0.70 → 0.57, so the hand-over exists. Cheap stacking. |
| **Nowcast of the current state** as a "virtual fresh price", from real-time wind error + frequency + consumption | Opus, DeepSeek ("latent net-imbalance") | **Adopt if Fingrid real-time is allowed** | ✔ The biggest measured prize: lag-1 info halves step-1 error. Go/no-go is how much of that the proxies recover. |
| **Day-ahead net position** (consumption − wind − solar forecasts) | Opus, GLM ("residual load") | **Adopt now (package-only)** | ✔ Up share 21 % → 49 %, \|gap\| 13 → 49 across quintiles. Stronger than wind alone. |
| **Merit order: forecast volume, map it to price** | GLM, Opus | **Adopt for F_up only** | ✔ Up gap rises with activated MW (median +8 → +61, rank corr 0.58). ✔ Down gap is flat (~−17). So volume features belong in the up-conditional model, not the down one. |
| **Train direction on pre-June Fingrid history** (last autumn and winter) | Opus only | **Test (medium)** | ☐ It depends on dataset 369 existing before June with the same definition. One API call settles it. It's the only way to show the model October/November conditions. |
| **Pinball-optimal per-band correction** (empirical q-quantile of residuals), shrunk towards the global correction | Kimi K3.1 Pro, Kimi K3 (50 % shrink) | **Adopt** | It directly minimises the scored loss. Shrinkage protects against a 4-week validation window. |
| **Stress test**: train Jun–Aug → score Sep; choose configs by min(validation, stress) | Kimi K3 | **Adopt** | Cheap. It guards against tuning to one volatile month. |
| Grouped/conditional conformal by direction-probability decile × step band | DeepSeek, GLM | **Test** | Plausible but data-hungry. Fall back to per-band. |
| **Trailing-state features** (trailing up-share, gap quantiles, our own past residuals) as a "live" drift defence | Kimi K3 | **Low priority** | ✔ On its own, trailing up-share predicts the next 10 h *worse* than a constant: Brier 0.236 (7 d) and 0.253 (24 h) vs 0.224, correlation −0.03 for 7 d. It might still help as a LightGBM feature: try it in one ablation, not as a pillar. |
| Point mass at gap ≈ 0 that direct quantile models "smear" | Kimi K3 | **Overstated** | ✔ Only 0.17 % of quarters are exactly 0, and 2.2 % have \|gap\| < 1. |
| Reconstruct the June-2026 VWAP rule (mFRR + aFRR) for a "damping" feature | Kimi K3 | **Skip** | ✔ The price equals the mFRR marginal price in 41 % of up quarters. aFRR *volumes* aren't in the package, so the rule can't be reconstructed, and it's ex-post anyway. |
| **HMM forward-backward smoothing** of direction probabilities across the 40 steps | DeepSeek | **Skip** | The classifier's per-step probabilities are already marginals given the same information, so smoothing them double-counts. Low expected value for its cost. |
| "Spot-differenced price persistence" at steps 1–4 | GLM | **No-op** | ✔ It's algebraically identical to spot + last gap (difference 4e-13). |
| Train on quarter-hour origins (4× rows) | GLM | **Skip** | Data becomes usable only at full hours, so the extra rows mostly repeat information already in the hourly rows. |
| Grid frequency deviation as an instantaneous imbalance signal | DeepSeek, Opus | **Test with the nowcast** | It's Nordic-wide rather than Finnish, but free once we're fetching Fingrid real-time anyway. |

## Recommended combined plan

Ordered by expected value per hour. Owners follow PLAN.md §11.

| # | Step | Owner | Gate on validation (and the Jun–Aug → Sep stress test) |
|---|---|---|---|
| 0 | Harness: `available_at()`, leak asserts, reproduce baseline 66.20 / 24.18 / 0.1132 / 0.4509, rolling folds | Pavlo + Pavel | Exact baseline match. **Nothing else starts before this.** |
| 1 | Direct LightGBM-on-gap ("crowd proxy") with package features + net position + hour × wind | Pavel | Beats baseline on all 4 metrics. This is the **safety submission** by Sat noon. |
| 2 | Mixture output layer (direction classifier + up/down quantile grids + CDF inversion), per-column selection against step 1 | Pavel | Keep per column whatever wins on both folds |
| 3 | Pinball- and Brier-optimal calibration per step band, shrunk, chosen on min(val, stress) | Pavel / Jim | Doesn't degrade on the stress test |
| 4 | Fingrid real-time fetch (wind, consumption, production, frequency) at a 30-min delay → wind error + nowcast features | Pavlo | First check: wind-error autocorrelation over 1–10 h (GLM's thesis test). Then: MAE gain at steps 1–8 |
| 5 | Pre-June Fingrid history for the direction model | Pavlo | Dataset 369 exists before June; direction Brier gain ≥ 2 % |
| 6 | Open-Meteo runs → auxiliary wind-error model (out-of-fold) → feature for price and direction | Pavlo + Pavel | Gain at steps 5–40 on both folds |
| 7 | Horizon bridge (fundamentals vs full-state blend) | Pavel | Direction or MAE gain |
| 8 | Final retrain to 4 Oct, test backtest, validator | All | `VALIDATION PASSED` |

**Cut order:** 7 → 6 → 5. Steps 0–3 need only the package and already contain the agreed core.

**For the reasoning chain (20 jury points):** the story all five proposals share is **wind forecast error → system imbalance → mFRR direction and volume → steep up-regulation merit order → price**. Each ablation step above is one link in that chain. Kimi K3 and GLM both stress not under-investing here.

## Questions for `#turku-energia` tonight

1. Are Fingrid **real-time 3-min** series allowed, and with what publication delay (we assume 30 min)? GLM notes that querying now returns *settled* values, which may differ from what was visible in real time. Is that acceptable?
2. Can **pre-June Fingrid history** (direction 369 and the DA forecasts) be used for training? It's before the cutoff, but it's a different price regime.
3. (Already in PLAN.md) May test-period prices that are usable at the origin feed calibration or trailing features?

## Caveats

- The models' gain estimates (MAE −1 to −6 %, pinball −3 to −12 %, and so on) are **guesses**. None was measured. Their "crowd" baselines range from MAE 35 to 46, which shows how uncertain they are.
- DeepSeek's and GLM's crowd numbers aren't grounded in our data. Re-estimate once step 1 gives us real numbers (Sat morning).
- MiMo-V2.6-Pro (rank 2) wasn't available on Featherless, so Kimi K3 (rank 5) stood in. Two of the five views are therefore from Moonshot models.
