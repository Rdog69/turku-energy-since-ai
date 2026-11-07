# Agent `probs`: spike/direction probabilities and pinball width

Code: `experiments/lab/features/probs.py` (19 direction- and spike-history features, leakcheck OK) and `experiments/lab/exp_probs.py`.
- Stage `gen` caches the raw components in `_cache/probs/` for the full model and for the 14- and 28-day inner models, with pkg and dir feature sets: p_up, direct spike classifiers, conditional spike classifiers and the mixture grids.
- Stage `eval` post-processes those caches.
- The REF reproduction from the caches matches the leaderboard **to 5 decimals** on both folds, for both mixture and direct spike.

## Final results (leaderboard rows, agent `probs`)

| config | fold | MAE | pinball | spike Brier | dir Brier |
|---|---|---|---|---|---|
| REF package mixture | A | 43.576 | 12.463 | 0.09485 | 0.43691 |
| **BEST** (dirfeat + EB50 Platt + mult_add) | A | 43.576 | **12.088** | **0.09402** | **0.42904** |
| BEST + tail_pupcal | A | 43.576 | 12.088 | 0.09320 | 0.42904 |
| REF package mixture | B | 29.402 | 7.014 | 0.07879 | 0.45278 |
| **BEST** | B | 29.402 | **6.925** | **0.07219** | **0.45190** |
| BEST + tail_pupcal | B | 29.402 | 6.925 | 0.07246 | 0.45190 |

Day-block bootstrap of BEST − REF (mean, sd, P(gain)):
- spike, fold A: −0.0008 ± 0.0005, P = 0.95
- spike, fold B: −0.0066 ± 0.0022, P = 1.00
- dir, fold A: −0.0079 ± 0.0088, P = 0.82
- dir, fold B: −0.0009 ± 0.0030, P = 0.65

## Sweep (Δ vs REF; negative = better; 14-day window unless noted)

| variant | spike A | spike B | dir A | dir B | pinball A | pinball B |
|---|---|---|---|---|---|---|
| spike_cal none (raw) | +.0016 | −.0059 | | | | |
| spike_cal temperature (Brier) | −.0013 | −.0045 | | | | |
| spike_cal Platt fitted on Brier | +.0010 | −.0001 | | | | |
| spike_cal isotonic | +.0042 | −.0004 | | | | |
| spike_cal Platt per band | +.0001 | −.0004 | | | | |
| spike_cal spot-conditional Platt | −.0010 | +.0039 | | | | |
| spike_cal shrink to train prior | +.0042 | −.0063 | | | | |
| spike_cal shrink to recent prior | +.0026 | +.0024 | | | | |
| **spike_cal EB-Platt m0=25/50/100** | **−.0006/−.0008/−.0008** | **−.0065/−.0066/−.0065** | | | | |
| spike direct classifiers (REF Platt) | +.0038 | −.0023 | | | | |
| avg(mix, direct) prob / logit | +.0007 / +.0016 | −.0006 / −.0019 | | | | |
| stack(mix, cond) | +.0000 | −.0049 | | | | |
| blends with EB50 (mix+direct, mix+cond) | −.0002 / −.0000 | −.0046 / −.0058 | | | | |
| factorised p_dir × P(spike\|dir), EB50 | +.0009 | −.0060 | | | | |
| tail_pupcal (with EB50) | −.0017 | −.0063 | | | | |
| dir_cal temperature / isotonic / shrink | | | +.0045 / +.0054 / −.0026 | −.0009 / +.0025 / +.0052 | | |
| dir_cal Platt per band | | | +.0001 | −.0000 | | |
| **dir features (probs.py) + Platt** | | | **−.0079** | **−.0009** | | |
| p_none 0 / 0.002 / 0.004 | | | +.0001 / −.0001 / −.0002 | ±.0000 | | |
| width none | | | | | +.336 | +.261 |
| width multiplicative | | | | | −.368 | −.078 |
| **width mult + additive** | | | | | **−.375** | **−.089** |
| mixture quantiles from calibrated p_up | | | | | −.129 | +.232 |
| window 7 days | +.0069 | −.0072 | +.0081 | +.0114 | +.143 | −.011 |
| window 28 days (REF recipe) | −.0022 | +.0026 | −.0123 | +.0166 | −.153 | +.270 |
| window 28 + EB50 | −.0021 | −.0039 | | | | |

Spike-history features (hi/lo shares, same quarter on previous days) add nothing to the spike classifiers.

## What helped on both folds
1. **Empirical-Bayes-shrunk Platt for spikes.** Fit Platt (a, b) on the 14-day window, then shrink towards identity: a′ = s·a, b′ = 1 + s(b−1), with s = m/(m+50), where m = the number of **distinct delivery quarters with an event** in the window. Fold B's window (late July) contains only ~3 low-spike quarters (0.2 % vs 6.7 % in August). Plain Platt collapses p_lo to a constant of about 0.002 there, which is most of REF's loss on B. EB keeps Platt where events are plentiful (fold A, s ≈ 0.8). The result is flat across m0 = 25–100, so it isn't knife-edge tuned.
2. **Direction-history features** for p_up: run length, previous run length, up-share over 1/4/8/24 h, switches in the last 4 h, and the same quarter on the previous 1–7 days. Keep the global Platt.
3. **Multiplicative width correction per step band, then the REF additive offset.** k is grid-searched to minimise pinball on the calibration window. Coverage goes up (B: 0.81 → 0.85), but pinball improves on both folds.

## Recommended recipe
p_up comes from package + `dir_features`, with global Platt on the last 14 days and p_none = the training rate. Spikes use the mixture tail, built from raw p_up as in REF, with EB-Platt (m0 = 50), and hi+lo normalised to at most 1. Quantiles use the REF mixture with per-band mult+add width, 14 days. Implementation: `recipe(F, dir_fs="dir", spike_cal="eb50", width="mult_add")`.
Optional: `tail_pupcal=True`. It gains a further 0.0008 on A but loses 0.0003 on B, so it fails the both-folds rule.

## What didn't help / suspicious
- **Calibration-window noise dominates.** Raw forecasts are too sharp and too low on validation in both folds: in the reliability table, p ≈ 0.007 has 4 % observed and p ≈ 0.6 has about 45 %. A 14-day window can even point the wrong way: late July was calm, August was spiky.
- Isotonic, per-band maps and spot-conditional calibration overfit or flip between folds. This matches the advice to prefer few parameters.
- **The 28-day window is confounded.** On fold B its inner model is trained on only one month (30k rows) and its maps don't transfer. It is strongly better on A for every metric (dir −0.012). The final model has about 4 months of history, so 28 days may actually be better at submission time. That is worth a check on a third fold if time allows.
- Direct/conditional classifiers and their blends: the mixture tail with EB beats all of them on A. On B the earlier "direct wins" result was mostly an artefact of the degenerate Platt.
- p_none: the effect is ≤ 0.0002, so skip it.
- Bootstrap noise: the dir gain is consistent in sign but not significant per fold, as the sd above shows.
