# Agent `dir_boost`: direction Brier on top of INT2

Code: `experiments/lab/dir_boost.py` (`blend_band_post`, `hist_variant_fit`). Base: INT2 spec (`runs`+`dir`, bands, 0.6 history blend).
Method: INT2 was run once with a capture post (stores the pre-blend p_up and the history logit; no targets). All blend variants were then swept offline on those saved predictions, and the final candidate was re-run end to end through `run_experiment`. The capture reproduces INT2 exactly (A 0.3895, B 0.4308). Fitted only on `fg_hist` (before June 2026). No leakage: posts only see origin/step/delivery.

## Results (direction Brier, lower is better)

| variant | A | B | verdict |
|---|---:|---:|---|
| INT2 (w = 0.6 everywhere) | 0.3895 | 0.4308 | base |
| classifier only (w = 0) | 0.4108 | 0.4373 | |
| history only (w = 1) | 0.4051 | 0.4460 | |
| w = 0.2 at steps 1-4 only | 0.3888 | 0.4299 | both better, tiny |
| w = 0.4 at steps 1-4 only | 0.3888 | 0.4300 | both better, tiny |
| w at steps 5-8: 0.4 / 0.8 | 0.3894 / 0.3902 | 0.4305 / 0.4315 | flat |
| w at steps 9-16: 0.2 / 0.4 / 0.8 | 0.4003 / 0.3931 / 0.3909 | 0.4315 / 0.4296 / 0.4346 | 0.6 is best on A; 0.4-0.5 helps B |
| **DIR band weights 0.3 / 0.5 / 0.6** | **0.3886** | **0.4296** | **both better (-0.0009 / -0.0012)** |
| temperature on blended logit, T = 0.8 / 0.9 / 1.1 / 1.2 | 0.3942 / 0.3912 / 0.3889 / 0.3892 | 0.4328 / 0.4313 / 0.4312 / 0.4322 | no gain (T = 1 is right) |
| history model, Sep-Nov 2025 weighted x3 (w 0.6) | 0.3938 | 0.4289 | A worse, B better |
| history model without Jun-Aug 2025 | 0.3947 | 0.4413 | worse on both |
| smaller history model (15 leaves, leaf 1000) | 0.3916 | 0.4307 | no gain |
| mean logit of full + autumn x3 model, weights 0.3 / 0.5 / 0.6 | 0.3898 | 0.4280 | A tie, B -0.0016 |

Direction Brier at steps 1-4 prefers a lower history weight (recent state dominates there) and long steps prefer 0.5-0.6; the effect is small, about 0.001 on each fold, which is inside the bootstrap noise found by `probs` (sd 0.003-0.009 per fold).

## Not run / judged not worthwhile
- **History P(up) as a feature and blend:** `history.md` already showed that feeding it as a feature gives A -0.009, B +0.002 and dilutes it; the blend is the useful use.
- **Real-time features inside the history blend:** the history model has no real-time wind or imbalance inputs, and fg_hist has no matching long history of `rt_wind`/`rt_misc` to fit them on; a stacker would need out-of-sample history predictions on 2026 rows, and the 14-day calibration window is too small to fit it. Not attempted.
- **Temperature fitted on the last 14 training days:** the fixed-temperature sweep shows the optimum at T = 1 on both folds, so there is nothing to fit.
- **Autumn-only history fit:** the validation months are not autumn, so folds cannot confirm it. Autumn-weighting x3 loses 0.004 on A and gains 0.002 on B at w = 0.6. With the band weights above the ensemble is A +0.0003 / B -0.0016, a tie on A. It is a reasonable bet against the autumn drift (more high-net-demand hours in October), but not proven.

## Recommendation
Use `blend_band_post([0.3, 0.5, 0.6])` instead of the flat 0.6 (tiny but consistent on both folds). Optional hedge for the autumn drift: average the logits of the full and autumn-weighted history models (`hist_variant_fit`). Only direction Brier changes; MAE, pinball and spike Brier are identical to INT2 because the post only rewrites p_up/p_down.

Honest note: nothing here is a big win. The 0.6 flat blend was already close to optimal; remaining direction error is mostly noise at long steps.
