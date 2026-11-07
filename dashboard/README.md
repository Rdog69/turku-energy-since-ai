# Situational view (Level 2)

**Built:** branch `front-end`, folder `frontend/` ("Tasehinta"), commit `19d667c`. It shows the submitted model: the same files as `forecast/forecast_backtest.csv`, plus its two members for the "models disagree" alert. Replay periods: September, August and the forecast period.

- **Overview** (the main page):
  - a headline for the next 10 hours;
  - "Worth checking" chips that open a side panel with the window, the probability, the drivers and what to check;
  - one chart on one time axis: the realised price, the forecast with its likely range, the day-ahead price, a price-risk row and the balancing need (grid short or surplus) quarter by quarter;
  - click any quarter for its detail;
  - the factors that move the forecast;
  - quarter tables and hindsight on demand.
- **Production:** the balancing need hour by hour, and where flexibility could pay (CHP, electric boilers).
- **Time travel:** scroll or drag the chart in 15-minute steps, Play, or use the period strip under the graph. It shows the whole period with a window marking what the chart shows.
- **English and Finnish**, keyboard accessible.

Run (from the `front-end` branch):

```bash
python frontend/scripts/build_data.py          # local data, git-ignored (licensed spot prices)
cd frontend && pnpm install && pnpm build && cd dist && python3 -m http.server 8080
```

The page shows only what was published by the moment you are looking at. Scrolling moves through time in 15-minute steps, and the strip under the graph shows where you are in the whole period.
