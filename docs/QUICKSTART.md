# Quickstart

Verified on a fresh clone of commit `e22354b`, Python 3.14.9, Linux. Python 3.11+ works.

## 1. Clone and install

```bash
git clone --branch femboystorming-pavlo <repo-url> turku && cd turku
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install -r requirements-app.txt     # only for the Streamlit fallback
```

Install takes about 5 minutes. No `.env` is needed for anything below. The starter package and all
external data tables are committed, so nothing is downloaded.

## 2. Run the tests

```bash
OMP_NUM_THREADS=1 .venv/bin/python -m pytest -q -rsf
```

Result on the fresh clone (about 10 min on one thread): 71 tests, 69 passed, 1 skipped, 1 failed.

- Skipped: `tests/test_availability.py:244`. The town weather files are not downloaded. Harmless;
  it needs `python -m src.data.open_meteo --points solar`.
- Failed: `tests/test_code_audit.py::test_no_lags_or_rolling_windows_in_src`. It flags
  `src/data/external/elering_spot.py:30` (`df.start.diff().shift(-1)`). That line sets the end of
  each spot interval in a fetcher, not a feature, so it is a false positive of the audit pattern.
  The fix is to add the line to `ALLOWED_WINDOW_OPS` in `tests/test_code_audit.py` or to rewrite it
  without `.shift`. The leakage truncation tests all pass.

## 3. One backtest (not run while writing this guide)

```bash
.venv/bin/python -m src.backtest.run --period validation --model split_all
```

Takes about 10 min on 4 cores. Trains, forecasts 7 Sep - 4 Oct, writes
`results/split_all/validation/forecast_backtest.csv`, runs the organisers' `validate_submission.py`
and `score.py`, and writes `results/split_all/validation/score/score_summary.md`.
Other periods: `--period fold_b` (August), `--period test` (673 origins). The submitted model is
`v6_hf` (see `MODELS` in `src/backtest/run.py`).

## 4. Dashboard export

```bash
.venv/bin/python -m src.export.dashboard --model split_all --period validation
```

Needs the backtest above first. Writes per-origin JSON to `results/dashboard/<period>/`. It
contains spot prices, so it stays local. `--demo` writes to `app_demo_data/<period>/` with a
synthetic spot price. (Not run here, because it needs backtest output.)

## 5. Streamlit fallback (local only)

```bash
.venv/bin/streamlit run app/streamlit_app.py
```

Verified: starts and serves HTTP 200 on port 8501 (or pass `--server.port`), using the committed
`app_demo_sample/test` data. It uses `results/dashboard/test` if that exists. It shows Nord Pool
spot data, so run it locally only and never deploy it.

## Notes

- Pre-June history (`external_data/history/pkg_history.csv.gz`) is committed here and used by
  `v6_hf`. Licensed spot data is in `starter_package/data/`, so the repo must stay private.
- `--period test` runs write the submission file; all outputs under `results/` are git-ignored.
