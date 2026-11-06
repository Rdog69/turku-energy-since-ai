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
pip install -r requirements.txt
```

Then unzip the organisers' **starter package** so that `starter_package_v1/` sits inside `starter_package/` (e.g. `starter_package/starter_package_v1/data/inputs.parquet`). Other locations work if you set `TE_PACKAGE_DIR` to the `starter_package_v1` folder. **It must never be committed**: it contains licensed Nord Pool data, and `.gitignore` excludes it.

### Run it

```bash
python -m pytest
```

Runs the leakage tests. **If any of them fail, fix that first:** using data before it was published scores 0.

```bash
python -m src.backtest.run --period validation --model spot_anchor
```

Trains on data published before 7 Sep, forecasts 7 Sep – 4 Oct, then runs the organisers' validator and `score.py` against the baseline. Results go to `results/<model>/validation/` (git-ignored).

```bash
python -m src.backtest.run --period test --model spot_anchor
```

Trains on everything up to 4 Oct and writes `results/<model>/test/forecast_backtest.csv` for the 673 test origins, checked with the validator.

The current best model is `split_all`, which needs the two external data tables. They're committed in `external_data/`, so no download is needed. To refresh them:

```bash
python -m src.data.fingrid
```

Downloads Fingrid real-time wind, nuclear, frequency and consumption. Needs `FINGRID_API_KEY` in `.env`.

```bash
python -m src.data.open_meteo
```

Downloads the ECMWF weather runs from Open-Meteo. No key needed.

**Dashboard data, briefings and alerts:**

```bash
python -m src.export.dashboard --model split_all --period test
```

Writes the per-hour JSON for the dashboard to `results/dashboard/` (contains spot prices, stays local).

```bash
python -m src.explain.featherless --period test
```

Adds an LLM briefing to each hour. Needs `FEATHERLESS_API_KEY`. Prompts are spot-free.

```bash
python -m src.automation.replay --period test --hours 24
```

Replays updates into the n8n alert workflow ([`automation/`](automation/)).

To get the baseline's own score for comparison, run the organisers' `baseline.ipynb` once in the package folder. It writes `baseline_output/validation/score/score_summary.csv`, which the runner picks up automatically.

Scores so far are logged in [`docs/RESULTS.md`](docs/RESULTS.md).

```
starter_package/starter_package_v1/
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

```
.
├─ README.md
├─ requirements.txt
├─ src/
│  ├─ config.py           # paths, periods, constants
│  ├─ data/
│  │  ├─ load.py          # load the package's long-format data
│  │  └─ availability.py  # THE availability rule: available_at(), fast SeriesIndex lookups
│  ├─ features/build.py   # leakage-safe feature table, one row per (origin, step)
│  ├─ models/anchor.py    # spot-anchor model (the floor to beat)
│  └─ backtest/run.py     # train → forecast → write → validate → score
├─ tests/                 # leakage tests (run with pytest)
├─ docs/                  # plan, TL;DR, results log
├─ results/               # model outputs, git-ignored
└─ starter_package/       # organisers' data, git-ignored
```

Planned additions: `src/models/` (quantile and probability models), `src/explain/`, `api/`, `app/`, `automation/`, `reports/`.

## Deliverables checklist

Due **Sunday 8 Nov, 10:00**, through the Since AI app.

- [ ] `forecast_backtest.csv`, passing `validate_submission.py`
- [ ] Source code and start-up instructions
- [ ] Short evaluation report: reasoning chain, factors affecting the forecast, validation-period metrics
- [ ] List of the data sources, external services, ready-made models and software components we used, with their licences
- [ ] 5–8 presentation slides
- [ ] Demo video (≤ 5 min): the next 10 h forecast in 15-min periods, its uncertainty, significant deviations, main drivers

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
