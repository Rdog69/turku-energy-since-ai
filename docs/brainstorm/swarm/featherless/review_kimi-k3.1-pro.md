## 1. Leakage review

**Bottom line:** I find no demonstrated `fu > origin` leak in the reference `package_features` path. However, the harness does **not** guarantee leak-freedom: target handling and the optional post-processing hook are serious protocol holes.

### Findings

- **High, conditional: training targets are not checked for availability at the fitting cutoff.**  
  `data.py:build_base` attaches `imb`, `gap`, and `dir` without their target `fu`. `run.py:run_experiment` selects training rows solely with `fold*` and `tr.gap.notna()`. Consequently, the full model can train on deliveries immediately before `val_start` whose imbalance/direction labels were only published after `val_start`. The same issue applies to labels used by `models.calibrate`, and potentially to the inner model producing calibration predictions.  
  **Fix:** retain target publication times separately from features. For the full fit require every used target’s `fu <= val_start`; for the inner fit require availability before the first calibration origin; for the calibrator require calibration outcomes to be usable by `val_start`. If target `fu` cannot be reconstructed, use a conservative publication-lag embargo.

- **Critical protocol hole, not triggered by the reference features: feature functions receive the targets.**  
  `run.py:features` passes the complete `base`, including `imb`, `gap`, and `dir`, to every feature function. `data.py:leakcheck` only rejects output columns *named* like targets and truncates `Data`; it does not remove or truncate `base`. Thus `return pd.DataFrame({"x": base["gap"]})`, or a global statistic fitted on all base targets, can pass leakcheck under a renamed column.  
  **Fix:** pass feature functions only `origin`, `step`, and `delivery` (plus explicitly approved known inputs). Target-free bases should also be used in leakcheck. Global fitted features need a separate check enforcing the rule-2 cutoff, **31 Jul 21:00Z**.

- **Critical if used: `post` can directly read validation outcomes.**  
  `run.py:run_experiment` calls `post(pred, va, X_va)`, where `va` contains `imb`, `gap`, and `dir`. A post-function can therefore trivially alter predictions using validation targets, with no check.  
  **Fix:** pass only origin/step/delivery and explicitly known inputs such as validated day-ahead spot; audit every `post` implementation. No issue when `post=None`, as in the reference rows.

- **Medium: leakcheck is a sample test, not a proof.**  
  `run.py:features` checks only six random origins, once per process and function key. It can miss publication-boundary bugs and does not enforce rule 2. `_feat_cache`/`_checked` are keyed only by module and function name, so editing code in a long-lived process can leave stale features marked as checked.  
  **Fix:** add exhaustive fold-boundary and publication-lag cases, key caches by code/data version, and clear them after edits.

### No issue in the supplied reference path

- `asof`, `asof_window`, and `at_delivery` gate values on `fu <= origin`. `nwp_latest` selects runs using the run’s maximum `fu`, conservatively making the whole run usable only then.
- `package_features` uses `at_delivery` for day-ahead values and `asof` for recent actuals. Its direct historical spot/forecast lookups occur at quarters whose actual imbalance/consumption is already usable; given day-ahead publication semantics, this is not a leak, though explicit `fu` assertions would be safer.
- `spot_rel_win` aggregates only the current origin’s `at_delivery`-checked values; it is not a future-data global statistic.
- Calibration is fitted on `tr`, not validation rows. The 10-hour separation exceeds the 9h45 forecast horizon, preventing inner-training/calibration delivery overlap. Only the target-availability caveat above remains.
- Fold boundaries do **not** overlap: training requires `delivery < cutoff`, while validation requires `origin >= cutoff`; since `delivery >= origin`, no row can satisfy both.
- HGB fitting uses only training matrices, with `early_stopping=False`; there is no global scaler or preprocessing fitted on validation data. Using `va["spot"]` is valid only because spot is day-ahead known for every row; an explicit availability assertion would make this auditable.

## 2. Metrics and mixture correctness

- **Metrics:** `models.metrics` implements MAE and pinball loss correctly, including averaging the p10/p90 pinball losses. Spike outcomes use the correct strict thresholds, `gap > 50` and `gap < -50`, and average the two Brier scores. Direction Brier is the **summed three-class Brier**, not divided by three. Without the organisers’ actual `score.py`, I cannot certify that normalization or valid-row conventions; an averaged class Brier would differ by a factor of three.
- **Minor conditional bug:** the common `ok` mask does not require nonmissing `dir`. Missing directions become three false outcomes in `brier_dir`. Similarly, `fit_predict` treats `NaN != 0` as a nonzero direction. Filter explicitly on observed direction if missing values are possible.
- **Mixture:** sorting conditional quantile grids, constructing the weighted CDF, and taking the first grid point with `F >= q` are correct for the discretized mixture. `p_hi = 1-F(50)` and `p_lo = F(-50.5)` consistently represent strict events on the 0.5-EUR grid. spike probabilities need not be renormalized before calibration.
- **Model assumption:** the no-direction component is a point mass at `gap=0`; verify this on training data or document it as an approximation.
- **Tail risk:** predictions are clipped to `Z=[-600,1500]`, with no interpolated quantile inversion. This can materially affect pinball/MAE during extremes. Choose a sufficiently wide grid from training/physical limits—never validation outcomes—and consider interpolation.
- Quantile-offset calibration and Platt scaling are algebraically reasonable; clipping p10/p90 around p50 prevents crossing. No additional issue.

## 3. Fold A/B fairness

The supplied protocol is fair **between experiments within the same fold**. Fold A has more training history and a different season/validation length than fold B, so their absolute scores should not be compared for difficulty; compare each against that fold’s reference row.

Repeatedly selecting experiments on the shared two-fold leaderboard adaptively overfits both validation windows. Final claims therefore need an untouched holdout or a predeclared selection rule. Stale in-process feature caching can also make rows non-reproducible, but does not affect the reported reference rows if each was run in a fresh process.