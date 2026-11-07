# Session note (Sat 7 Nov, afternoon): blend tweaks, wind map, Nordic wind

These were run in parallel with the history-mode session, all on the **old (Jun–Oct 2026) training data**. Scores are lab scores on folds A + B (`fl_lab.scored_board`).

## 1. Sakibul's "Grand Champion V2" banded weights are overfit
Script: `experiments/lab/exp_banded.py`. It picks the Frank/ours weights per step band and per output on one fold, then scores them on the other.

| Blend | Lab score |
|---|---:|
| team5050 (flat 50/50) | **+6.58** |
| Flat weight, cross-fitted | +6.19 |
| Sakibul's 4 bands, cross-fitted | +6.09 |
| Sakibul's 4 bands, in-sample | +7.02 |

His 40.73 is an in-sample number. Two parts were stable on both folds: Frank's share in the p10/p90 blend is about 0.3, and his share in p50 at steps 1–4 is about 0.

## 2. team_v2: a small win that passes both folds
Recipe: `experiments/lab/recipe_team_v2.json`. Scripts: `exp_trio.py` and `exp_team_variants.py`.

What it is: team5050, plus our weather-only member `m_w6ss_lgb21` in the p10/p90 blend, plus our model's p50 alone at steps 1–4.

| | Lab score | Weeks won vs team5050 | Official Sep MAE / pinball / spike / dir |
|---|---:|---:|---|
| team5050 | +6.58 | – | 40.97 / 11.63 / 0.0861 / 0.3803 |
| team_v2 | **+6.87** | 7–8/10 | **40.91 / 11.52** / 0.0861 / 0.3803 |

Both files passed the validator (`submissions/*team_v2*`). Adding W6 to the p50, spike or direction blends hurts September.

**For the history session:** try the same two tweaks on the history blends: a W6 or weather-only member in the p10/p90 blend, and the history INT4 alone for p50 at steps 1–4.

## 3. Learned wind map (Frank's idea, our build): it fails the both-folds rule
Files: `features/wmap.py` and `fit_wmap.py`. Data: Frank's 14 IFS + 8 ICON points, lab source `fw`. Rebuild it with `tools/convert_frank_weather.py`.

The map was fitted only on 1 Jun – 31 Jul, before both folds. It reaches R² 0.92 in August (old 7-point curve: 0.87). In **October** it drops to 0.64, against 0.84 for the old curve. The summer-only fit saturates at a capacity factor of about 0.53, while October's correlation is still the best. With the history data, refit it including autumn 2025 (IFS only; there's no ICON before May 2026).

| Model | Lab score | Sep MAE | Note |
|---|---:|---:|---|
| INT4+ss lgb7 (base) | +6.17 | 41.37 | |
| + `wmap` | **+6.56** | 41.53 | Best single model, but worse on Sep MAE and direction |
| + `wmap_s` (adaptive scale) | +6.41 | 41.50 | |
| + `wmap_core` | +6.29 | 41.45 | |

Swapping it into team_v2 gives +7.04 to +7.09 on average, but September falls from +6.56 to +6.43–6.51, and it wins only 6/10 weeks. **Not adopted.**

## 4. Nordic wind (SE/NO/DK/EE revisions): fails
File: `features/nordic.py`.

| Model | Lab score | Sep | Aug |
|---|---:|---|---|
| + `nordic` | +5.92 | Better (MAE 41.20, pinball 11.56) | Worse on all four scores |
| + `nordic_rev` | +6.06 | | |

This matches Frank's finding that Nordic wind helps September's median only.
