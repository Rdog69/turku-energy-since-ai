# Figures

Made by `python reports/figures/make_figures.py` from the repo root (~40 s). Figures 1–2 use **training data only** (deliveries before 7 Sep 2026) and show the gap to spot, never spot levels (licensed). Figure 3 needs `results/split_all/validation/score/score_by_horizon.csv` from a validation backtest.

| File | Caption |
|---|---|
| `gap_by_wind_quintile.png` | Low day-ahead wind: the imbalance price jumps further from spot, and up-regulation is more frequent (42–45 % vs 26 % at high wind). |
| `gap_by_local_hour.png` | Jumps are largest in the evening peak (21–23 local) and in the morning ramp. |
| `error_by_horizon.png` | split_all on validation: error grows with the forecast hour; the P10–P90 band stays near the 80 % target at every hour. |
