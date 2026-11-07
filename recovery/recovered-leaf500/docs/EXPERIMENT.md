# Experiment: Increase Minimum Leaf Samples

## Hypothesis
Increasing `min_child_samples` from 300 to 500 will reduce probability overconfidence in the GBM model predictions.

## Change
Modified `src/models/gbm.py` to increase `min_child_samples` parameter in `BASE_PARAMS` from 300 to 500.

## Test
Added unit test in `tests/test_candidate.py` to verify that the increased `min_child_samples` parameter is correctly passed to LightGBM models during initialization.

## Limitations
This is a parameter adjustment only; actual performance impact on probability calibration needs to be validated with proper evaluation metrics.