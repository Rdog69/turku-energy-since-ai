# Design challenge: win a 10-hour imbalance price forecasting competition

You are advising a 5-person team at a weekend hackathon (Since AI 2026, Turku, Finland). About **34 hours remain** until submission (Sunday 8 Nov 2026, 10:00 Finnish time). The team has laptops, Python, and a free Fingrid Open Data API key. The organisers have scored data; we don't see the test actuals.

**The obvious approach is LightGBM quantile regression on the gap between imbalance price and spot, plus classifiers.** Nearly every competing team will do this or something close to it. Because scoring is **relative to the best team**, matching the crowd earns few points. **We need an edge**: a method, data source, target formulation or calibration trick that measurably beats a well-tuned LightGBM-on-gap model, and is still buildable and leakage-safe in the time left.

Think hard, be concrete and quantitative, and be honest about what is uncertain.

---

## 1. The task

Forecast the **Finnish imbalance price** (Fingrid dataset 319, €/MWh) for each **15-minute quarter-hour**, **1–40 steps (10 h) ahead**, from **every full-hour forecast origin**. Step 1 is the quarter-hour starting at the origin.

- **Test period:** 673 hourly origins, 2026-10-04T21:00Z → 2026-11-01T21:00Z (Finnish time 5 Oct – 1 Nov; DST ends 25 Oct). 673 × 40 = 26,920 rows.
- **Training data:** 1 Jun – 4 Oct 2026 only. The price formula changed on 1 Jun 2026 (see §3), so the package starts then.
- **Validation:** 7 Sep – 4 Oct (part of training). The organisers' scoring script runs locally on it.
- **Test-period inputs are in the package**, but may only be used as features under the availability rule (§4), **never for training**.

Per row we submit:

| Column | Meaning | Constraint |
|---|---|---|
| `p10`, `p50`, `p90` | Quantiles of the imbalance price | `p10 ≤ p50 ≤ p90` |
| `p_up`, `p_down`, `p_none` | Probability of the dominating mFRR direction (Fingrid 369: up / down / none) | Sum to 1 |
| `p_spike_high`, `p_spike_low` | P(price > spot + 50) and P(price < spot − 50) | Sum ≤ 1 |
| `data_cutoff_utc`, `top_drivers` | Optional, not scored | |

## 2. Scoring

Total = 80 % Level 1 + 20 % Level 2 (dashboard, jury-scored).

Level 1 (100 points):

| Component | Points | Metric (lower is better) | Baseline on validation |
|---|---:|---|---:|
| Accuracy | 30 | MAE of p50 | 66.20 |
| Calibration | 20 | Mean of the pinball losses of p10 (q = 0.1) and p90 (q = 0.9). p50's pinball is not scored here. | 24.18 (coverage 0.68) |
| Exceptional prices | 20 | Mean of the two-class Brier scores of `p_spike_high` and `p_spike_low` | 0.1132 |
| Direction | 10 | Three-class Brier, Σ_k (p_k − o_k)², range 0–2 | 0.4509 |
| Reasoning chain | 20 | Jury, 0–5: clarity, consistency and inventiveness of how data sources and factors are used (report, slides, video) | – |

For each automatic metric: `points = weight × clip((B − T) / (B − best), 0, 1)`, where B = baseline, T = our metric and best = the best accepted team. **Each metric is scored separately against the best team on that metric.** All 40 steps count equally. The baseline is persistence: p50 = the latest usable imbalance price held flat; p10/p90 from historical persistence errors per step; the probabilities are historical shares. Spike shares in validation: 12.1 % high, 13.0 % low.

A leak (using any data before it was available) means **automatic score 0**. Top teams' code is reviewed, possibly with AI.

## 3. How the price is formed

- The dominating direction of each quarter-hour comes from **mFRR activations** (Nordic mFRR energy activation market, 15-min).
- **Up-regulation:** the price is above spot. **Down-regulation:** below spot. **No dominating direction:** the price equals the day-ahead spot price.
- Since 1 Jun 2026: when activated mFRR and fulfilled aFRR demand in Finland are both in the dominating direction, the price is the **volume-weighted average** of their energy prices.
- Day-ahead spot is 15-minute resolution, published around 14:00 Finnish time on D-1.

## 4. Data and the availability rule

At origin `t`, a row may be used only if its `first_usable_origin_utc ≤ t`. That column is the publication time rounded **up** to the next full hour. In practice:

| Series (package, 15-min, long format) | Freshness at origin `t` |
|---|---|
| FI imbalance price, mFRR up/down marginal prices, mFRR up/down activated MW, mFRR direction, aFRR up/down prices (sparse: missing when no activation) | Published 60 min after quarter end → newest usable quarter starts at `t − 75 min` (5 quarters before step 1) |
| FI measured consumption, production (total only, no per-type split), cross-border flows FI–SE1, FI–SE3, FI–NO4, FI–EE | 30 min after quarter end → newest is 3 quarters before step 1 |
| ENTSO-E imbalance prices SE1, SE3, EE; load forecasts SE1, SE3, EE | 120 min after period end → newest is 9 quarters before step 1 |
| Fingrid day-ahead forecasts: consumption (165), wind (246), solar (247) | Usable from D-1 13:00 local → known for **all 40 steps** at every origin (verified) |
| Nord Pool day-ahead spot (licensed: may not be sent anywhere) | D-1 14:00 local → known for **all 40 steps** at every origin (verified) |
| FI–EE and EE–FI day-ahead capacity | D-1 14:00 local |
| Calendar: local weekday, hour, holiday, DST | Always |

**Not in the package:** realised wind production, per-type production, weather, outages, intraday prices, Fingrid's continuously updated forecasts (only the latest version is stored, so their history leaks).

**External data is allowed** if we list it, handle its licence and use an honest publication delay:

- **Open-Meteo Single Runs API:** archived individual NWP runs (ECMWF IFS, ICON, …) with init times. Usable from init + model availability delay (~3–7 h). Recommended by the organisers. Their *Historical Forecast* API is **not** allowed (it leaks).
- **Fingrid Open Data API** (key available): real-time 3-minute data (wind production, nuclear, hydro, total production and consumption, frequency, …) and full history, including periods before June 2026. The honest publication delay of real-time series is still to be confirmed with the organisers (we'd assume 15–30 min).
- **Nord Pool UMM** (outage messages, versioned with publication dates), **FMI** weather observations, **Elering** (Estonian real-time balance).

## 5. What we verified in the training data (≤ 4 Oct; aggregates only)

1. **Spot is the anchor.** On validation quarters: p50 = spot → MAE 46.5; spot − 7.7 (median training gap) → 44.2; persistence → 64.8.
2. **Gap by direction.** Up (35 % of quarters): median gap +25, P10 0, P90 +91, max +3,800. Down (65 %): median −17, P10 −52, P90 −3.5. None: 0.17 %, gap exactly 0. About 10 % of up quarters have a slightly negative gap, and 3 % of down quarters a positive one.
3. **Staleness.** Raw "spot + last usable gap" has MAE 50.8 at step 1 and 61.8 averaged over all steps. A shrunk version (½ last gap + ½ constant) gets 43.0 at step 1. Direction agreement with the last usable direction: 0.70 at lag 5, 0.66 at 8, 0.62 at 12, 0.60 at 20, 0.57 at 44; chance (Σp²) is 0.54.
4. **The day-ahead wind forecast level is the strongest single signal.** Lowest vs highest wind quintile: mean |gap| 40.0 vs 13.6; low-spike share 10 % vs 1 %; high-spike share 10 % vs 2.6 %; up share 43 % vs 21 %.
5. **Spot ramps.** Mean |gap| rises from 18.5 to 50.4 between the lowest and highest quintiles of |Δspot| (quarter to quarter).
6. **Time of day.** Mean |gap| by local hour: ~24 at 02–05, a morning ramp of 31–36 at 06–09, a dip to ~25 at 14–16, then 38 at 18, **58 at 20** and 40 at 21.
7. **Weak signals.** Neighbour imbalance prices correlate ~0.1 with the FI gap at usable lags. The consumption forecast error at usable lags correlates −0.03 to −0.06.
8. **Spikes follow the direction.** Only 7 high spikes occur outside up-regulation and 18 low spikes outside down-regulation, out of ~12,000 quarters.
9. **Drift.** Imbalance price std by month: Jun 59, Jul 25, Aug 62, **Sep 141**, 1–4 Oct 76. The up share is 35 % overall but 25 % on 1–4 Oct. Spike shares: training 9.0 % high / 7.3 % low vs validation 12.1 % / 13.0 %. Solar falls ~5× from June to October. The test period (Oct) moves towards winter: more wind, darker, possible turbine icing.
10. Finnish wind capacity is concentrated on the west coast (Ostrobothnia). The organisers say rapid, unforecast changes in wind production are the main driver of imbalance price errors.

## 6. The team's current plan (assume competitors do roughly this too)

LightGBM quantile regression on `gap = imbalance − spot` (q = 0.1/0.5/0.9) with step as a feature; a binary up/down classifier with calibration and a constant `p_none`; spikes as P(direction) × P(tail | direction); conformal adjustment of p10/p90 per step band; recency weighting. Features: day-ahead (spot level, ramps, daily shape, wind/consumption/solar forecasts, hour, weekday) plus recent state (last usable gap, direction, mFRR volumes, flows) plus external (Open-Meteo wind revisions on the west coast, Fingrid real-time wind minus the DA forecast, nuclear changes, UMM outages, an icing proxy).

---

## What we want from you

Propose **the solution you would bet on to finish first**. Go beyond the plan above where you believe it pays off; keep what is already right. Answer in Markdown with exactly these sections:

1. **Thesis (≤ 5 sentences):** your edge in one paragraph. What will we do that a good LightGBM-on-gap team won't?
2. **Method:** targets and how each submitted column is produced (p10/p50/p90, the three direction probabilities, the two spike probabilities); model types and losses; key features; how the outputs stay consistent with each other; calibration. Be specific enough that an engineer could start building it.
3. **Expected gain per score component:** for each of the four automatic metrics, what improves, why, and a rough estimate versus a well-tuned LightGBM-on-gap model. Say how confident you are.
4. **Data:** which external data you would add (or skip), with its honest publication delay, how to fetch its history quickly, and the leakage traps.
5. **Experiment plan:** ordered by expected value per hour of work, each with a go/no-go criterion on the validation set, and fitting the remaining ~34 h with 5 people. Include what to cut first if time runs short.
6. **The idea others won't think of:** one or two non-obvious ideas, and why they would work here.
7. **Risks and what to verify first:** what could make your approach fail, and the quick data checks to run before committing.

Keep it under ~2,000 words. Prefer ideas you can justify from the facts above, or from how the Nordic mFRR market and Finnish imbalance pricing actually work. Don't invent dataset IDs or numbers; mark anything unverified as such.
