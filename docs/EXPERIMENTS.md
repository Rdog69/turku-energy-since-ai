# Everything we tried: experiment log and final choice

> Branch `brainstorming-abdo`, Fri 6 – Sat 7 Nov 2026. About 220 leak-checked experiments: by Claude agents, Featherless LLM loops, a LUMI supercomputer grid, and teammates' models scored on the same footing.
>
> All scores are lower-is-better. **Official** = the organisers' `score.py` on the validation period (7 Sep – 4 Oct). **Lab** = the same formulas on two folds: **A** = September (the organisers' window, trained on data before 7 Sep) and **B** = August (trained on June–July). **Score** = the points-weighted % gain over our reference model (30 MAE, 20 pinball, 20 spike, 10 direction), averaged over both folds.

## 1. What to submit

| Priority | File (`submissions/`) | What it is | Official validation: MAE / pinball / spike / direction |
|---|---|---|---|
| **1** | `forecast_backtest_team5050.csv` | ½ Frank's `v4_n50` + ½ our `P2 INT4+ss lgb7`, equal weights | **40.97 / 11.63 / 0.0861 / 0.3803** (coverage 0.80) |
| 2 | `forecast_backtest_final_greedy.csv` | 9-member per-output ensemble (our models + Frank's `final_capw` for direction) | 41.40 / 11.43 / 0.0879 / 0.3843 |
| 3 | `forecast_backtest_cal_int4.csv` | Our best single model with eb50 calibration | 41.51 / 11.88 / 0.0900 / 0.3889 |
| Safety | `forecast_backtest_ref_mixture.csv` | Package-only mixture | 43.54 / 12.33 / 0.0945 / 0.4294 |
| – | Organisers' baseline | Persistence | 66.20 / 24.18 / 0.1132 / 0.4509 |

All four files pass `validate_submission.py` (673 origins × 40 steps).

**Why `team5050`?**
- It beats Sakibul's 65/35 blend (rebuilt with the official scorer: 40.95 / 11.78 / 0.0865 / 0.3822) on pinball, spikes and direction. MAE is a statistical tie.
- On **August** it's better on all four metrics.
- It wins **9 of 10 weeks** across both months.
- It has **equal weights and nothing tuned**, which is the safest bet for the unseen test month. Our rule is to optimise for the test, not for September.

Against the baseline, `team5050` is about **−38 % MAE, −52 % pinball, −24 % spike Brier and −16 % direction Brier**.

## 2. The approach in one paragraph

Price = day-ahead spot + **gap**. The gap depends on the balancing direction:
- **Up-regulation:** the price is above spot, median +25.
- **Down-regulation:** the price is below spot, median −17. This is 65 % of quarters.

We model it as a **direction mixture**: P(up) × the gap distribution given up, plus P(down) × the gap distribution given down. All eight submitted numbers are read off that one distribution, so the quantiles, direction and spikes are consistent. On top of that:
- **Fresh information:** Fingrid real-time data and weather-model revisions;
- **Last autumn's history** for the direction model;
- **Probabilities calibrated on the most recent weeks;**
- **Ensembles of diverse models.**

## 3. What worked (kept)

| Component | Effect (both folds) | Evidence |
|---|---|---|
| **Spot anchor** (predict the gap, not the price) | Baseline MAE 66.2 → 44.3 by itself | Round 1–2 |
| **Direction mixture** over direct quantile models | Spike Brier −10 %, pinball −4 % | Round 2 measurement |
| **Regularised trees** (15 leaves, ≥ 400 rows per leaf, 150 iterations) | Better on every metric | Structure agent |
| **Separate models for steps 1–4 / 5–8 / 9–16** | Step 1–4 MAE −7 %, about +1.6 score | Structure agent, loop |
| **Fingrid real-time wind error** (`rt_wind`) + frequency/nuclear/net import (`rt_misc`) | MAE steps 1–4 −3.5 %; direction steps 1–4 0.418 → 0.386 | Nowcast agent |
| **Direction-history features** + **blend with a model trained on last year's Fingrid history** (`hist_blend` 0.6) | Direction Brier 0.437 → 0.397 (Sep) | History, probs agents |
| **eb50 spike calibration** (Platt shrunk toward "no change" when the 14-day window has few spikes) | Fixed August's collapse of P(low spike) (0.002 predicted vs 6.7 % actual). **The biggest single gain:** CAL INT4 +3.9 → +5.5 | Probs, calib agents. Frank adopted it too. |
| **ECMWF wind revision** (power curve, newest run minus the day-ahead forecast) | All four metrics better, both folds | Weather agent (W6) |
| **Spot-curve shape** (rank in the day, distance to the day's max/min, ±1 h ramps) | +0.3 score | Features-v2 agent |
| **LightGBM with small trees** (7 leaves, 350 trees, 3 seeds, bagging) | Best single model: `P2 INT4+ss lgb leaves7` +6.17 | LUMI phase 2 |
| **Ensembles of DIVERSE models** | Cross-fitted +5.90 vs +5.45 for the best single; averaging near-copies gives nothing | Ensemble agent, `ens_greedy.py` |
| **Blending with Frank's model** | `team5050` beats both models on both folds | Head-to-head |

## 4. What didn't work (killed: don't redo)

| Tried | Result |
|---|---|
| Price target instead of gap | Loses MAE on both folds |
| Recency weighting (21–120-day half-life) | Helps one fold, hurts the other; 21 days hurts direction |
| Bigger trees (31+ leaves, more iterations) | Worse |
| Fingrid consumption / production-plan error (`rt_cons`) | Hurts August |
| Fingrid RT batch 2 (boilers, CHP, real-time border flows) | Slightly worse on all leaders |
| Real-time data in short horizons only (Frank's split) | No gain in our setup (+3.66 vs +3.90) |
| UMM outage features | No gain on both folds. Big trips (≥ 800 MW) never occur in training; only the 9 Sep OL3 trip, which is in validation. Planned-outage MW acts as a date proxy. Kept only as a rule-based insurance idea. |
| Import saturation / FI–SE1 decoupling as a spike regime | Killed by its own check (0.281 vs 0.249) |
| Snapping prices to round bids | Prices aren't atomic (only 14 % whole euros) |
| ICON-vs-ECMWF disagreement (our raw-wind version), capacity-weighted wind, net-position shape | Worse on August. Frank's ICON construction (wind index + revision) does work. |
| Estonian (Elering) and Danish (Energinet) system data | Weak; hurts August MAE |
| Month × hour direction prior, autumn-only history model | Worse or noise |
| Isotonic / per-band / spot-conditional calibration, a fixed recalibration layer | Doesn't transfer between months (+0.3 % to +4 % worse) |
| HMM smoothing of direction across steps | Double-counts information |
| A 28-day calibration window for everything | Better in Sep, worse in Aug. 14 days is the default; 21/28 only as ensemble members. |
| Featherless LLM-designed blend recipes (≈ 150) | Overfit August: best Aug +6.8 → Sep +3.5 |
| Day-ahead FCR prices / day-ahead transmission capacity (`dafcr`) | 72 % missing (no longer published since flow-based); low value |

## 5. Research findings (validation errors of the best model)

- **MAE is dominated by rare events.** In September the top 5 % of rows carry 37 % of the error, and **3 days** (9 Sep OL3 trip, 14–15 Sep) carry **34 %**. Accuracy is close to its limit with public data.
- **Bias is small:** ±3 €/MWh by hour. Interval coverage is 0.77–0.82 (target 0.80).
- **Spike probabilities are under-predicted at the low end in both months**, but the size changes month to month. That's why recent-window calibration (eb50) is right and a fixed correction fails.
- **Direction probabilities are well calibrated.**
- **Drift warning for October:** last autumn's up-regulation peaked **at midday**, against **evenings** in summer 2026, and it had far more high-demand hours. The last-year history blend is our hedge.

## 6. Teammates' models, scored by us with the official scorer

| Model | Sep (official): MAE / pinball / spike / dir | Aug (lab): MAE / pinball / spike / dir |
|---|---|---|
| Frank `final_capw` (round 2) | 42.34 / 12.06 / 0.0900 / 0.3908 | 29.53 / 7.34 / 0.0882 / 0.4562 |
| **Frank `v4_n50`** (round 4) | **41.08 / 11.88 / 0.0871 / 0.3899** (reproduced exactly) | 27.99 / 7.00 / 0.0710 / 0.4466 |
| Sakibul "grand champion" (65 % Frank v4 + 35 % our CAL INT4) | 40.95 / 11.78 / 0.0865 / 0.3822 (our official rebuild) | 27.39 / 6.73 / 0.0689 / 0.4334 |
| **Ours `team5050`** | **40.97 / 11.63 / 0.0861 / 0.3803** | **27.27 / 6.57 / 0.0677 / 0.4281** |

**What Frank does well,** which we adopted or use through the blend:
- every change must win in Sep **and** Aug, week by week;
- tree settings tuned on training-only folds;
- ICON-EU as a capacity-weighted wind index plus its revision;
- a learned wind map (22 weather points fitted to Fingrid 181);
- Nordic wind used for the median only;
- 4-hour memory.

## 7. Data sources

See [`SOURCES.md`](../SOURCES.md). Every row carries `first_usable_origin_utc` from a documented, conservative delay. Sources:

- **Starter package**
- **Fingrid:** real-time (30-min rule), RT batch 2, balancing-market internals (60-min rule), history from Mar 2025
- **Open-Meteo:** ECMWF IFS, ICON-EU, ERA5 (fitting only)
- **FMI observations**
- **Nord Pool UMM**
- **Elering, Energinet**

**Pending organiser answers:** [`docs/QUESTIONS_FOR_ORGANISERS.md`](QUESTIONS_FOR_ORGANISERS.md). The most important are Fingrid real-time use and pre-June history. If either is disallowed, use the weather-only W6 members; W6+ss+eb50 alone scores about +5.5.

## 8. Anti-overfitting and anti-leakage safeguards

- **Leak test** on every feature function: it recomputes the features with every source truncated to `fu ≤ origin`. It catches a deliberately leaky feature. Feature and post functions never see targets.
- **2-hour label embargo** at every training cutoff. Calibration only uses training data.
- **Two forward folds** (Sep, Aug): a change counts only if it wins on both. **Weekly consistency** checks for final choices.
- **Cross-fitted** ensemble selection (fit on one month, score on the other). The Featherless loop only saw August, and September stayed hidden.
- **Final choice:** equal weights, few members, nothing tuned to September.

## 9. Infrastructure

| Tool | Purpose |
|---|---|
| `experiments/lab/` | `data.py` (leak-safe helpers + `leakcheck`), `models.py` (mixture/direct, metrics, calibration), `run.py` (two-fold runner + leaderboard), `combo.py` (any spec: features, bands, engines `hgb`/`lgb`/`cat`, eb50, history blend), `submit.py` (official templates → validated CSV), `combine.py` (per-group ensemble of member files + validator + `score.py`), `ens_greedy.py` (cross-fitted greedy ensemble) |
| `experiments/lab/leaderboard.csv` | Every experiment, both folds, full spec in `notes` |
| `lumi/` | LUMI kit: sync, setup, job arrays (60 in parallel), official builds, collect. **Fallback when LUMI is down:** run the same `combo`/`submit`/`combine` commands locally. |
| `tools/fl_lab.py`, `tools/fl_post.py` | Featherless loops (stopped: compute was the bottleneck, and the blend loop overfit) |
| `src/data/external/` | Fetchers for every external source |

## 10. Still open

1. **Round 5 on LUMI** (interrupted by maintenance):
   - Frank's other variants (`v3_bmi_n50`, `v4_eb`, `v4_wh`, `v4_b4`, `final_tuned`, `final_tuned_long`, `final_nordic`) on Sep/Aug/test;
   - 15 official builds of diverse top models;
   - a 10-seed core model;
   - phases 5a (diversity grid) and 5b (balancing-market data).

   Resume after maintenance; replace `team5050` only if a **simple, equal-weight** blend beats it on both months and most weeks.
2. **`top_drivers`** is empty in our files (optional, not scored). Frank's `v4_n50` file has TreeSHAP drivers we could reuse.
3. **Organiser answers** to the questions file.
