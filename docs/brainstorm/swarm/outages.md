# Agent `outages`: UMM outage messages and real-time nuclear

Code: `experiments/lab/features/outages.py`, `experiments/lab/exp_outages.py`. Every feature function passes `leakcheck` (12 random origins offline, plus 6 inside each run). Nothing is fitted.

## Builder (leak-safe)
- At each origin, a message version is usable when `fu ≤ origin`, where fu = ceil_hour(publication). Per `messageId`, the version in force is the highest one among the usable versions. Each version is in force over the interval [fu, next fu), and a loop over the unique origins (3 s) evaluates these intervals.
- **`isOutdated` is never used**, because it's a fetch-time field and knows the future. Dismissed messages (`eventStatus` 3) count as 0 MW.
- **Dedup is needed.** The same outage is reported under the production unit "Olkiluoto 3" and the generation unit "B3", and "Metsä Fibre Kemi" is reported by two publishers. For each delivery quarter the builder takes the max MW per unit key (name alias plus installed MW), then sums over units.
- Features, all at the delivery quarter:
  - unplanned FI generation MW, and the largest unplanned unit;
  - unplanned MW from events that started in the last 1, 3 or 6 h (`fresh`);
  - a fresh-big flag (≥ 800 MW);
  - hours since the last unplanned message of at least 250 MW;
  - **unplanned MW now minus what was known 6 h earlier** (coordinator's idea, `o_unpl_delta6`);
  - planned MW, planned nuclear MW, and the planned delta over 6 h;
  - unplanned consumption MW;
  - neighbour (SE1/SE3/EE) unplanned MW;
  - FI border transmission reductions;
  - RT nuclear (`fg188`) vs its 24 h max and 1 h ago.

## Results (mixture, gap, calibrated; leaderboard rows)

| run | fold | MAE | pinball | spike | dir | MAE s1-4 | MAE s5-12 |
|---|---|---:|---:|---:|---:|---:|---:|
| REF package mixture | A | 43.576 | 12.463 | 0.0949 | 0.4369 | 41.81 | 43.09 |
| outages fresh (levels + fresh) | A | 43.657 | 12.730 | 0.0957 | 0.4412 | 42.95 | 43.37 |
| outages delta (delta6, pl_delta6, pl_mw) | A | **47.497** | 13.218 | 0.1072 | 0.4271 | 46.43 | 47.05 |
| outages trip (fresh1/3/6, delta6, hrs_since_big) | A | 43.639 | 12.627 | 0.0966 | 0.4427 | 42.51 | 43.18 |
| outages trip_rt (trip + RT nuclear) | A | 43.761 | 12.685 | 0.0958 | 0.4394 | 42.50 | 43.49 |
| REF package mixture | B | 29.402 | 7.014 | 0.0788 | 0.4528 | 28.49 | 29.07 |
| outages fresh | B | 29.436 | 7.049 | 0.0708 | 0.4539 | 28.45 | 28.85 |
| outages delta | B | 32.085 | 7.205 | 0.0790 | 0.4624 | 31.27 | 31.81 |
| outages trip | B | **29.290** | **7.005** | **0.0697** | **0.4522** | 28.47 | 28.81 |
| outages trip_rt | B | 29.423 | 7.249 | 0.0773 | 0.4523 | 28.66 | 29.04 |

Offline post-rule on saved predictions (no retraining): when a fresh unplanned FI outage of at least 800 MW is active at delivery, set p_hi ≥ 0.5 (steps 1–8) or ≥ 0.3 (steps 9–16), and P(up) ≥ 0.8. Optionally also set p90 ≥ spot + 300.
- On REF, fold A: spike 0.09485 → 0.09480 and pinball 12.463 → 12.426 (p90 variant). Only 48 rows are affected.
- On fold B no rows are affected.

## What helped, on both folds
**Nothing passes on both folds.** Every UMM set is worse than REF on fold A on MAE, pinball and spike Brier. The best set, `trip` (shock-only features), wins all four metrics on fold B. The coordinator's kill criterion (≥ 1 % relative spike gain on both folds) therefore **kills every set**, including the delta.

## Why (and what's suspicious)
1. **No training signal for big trips.** Training has no rows with a published unplanned outage of at least 800 MW. The B1 trip on 25 Jun ended about when its message became usable (fu 10:00). The only usable big trip is OL3 on 9 Sep, in fold A validation, so the trees can't learn it. Fold A validation has 48 such rows, with a 44 % high-spike rate. They make up only 0.0004 of the 0.095 spike Brier, so even a perfect trip model barely moves the average. They do add about 0.37 to total MAE, from 12 step 1–4 rows where REF's MAE is 821.
2. **The SOURCES.md stat ("> 800 MW: 20 quarters, 50 % spikes, +527 gap") is the OL3 event itself.** All 5 hourly step-1 quarters fall on 9 Sep, in fold A validation, so any trip rule tuned on it leaks into fold A. My post-rule thresholds were set a priori, and it is validated on n = 1 event.
3. **The fold B "gains" are mostly a REF-mixture artefact.** REF mixture predicts a mean p_lo of 0.002 on fold B against a low-spike rate of 0.067. The runs that improve fold B spike Brier (fresh, trip) are the ones where p_lo doesn't collapse (low part of the Brier 0.033 → 0.025). trip_rt collapses again (p_lo 0.007) and loses the gain. Spike Brier noise from feature perturbations is therefore about 0.005 on fold B, which is 6 %, far above the 1 % kill threshold. **The REF mixture's p_lo calibration on fold B looks broken (Platt on a 14-day window with almost no low spikes) and is worth fixing in `models.py`.**
4. **The delta run isn't a delta bug.** The deltas were hand-checked. Its feature set also contains `o_pl_mw`, a level that trends from about 220 MW (early June) to about 2,900 MW in September (autumn nuclear maintenance). Fold A validation sits entirely above the training range (validation mean 2,934, training max 2,601), so the model extrapolates a date proxy. The early-June planned levels are also biased low, because UMM was fetched only for publications from 25 May, so outages announced earlier are missing unless they were updated later. **Do not use slow level variables** (planned MW, nuclear planned, border reductions, neighbour MW, or even `o_unpl_mw` / `o_unpl_max`, which equal the B3 301 MW derate on every fold B validation row).
5. **RT nuclear is slower than UMM.** With a 30 min delay plus ceil-to-hour, the 16:42 trip only shows at the 18:00 origin, while UMM is usable at 17:00. `rt_nuc_drop24` also fires on planned shutdowns (it was above 800 MW from the 16:00 origin, before the trip). It didn't help.

## Recommendation
- Leave UMM features out of the final model's trees; there's no fold-robust gain.
- Keep the **leak-safe builder** and a small, a-priori **fresh-trip override** as insurance for the test week. Use `o_unpl_fresh3 ≥ 800` at delivery, then p_hi ≥ 0.5 (steps 1–8) or ≥ 0.3 (steps 9–16), P(up) ≥ 0.8, and p90 ≥ spot + 300. It's neutral on fold B, slightly positive on fold A, and protects against a repeat of 9 Sep. Its parameters are not validated and it must be described as such.
- Optional: `umm_trip` (shock-only, 5 features) if the coordinator accepts a fold-B-only gain. I wouldn't, given point 3.
