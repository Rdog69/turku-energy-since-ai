"""Unit test for hypothesis 19: BASE_PARAMS learning_rate 0.05 -> 0.03.

Lightweight only — no fit, no predict, no dataframes.
"""
from src.models.gbm import BASE_PARAMS, GBMModel


def test_base_params_learning_rate_is_0_03():
    assert BASE_PARAMS["learning_rate"] == 0.03


def test_default_model_params_use_new_learning_rate():
    m = GBMModel()
    assert m.params["learning_rate"] == 0.03


def test_tree_budget_unchanged():
    assert BASE_PARAMS["n_estimators"] == 400
    assert GBMModel().params["n_estimators"] == 400