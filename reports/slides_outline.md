# Slides outline (7 slides)

Numbers are fold A (validation 7 Sep - 4 Oct, 672 origins) unless stated. Figure files marked (S5) come from side job S5 and may not exist yet; fall back to the table named next to them. The pipeline model is `v6_hf` (numbers from `docs/RESULTS.md`). TODO(team): v6_hf or team5050 — which file is submitted.

## 1. The problem and what we built
- **Visual status:** missing. A dashboard screenshot needs `python -m src.export.dashboard --model <model> --period validation` (after a backtest of that model), then `streamlit run app/streamlit_app.py` and a screenshot. It shows spot as a line, so check the licence note in `reports/demo_script.md` first. `app_demo_sample/test` exists as sample data.
- **Message:** Imbalance prices jump away from spot in 15-minute blocks; we forecast the next 10 h with an honest uncertainty band, and show a trader what to check now.
- **Visual:** one screenshot of the dashboard fan chart (P10/P50/P90 + spot) with the spike strip below.
- **Notes:** Level 1 is the forecast (80 %), Level 2 the situational view (20 %). Say "review, never do": suggestions only.

## 2. Our framing: forecast the gap to spot
- **Visual status:** exists as a table in `docs/RESULTS.md` (rows `Organisers' baseline` and `spot_anchor`: MAE 66.20 and 44.29). No image file; build the slide table from those two rows.
- **Message:** Spot is known for all 40 steps, so we forecast the gap (imbalance - spot). This one choice removes a third of the baseline error.
- **Visual:** table baseline vs spot anchor (RESULTS.md rows 1-2): MAE 66.20 -> 44.29.
- **Notes:** Everything the day-ahead market already knew is priced in; the gap is what the plan missed in Finland. Do not show spot price levels.

## 3. What drives the gap
- **Visual status:** exists. `reports/figures/gap_by_wind_quintile.png` and `reports/figures/gap_by_local_hour.png` (made by `python reports/figures/make_figures.py`, training data only). The factor table is in `reports/evaluation_report.md` section 3.
- **Message:** Low wind forecast, spot ramps and the evening peak are where large gaps live.
- **Visual:** (S5) gap by day-ahead wind quintile and by local hour, training data only. Fallback: the factor table in `reports/evaluation_report.md` section 3.
- **Notes:** Top vs bottom wind quintile mean |gap| 40.0 vs 13.6; evening 20:00 |gap| 52.6 vs about 23 at night.

## 4. Rule-proof data: the availability rule
- **Visual status:** exists. `reports/figures/availability_timeline.png` (worked example at the 12:00 origin, made by `reports/figures/make_availability_timeline.py`); the delays table is in `reports/evaluation_report.md` section 2 and `SOURCES.md`.
- **Message:** Every row is used only when it was actually published; this is tested, not promised.
- **Visual:** small diagram: row with `first_usable_origin_utc`, origin t, truncation test (delete future rows, features identical). Table of delays: Fingrid RT +30 min, ECMWF +8 h, ICON-EU +5 h.
- **Notes:** Open-Meteo Single Runs API only, never the Historical Forecast API (it leaks). Mention the DST test around 25 Oct.

## 5. The reasoning chain: what each step added
- **Visual status:** exists. `reports/figures/ladder.png` (baseline 66.20 to `v6_hf` 40.67 MAE, pinball 24.18 to 11.19); the full step table is in `reports/evaluation_report.md` section 5 and `docs/RESULTS.md`.
- **Message:** Calibration, fresh data only where fresh, and weather each earned their place; we kept a source only if validation improved.
- **Visual:** the step table in `reports/evaluation_report.md` section 5 (MAE, pinball, coverage, two Briers) with the `split_all` and `split_all_icon` rows highlighted, then Frank's rows down to `v6_hf` (MAE 40.67, pinball 11.19, spikes 0.0856, direction 0.3892).
- **Notes:** Calibration took coverage 0.53 -> 0.80. Real-time data helps hour 1 (direction 0.408 -> 0.342) but is noise by hour 3, hence the horizon split. ICON-EU adds a small gain: MAE 42.53 -> 42.14, direction 0.4011 -> 0.3995 (our `split_all_icon`; Frank ported it into `v3_bmi`). Later steps: smaller, slower trees and 4-hour memory (41.68), learned wind production (41.08), 15 months of pre-June history with the `regime_2026` flag (`v6_hf`, 40.67; pinball 11.88 -> 11.19).

## 6. Results against the baseline, and honesty about them
- **Visual status:** partly. `reports/figures/error_by_horizon.png` exists but shows `split_all`, not `v6_hf`; it comes from `results/split_all/validation/score/score_by_horizon.csv` via `reports/figures/make_figures.py`. A `v6_hf` version is missing: it needs `python -m src.backtest.run --period validation --model v6_hf` first. `reports/figures/reliability_split_all.png` also exists (`split_all`). The baseline vs `v6_hf` table for both folds exists in `reports/evaluation_report.md` section 6.
- **Message:** `v6_hf`: MAE -39 %, pinball -54 %, spike Brier -24 %, direction Brier -14 % vs persistence (35.7 % better weighted by points in September, 26.0 % in August). `team5050` (Abdo) leads the team scoreboard: 31.1 % average against 30.9 % for `v6_hf`.
- **Visual:** (S5) validation error by horizon from `score/score_by_horizon.csv`; table baseline vs `v6_hf` (and `team5050`) for fold A and fold B (August: MAE 27.74, pinball 6.59, spikes 0.0680, direction 0.4388). Our own `split_all_rt_icon` (42.14 / 12.06 / 0.0922 / 0.3978) is only an ablation row.
- **Notes:** We picked among about 37 variants on one window, so numbers are optimistic; fold B is the check. Limitation: the real-time delay (30 min) is our assumption.

## 7. The situational view and next steps
- **Visual status:** missing. Same as slide 1: a screenshot of the dashboard with alert, "why" sentence and track-record panel, from `src.export.dashboard` output shown in `app/streamlit_app.py`. The track-record data comes from `track_record.json` in that export.
- **Message:** The dashboard turns the forecast into three answers: anything unusual in 1-3 h, why, and what to review.
- **Visual:** dashboard screenshot with alert, "why" sentence and track-record panel.
- **Notes:** Explanations come from SHAP drivers in a fixed template; an LLM only rewords downstream and is cached. Alerts tuned to about 1-3 per day. Next: outage messages, real-time and weather data for the pre-June rows, and plant data.
