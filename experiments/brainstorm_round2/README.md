# Round-2 brainstorm experiments (quick, leak-checked)

Rough experiments behind [`docs/brainstorm/round2/05_claude-opus-5.5.md`](../../docs/brainstorm/round2/05_claude-opus-5.5.md). They're **not** the production pipeline: they use scikit-learn `HistGradientBoosting` (LightGBM-family; LightGBM needs `libomp` on macOS) and fixed lags. Those lags are asserted against `first_usable_origin_utc` at every origin, and the asserts fail if you try lag 4 for the imbalance family.

Run them from the repo root (needs pandas, numpy, pyarrow, scikit-learn):

```bash
python experiments/brainstorm_round2/exp_mixture.py starter_package 0 base    # direct vs mixture; writes preds_base.npz
python experiments/brainstorm_round2/exp_mixture.py starter_package 21 hl21   # same with a 21-day recency half-life
python experiments/brainstorm_round2/calib.py                                 # 2-fold calibration test on preds_base.npz
python experiments/brainstorm_round2/exp_target.py experiments/brainstorm_round2/exp_mixture.py starter_package  # price vs gap target
python experiments/brainstorm_round2/check7.py                                # kill-checks for the round-2 ideas
```

Train: origins from 2 Jun with targets before 7 Sep. Validation: origins 7 Sep – 4 Oct (26,700 rows, 2,688 distinct quarter-hours). Metrics follow `score.py`.
