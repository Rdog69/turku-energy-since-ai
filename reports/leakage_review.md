# Leakage review

Scope: the code of commit `e22354b` (Frank's rounds 3-6 plus our live-imbalance port), read by hand.
The rule: at forecast origin `t`, a row may be used only if `first_usable_origin_utc <= t`.

Result: no mechanism was found that breaks the rule. There is one weak point that does not affect
any submitted forecast (row 2, calibration only). There is one known optimism in our own August
check (row 6). No spot price values are quoted here.

## One row per mechanism

| # | Mechanism | Rule the code applies (file:function) | Test that covers it | Verdict |
|---|-----------|---------------------------------------|---------------------|---------|
| 1 | Package and external feature values | Every value is read with `SeriesIndex.value_at` / `latest` / `first_usable_at` (`src/data/availability.py`). `value_at` returns NaN unless `fu <= origin`. `latest` returns the newest timestamp among rows with `fu <= origin`, and the value only on an exact timestamp match. `SeriesIndex.__init__` rejects duplicate timestamps. | `test_availability.py::test_features_ignore_unpublished_rows`, `::test_matches_reference_filter`, `::test_latest_equals_newest_reference_row_for_all_series`, `::test_external_series_ignore_unpublished_rows`; `test_leak_hardening.py::test_latest_non_monotonic_publication`, `::test_latest_first_usable_exactly_at_origin`, `::test_latest_random_series_match_reference`, `::test_duplicate_timestamps_are_rejected`; `test_code_audit.py::test_no_lags_or_rolling_windows_in_src` | SAFE |
| 2 | Wind map fit (`om_wind_hat*`) | `src/models/wind_power.py:WindPowerMap.fit` keeps measured wind rows with `ts < cutoff` and `fu <= cutoff`. Each is paired with the weather runs usable at `floor(ts - 5 h)`, which is before the cutoff. `predict` uses `WeatherIndex.lookup(origin, ...)`, so it sees only runs with `run_fu <= origin`. `add_wind_hat` (`src/features/build.py`) compares with the run usable at `min(first_usable_at(delivery), origin)`. | `test_availability.py::test_wind_map_fit_uses_only_data_published_by_cutoff`, `::test_wind_hat_features_ignore_unpublished_runs` | SAFE for forecasts. Weak point in calibration only: the weights are fitted once at the cutoff, so the calibration holdout rows (last 28 days) get a feature whose weights saw the holdout wind values. This makes the calibration offsets slightly too optimistic. It does not use any data after the cutoff, so it cannot leak into a forecast. |
| 3 | History rows (Mar 2025 - May 2026) | `src/data/load.py:load_history` keeps only series that the package also has, only `timestamp < DATA_START`, and drops repeated quarters (keeps the copy published last). For measured series it raises `first_usable` to at least `timestamp + (largest package delay for the same minute of the hour)`. Day-ahead and calendar rows keep their own times. `with_history` raises on any overlap with package rows. Training adds early origins in `src/backtest/run.py:training_table`, then keeps only rows with `y_first_usable <= cutoff`. The history table has no ids in common with the external tables (checked). | `test_availability.py::test_history_rows_follow_package_rules_and_availability`, `::test_training_rows_known_before_cutoff`; `test_leak_hardening.py::test_training_table_respects_the_cutoff`; `test_external.py::test_pending_history_is_opt_in` | SAFE |
| 4 | Nordic, ICON and town weather comparisons | `add_weather_nordic`, `add_weather2`, `add_towns` (`src/features/build.py`) look up "now" with `WeatherIndex.lookup(origin, ...)`. The comparison run is looked up at `np.minimum(first_usable_at(delivery), origin)`, so it is never later than the origin. If no day-ahead row exists, `first_usable_at` returns int64 max and the minimum gives the origin (revision 0). `lookup` picks the newest run with `run_fu <= time`. All weather indexes have increasing run order (checked for ECMWF, ICON and the four Nordic areas). | `test_availability.py::test_nordic_weather_ignores_unpublished_runs`, `::test_icon_features_ignore_unpublished_runs`, `::test_icon_run_used_was_published`, `::test_town_features_ignore_unpublished_runs`, `::test_weather_features_ignore_unpublished_runs`, `::test_weather_run_used_was_published` | SAFE |
| 5 | Live imbalance (Fingrid 198, 186, 192, 242, 191) | `src/features/build.py:add_rt_imbalance`: the newest quarter comes from `SeriesIndex.latest`, older quarters and the BRP plan from `value_at(..., origin)`. The external loader (`src/data/external_long.py:_conservative_fu`) sets `fu` to the later of the file value and the documented delay rule (quarter end + 30 min, rounded up to the hour). `write_submission` (`src/backtest/run.py`) now raises if `data_cutoff > origin`. The v6_hf model does not use these columns. They only add to `latest_ts`, which feeds `data_cutoff`. | `test_availability.py::test_rt_imbalance_matches_reference_filter`, `::test_data_cutoff_before_origin`; `test_external.py::test_loader_makes_too_early_fu_conservative`, `::test_loaded_fu_never_earlier_than_documented_rule`, `::test_existing_features_unchanged_by_external_series`; `test_leak_hardening.py::test_write_submission_rejects_cutoff_after_origin` | SAFE. For 40 origins (20 validation, 20 training) the features and `data_cutoff` of v6_hf are identical with and without the external series. |
| 6 | Tuning folds (`src/models/tune.py`) | Folds start 26 Jul, 9 Aug and 23 Aug 2026 (21:00 UTC). Each fold trains on rows with `y_first_usable <= fold start` and is scored on the next 14 days. The last fold ends at the first validation origin. Only hyperparameters are chosen here. Tuning uses no row from the test period. | No automated test. Checked by reading the code. | SAFE for validation (7 Sep - 4 Oct) and for the test period. For fold B (August) the tuned settings were chosen on folds that contain August, so fold B is slightly optimistic for tuned models (already stated in `docs/RESULTS.md`). The last fold scores targets up to 10 h past its end, which touches the first hours of validation. This only affects the choice of hyperparameters. |
| 7 | `MedianFrom` (`src/models/blend.py`) | Both sub-models are fitted on the same training table with the same `cutoff`. `use_history` raises if the two models disagree. Features and flags are the union of both models. P50 and drivers come from the second model, all other outputs from the first. No extra data enters. | `test_leak_hardening.py::test_training_table_respects_the_cutoff` (training table), plus the feature tests in rows 1-4 (same features) | SAFE |
| 8 | Calibration (`src/models/gbm.py:GBMModel.fit`) | The inner models use only rows with `y_first_usable <= cutoff - holdout_days`. Platt maps and quantile offsets are fitted on the holdout rows with `origin >= cutoff - holdout_days`. The final models are refitted on all rows with `y_first_usable <= cutoff`. | `test_availability.py::test_training_rows_known_before_cutoff` | SAFE (see row 2 for the wind-map caveat) |

## Feature coverage by the truncation test

The truncation test builds features from all data and from data cut to `fu <= t`, and requires equal
values. Every column of the v6_hf feature list (both sub-models, short and long) belongs to a
column group that a truncation test checks:

| Column group | Test |
|--------------|------|
| `FEATURE_COLUMNS`, `MEMORY_COLUMNS`, `FINGRID_RT_COLUMNS`, `FINGRID_RT2_COLUMNS`, `data_cutoff` | `test_features_ignore_unpublished_rows` |
| `WEATHER_COLUMNS` | `test_weather_features_ignore_unpublished_runs` |
| `NORDIC_COLUMNS` | `test_nordic_weather_ignores_unpublished_runs` |
| `WEATHER2_COLUMNS` (ICON) | `test_icon_features_ignore_unpublished_runs` |
| `WINDHAT_COLUMNS` | `test_wind_hat_features_ignore_unpublished_runs` |
| `HISTORY_COLUMNS` (`regime_2026`, a function of the delivery time only) | `test_history_rows_follow_package_rules_and_availability` |
| `RT_IMBALANCE_COLUMNS`, `TOWN_*` (not used by v6_hf) | `test_rt_imbalance_matches_reference_filter`, `test_town_features_ignore_unpublished_runs` |

## Targets

Targets (`y_*`) are never features: `test_targets_are_not_features` and
`test_code_audit.py::test_no_target_columns_in_any_feature_list`.
