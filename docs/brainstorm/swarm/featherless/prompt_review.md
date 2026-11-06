You are a strict code reviewer for a forecasting competition where ANY use of data before its first-usable time scores zero. Attached: the experiment lab (data.py, models.py, run.py, features/package.py, README.md) and the current leaderboard.

1. Leakage review: find every way a feature, the calibration step, the fold construction or the model fitting could use information not available at the forecast origin (rows with fu > origin, targets as features, calibration fitted on validation rows, training rows whose targets are not yet published at the cutoff, fold boundary overlaps, global statistics, etc.). For each: file + line/function, why it leaks or not, severity, fix.
2. Correctness review of the metrics vs the organisers' score.py formulas (described in README/models.py docstrings) and of the mixture CDF inversion and spike probabilities.
3. Anything that makes fold A/B comparisons unfair.
Be concrete; cite code. Say "no issue" where the code is fine. Max 1200 words.
