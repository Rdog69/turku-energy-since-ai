# Implementation plan

> Working plan for the Turku Energia imbalance price challenge. Living document: update it when decisions change.

## 1. What we are actually forecasting

The target is the **Finnish imbalance price per 15-minute period, 1–40 steps (10 h) ahead**. We don't forecast "the energy market" as a whole.

That price is:

- **spot** (the day-ahead price, already known at the forecast origin), **plus**
- a jump up or down when the system is short (up-regulation) or long (down-regulation), **or**
- **exactly spot** when there is no dominating mFRR direction.

So the real question is: *in which direction will Finland's plans be wrong in the next 10 hours, and by how much?*

- A factor that changes the **deviation between plans and reality** is relevant.
- A factor that only changes the **general price level** is already captured by spot.

## 2. Candidate factors

| Factor | Verdict | Reasoning |
|---|---|---|
| Wind and solar weather forecasts | ✅ **Top priority** | Wind forecast error is the main imbalance driver in Finland. What we want is the *revision*: the newest weather model run vs. the day-ahead wind forecast (Fingrid dataset 246) the market planned on. |
| Current forecast errors (actual − day-ahead forecast) | ✅ Top priority | Wind, consumption and solar errors persist for hours. All of these are already in the package. |
| Recent imbalance price and mFRR direction | ✅ Top priority | Short-horizon persistence is strong, and it's what the baseline exploits. |
| Neighbours (SE1, SE3, EE imbalance prices, cross-border flows, FI–EE capacity) | ✅ High | This is the physical form of "Nordic relations", and it's in the package. |
| Unplanned outages (REMIT UMM: nuclear such as OL3 at 1.6 GW, interconnectors such as Estlink and Fenno-Skan) | ✅ High, **with risk** | This is "news analysis" done right: structured events with publication timestamps. We still need to verify that historical publication times can be retrieved. |
| Spot level, ramps and hour boundaries | ✅ Medium | Large changes in spot from one hour to the next cause imbalance around the hour change. Spot is known day-ahead. |
| Calendar (hour, weekday, holidays, DST, step) | ✅ Medium | Cheap to add. |
| Gas, CO₂ and oil prices; stock and headline sentiment | ❌ Skip | They move spot over days to weeks, and spot is already an input. They add almost nothing at a 10 h horizon, and they carry a leakage risk (score 0). |
| Turku Energia's own plants | ❌ For the forecast, ✅ for Level 2 | Turku Energia produces only about a quarter of the electricity it sells, so its plants don't move the national price. Its **flexible assets** (Naantali CHP share, heat pumps, hydro shares) are what the recommendations should be about. |

## 3. Data inputs

### From the starter package

- **Fingrid:** imbalance price (target), mFRR and aFRR, consumption, production, cross-border flows
- **Fingrid day-ahead forecasts:** 165 (consumption), 246 (wind), 247 (solar)
- **ENTSO-E:** SE1/SE3/EE imbalance prices and load forecasts, FI–EE transfer capacity
- **Nord Pool:** spot price (⚠️ licensed, never commit it or deploy it publicly)
- **Calendar features**

Every row carries `first_usable_origin_utc`. **At origin `t`, use a row only if `first_usable_origin_utc ≤ t`.**

### External, to verify early

| Source | Use | Availability handling | Status |
|---|---|---|---|
| Open-Meteo **Single Runs API** | Wind speed at ~100 m and solar radiation at Finnish wind and solar locations, per model run | A run initialised at time `R` is usable from `R + ~5 h` (00 UTC runs appear around 04–06 UTC). Pick a conservative fixed delay per model. Archive: ECMWF IFS from Mar 2024, other models from Sep 2025. | ☐ test API, ☐ check retention |
| Nord Pool **REMIT UMM** API (free, Developer Hub) / ENTSO-E unavailability data | Unplanned outages, as MW unavailable per asset type | Use each notice's **publication timestamp** as its availability time | ☐ check historical access |
| Wind farm locations (e.g. Finnish Wind Power Association data, OpenStreetMap) | Weights for aggregating weather to national wind output | Static data, no leakage | ☐ |

**Not allowed:** the Open-Meteo Historical Forecast API, because it leaks future information.

## 4. Level 1: model

### Availability layer (build first)

`available_at(df, t)` filters rows to `first_usable_origin_utc ≤ t`.

- **Every** feature goes through it, including external sources once they have a computed `first_usable_origin_utc`.
- A unit test checks for every origin that no feature uses a row with `first_usable_origin_utc > t`.
- The organisers check the top solutions' code for leakage, possibly with AI, and leakage scores 0.

### Features per (origin `t`, step `k`)

- Latest usable imbalance price, imbalance − spot, mFRR direction, mFRR and aFRR volumes; lags and rolling statistics
- Latest wind, consumption and solar error (actual − day-ahead forecast), plus their recent trend
- Spot at the delivery quarter-hour, spot change across the hour boundary, daily spot shape
- Day-ahead wind, consumption and solar forecasts at the delivery quarter-hour
- Neighbour imbalance prices, flows, transfer capacity
- Wind revision: latest available Open-Meteo run vs. Fingrid's day-ahead wind forecast for the delivery quarter-hour
- Outage MW active at the delivery quarter-hour, as known at `t`
- Step `k`, hour of delivery, weekday, holiday flag, DST flag

### Models

- **Price:** LightGBM quantile regression on `y = imbalance − spot`, one global model with step as a feature, separate models for q = 0.1, 0.5 and 0.9. Add spot back to get the price forecast, then sort the three quantiles so P10 ≤ P50 ≤ P90.
- **Direction:** LightGBM multiclass (up / down / none), then calibration (temperature scaling or isotonic).
- **Spikes:** binary models for `> spot + 50` and `< spot − 50`, calibrated and kept coherent with direction (a high spike implies up). Clip so `p_spike_high + p_spike_low ≤ 1`.
- **Interval calibration:** conformal adjustment of P10 and P90 per step band on the validation period, targeting 80 % coverage. The baseline reaches 0.68.
- **Structure to exploit:** when there is no dominating direction, the price equals spot. Try modelling the price as a mixture of "exactly spot" and two tails as an alternative P50.

### Evaluation

- Train on 1 Jun – 6 Sep and validate on 7 Sep – 4 Oct with `score.py` against the baseline.
- For the test run, retrain on 1 Jun – 4 Oct.
- Baseline (validation): MAE 66.20, pinball loss 24.18, coverage 0.68, Brier (spikes) 0.1132, Brier (direction) 0.4509.
- Track per-step MAE so the report can show where we beat persistence.

## 5. Level 2: situational view

**Precompute all forecasts** (validation and test origins) into parquet files. The dashboard only reads files, so "time travel" is just a slider over forecast origins.

Panels:

1. **Next 10 h:** fan chart of P10/P50/P90 with the spot line, a direction strip (up/down/none probabilities), and a spike-risk heatmap.
2. **What changed:** difference from the previous origin's forecast for the same quarter-hours, with alerts when spike risk or P50 moves beyond set thresholds.
3. **Drivers:** the main factors behind the forecast (SHAP per quarter-hour or per block) and a plain-language explanation.
4. **Track record:** MAE vs. the baseline by day and week, interval coverage, calibration charts, and actual vs. forecast for the selected past window.
5. **Recommendations:** rule-based suggestions tied to Turku Energia's flexibility, with an LLM writing the justification text. Examples:
   - "High up-regulation risk 16–18 h: check the market position; consider shifting heat-pump load or raising CHP output; consider offering mFRR capacity."
   - "Low-price risk overnight: consider extra heat-pump or electric-boiler load."

**Stack:** Streamlit + Plotly in Python, so it shares code with the model. Run it locally or privately only, because of the Nord Pool licence.

## 6. Where an LLM fits

- **Explanations:** turn SHAP drivers plus forecast changes into `top_drivers` text and short briefings in the style of the jury's example.
- **Outage parsing:** turn the free text of REMIT notices into structured records (asset, MW, start, end, published at).
- **Dashboard chat:** answers "What should I check now?" and "What is coming in the next 10 hours?" from the precomputed forecast.
- **Provider:** Featherless.ai or LUMI Aitta (both event partners), or another API. We record every model and licence in `SOURCES.md`.
- **Optional event-partner extras:**
  - n8n workflow that pushes alerts to Discord or Teams
  - ElevenLabs spoken shift briefing for the demo video
  - Red Hat OpenShift AI award, if it's easy to enter

## 7. Repository structure

```
src/
  data/        load package, available_at(), external fetchers (open-meteo, umm)
  features/    build_features(origin) → one row per step
  models/      train / predict / calibrate
  backtest/    loop over origins → forecast_backtest.csv, validation file
  explain/     SHAP + LLM text generation
app/           Streamlit dashboard
tests/         leakage test, output format test
reports/       evaluation report, slides
docs/          this plan
starter_package/  (git-ignored)
```

## 8. Timeline

| When | Goal | Done when |
|---|---|---|
| Fri night | Load data, `available_at()`, leakage test, reproduce baseline score | `score.py` matches the baseline numbers |
| Sat morning | Features v1 + LightGBM v1 on validation | Beats the baseline on all 4 metrics |
| Sat 12–15 | Calibration, wind revision and outage features (if the data works) | Coverage ≈ 0.80; ablation table for the report |
| Sat afternoon (parallel) | Dashboard on validation forecasts | All 5 panels working with time travel |
| Sat evening | LLM explanations, recommendations, evaluation report draft | `top_drivers` filled in |
| Sun 06–09 | Final retrain, test-period backtest, validator, slides, video (≤ 5 min) | `VALIDATION PASSED` |
| **Sun 10:00** | **Submit via the Since AI app** | |

## 9. Roles (suggested)

| Area | Owner |
|---|---|
| Data, availability layer, external sources | TBD |
| Models, calibration, backtest | TBD |
| Dashboard | TBD |
| LLM, report, slides, video | TBD |

## 10. Open questions

- [ ] Can historical REMIT UMM notices be retrieved with publication times for Jun–Nov 2026? (ask in `#turku-energia`)
- [ ] Open-Meteo Single Runs retention: are Sep–Nov 2026 runs still available?
- [ ] Python 3.11+ on all laptops (the package requires it)
- [ ] Is an LLM API key from an event partner available, or do we bring our own?
