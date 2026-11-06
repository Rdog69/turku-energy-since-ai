# Implementation plan

> Working plan for the Turku Energia imbalance price challenge. It's a living document, revised after looking at the starter package (6 Nov) and re-checked against the challenge brief and the training data the same evening. Every claim here is either **checked against the data** (✔ data), **from the official README** (✔ README), or marked as an **assumption** (☐).

## 1. What we are actually forecasting

The target is the **Finnish imbalance price per 15-minute period, 1–40 steps (10 h) ahead**, from every full-hour origin. It works like this (✔ README, ✔ data):

- **Up-regulation:** the price is above spot. In training, the median gap to spot is +25 €/MWh (P10 0, P90 +91).
- **Down-regulation:** the price is below spot. The median gap is −17 €/MWh (P10 −52, P90 −3).
- **No dominating direction:** the price is exactly spot. This happens in only **0.17 %** of training quarter-hours.

So the question is *which side of spot, and how far*, and most of the information about that is **known a day ahead**. See §2.

## 2. What the data told us (training data only, ≤ 4 Oct)

My first pass accidentally included October and November input rows in some monthly statistics. I re-ran everything on training data only and the conclusions below hold. **Rule from here on: exploration and tuning use data up to 4 Oct only.**

| # | Finding | Evidence | Consequence |
|---|---|---|---|
| 1 | **Spot alone beats the baseline by about 33 %.** | Validation MAE: p50 = spot gives 46.5; spot − 7.7 (median gap) gives **44.2**; persistence (≈ baseline) gives 64.8 (official baseline 66.2). | The baseline is weak because it ignores spot. Predicting **the gap to spot** is the right framing, and other teams will probably find this too, so the real competition is beyond it. |
| 2 | **Recent imbalance data is stale, and persistence fades fast.** | The imbalance price becomes usable ~60 min after its quarter ends, so the newest value is 5 quarters before step 1. Even at step 1, the raw "spot + last gap" (MAE 50.8) is *worse* than spot + constant (44.2); averaged over all 40 steps it is 61.8. A **shrunk** version, spot + ½ × last gap + ½ × constant, gets **43.0 at step 1**, so the recent state does help when it's down-weighted. Direction agreement drops from 0.70 at 5 quarters to 0.57 at 44, close to chance (0.54). | Recent state helps only in the first few steps, through features the model can down-weight. **Information known a day ahead dominates.** Fresher real-time data (§4) is a real edge if its delays are honest. |
| 3 | **The day-ahead wind forecast level is the strongest single signal.** | Top wind quintile vs. bottom: mean \|gap\| 13.6 vs 40.0; low-spike share 1 % vs 10 %; up-regulation share 21 % vs 43 %. | The briefing claim that wind matters most is ✔ confirmed, but by **wind level** (known day-ahead), not only by sudden changes. |
| 4 | **Spot ramps drive the gap.** | \|gap\| rises from 18.5 to 50.4 between the lowest and highest quintile of quarter-to-quarter spot change. | Features: spot change across the hour boundary, daily spot shape, spot level. |
| 5 | **Time of day matters.** | Evening peak around 20:00 local (\|gap\| 52.6 vs ~23 at night); morning ramp 06–09. | Hour-of-day features, possibly interacting with wind. |
| 6 | **Neighbours carry little signal about the gap.** | ENTSO-E rows become usable 2.25–3 h after the quarter starts, so the newest value is **9 quarters** before step 1. At an 8-quarter shift, SE1 correlates 0.35 with the FI imbalance *price* (SE3 0.27, EE 0.23), but only **0.10 with the gap** (SE3 0.07, EE 0.06). The price correlation mostly reflects a shared spot level. | Marginal. Include as cheap features and keep only if the ablation shows a gain. |
| 7 | **The consumption error is weak.** | Same-quarter corr(actual − day-ahead consumption, gap) = −0.09, but that isn't known at the origin. At usable delays (≥ 3 quarters) it is −0.03 to −0.06. | Low priority. |
| 8 | **"None" almost never happens.** | 0.17 % of quarter-hours. | `p_none` ≈ a small constant; direction is essentially up vs. down. Drop the mixture-model idea. |
| 9 | **The season shifts.** | September was the most volatile training month (imbalance price std 141). Solar falls ~5× from June to October. Base rates drift too: spike shares are 9.0 % high / 7.3 % low across training but 12.1 % / 13.0 % in validation, and the up-regulation share falls from 35 % overall to 25 % on 1–4 Oct. | Weight recent data more and favour features that don't depend on the season (wind level, spot shape). Calibrate the probabilities on recent data, since the spike and direction scores (30 points) depend on them. |
| 10 | **Spot and the day-ahead forecasts cover the whole horizon.** | Checked at every hourly origin from 2 Jun to 1 Nov: spot and `fi_wind_fc_da` are usable for all 40 steps, with no exceptions. | The "gap to spot" framing never lacks its anchor. No fallback is needed. |
| 11 | **Spikes almost only happen in the matching direction.** | Of ~12,000 training quarters, only 7 high spikes fall outside up-regulation and 18 low spikes outside down-regulation. | Model spikes as P(up) × P(gap > 50 \| up) and P(down) × P(gap < −50 \| down). The probabilities then stay consistent with the direction forecast, and the two spikes automatically sum to ≤ 1. |

**Not in the package:** realised wind production (the package has only *total* production), outages, weather, and Fingrid's hourly-updated forecasts (only the latest version is stored, so using their history would leak).

## 3. Briefing claims, checked

We keep a claim only where it helps the score or the Level 2 demo.

| Claim from the talk | Verdict | Action |
|---|---|---|
| Wind is the main error driver | ✔ Confirmed by data (finding 3) | Wind is the core feature group. |
| Wind is concentrated in Ostrobothnia | ✔ Plausible and cheap to use (public wind farm maps show the west-coast cluster). Not verifiable in the package. | Weight Open-Meteo grid points toward the west coast. We confirm that it helps with an ablation; if not, we use a national average. |
| Rain causes swings | ☐ Weak. Rain barely changes wind output. | **Dropped.** We do add a **turbine-icing proxy** (temperature near 0 °C plus high humidity), a known Finnish winter problem that matters more as the test period moves into November. Kept only if the ablation shows a gain. |
| Decisions are made 1–2 h before gate closure | ✔ A product insight, **not** a scoring rule: `score.py` weights all 40 steps equally. | The model optimises **all** steps equally. Only the dashboard emphasises the next 1–3 h. |
| They want to see the drivers (vendor black box) | ✔ Helps the 20 jury points for the reasoning chain and Level 2. | Explanations are a core feature. |
| Cost reduction is the motivation | ✔ Product framing | Recommendations are framed as "avoid the wrong side". |
| Training data runs 1 Jun – 1 Oct | ✘ The README says **4 Oct** | Use 4 Oct. |
| Winter adds complexity | ✔ Data shows drift (finding 9) | Recency weighting, check results week by week. |

## 4. Data sources: what we can get, and is it worth it?

Every external source needs an **honest publication delay**, which becomes its `first_usable_origin_utc` (rounded up to the next full hour). The delays get documented in `SOURCES.md`. Delays marked ☐ are our own conservative assumptions.

| Source | Access (tested 6 Nov) | What we get | Delay to assume | Value | Decision |
|---|---|---|---|---|---|
| **Starter package** | ✔ | Everything in README §5.2 | per row (binding) | Core | **Use** |
| **Open-Meteo Single Runs** | ✔ Works with no key; Sept and Oct 2026 runs return data (ECMWF IFS, ICON) | Wind at 100 m, 10 m wind, gusts, temperature and humidity, per model run, at chosen points | init + model availability ☐ (ECMWF IFS ~+6–7 h, ICON ~+3–4 h; take the conservative end) | **High**: measures how the *wind forecast has been revised* since the day-ahead forecast | **Use** (priority 1) |
| **Fingrid Open Data API** | ✔ Needs a **free API key** (instant sign-up at data.fingrid.fi); rate limits apply | Real-time **wind**, **nuclear** and **hydro** production and frequency (3-min data; dataset IDs ☐ to confirm, e.g. 181 wind, 188 nuclear, 191 hydro) | ☐ 15–30 min (the package itself uses 30 min for measured data) | **High**: realised wind gives the *current wind forecast error*, and a nuclear drop reveals an outage within minutes. Both are fresher than the package's 60-min imbalance delay. | **Use** (priority 1). ⚠ Never use dataset 245/hourly-updated forecasts: only the latest version is stored. |
| **Nord Pool UMM API** | ✔ Public, no key; historical Finnish messages with `publicationDate` and versions | Planned and unplanned outages: production units (e.g. OL3, wind farms) and transmission (e.g. Fenno-Skan) with MW unavailable | `publicationDate` of each **version** (use the version valid at the origin) | **Medium**: big outages are rare but explain spikes, which is good for the dashboard's "why" view | **Use** (priority 2) |
| **FMI open data** | ✔ WFS, no key | Weather station observations (wind, temperature), e.g. Vaasa | ☐ ~10–20 min | Low–medium: overlaps with Fingrid realised wind | Optional |
| **ENTSO-E API** | ✘ The token takes "several working days" | Outages 10.1, more areas | – | Covered by UMM | **Skip** |
| **News, gas or oil prices, sentiment** | – | Price level effects over days to weeks | – | Spot already covers it; leak risk | **Skip** (as concluded earlier) |

**Fallbacks:** if Open-Meteo or Fingrid fail or eat too much time, the model still works on the package alone (finding 1 already beats the baseline).

## 5. Level 1: model

### Availability layer (build first)

`available_at(df, t)` filters to rows with `first_usable_origin_utc ≤ t`, for package and external rows alike. A unit test asserts this for every origin. Leakage means a score of 0, and the code review may use AI.

### Features per (origin `t`, step `k`)

- **Known day-ahead:** spot at the delivery quarter, spot change across the hour boundary and daily shape; day-ahead wind, consumption and solar at delivery (plus wind as a share of consumption); FI–EE capacity; hour, weekday, holiday, DST; step `k`.
- **Recent state (decays with `k`):** the last usable gap (5 quarters before step 1), direction and mFRR volumes, with lags and rolling statistics; last neighbour imbalance prices (SE1, SE3, EE; 9 quarters before step 1); last flows and consumption error (3 quarters before step 1). All lags come from `available_at()`, never from fixed shifts.
- **External:**
  - Wind revision: latest available Open-Meteo run minus the earlier run the day-ahead forecast was based on, at weighted west-coast points.
  - Current wind error: Fingrid realised wind minus day-ahead wind.
  - Nuclear MW change (Fingrid real-time).
  - Active outage MW (UMM).
  - Icing proxy.

### Models

- **Price:** LightGBM quantile regression on `y = imbalance − spot` for q = 0.1, 0.5 and 0.9, with step as a feature. Add spot back, then sort the quantiles. Simple anchors to beat: spot − 7.7 (MAE 44.2), and at short steps the shrunk last gap (43.0 at step 1).
- **Direction:** binary LightGBM for up vs. down, then calibration; `p_none` = the small training share (~0.002).
- **Spikes:** conditional tail models, P(gap > 50 \| up) and P(gap < −50 \| down), multiplied by the direction probabilities (finding 11). This keeps the outputs consistent and the spike sum ≤ 1. Compare against two independent binary spike models and keep whichever scores the better Brier.
- **Calibration:** conformal or quantile adjustment of P10 and P90 per step band to reach ~80 % coverage.
- **Season shift:** recency weights; retrain on everything up to 4 Oct for the test run.

### Optional output columns

They aren't scored, but the brief lists both as Level 1 outputs and they cost little:

- `data_cutoff_utc`: the latest `timestamp_utc` among the rows actually used at the origin (always ≤ origin).
- `top_drivers`: the top 3 feature names by |SHAP| for the row, semicolon-separated as the schema shows (e.g. `wind_fc_da;spot_ramp;last_gap`). This comes straight from SHAP. The LLM never writes this column.

### Evaluation

- Train on data up to 6 Sep, validate on 7 Sep – 4 Oct with `score.py`; also check week by week.
- **Ablations** for the report: spot only → + day-ahead features → + recent state → + Open-Meteo → + Fingrid real-time → + UMM. This produces the reasoning chain the jury scores.

## 6. Level 2: situational view

**Users:** the three-person purchasing team and the production manager at Naantali. The top of the screen covers the next 1–3 h ("what should I check now?"); the full 10 h sits below it.

All forecasts are precomputed, so the time-travel slider just moves over forecast origins.

1. **Next 10 h:** fan chart (P10–P90, P50, spot), up/down probability strip, spike-risk heatmap.
2. **What changed:** difference from the previous origin, plus alerts when spike risk or P50 shifts.
3. **Drivers ("why"):** SHAP per quarter-hour, explained in plain language by an LLM, e.g. "wind on the west coast revised −400 MW since the day-ahead forecast; evening spot ramp".
4. **Track record:** MAE vs. the baseline by day and week, coverage, calibration chart.
5. **Suggestions to review:** "check this situation" prompts tied to the levers the company named (the Naantali production plan, electric boilers or heat pumps, the trading position, mFRR offers), with the expected gap to spot and the model's confidence. The brief asks for **suggestions to review, not instructions**: open data can't tell us the available capacity, marginal costs, ramp rates, heat or contract constraints, or capacity already committed elsewhere. So the wording is "check the Naantali plan for 16–18", never "produce more". Real capacity recommendations are the natural next step once internal plant data is available, which is a good point for the pitch.
6. **Conflicting signals:** a flag when sources or models disagree, one of the brief's example situations. Examples: the direction model says up but P50 is below spot; the Open-Meteo wind revision points the other way from the Fingrid day-ahead wind; P10–P90 is unusually wide for the hour. Each flag says "worth an expert look".
7. **Outage feed:** UMM events on the timeline.

**API:** the brief asks for "an API from which this information can be retrieved for display". A small FastAPI app (or static JSON per origin) serves the forecast, alerts and drivers for a given origin, and the dashboard reads from it.

**Stack:** Streamlit + Plotly + FastAPI, running locally. The Nord Pool data must not be deployed publicly.

## 7. Event tools and how we use them

| Tool | Use | Priority |
|---|---|---|
| **Featherless.ai** (OpenAI-compatible API, open-weight models) | LLM for the plain-language explanations in the dashboard and the dashboard chat ("what should I check now?"). Not for the `top_drivers` column, which comes from SHAP. | High |
| **LUMI AI Factory / Aitta** (CSC) | Backup LLM inference (needs pre-registration); GPU compute isn't needed, since LightGBM trains in seconds | Low |
| **n8n** | Alert workflow: when a new forecast shows a spike-risk jump, post to Discord or Teams. Good demo of "alerts". | Medium |
| **ElevenLabs** | Spoken 20-second shift briefing generated from the LLM text, for the demo video | Low (nice to have) |
| **Lovable** | Not needed if Streamlit does the job; keep as an option for a polished frontend | Low |
| **Red Hat OpenShift AI award** | Optional extra prize; only if it's cheap to enter | Low |

LLM output stays **downstream** of the forecast (text only), so it can't leak data or change the scores.

## 8. Repository structure

```
src/
  data/        load package, available_at(), fetchers: open_meteo.py, fingrid.py, umm.py
  features/    build_features(origin) → one row per step
  models/      train / predict / calibrate
  backtest/    loop over origins → forecast_backtest.csv, validation file
  explain/     SHAP + LLM text
api/           FastAPI: forecast, alerts and drivers per origin
app/           Streamlit dashboard (reads from api/)
automation/    n8n workflow export
tests/         leakage test, format test
reports/       evaluation report, slides
starter_package/  (git-ignored)
```

## 9. Timeline

| When | Goal | Done when |
|---|---|---|
| Fri night | `available_at()` + leakage test; reproduce the baseline; spot-anchor model; **Fingrid key**; start the Open-Meteo download | Validation MAE ≈ 44 with `score.py` |
| Sat morning | LightGBM v1 (package features), calibration, SHAP-based `top_drivers` and `data_cutoff_utc` | Beats the baseline on all 4 metrics |
| Sat midday | External features (Open-Meteo, Fingrid, UMM) + ablations | Ablation table |
| Sat afternoon (parallel) | API + dashboard on validation forecasts | Panels 1–6 with time travel |
| Sat evening | LLM explanations (Featherless), n8n alert, report draft | Plain-language "why" text in the dashboard |
| Sun 06–09 | Final retrain, test backtest, validator, slides, video | `VALIDATION PASSED` |
| **Sun 10:00** | **Submit** | |

## 10. Roles

| Area | Owner |
|---|---|
| Data, availability layer, external fetchers | TBD |
| Models, calibration, backtest | TBD |
| Dashboard + n8n | TBD |
| LLM, report, slides, video | TBD |

## 11. Open questions

- [ ] Ask in `#turku-energia`: are Fingrid real-time 3-min series acceptable with our own documented publication delay?
- [ ] Ask in `#turku-energia`: is the Nord Pool UMM API allowed? (It's public, but it's Nord Pool.)
- [ ] Ask in `#turku-energia`: during the test backtest, may we correct bias or recalibrate using test-period imbalance prices that are already usable at the origin (`first_usable_origin_utc ≤ t`)? The data rule allows it, but "train only on data up to 4 Oct" may not. This could be a real gain given the drift in finding 9, so ask before relying on it.
- [ ] Confirm the Fingrid dataset IDs once we have the key.
- [ ] Open-Meteo: decide publication delays per model; confirm the archive covers 1 Jun – 2 Nov for the chosen models.
- [ ] Featherless API key: does the event provide one?
- [ ] The package README suggests a short path on Windows (OneDrive paths can exceed 260 characters). Move the checkout if scripts fail.
