# Experiment 19: lower learning rate (0.05 → 0.03), fixed tree budget

**Hypothesis.** With `n_estimators` held at 400, a smaller learning rate (0.03) may
generalise better on the seasonal drift than the baseline 0.05, without needing more
trees.

**Change.** `BASE_PARAMS["learning_rate"] = 0.03` in `src/models/gbm.py`; all other
hyperparameters unchanged. This applies to every GBM variant, including
`gbm_cal_product_norecency` (its `GBMModel` uses the default params).

**Test.** `tests/test_candidate.py` asserts `GBMModel().params["learning_rate"] == 0.03`
and `n_estimators == 400`. No fit/predict, no training data.

**Limitations.** No local dataset, so no performance numbers here; validation is left
to the protected host evaluation. Fitting/recency/calibration logic untouched.