# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Since AI 2026 hackathon entry for the Turku Energia challenge. From every full-hour forecast origin, the pipeline forecasts the Finnish **imbalance price** for 40 quarter-hours (10 h): P10/P50/P90, `p_up/p_down/p_none`, and `p_spike_high/p_spike_low` (more than ±50 €/MWh from spot). The submission is `forecast_backtest.csv` for 673 test origins, checked by the organisers' `validate_submission.py` and scored by `score.py` (in `starter_package/`). The product is a "situation room" dashboard for traders.

Start with `docs/HANDOFF.md` if it exists (where the last session stopped); `docs/QUICKSTART.md` is the verified setup path. `docs/PLAN.md` is the source of truth for decisions. `docs/RESULTS.md` logs every scored run and is the ablation table for the jury, so add a row for every result you report. Also log every September (`validation`) and August (`fold_b`) score on the team scoreboard (`scoreboard/README.md`, `python scoreboard/leaderboard.py`); never score or log the test month. `SOURCES.md` (data sources, delays, licences) is a required deliverable.

## The rule that overrides everything

At forecast origin `t`, a data row may be used only if `first_usable_origin_utc <= t`. A leak means an automatic score of 0, and the organisers review the code (possibly with AI).

- Read every feature value through `SeriesIndex.value_at` / `latest` / `first_usable_at` (`src/data/availability.py`) or `WeatherIndex.lookup` (`src/data/weather.py`). Never use `.shift()` lags, rolling windows over a whole series, or any table without its own `first_usable_origin_utc`. `tests/test_code_audit.py` scans `src/` for these patterns.
- Targets (`y_*`, from `add_targets`) are read without the availability mask on purpose, but they are never features. Training rows must satisfy `y_first_usable <= cutoff`; calibration inner models use only rows published by their holdout start.
- Every new feature column must be covered by the **truncation test** in `tests/test_availability.py`: features built from all data must equal features built from data cut to `fu <= t`.

## Licensed data

`starter_package/data/spot_nordpool.csv` (Nord Pool spot) is licensed for hackathon use only. The starter package is committed **on purpose** because the repo is private. Never make the repo public without purging every path on the purge list in `reports/repo_hygiene.md` (starter package data, the two spot-history files, `submissions/`) from history.

- Never print, log, plot or export rows or values of `fi_spot_price`. Aggregates and the gap to spot are fine.
- Never send data to external services. `tools/kimi.py` (Featherless LLM workers) has a data guard that refuses spot data, actuals and raw data rows; LLMs only ever see code, docs and aggregates.
- Abdo's branch also commits spot prices: `external_data/elering/fi_spot_history.csv.gz` (2025 spot from Elering, originally Nord Pool) and `external_data/history/pkg_history.csv.gz` (the pre-June history). They must be purged from history too before the repo could ever go public.
- API keys (`FINGRID_API_KEY`, `FEATHERLESS_API_KEY`, `FEATHERLESS_KEYS`) live in the git-ignored `.env`.

## Commands

```bash
python -m venv .venv && .venv/bin/pip install -r requirements.txt   # works on Python 3.11-3.14
.venv/bin/pip install -r requirements-app.txt                      # Streamlit fallback dashboard

.venv/bin/python -m pytest                                          # all tests, ~10 min on one thread; expect 1 skip (town weather)
.venv/bin/python -m pytest tests/test_availability.py::test_features_ignore_unpublished_rows

# Backtest: train -> forecast -> write -> organisers' validator -> score.py
.venv/bin/python -m src.backtest.run --period validation --model split_all   # fold A: 7 Sep - 4 Oct
.venv/bin/python -m src.backtest.run --period fold_b --model split_all       # fold B: August
.venv/bin/python -m src.backtest.run --period test --model v6_hf             # 673 test origins
```

- The submitted model is Frank's `v6_hf` (built by `make_final` / `_v4_hybrid` in `run.py`); it needs the pre-June history file. `split_all` is the cheap reference.

- Outputs go to `results/<model>/<period>/` (git-ignored): `forecast_backtest.csv`, plus `score/score_summary.md` with per-horizon tables.
- A split-model backtest takes about 10 min on 4 cores; `make_final` models (5 seeds, two models for `MedianFrom`) and history models take much longer. Set `OMP_NUM_THREADS` when running several at once.
- Model names are the keys of `MODELS` in `src/backtest/run.py`. Add a new key for a new variant rather than changing an existing one, so older RESULTS.md rows stay reproducible.
- Accept a model change only if it beats the reference on **both** folds.

Other entry points:
- `python -m src.export.dashboard --model <m> --period test`: per-origin JSON for the dashboard.
- `streamlit run app/streamlit_app.py`: local fallback dashboard. Never deploy it; it shows spot.
- `python reports/figures/make_figures.py`: slide figures. It has no `--help`: any run regenerates the committed PNGs.
- `python tools/pick_demo_moments.py --model <m>`: demo hit/miss and alert stats from validation forecasts. `python tools/paired_bootstrap.py`: paired day-block intervals between models (`reports/uncertainty.md`).
- `python -m src.explain.featherless` / `python -m src.automation.replay`: LLM briefings and n8n alerts.

## Architecture (data → submission)

1. **Load** (`src/data/load.py::load_long_all`): the package long table (`series_id, timestamp_utc, value, first_usable_origin_utc, ...`) plus external series in the same format:
   - Frank's Fingrid real-time parquet (`src/data/fingrid.py`).
   - Abdo's master external tables via `src/data/external_long.py`. That loader recomputes `fu` as the later of the file value and the documented delay rule. Its pre-June periods (`last_autumn`, `history`) are not loaded by default and no model uses them.
   - Series-id clashes raise.
   - Pre-June history (allowed by the organisers on 7 Nov): models with `use_history` add Abdo's package-format table through `with_history` / `load_history`, which makes every measured row usable no earlier than the package's own rule. Training then also uses every 3rd hourly origin from March 2025.
2. **Index** (`build_index`): one `SeriesIndex` per series. Weather-model runs (ECMWF IFS, ICON-EU from Open-Meteo **Single Runs** only) get a `WeatherIndex` each, where a run is usable at `ceil_hour(init + delay)`.
3. **Features** (`src/features/build.py::build_features`): one row per (origin, step), in column groups:
   - `FEATURE_COLUMNS`: package data. Day-ahead values at delivery, plus the newest usable realised values.
   - `FINGRID_RT_COLUMNS`, `FINGRID_RT2_COLUMNS`, `RT_IMBALANCE_COLUMNS`: Fingrid real-time series, usable 30 min after the quarter (an assumption we made).
   - `WEATHER_COLUMNS` (ECMWF), `WEATHER2_COLUMNS` (ICON-EU), `NORDIC_COLUMNS`, `TOWN_*_COLUMNS`: weather revisions measured against the run that was available when the day-ahead forecast was published. `WINDHAT_COLUMNS`: wind production from a map fitted on data published before the cutoff (`src/models/wind_power.py`).
   - `MEMORY_COLUMNS` (4-hour gap and direction means), `HISTORY_COLUMNS` (`regime_2026` pricing-rule flag).
   - `data_cutoff` is the newest *measured* quarter used, always before the origin.
4. **Models** (`src/models/`):
   - `GBMModel` (LightGBM) fits quantiles on the **gap to spot** (spot is added back afterwards), an up-vs-down classifier (`p_none` is a constant), and spikes as P(direction) × P(tail | direction).
   - Calibration (`gbm.py`) fits Platt maps plus per-step-band quantile offsets on the last `holdout_days` of training (`spike_shrink` shrinks the spike maps when the holdout has few spikes). Pooled rolling holdouts were tried and rejected on fold B.
   - Flags (`use_fingrid`, `use_fingrid2`, `use_rt_imbalance`, `use_weather`, `use_icon`, `use_nordic`, `use_wind_hat`, `use_memory`, `use_history`, ...) select the column groups; `n_seeds` averages several seeds.
   - `HorizonSplit` (`blend.py`) uses a short model for steps 1–8, the only steps that get fresh real-time data, and a long model for the rest. `MedianFrom` takes P50 (and its drivers) from one model and everything else from another.
   - `top_drivers` comes from LightGBM TreeSHAP of the p50 model, never from an LLM.
5. **Write** (`src/backtest/run.py::write_submission`): keeps the template's row order, sorts the quantiles, normalises the probabilities, then runs `validate_submission.py` and `score.py` inside the package folder. `src/backtest/actuals.py` builds score.py actuals for any period; it reproduces the organisers' validation file byte for byte.

**Adding a feature group** touches several places together:
- Compute it in `build_features` through `SeriesIndex` and give it a `*_COLUMNS` list.
- Add it to `GBMModel.features` behind a flag, and to `_mask_fresh` if it's real-time.
- Add `HorizonSplit` and `MedianFrom` properties so `run.py` loads the right data.
- Cover it in the truncation test.
- Give it `DRIVER_LABELS` entries in `src/export/dashboard.py`; `tests/test_driver_labels.py` enforces this.
- Append new groups at the end of `GBMModel.features` (current order: FEATURE, WEATHER, FINGRID_RT, FINGRID_RT2, NORDIC, WEATHER2, WINDHAT, TOWN_SOLAR, TOWN_TEMP, HISTORY, MEMORY, RT_IMBALANCE): LightGBM column sampling depends on the order, so reordering changes old results.

## Repo quirks

- Agent worktrees (`.claude/worktrees/`) have no `.venv`: use the main checkout's interpreter by absolute path. Git-ignored files (`results/`, the dashboard export) are not in a worktree either; copy what you need.
- LightGBM seeds: `GBMModel` passes `random_state=seed` (0 with one seed). Seed noise alone moves September MAE by about 0.2, as much as many feature changes; compare variants on both folds and see `reports/uncertainty.md`.
- Under pandas 3, timestamps may be stored in microseconds. Convert with `src.data.availability.to_ns`; never call `.asi8` directly.
- The whole repo is an **Obsidian vault**. The obsidian-git plugin makes `vault backup` commits, `brainstorm/` holds draft notes, and `.obsidian/workspace.json` changes constantly. Stage files explicitly; don't use `git add -A`.
- `tests/test_code_audit.py` scans `src/` for `.shift(`/`.rolling(` and raw table reads outside `src/data/`; reviewed exceptions are whitelisted there with a reason.
- `experiments/lab/` is a separate harness (scikit-learn HistGradientBoosting, its own `leakcheck`, folds A/B). Its leaderboard numbers are not directly comparable with `src/` results.
- `src/data/external/` (fetchers, need `FINGRID_API_KEY` for Fingrid) and `src/data/fingrid.py` / `open_meteo.py` are two fetcher families. Their processed outputs are committed in `external_data/`, so no download is needed to run backtests.
