# Situational view (Level 2)

**Built:** branch `front-end`, folder `frontend/` ("Tasehinta"), commit `19d667c`. It shows the submitted model: the same files as `forecast/forecast_backtest.csv`, plus its two members for the "models disagree" alert. Replay periods: September, August and the forecast period.

- **Views:**
  - **Simple:** status badge, 10-hour traffic light (15 min or 1 h), plain glossary, track record.
  - **Trader:** fan chart with direction and spike-risk strips; "Worth checking" with icons and drivers; details on demand.
  - **Production:** balancing need and flexibility checks.
- **Time travel:** a slider over every forecast hour, Play, arrow keys. Every view shows only data published by the review time.
- **Hindsight:** median error against the day-ahead price, band coverage, flagged high-price quarters, direction hits; zoomable chart.
- **English and Finnish**, keyboard accessible.

Run (from the `front-end` branch):

```bash
python frontend/scripts/build_data.py          # local data, git-ignored (licensed spot prices)
cd frontend && pnpm install && pnpm build && cd dist && python3 -m http.server 8080
```

The page shows only what was published by the moment you are looking at. Scrolling moves through time in 15-minute steps, and the strip under the graph shows where you are in the whole period.
