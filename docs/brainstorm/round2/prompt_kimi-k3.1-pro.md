# Round 2: from "good" to "first"

You are advising a 5-person team in the Turku Energia imbalance-price challenge (Since AI 2026). About 32 hours remain until submission (Sun 8 Nov 2026, 10:00 Finnish time). **Everything you need is attached as files:**

- The organisers' starter-package README (rules, schema, availability rule, scoring)
- `availability.csv`
- `score.py`
- The baseline notebook code, including `rows_available_at()`
- The challenge brief
- The briefing transcript
- `data_samples.md`: **real rows** of every non-spot series, a volatile day and a calm day in full, freshness at an example origin, per-series statistics and the quality report. Spot rows are withheld for licence reasons; spot is described by monthly aggregates.
- The team plan (`PLAN.md`)
- **Round 1:** five model proposals and their comparison

Read them. Ground your answer in them, and cite the file or number you rely on.

## Round 1 converged; assume the field converges too

All five round-1 proposals independently landed on the same core, which we **will build anyway**:

1. A direction-mixture CDF, P(up)·F(gap | up) + P(down)·F(gap | down) + p_none·δ₀, with all eight columns read off it.
2. A direct LightGBM-on-gap challenger, choosing the source per column.
3. Fingrid real-time wind production minus the DA wind forecast as the key external feature.
4. Pinball- and Brier-optimal calibration per step band.
5. Open-Meteo wind revisions.
6. Recency weighting.

**Assume the two or three strongest competing teams also build roughly this.** Scoring is relative to the best team on each metric, so this core only gets us to "tied with the leaders". **Don't re-propose the core as your edge.** Your job is what moves us from tied to **first** *on top of it*, or what in the core is wrong and should change.

## New facts measured on training data (≤ 4 Oct), beyond round 1

- **Freshness is worth a lot.** A shrinkage forecast spot + c + w·(gap at lag L − c), with w fitted before 7 Sep, gives a validation MAE of 26.4 at lag 1, 33.9 at lag 2, 39.4 at lag 3, 42.4 at lag 4 and 43.8 at lag 5 (lag 5 is what the package gives at step 1). Direction agreement with the lagged direction: 0.85, 0.81, 0.77, 0.74, 0.71.
- **Merit-order asymmetry.** In up-regulation the gap rises with activated mFRR-up MW: median +8, +14, +24, +37, +61 across volume quintiles (rank correlation 0.58). In down-regulation the gap is flat: median −18 to −15 across volume quintiles (rank correlation 0.10).
- **The price is mostly the mFRR marginal price.** The imbalance price equals the mFRR marginal price in its direction (±0.5 €/MWh) in 43 % of directional quarters. The median absolute difference is 1.0; the rest is the volume-weighted average with aFRR.
- **The Nordic price is often shared.** SE1's imbalance price equals Finland's mFRR marginal price (in Finland's direction) in **75 %** of quarters; SE3's in 52 %. But ENTSO-E neighbour data arrives 9 quarters before step 1, versus 5 for Fingrid's own data.
- **The day-ahead net position** (consumption forecast − wind forecast − solar forecast) separates outcomes across its quintiles:

  | | Q1 | Q5 |
  |---|---:|---:|
  | Up share | 21 % | 49 % |
  | Mean \|gap\| | 13 | 49 |
  | High-spike share | 3 % | 14 % |
  | Low-spike share | 0.3 % | 16 % |

- **Direction runs are short:** down runs have a median of 3 quarters (mean 7.9); up runs a median of 2 (mean 4.3).
- **Dead ends we tested:**
  - Trailing up-share as a predictor of the next 10 h is *worse* than a constant: Brier 0.236 (7 d) and 0.253 (24 h) vs 0.224.
  - "Spot-differenced price persistence" is algebraically identical to gap persistence.
  - Only 2.2 % of quarters have \|gap\| < 1, so there is little mass at zero.
  - aFRR presence barely changes the up share: 36 % when an aFRR-up price is present, 32 % when absent.
  - Within-hour quarter position barely matters: mean \|gap\| 30.9 / 31.1 / 32.3 / 31.4.

## Your angle

Each of the five advisors gets a **different angle** this round, so that we get different ideas. Yours is described below. Stay in it, but name the single best idea you see even if it falls outside it.

**Scoring mathematician.** Treat this as **four separate optimisation problems scored relative to the best team**, with `score.py` as the exact objective. For each metric (MAE of p50, mean pinball of p10/p90, mean Brier of the two spike probabilities, three-class Brier of direction), work out where the cheapest points are. Cover: decision-theoretic optimal outputs given a predictive distribution (e.g. the optimal p50 under MAE for a bimodal mixture; whether to shrink probabilities under drift); post-processing and blending across models, steps and origins; per-step or per-band selection; how validation noise (one volatile month) should change our choices; and how the relative-to-best formula changes what to prioritise. Use numbers from the files.

## Answer format (Markdown, ≤ 2,500 words)

1. **Thesis (≤ 4 sentences):** what puts us *first*, not merely tied.
2. **Top 5 ideas, ranked by expected points per hour of work.** For each idea:
   - **What:** precise enough to implement; a short pandas/LightGBM sketch is welcome.
   - **Evidence:** which file, number or mechanism supports it.
   - **Metric(s) it moves,** with a rough size and your confidence.
   - **Cost in person-hours.**
   - **Leak traps.**
   - **A go/no-go test on the validation period** (7 Sep – 4 Oct), plus a second fold.
3. **What to change or drop in the round-1 core,** if anything, and why.
4. **Three quick checks** to run on the package data first, as concrete pandas steps, that would confirm or kill your top idea.

Be honest about uncertainty. Don't invent dataset IDs, API fields or numbers; mark anything unverified with ☐.
