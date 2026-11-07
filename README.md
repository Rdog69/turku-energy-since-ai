# Turku Energia × Since AI 2026: Imbalance Price Forecast

> We forecast the Finnish power system imbalance price 10 hours ahead, give it a calibrated uncertainty band, and build a situational view that tells a shift supervisor or trader **what to check now** and **what's coming**.

Built at the **Since AI 2026** hackathon in Turku, 6–8 Nov 2026, for the **Turku Energia** challenge.

📋 **Implementation plan:** [`docs/PLAN.md`](docs/PLAN.md) covers which factors matter, the data inputs, the model, the dashboard and the timeline.

🧒 **Short version:** [`docs/TLDR.md`](docs/TLDR.md) explains the whole thing in two minutes.

---

## Contents

- [The problem](#the-problem)
- [The challenge](#the-challenge)
- [Data](#data)
- [The data availability rule](#the-data-availability-rule)
- [Output format](#output-format)
- [Scoring](#scoring)
- [Baseline to beat](#baseline-to-beat)
- [Getting started](#getting-started)
- [Repository layout](#repository-layout)
- [Deliverables checklist](#deliverables-checklist)
- [Timeline](#timeline)
- [Rules and licensing](#rules-and-licensing)
- [Team](#team)

---

## The problem

Production and consumption have to match at every moment. When a market party's plan and its actual production or consumption differ, the difference is an **imbalance**, and it gets settled at the **imbalance price**.

- The price is set separately for every **15-minute** period.
- The dominating direction comes from **mFRR** (manually activated reserve):
  - **Up-regulation**: the price is above spot.
  - **Down-regulation**: the price is below spot.
  - **No dominating direction**: the price follows the day-ahead spot price.
- Since **1 June 2026**, when both mFRR and **aFRR** are in the dominating direction, the price is the volume-weighted average of their energy prices.
- More wind and solar on the grid means balancing needs, and therefore prices, change faster.

Turku Energia plans purchases, trading, and the use of its production and flexible capacity from market forecasts. Seeing price spikes earlier means less imbalance cost and better-timed decisions.

## The challenge

### Level 1: the forecast (80 % of the total)

From **every full-hour forecast origin**, forecast the next **10 hours = 40 quarter-hours**:

| What | Columns | Meaning |
|---|---|---|
| Imbalance price | `p10`, `p50`, `p90` | Median forecast and an 80 % interval (€/MWh) |
| Direction of the balancing need | `p_up`, `p_down`, `p_none` | Probabilities of the dominating mFRR direction (they sum to 1) |
| Exceptional prices | `p_spike_high`, `p_spike_low` | P(price > spot + 50 €/MWh) and P(price < spot − 50 €/MWh) (they sum to ≤ 1) |
| *Optional, not scored* | `data_cutoff_utc`, `top_drivers` | Data freshness and the main drivers of the forecast |

### Level 2: the situational view (20 % of the total)

A UI for an energy expert that the jury judges on:

- Clarity and usability for a shift supervisor or electricity trading specialist
- Two time spans: **right now / next 10 h**, and **past performance** (previous day, week, month)
- **Time travel**: move the viewing time into the past to show the forecast's usefulness over time
- Inventiveness: insights that give experts new information

Extra credit:

- Alerts when the balancing need or the price forecast changes significantly
- Justified suggestions for when Turku Energia should review trading, the production plan, or capacity use

> *Example:* "The risk of an exceptionally high price has increased for 16:00–18:00. The forecast is driven mainly by a lower wind power forecast, higher consumption and the cross-border flow situation. Uncertainty is high, so the production plan and market position should be checked."

### Why we forecast the past (backtest)

Future forecasts can't be scored during the weekend, so we forecast the test period **as if it were then**:

| Period | Dates (2026) | Use |
|---|---|---|
| Training | 1 Jun – 4 Oct | Model fitting |
| ↳ Validation | 7 Sep – 4 Oct | Part of training, used for our own scoring |
| **Test** | **5 Oct – 1 Nov** | **673 forecast origins**, scored by the organisers |

The 673 origins run from `2026-10-04T21:00:00Z` to `2026-11-01T21:00:00Z`. **All timestamps are UTC.**

## Data

All of it ships in the organisers' starter package at 15-minute resolution from 1 June 2026:

| Source | Content |
|---|---|
| **Fingrid** | Imbalance price (the target), mFRR and aFRR, consumption, production, cross-border flows |
| **Fingrid forecasts** (datasets 165, 246, 247) | Day-ahead consumption, wind and solar forecasts (the weather signal) |
| **ENTSO-E** | Imbalance prices and load forecasts for SE1, SE3 and EE; FI–EE transfer capacity |
| **Nord Pool** | Day-ahead spot price (⚠️ licensed, see [Rules](#rules-and-licensing)) |
| **Calendar** | Weekday, hour, holidays, DST |

The data is in long format, one row per series per quarter-hour:

```
series_id, source, dataset_id, timestamp_utc, value, unit, first_usable_origin_utc
```

Other open or paid data is allowed if we list it and handle its licence. For weather, use the **Open-Meteo Single Runs API**. The Historical Forecast API is not recommended because it leaks future information.

## The data availability rule

> **At forecast origin `t`, use a row only if `first_usable_origin_utc ≤ t`.**

Breaking this rule gets an **automatic score of 0**. The organisers check the source code of the top solutions for leakage, possibly with AI.

Example: the 09:00–09:15 UTC quarter-hour is published at 10:15 UTC (+60 min), so it's first usable at the 11:00 UTC origin.

Use `rows_available_at()` from `baseline.ipynb` for **every** feature lookup, and treat any feature that skips it as a bug.

## Output format

Submit one file, `forecast_backtest.csv`, with **673 origins × 40 steps = 26,920 rows and 13 columns**:

```
forecast_origin_utc, delivery_start_utc, step,
p10, p50, p90,
p_up, p_down, p_none,
p_spike_high, p_spike_low,
data_cutoff_utc, top_drivers
```

Constraints:

- `step` runs 1–40, and step 1 starts at the forecast origin.
- `p10 ≤ p50 ≤ p90`
- `p_up + p_down + p_none = 1`
- `p_spike_high + p_spike_low ≤ 1`

Start from `sample_submission.csv` and keep its identifier columns and row order as they are. Then validate the file:

```bash
python validate_submission.py --backtest forecast_backtest.csv --origins forecast_origins.csv
```

A file that fails validation scores **0**, and nothing can be fixed after the deadline.

## Scoring

**Total = 80 % Level 1 + 20 % Level 2**

| Level 1 component | Points | Metric | Scored by |
|---|---:|---|---|
| Forecast accuracy | 30 | MAE of P50 (€/MWh) | `score.py` |
| Uncertainty calibration | 20 | Mean pinball loss of P10 and P90 | `score.py` |
| Exceptional prices | 20 | Brier score of the spike probabilities | `score.py` |
| Direction of the balancing need | 10 | Brier score of the direction probabilities | `score.py` |
| Reasoning chain | 20 | Evaluation report, slides, demo | Jury (0–5 in half-point steps) |

For each automatic metric, matching the baseline (or doing worse) gets **0 points** and the best accepted submission gets **full points**. Everyone else gets the share of the gap they close. For example, baseline MAE 60, best 30, ours 40 means we close 2/3 of the gap, which is worth 20/30 points.

## Baseline to beat

The baseline is persistence: P50 is the latest usable imbalance price, held flat for all 40 steps. P10 and P90 come from historical persistence errors per step, and the probabilities are historical shares.

Baseline metrics on the validation period (7 Sep – 4 Oct):

| Metric | Baseline |
|---|---|
| MAE | 66.20 €/MWh |
| Pinball loss (mean) | 24.18 |
| P10–P90 coverage | 0.68 (target 0.80) |
| Brier, exceptional prices | 0.1132 |
| Brier, direction | 0.4509 |
| High / low spike share | 12.1 % / 13.0 % |

Score our validation forecast against it:

```bash
python score.py --submission my_validation.csv --actuals data/actuals_validation.csv \
  --spike-margin 50 --output-dir results/my_model \
  --baseline-summary baseline_output/validation/score/score_summary.csv
```

## Getting started

**Requirements:** Python **3.11+**.

```bash
git clone https://github.com/Rdog69/turku-energy-since-ai.git
cd turku-energy-since-ai
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt   # coming soon
```

Then place the organisers' **starter package** in `starter_package/`. **It must never be committed**: it contains licensed Nord Pool data.

```
starter_package/
├─ README.md               # organisers' quick start, rules, glossary
├─ baseline.ipynb          # data loading, rows_available_at(), baseline, scoring
├─ data/
│  ├─ inputs.parquet / inputs.csv
│  ├─ spot_nordpool.csv    # ⚠️ licensed, do not commit
│  ├─ actuals_validation.csv
│  └─ quality_report.csv / .md
├─ sample_submission.csv
├─ forecast_origins.csv
├─ availability.csv
├─ validate_submission.py
├─ score.py
└─ make_templates.py
```

## Repository layout

*Planned; it will be updated as the code lands.*

```
.
├─ README.md
├─ src/
│  ├─ data/        # loading + availability-safe feature lookups
│  ├─ features/    # feature engineering per forecast origin
│  ├─ models/      # quantile price model, direction & spike classifiers
│  └─ backtest/    # origin loop → forecast_backtest.csv
├─ app/            # Level 2 situational view (dashboard)
├─ notebooks/      # exploration
├─ reports/        # evaluation report, slides
└─ starter_package/  # organisers' data, git-ignored
```

## Deliverables checklist

Due **Sunday 8 Nov, 10:00**, through the Since AI app.

- [x] `forecast_backtest.csv` (26,920 rows), passing `validate_submission.py` with 0 errors
- [x] Source code and start-up instructions (see [Getting started](#getting-started))
- [x] Evaluation report with physical reasoning chain and ablation study: [`reports/evaluation_report.md`](reports/evaluation_report.md)
- [x] List of data sources, external services, and licenses: [`SOURCES.md`](SOURCES.md)
- [x] 6-slide presentation deck for pitch & video: [`reports/slides.md`](reports/slides.md)
- [x] Interactive situation room dashboard (Level 2): [`app/dashboard.py`](app/dashboard.py)
- [x] FastAPI backend microservice: [`api/main.py`](api/main.py)
- [x] Automated n8n alert workflow: [`automation/imbalance_alert_workflow.json`](automation/imbalance_alert_workflow.json)

## Benchmark Results (Validation Period)

| Metric | Official Baseline | Direct LightGBM | **Composite / Mixture Model** | Improvement vs Baseline |
|---|:---:|:---:|:---:|:---:|
| **Accuracy: MAE ($p_{50}$)** | 66.20 €/MWh | 44.16 €/MWh | **`42.88 €/MWh`** | **-35.23% error reduction** (-23.33 €/MWh) |
| **Calibration: Pinball ($p_{10}/p_{90}$)** | 24.18 | 13.22 | **`12.80`** | **-47.1% loss reduction** |
| **P10–P90 Coverage** | 0.68 | 0.596 | **`0.646`** | **+5.0% gain towards target** |
| **Exceptional Prices (Spikes Brier)** | 0.1132 | 0.0983 | **`0.0965`** | **-14.8% better** |
| **Direction (3-Class Brier)** | 0.4509 | 0.4244 | **`0.4244`** | **-5.9% better** |
| **Validator Status** | Passed | Passed | **PASSED (0 Errors)** | Ready for scoring |

## Quickstart & Reproducibility

### 1. Setup Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r Dataset/starter_package_v1/requirements.txt lightgbm catboost xgboost shap fastapi uvicorn streamlit plotly pytest httpx
```

### 2. Run Anti-Leakage Tests
```bash
.venv/bin/pytest tests/
```

### 3. Launch the Situation Room Dashboard (Level 2)
```bash
.venv/bin/streamlit run app/dashboard.py
```

### 4. Launch the FastAPI Microservice
```bash
.venv/bin/uvicorn api.main:app --port 8000 --reload
```

### 5. Regenerate & Validate Official Submission
```bash
.venv/bin/python src/backtest/generate_test_submission.py
```

## Timeline

| When | What |
|---|---|
| Fri 6 Nov, 18:50 | Challenge briefing |
| Sat 7 Nov | Organisers available 09:00–12:00 and 14:30–18:00 |
| **Sun 8 Nov, 10:00** | **Submission deadline** |
| Sun 8 Nov, 13:30 | Top 3 announced |

Questions go to the **`#turku-energia`** channel in the Since AI Discord. Ask there so that every team gets the same answer.

## Rules and licensing

- ✅ Public code, other data with listed sources, Open-Meteo Single Runs
- ❌ **Sharing Nord Pool spot data.** It's for hackathon use only. Don't put it in this repo, and delete it after the event.
- ❌ **Using data before its `first_usable_origin_utc`**, which scores 0

All data sources and third-party components we use will be listed in [`SOURCES.md`](SOURCES.md) *(to be added)*.

## Team

| Name | Role |
|---|---|
| Pavlo | Data: availability layer, features, external sources |
| Pavel | Models: forecasts, calibration, backtest |
| Frank | Dashboard: API and Lovable situation room |
| Jim | Explanations & alerts: drivers, LLM text, n8n |
| Abdo | Story & quality: report, slides, video, submission |

Details of each role are in [`docs/PLAN.md` §11](docs/PLAN.md#11-roles).
