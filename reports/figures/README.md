# Figures

Made by `python reports/figures/make_figures.py` from the repo root (~40 s). Figures 1–2 use **training data only** (deliveries before 7 Sep 2026) and show the gap to spot, never spot levels (licensed). Figure 3 needs `results/split_all/validation/score/score_by_horizon.csv` from a validation backtest.

| File | Caption |
|---|---|
| `gap_by_wind_quintile.png` | Low day-ahead wind: the imbalance price jumps further from spot, and up-regulation is more frequent (42–45 % vs 26 % at high wind). |
| `gap_by_local_hour.png` | Jumps are largest in the evening peak (21–23 local) and in the morning ramp. |
| `error_by_horizon.png` | split_all on validation: error grows with the forecast hour; the P10–P90 band stays near the 80 % target at every hour. |
| `reliability_split_all.png` | Reliability diagram of split_all on validation (forecast vs realised frequency). Not made by `make_figures.py`; it comes from the calibration check, see `reports/calibration_check.md`. |
| `ladder.png` | The September (validation) ladder from the organisers' baseline to the submitted model: MAE 66.20 to 40.67, mean pinball 24.18 to 11.19 (numbers from `docs/RESULTS.md`, table in `make_figures.py`). |
