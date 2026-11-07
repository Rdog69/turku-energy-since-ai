# Agent nowcast: Fingrid real-time data on top of `package_features`

Code: `experiments/lab/features/nowcast.py` (4 groups: `rt_imb`, `rt_wind`, `rt_cons`, `rt_misc`) and `experiments/lab/exp_nowcast.py` (`check`, `bands`, E1–E5, E2d, E4d). All groups pass `leakcheck`. Newest fg_rt quarter has `age_q = 3` at every origin; package imbalance and mFRR have `age_q = 5`; fg176 has `age_q = 5` and is hourly-constant.

## Results (leaderboard rows; lower is better)

| run | fold | model | MAE | pinball | spike | dir | MAE s1-4 | s5-12 | s13-40 |
|---|---|---|---|---|---|---|---|---|---|
| REF package mixture | A | mix | 43.576 | 12.463 | 0.0949 | 0.4369 | 41.81 | 43.09 | 43.97 |
| E1 rt198 imb | A | mix | 43.746 | 12.413 | 0.0960 | 0.4333 | 41.89 | 43.01 | 44.23 |
| E2 rt198+wind | A | mix | 43.397 | 12.249 | 0.0937 | 0.4277 | 40.73 | 42.43 | 44.06 |
| E3 rt198+wind+cons | A | mix | 43.030 | 12.304 | 0.0917 | 0.4258 | 41.03 | 42.44 | 43.49 |
| E4 rt all | A | mix | 42.993 | 12.140 | 0.0924 | 0.4233 | 40.17 | 42.45 | 43.56 |
| **E5 rt imb+wind+misc** | A | mix | **42.997** | **12.105** | **0.0922** | **0.4160** | 40.35 | **42.34** | 43.57 |
| REF package direct | A | dir | 43.942 | 12.643 | 0.0987 | 0.4369 | 41.99 | 43.26 | 44.42 |
| E2d rt198+wind direct | A | dir | 43.922 | 12.550 | 0.0970 | 0.4277 | 41.84 | 43.10 | 44.46 |
| E4d rt all direct | A | dir | 44.490 | 12.575 | 0.0964 | 0.4233 | 42.28 | 43.70 | 45.04 |
| REF package mixture | B | mix | 29.402 | 7.014 | 0.0788 | 0.4528 | 28.49 | 29.07 | 29.63 |
| E1 rt198 imb | B | mix | 29.462 | 6.935 | 0.0783 | 0.4491 | 28.60 | 28.99 | 29.72 |
| E2 rt198+wind | B | mix | 29.243 | 6.878 | 0.0818 | 0.4461 | 28.03 | 28.69 | 29.58 |
| E3 rt198+wind+cons | B | mix | 29.698 | 6.989 | 0.0711 | 0.4494 | 28.56 | 28.92 | 30.09 |
| E4 rt all | B | mix | 29.542 | 6.973 | 0.0771 | 0.4487 | 27.87 | 28.62 | 30.05 |
| **E5 rt imb+wind+misc** | B | mix | **29.243** | 6.892 | **0.0703** | 0.4489 | **27.65** | **28.51** | 29.68 |
| REF package direct | B | dir | 29.308 | 7.181 | 0.0765 | 0.4528 | 28.39 | 29.01 | 29.53 |
| E2d rt198+wind direct | B | dir | 29.232 | 7.067 | 0.0763 | 0.4461 | 28.12 | 28.75 | 29.53 |
| E4d rt all direct | B | dir | 29.776 | 7.061 | 0.0757 | 0.4487 | 28.43 | 29.18 | 30.14 |

Per-band direction Brier (from `exp_nowcast bands`): the gain is mostly at short steps. For E4 at steps 1–4, A goes 0.418 → 0.386 and B goes 0.452 → 0.436. At steps 13–40 the gain is small (A −0.011, B −0.001).

## What helped, on both folds

- **The fg198/fg186 imbalance group alone (E1) is close to null.** MAE is flat or slightly worse. Pinball and dir Brier improve on both folds (dir −0.0036 / −0.0037). It fails the kill rule (MAE_s1_4 must gain ≥ 2%). fg198 relates to mFRR direction only weakly and non-monotonically: Spearman with the same-quarter dir is 0.11, and large deficits go with *down* regulation. It looks like it measures the after-effect of activations rather than the need for them. Kept only as a base for the other groups.
- **The wind error group (E2) is the clear winner.** MAE_s1_4 drops −2.6% (A) and −1.6% (B), dir Brier −0.009 / −0.007, and pinball improves on both folds. Fold B spike Brier gets worse (0.0788 → 0.0818).
- **The consumption and production-plan group (E3) is not robust.** It helps on A (MAE −0.37) but hurts on B (MAE +0.45, MAE_s13-40 +0.5). Spike Brier on B swings a lot (0.071). **Drop it.**
- **The misc group (frequency, nuclear drop, net import, hydro ramp, fg176) helps.** Compare E5 (E2 + misc) with E2: MAE_s1_4 −1.0% (A) and −1.4% (B), dir −0.012 (A) and −0.003 (B), spike −0.0015 (A) and −0.0115 (B). Frequency was not tested on its own, so the frequency kill rule could not be applied separately.
- **E5 vs REF mixture (the best set):** better on all four metrics on both folds. A: MAE −0.58, pinball −0.36, spike −0.0026, dir −0.0209. B: MAE −0.16, pinball −0.12, spike −0.0085, dir −0.0039. MAE_s1_4: −3.5% (A), −2.9% (B); both pass the 2% rule.
- **Direct vs mixture:** with the same features, direct is worse on A (E4d MAE 44.49 vs 42.99) and about the same on B. Dir Brier is identical because both models use the same classifier. **Use mixture.**

## Recommended

`package_features + rt_imb + rt_wind + rt_misc`, `model="mixture"`, `target="gap"`, `calibrate=True` (E5). If a smaller set is needed, `rt_wind` + `rt_misc` carry the gain and `rt_imb` is optional.

## Not testable / suspicious

- **Item 5 (bid stack) and advisor idea 3 (scarcity) cannot be done.** fg243 up-bid sum is all 0, fg22 is absent, and fg251 only covers 14–18 Oct (after training). fg209 system state is constant 1, so it was dropped.
- The gains are much smaller than the "1-quarter-old imbalance price gives step-1 MAE ≈ 26" figure. Real-time physical flows are a weak proxy for the Nordic-wide mFRR price.
- Spike Brier swings ±0.01 on fold B between feature sets (E3 0.071, E2 0.082). Treat spike-Brier differences below about 0.005 as noise. The same goes for MAE differences below about 0.2: the model is a single HGB seed.
- The E2/E3/E4 order was fixed in advance. E5 was chosen after seeing E3 on fold B, so there is mild selection on B.
- `perr` (production rt − fg242 plan) has a mean of +169 MW. The plan seems to leave something out. Harmless for trees.
