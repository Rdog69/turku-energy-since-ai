# Agent `structure`: model structure and training setup (package features only)

Code: `experiments/lab/features/structure.py` (hooks: `recency`, `band_post`, `blend_post`, `causal_post`, `save_post`) and
`experiments/lab/exp_structure.py` (`screen`, `clf`, `run`, `analyze`, `causal` modes). All rows use the 35 package
features and nothing else.

**G** = HGB `max_leaf_nodes=15, min_samples_leaf=400, max_iter=150` (lr 0.06 and l2 1.0 unchanged).
**Bands** = separate, separately calibrated models for steps 1–4, 5–8 and 9–16, refit inside `post` on the fold's
training rows with run_experiment's own inner/cal split. Steps 17–40 stay with the pooled model.

## Leaderboard rows (calibrated, both folds)

| run | fold | MAE | pinball | spike | dir |
|---|---|---|---|---|---|
| REF package direct | A | 43.942 | 12.643 | 0.0987 | 0.4369 |
| REF package mixture | A | 43.576 | 12.463 | 0.0949 | 0.4369 |
| S direct gap G | A | 43.016 | 12.226 | 0.0979 | 0.4263 |
| S direct price G | A | 43.282 | 12.287 | 0.0979 | 0.4263 |
| S direct gap G bands | A | 42.588 | 12.139 | 0.0958 | 0.4212 |
| S mixture gap G bands | A | 42.309 | 12.058 | 0.0926 | 0.4212 |
| **S final** | A | **42.245** | **12.050** | **0.0923** | **0.4193** |
| REF package direct | B | 29.308 | 7.181 | 0.0765 | 0.4528 |
| REF package mixture | B | 29.402 | 7.014 | 0.0788 | 0.4528 |
| S direct gap G | B | 28.157 | 7.021 | 0.0737 | 0.4396 |
| S direct price G | B | 28.812 | 6.921 | 0.0737 | 0.4396 |
| S direct gap G bands | B | 27.940 | 6.923 | 0.0753 | 0.4381 |
| S mixture gap G bands | B | 27.730 | 6.821 | 0.0745 | 0.4381 |
| **S final** | B | **27.581** | **6.808** | **0.0729** | **0.4375** |

Offline (calibrated, pre-post predictions saved as `structure__S_mixture_gap_G_raw`): mixture G pooled A 42.868 / 12.073 / 0.0946 / 0.4263,
B 27.853 / 6.871 / 0.0705 / 0.4396.

## p50 screen (direct p50 only, uncalibrated; exact for MAE). A / B

| config | A | B |
|---|---|---|
| gap, default HGB (= REF) | 43.99 | 29.45 |
| price, default | 44.12 | 29.63 |
| price iter500 / iter150 | 44.48 / 44.03 | 30.19 / 29.19 |
| price leaf63 msl100 | 44.70 | 30.48 |
| price leaf15 msl400 | 43.43 | 29.02 |
| price max_features 0.5 | 44.26 | 29.76 |
| gap leaf15 msl400 | 43.22 | 28.75 |
| **gap G (leaf15 msl400 iter150)** | **43.04** | **28.18** |
| gap G iter100 / leaf7 / msl800 / lr.03 iter300 | 43.04 / 43.03 / 43.17 / 43.08 | 28.06 / 28.27 / 28.27 / 28.37 |
| gap G, recency hl 60 / 90 / 120 d | 42.92 / 42.89 / 43.26 | 28.39 / 28.35 / 28.49 |
| gap G + bands 1–4, 5–12 | 42.68 | 28.01 |
| **gap G + bands 1–4, 5–8, 9–16** | **42.61** | **27.96** |
| gap G + bands 1–4, 5–12, 13–24 | 42.80 | 28.12 |

Separate band models are dramatically better at the short steps (steps 1–4 MAE: A 41.6 → 39.5, B 27.4 → 25.6) and
slightly worse at long steps, which is why steps 17–40 keep the pooled model.

## What helped on both folds

1. **Regularising HGB (G)**: the single biggest structural gain. Every metric improves on both folds, including
   direction Brier (0.437 → 0.426 on A, 0.453 → 0.440 on B), because the classifier heads share the same hyperparameters.
   250 iterations with 31 leaves overfits; the plateau is leaf 7–15, msl 400, 100–150 iterations.
2. **Step-band models (1–4, 5–8, 9–16)**: MAE, pinball and dir better on both folds, in both direct and mixture.
   Spike Brier is mixed: A improves, B is slightly worse (direct 0.0737 → 0.0753, mixture 0.0705 → 0.0745).
3. **Mixture over direct (with G and bands)**: better on all four metrics on both folds.
4. **Convex blend of mixture and direct (bands)**: weights fitted on fold B (mixture weight 0.6 for p50, 0.9 for p10/p90,
   0.6 for spike; dir is the same classifier) and applied unchanged to A. Beats both endpoints on MAE and pinball
   on both folds; spike ties on A. Small gain (A 42.31 → 42.26, B 27.73 → 27.63).
5. **Causal averaging with earlier origins**: pred(o,k) ← (1−w1−w2)·pred(o,k) + w1·pred(o−1h,k+4) + w2·pred(o−2h,k+8),
   with w1 ramping 0 → 0.2 over steps 4–16 and w2 0 → 0.15 over steps 8–24. Improves all four metrics on both folds, but
   only slightly (MAE −0.03 %/−0.2 %, dir −0.4 %/−0.1 %). The B-optimal weights (0.5/0.15) hurt A's MAE, so I used the
   milder setting; that choice is informed by A and is not a pure B fit. It is only valid if the production
   system keeps its own forecasts from the previous two hourly origins (the first origins of a window have none).

## What did not help

- **target=price** loses MAE on both folds, both at default HGB and with G (gap wins by 0.3–2 %); it only improved
  pinball on B. This reverses round 2's direct-p50 result: with `spot` among the features, gap is the better target.
- **Recency weights (60–120 d)** do not hold on both folds: they help A and hurt B. They are also
  non-monotonic in the half-life, so the differences sit within fit noise.
- **More capacity** (iter 500, leaf 63, max_features 0.5): consistently worse.

## Recommended setup

Mixture, target gap, HGB G, plus separate calibrated band models for steps 1–4, 5–8 and 9–16, then a convex blend
with the direct model built the same way (weights as above), then mild causal averaging with the previous two origins'
forecasts. The command is `exp_structure run "S final"`. If simplicity matters, "S mixture gap G bands" alone keeps
about 90 % of the gain. Because the final model trains on about 4 months instead of 2–3, re-check `max_iter`; it
might tolerate 200.

## Suspicious and caveats

- The noise of a single HGB fit is about ±0.3 % MAE (e.g. hl60/90/120 is non-monotonic), so differences below that
  are not meaningful.
- Fold B's direction Brier is nearly flat across steps (REF step 1 0.469 vs step 40 0.45, worse at step 1), while A
  is 0.396 at step 1. That looks odd for a persistence-driven target; worth a look by the direction agent.
- `p_none` is a constant (about 0.1 % of quarters), so the direction metric is effectively binary.
- Band models change the spike heads too, and their spike Brier gets worse on B (only a few spikes per band in the
  14-day calibration window). Pooled spike heads would be a reasonable alternative.
- Blend weights and the causal setting were chosen on B, which makes the B numbers of "S final" in-sample for 4+2
  scalar weights.
