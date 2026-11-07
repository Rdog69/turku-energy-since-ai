# Agent `history`: longer history, regime and direction

Code: `experiments/lab/features/history.py`, `experiments/lab/exp_history.py`
(`python -m experiments.lab.exp_history <exp> <model> [blend0.6]`, plus `drift` for the analysis below).
Every feature function passed leakcheck. History models are fitted **only on `fg_hist`** (Mar 2025 – 31 May 2026). An assert checks that `fu` max is before the 2026-07-31T21:00Z cutoff. The fitted models are cached in `_cache/history_<hash>.pkl`, keyed by a fingerprint of the training data.

## Results (copied from the leaderboard)

| name | fold | MAE | pinball | spike | **dir** |
|---|---|---|---|---|---|
| REF package direct | A | 43.94 | 12.64 | 0.0987 | 0.4369 |
| REF package mixture | A | 43.58 | 12.46 | 0.0949 | 0.4369 |
| runs direct | A | 43.69 | 12.89 | 0.0987 | 0.4198 |
| hda direct | A | 44.01 | 12.70 | 0.0987 | 0.4359 |
| hfull direct (as feature) | A | 43.91 | 12.53 | 0.0974 | 0.4283 |
| hprior direct | A | 44.74 | 12.50 | 0.1033 | 0.4561 |
| neigh direct | A | 43.98 | 12.56 | 0.0966 | 0.4273 |
| runs blend0.6 direct | A | 43.69 | 12.89 | 0.0987 | **0.3970** |
| **runs blend0.6 mixture** | A | **42.59** | **12.34** | **0.0941** | **0.3970** |
| REF package direct | B | 29.31 | 7.18 | 0.0765 | 0.4528 |
| REF package mixture | B | 29.40 | 7.01 | 0.0788 | 0.4528 |
| runs direct | B | 29.12 | 7.15 | 0.0748 | 0.4549 |
| hda direct | B | 29.47 | 7.20 | 0.0765 | 0.4549 |
| hfull direct (as feature) | B | 29.37 | 7.11 | 0.0766 | 0.4544 |
| hprior direct | B | 29.41 | 7.10 | 0.0791 | 0.4463 |
| neigh direct | B | 29.70 | 7.17 | 0.0754 | 0.4509 |
| runs blend0.6 direct | B | 29.12 | 7.15 | 0.0748 | **0.4392** |
| **runs blend0.6 mixture** | B | 29.52 | 7.09 | **0.0754** | **0.4392** |

Experiments:
- `runs`: direction run length, previous run length, switches in the last 16 quarters, up share over the last 8/32/96 quarters, hi/lo spike shares over the last 16/96 quarters, max/min gap over the last 16, direction at the same quarter yesterday, and the up share at the same quarter over the last 7 days.
- `hda`: HGB P(up | day-ahead net, wind, consumption, solar, ramps, hour, weekday) fitted on history.
- `hfull`: HGB P(up) fitted on history with simulated hourly origins × 40 steps. Its inputs are the day-ahead inputs plus the last known direction, age, run length, up8/up32, switches, mFRR up/down MW, consumption error and production − consumption (no spot needed).
- `hprior`: month × hour P(up) prior from the featherless idea 5.
- `neigh`: Elering system/AC balance and Energinet aFRR DK1/DK2 and DK-SE exchanges, as level, mean of the last 4 and change over 4 quarters.
- `blend0.6`: a `post` step that sets P(up | not none) = σ(0.6·logit(hfull) + 0.4·logit(classifier)).

## What helped on both folds

- **The history model blended into P(up) is the big win**: direction Brier −0.040 on A and −0.014 on B against REF. On its own, uncalibrated, hfull already beats REF (offline: A 0.4051, B 0.4460). The gain is largest at steps 1–4 (B: 0.416 against 0.453 for the in-sample classifier). With 15 months of data the history model learns persistence much better than the June–September classifier does.
- **Feeding hfull as a feature mostly wastes it** (A −0.009, B +0.002). The in-sample classifier and the 14-day Platt step dilute it. Use it as a blend.
- **Platt recalibration of hfull on 2026 training rows hurts** (slope ≈ 0.5, and validation gets worse on both folds). Keep it uncalibrated. Offline, the blend weight is flat between 0.5 and 0.7.
- **runs features**: direction −0.017 on A and +0.002 on B on their own. MAE improves on both folds with the direct model, spike Brier on B. Combined with the blend they are best on A (0.3970 against 0.4016 for REF plus the blend) and tied on B.
- **The mixture with the blend** improves on REF mixture on A in every metric (MAE −0.98, pinball −0.12, spike −0.0008). On B, spike improves (−0.0034) but MAE (+0.11) and pinball (+0.08) are worse. The blend only changes the reported P(up). The mixture's CDF still uses the unblended P(up), so the coordinator could push the blended P(up) into the mixture weights in models.py.

## Killed

- `hda`, the day-ahead-only history prior: ±0.002, a null result.
- `hprior`, the month×hour prior: A is worse by +0.019 on direction and +0.004 on spike. Killed by the coordinator's criterion.
- `hfull2`, which adds the previous run, up96, mFRR spread and same quarter on previous days to the history model: no better than hfull offline (A 0.4062, B 0.4496), so it was never run.
- `neigh`: weak, as expected. Direction is a little better (A −0.010, B −0.002) and spike too, but B MAE is worse by +0.39. Not recommended unless another agent finds a use; probably redundant with the Fingrid real-time data.

## Recommended

`package + runs_features`, the mixture model, and `post = blend_post(0.6)` (logit blend with the `hist_full_features` history model). For the final model, keep the history model fitted on `fg_hist` only. Refitting it on history plus June–September 2026 is possible for the test, but it is untested here.

## Drift: autumn 2025 against summer 2026

`fg_hist` matches the package exactly on the 12 overlapping quarters (direction, price, wind and consumption forecasts). Direction is quarter-resolved from April 2025; March 2025 is partly hourly, before the mFRR energy market started.

| period | P(up) | P(none) | mean DA net (MW) | persistence (dir equal 5 quarters apart) |
|---|---|---|---|---|
| Jun–Aug 2025 | 0.446 | 0.011 | 6259 | 0.66 |
| Sep–Nov 2025 | 0.398 | 0.005 | 6388 | 0.70 |
| 5 Oct–1 Nov 2025 | 0.387 | 0.006 | 6195 | 0.70 |
| Dec 2025–Feb 2026 | 0.458 | 0.002 | 9481 | 0.71 |
| Jun–Aug 2026 | 0.358 | 0.001 | 6090 | 0.69 |
| Sep 2026 | 0.323 | 0.003 | 5930 | 0.72 |

- **The level shifts year on year**: summer 2025 was 9 pp more often up than summer 2026. The history level does not transfer one-to-one. The blend still works because the history model mainly contributes persistence and day-ahead structure.
- **The hour profile flips in autumn.** In Oct 2025, P(up) at 10–15 local was 0.50 and at 20–23 was 0.26. In summer 2026 it was 0.33 at midday and 0.44 in the evening; in Sep 2026, 0.34 and 0.30. A model trained on summer will likely under-predict up at midday and over-predict it in the evening during the test period. This is probably why `hprior` hurt on A: month-specific shapes are unstable.
- **Net position is out of range.** P(up) rises with day-ahead net in every period, but the slope varies (logit slope per GW: 0.62 in summer 2026, 0.43 in Oct 2025 and Sep 2026, 0.16 over Sep–Nov 2025). In Oct 2025, 26% of quarters had a net of 8–10 GW, against 4% in summer 2026 and 8% in Sep 2026. Trees extrapolate flat, which happens to match Oct 2025 (P(up) ≈ 0.52 at 8–10 GW).
- **P(none) is about 0.5% in autumn 2025**, against 0.1% in the 2026 training data. That is negligible for the Brier score.

## Suspicious / notes

- The REF direction classifier on fold B has almost no skill at steps 1–4 (3-class Brier 0.453, about climatology), although persistence is strong. The 14-day Platt step and overfitting (the `structure` agent's regularised HGB also improves direction) are the likely causes. Worth checking `calibrate` for direction separately.
- The Platt slope of hfull on June–July 2026 is about 0.5, yet August and September validate better uncalibrated. June–July 2026 looks like an atypical, low-predictability period, so calibrating on it may hurt the test.
- The blend weight of 0.6 was chosen offline on both folds' validation sets (it is flat between 0.5 and 0.7), so it carries a small selection bias.
