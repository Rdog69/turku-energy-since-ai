
## Round 0 (02:04)
- **INT1 reg+bands+rt** [fl-seed] ok score=3.693 (6.3 min): structure's best setup + nowcast's best features
- **INT2 reg+bands+rt+dir+blend** [fl-seed] ok score=3.882 (7.6 min): all winners stacked
- **INT3 reg+rt+dir+blend nobands** [fl-seed] ok score=2.27 (5.2 min): same without bands, to measure the band contribution with rich features
- leader after round: **INT2 reg+bands+rt+dir+blend** [fl-seed] score=3.882 all-better-both=True

## Round 1 (02:16)
- **INT4 int2+wind_hat** [fl-GLM-5.3] ok score=3.084 (9.3 min): INT2's real-time gains concentrate in steps 1-4, while wind_hat (per-step-band day-ahead wind-error estimate) was the only weather addition that improved all four metrics on both folds (pinball_B 6.70 vs INT2's 6.80), so it should complement the stack at steps 5-16+ where INT2 is weakest.
- **INT5 int2+causal0.2** [fl-GLM-5.3] ok score=3.896 (9.2 min): Causal averaging with the o-1h origin gave a small but consistent gain (~0.1-0.5%) in the structure agent's runs at w<=0.2, and since scoring rewards small consistent gains it is a low-risk single-change addition to the full INT2 stack.
- **INT6 int2+band17-40** [fl-GLM-5.3] ok score=3.713 (11.3 min): Steps 17-40 currently fall back to the pooled model; giving them a dedicated refit extends the banding mechanism that already delivered -7% MAE at steps 1-4 and should help pinball and direction at the long horizons where no band-specific model exists yet.
- leader after round: **INT5 int2+causal0.2** [fl-GLM-5.3] score=3.896 all-better-both=True

## Round 2 (02:29)
- **INT7 int5+blend0.7** [fl-Kimi-K3] ok score=3.856 (12.4 min): Direction Brier has the largest relative headroom and the blend weight has never been varied since 0.6 was set; probing 0.7 tests whether more history weight keeps improving direction on both folds with bounded downside.
- **INT8 int5+maxfeat0.8** [fl-Kimi-K3] ok score=3.613 (12.5 min): Feature bagging is an untested regularization axis on a wide feature set; decorrelating boosting stages often yields small simultaneous gains on MAE, pinball and both Briers that transfer across folds.
- **INT9 int5+temp** [fl-Kimi-K3] ok score=3.559 (12.4 min): Exploration: weather agents show temp gives the best pinball_B on the board and helps direction_A, and unlike wind_hat (which broke spike Brier B) it is orthogonal to the rt wind-error features, so it is the safest untested combination with the champion spec.
- leader after round: **INT5 int2+causal0.2** [fl-GLM-5.3] score=3.896 all-better-both=True

## Round 3 (02:44)
- **INT10 rt-short** [fl-DeepSeek-V4.1-] ok score=3.662 (14.4 min): Implements Frank's finding by giving real-time Fingrid sets only to bands ending at step 8, keeping the long band free of their noise while retaining runs/dir everywhere.
- **INT11 rt-short+calib** [fl-DeepSeek-V4.1-] ok score=3.544 (13.9 min): Adds the known-good spike-calibration fix and 28-day calibration window on top of the short-band real-time feature split, targeting spike Brier without sacrificing MAE/pinball/direction.
- leader after round: **LGB blend HGB+1seed 50/50** [lgb] score=3.981 all-better-both=True
