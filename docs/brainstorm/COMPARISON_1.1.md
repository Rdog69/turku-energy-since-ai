# Brainstorm comparison 1.1 (round 2)

> Branch `brainstorming-abdo`, Fri 6 Nov night. Round 1 converged on one design (see [COMPARISON.md](COMPARISON.md)), so round 2 changed the setup to get different ideas, and **measured** them instead of trusting estimates. ✔ = measured on package data (≤ 4 Oct); ☐ = judgement.

## TL;DR

1. **The round-1 design is confirmed by measurement.** On validation, the direction mixture beats a crowd-style direct model on spike Brier (**−10 %**), pinball (−4 %) and MAE (−1 to −2 %) ✔. Calibrating on the most recent weeks adds another step on every metric and fixes coverage from 0.60 to 0.78 ✔.
2. **The edge to "first" is in the probability columns.** Spike and direction Brier have a tiny baseline-to-best range, so they're the most points per unit of work ☐ (arithmetic in [05](round2/05_claude-opus-5.5.md#3-where-the-points-are)).
3. **The best new idea is to model spikes against the spot threshold** (from DeepSeek): the low-spike rate in down quarters goes from **0.3 % to 58 %** across spot quintiles ✔. Spot is known for all 40 steps, so this is free signal *and* a drift defence.
4. **Second-best is regime-aware calibration** (from GLM): September's down-regulation intervals are much wider than June–August's (P10 −82 vs −29 to −53) ✔. Don't fit widths on September alone; condition them on context known at the origin.
5. **Several ideas are killed by their own tests:** import saturation as a spike driver, FI–SE1 price decoupling, snapping to round bids (Kimi K3), and aggressive recency weighting (**hurts**, ✔).

## What changed from round 1

| | Round 1 | Round 2 |
|---|---|---|
| Context | A summary brief | **Everything:** starter README, `availability.csv`, `score.py`, baseline notebook code, challenge brief, briefing transcript, PLAN.md, all round-1 answers, and **[real data samples](round2/context/data_samples.md)** (about 80k tokens per model) |
| Data samples | Aggregates only | Real rows of every Fingrid/ENTSO-E series, one volatile day (9 Sep) and one calm day (19 Sep) in full, freshness at an origin, per-series statistics. Spot only as monthly aggregates ⁽*⁾ |
| Question | "Your best solution" | "The core is assumed (we and the leaders build it); what puts us **first**?" |
| Angle | The same for all | **One each:** Kimi K3.1 Pro = scoring mathematician, Kimi K3 = Nordic market insider, DeepSeek = data detective, GLM-5.3 = red team, Opus = **empirical lab** (runs experiments) |
| Verification | Estimates | ✔ Experiments + kill-checks on training data ([`experiments/brainstorm_round2/`](../../experiments/brainstorm_round2/)) |

⁽*⁾ The starter package is now committed in this private repo. **Raw spot rows were still not sent to Featherless:** the licence forbids sharing the data further, and a third-party API is outside the team. `tools/kimi.py` blocks it.

Files: prompts in [`round2/`](round2/) (`00_prompt_common.md` + [`lenses.md`](round2/lenses.md)); answers [01 Kimi K3.1 Pro](round2/01_kimi-k3.1-pro.md) · [02 Kimi K3](round2/02_kimi-k3.md) · [03 DeepSeek](round2/03_deepseek-v4.1-flash.md) · [04 GLM-5.3](round2/04_glm-5.3.md) · [05 Opus (measured)](round2/05_claude-opus-5.5.md).

## Measured results (validation 7 Sep – 4 Oct, 26,700 rows) ✔

| Model | MAE | Pinball | Coverage | Spike Brier | Direction Brier |
|---|---:|---:|---:|---:|---:|
| Official baseline | 66.20 | 24.18 | 0.68 | 0.1132 | 0.4509 |
| Spot + constant | 44.28 | 15.00 | 0.67 | 0.1133 | 0.4508 |
| Crowd proxy (direct) | 43.98–44.39 | 13.37–13.47 | 0.54 | 0.1073 | 0.4388 |
| **Mixture** | 43.39–43.46 | 12.77–12.84 | 0.60 | 0.0960–0.0966 | 0.4388 |
| **Mixture + recent calibration** | 43.41 | **12.45** | **0.78** | **0.0941** | **0.4289** |
| Mixture, 21-day recency weighting | 43.36 | 13.17 | 0.59 | 0.0984 | 0.4530 ❌ |
| Direct p50, **price** target instead of gap | 43.93 vs 44.34 (wins both folds) | | | | |

Ranges are two runs (random early-stopping split, about ±0.4 MAE of noise). Only 2,688 distinct quarter-hours lie under the 26,700 rows, so decide with day-block bootstrap, not row counts (Kimi K3.1 Pro).

## The five angles at a glance

| Advisor (angle) | Top idea | Status |
|---|---|---|
| **Kimi K3.1 Pro** (scoring maths) | Convex blends instead of per-column winner selection; Brier-optimal shrinkage towards a recent prior; uncertainty-scaled interval widths; causal averaging with the previous origin's forecast | ⚠️ Blend headroom is small (error correlation 0.993 ✔). **Shrinkage and calibration ✔ help.** The rest are untested but cheap. Its evaluation protocol is the most rigorous of the five: adopt it. |
| **Kimi K3** (market insider) | Congestion/decoupling regime from flow saturation; snap quantiles to round bids; volume → merit-order tail; aFRR damping; episode survival | ❌ Saturation (0.281 vs 0.249), decoupling (not monotone) and bid snapping (14 % whole euros) are killed by its own checks ✔. Volume → tail is still plausible (up gap rises with MW ✔), but the volume itself must be forecast. |
| **DeepSeek** (data detective) | Anchor on the last mFRR price and model the **price** level; **spike threshold-distance** features; a July fold; lag-3 flows; online recalibration (gated) | ✅ The **spike threshold idea is the strongest new signal ✔.** The price target wins modestly ✔. The identity check ✔ shows no package-only nowcast exists. ❌ It got the high-spike sign wrong, and read 1–4 Oct as "October". |
| **GLM-5.3** (red team) | **Context-conditional calibration** (fit widths and base rates on known context, not on September); k-NN analogue hedge; direction run-length features; demote Fingrid real-time; DST and fallback suite | ✅ The September-width risk is real ✔. Its point that an honest delay gives lag 2–3, not lag 1 (MAE 33.9–39.4, not 26.4) corrects round 1 ✔. The analogue hedge is untested but cheap (3 h). |
| **Opus** (empirical lab) | Measure everything; prioritise the probability columns | ✔ The numbers above |

## Mistakes the models made (so the team doesn't inherit them)

- **"October is calmer / more down-heavy"** (DeepSeek, GLM). The "Oct" row in the data samples is **1–4 Oct only** (384 quarters at the end of training), not the test month. This was my labelling. Their *fixes* (conditioning on per-origin context) are still right.
- **"Higher spot → fewer high spikes"** (DeepSeek). It's the opposite: within up-regulation the high-spike rate *rises* with spot (12 % → 30–37 %) ✔.
- **"Bid prices are atomic"** (Kimi K3). They were generalised from a single spike day; ✔ only 14 % of up prices are whole euros.
- **"Use direct spike classifiers rather than the mixture tail"** (Kimi K3.1 Pro). ✔ The mixture tail is 10 % better on validation. Keep the direct classifier only as a blend candidate.

## Updated plan (package-only first, everything gated on two folds)

| # | Step | Evidence | Owner |
|---|---|---|---|
| 0 | Harness + exact baseline reproduction; **folds: A = 7 Sep – 4 Oct, B = a different regime (e.g. July as target, GLM)**; day-block bootstrap for decisions | Kimi K3.1 Pro, GLM | Pavlo + Pavel |
| 1 | **Mixture** (P(up) × conditional quantile grids) + direct challenger | ✔ −10 % spikes, −4 % pinball | Pavel |
| 2 | **Spike threshold-distance features** (`spot − 50 − last down price`, `last up price − spot − 50`, spot level) in the direction and conditional models | ✔ 0.3 % → 58 % low-spike gradient | Pavel |
| 3 | **Calibration on recent weeks**: per-band quantile offsets + Platt or shrinkage for the probabilities; widths conditioned on context, not month (GLM) | ✔ Pinball −2.6 %, direction −2.2 % | Pavel / Jim |
| 4 | Price-space target inside the mixture; direction run-length features | ✔ (direct) / ☐ | Pavel |
| 5 | **No aggressive recency weighting** (a long half-life at most, ablated) | ✔ 21 d hurts | Pavel |
| 6 | External data behind measured gates: Fingrid real-time (honest delay → lag 2–3), Open-Meteo | ☐ Smaller prize than round 1 claimed | Pavlo |
| 7 | Hedges if time allows: k-NN analogue CDF (GLM); causal averaging with the previous origin (Kimi K3.1 Pro) | ☐ | – |
| 8 | DST + fallback-CSV suite; negative-results appendix for the jury | GLM, DeepSeek | Abdo |

**The reasoning chain for the jury** (all five agree): the day-ahead plan → its error (wind, net position) → direction and activated volume → an asymmetric merit order (steep up, flat down ✔) → price relative to spot → the spike thresholds. The killed ideas go into a **negative-results appendix**, which is cheap credibility (DeepSeek, GLM).

## Questions for `#turku-energia` (unchanged, still open)

1. Fingrid real-time series: allowed, and with what delay? Settled values vs what was visible in real time?
2. Pre-June Fingrid history for training?
3. Calibration using test-period prices already usable at the origin?

*Cost of this round:* about 324k prompt and 91k completion tokens over four models, on two working keys (#1 and #2 still return 401).
