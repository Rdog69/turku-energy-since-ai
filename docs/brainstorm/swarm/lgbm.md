# LightGBM instead of HGB (INT5 pipeline)

Code: `experiments/lab/models_lgb.py` (`fit_predict_lgb`, drop-in for `models.fit_predict`; swaps the two learners for LightGBM quantile regressors and a classifier, with bagging and `n_seeds` averaging), `experiments/lab/exp_lgb.py` (runs the INT5 spec through `combo.run_spec` with `models.fit_predict` and `run.fit_predict` monkeypatched; leakcheck and both folds kept), `experiments/lab/exp_lgb_blend.py` (50/50 blend of saved npz predictions). Shared files untouched. Note the `blend_post` history model and the bands also use the patched learner.

Defaults: num_leaves 15, min_child_samples 400, 150 trees, lr 0.05, subsample 0.8 (freq 1), colsample 0.8, lambda 1.

| Experiment | Score (INT5 = 3.90) | All metrics better on both folds |
|---|---:|---|
| LGB INT5, 1 seed | 3.84 | yes |
| LGB INT5, 5 seeds | 4.01 | yes |
| leaves 31, 300 trees, lr 0.03, 3 seeds | 3.68 | yes |
| leaves 7, 300 trees, lr 0.05, 3 seeds | 4.15 | yes |
| **leaves 15, 250 trees, lr 0.04, min_child 300, 3 seeds** | **4.21** | yes |
| Blend 50/50 HGB INT5 + LGB 1 seed | 3.98 | yes |
| Blend 50/50 HGB INT5 + LGB 5 seeds | 4.05 | yes |
| Blend 50/50 HGB INT5 + LGB mcs300 | 4.16 | yes |

Findings
- One seed is slightly below HGB; seed averaging is worth about +0.17. LightGBM with bagging is a gain only with several seeds.
- Smaller or more-regularised trees win (7 leaves, or 15 leaves with min_child 300 and more trees); 31 leaves loses, as with HGB.
- Blending with HGB does not beat the best pure LightGBM run (4.16 vs 4.21), so just use LightGBM.
- Differences of about 0.05 between runs are within noise (seed and tuning chosen on the same two folds); the seed-averaging gain is the robust part.
- Cost: about 5 min for 1 seed, about 25 min for 3-5 seeds (whole INT5 pipeline, both folds, shared CPU).
- Not tried: combining with the newer V2 INT5 + spot_shape (4.21), which is on the same level.

Reproduce: `OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.exp_lgb "name" n_seeds=3 n_estimators=250 learning_rate=0.04 min_child_samples=300`
