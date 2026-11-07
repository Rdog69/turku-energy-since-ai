# AGENT HANDOUT & REPOSITORY BLUEPRINT

> **Challenge:** Since AI 2026 Hackathon (Turku, Finland) — Turku Energia Challenge  
> **Target:** 15-minute Finnish Electricity Imbalance Price (1–40 steps / 10 hours ahead)  
> **Active Branch:** `brainstorming-jim` (pushed to remote `origin/brainstorming-jim`)  
> **Key Companion Branch:** `origin/brainstorming-abdo` (contains safety reference submission & Fingrid external lab data)  
> **Last Updated:** November 7, 2026 (Local time 02:15 UTC+2)  
> **Deliverable Due Date:** Sunday, November 8, 2026 @ 10:00 AM UTC+2  

---

## 1. Quick Orientation for Incoming Agents

If you are an AI agent or engineer taking over this repository, here is the 60-second summary:

1. **The Goal:** Generate `forecast_backtest.csv` (26,920 rows: 673 test origins × 40 quarter-hour steps) predicting the Finnish imbalance price distribution:
   * **Accuracy ($p_{50}$):** Median price forecast (scored by MAE).
   * **Calibration ($p_{10}, p_{90}$):** 10th and 90th percentile bounds (scored by Mean Pinball Loss).
   * **Direction ($p_{\text{up}}, p_{\text{down}}, p_{\text{none}}$):** Dominating reserve direction (scored by 3-class Brier).
   * **Spikes ($p_{\text{spike\_high}}, p_{\text{spike\_low}}$):** Probability of price deviation $> \pm 50$ €/MWh from Spot (scored by Brier).
2. **Current Performance:**
   * Baseline MAE: **`66.20 €/MWh`** $\rightarrow$ Our Model MAE: **`42.88 €/MWh`** (**-35.2% error reduction**).
   * Baseline Pinball: **`24.18`** $\rightarrow$ Our Model Pinball: **`12.80`** (**-47.1% loss reduction**).
   * Teammate's Submitted Safety Model: **`43.54 €/MWh`** (Our model **beats** teammate's submitted safety model by **0.66 €/MWh**).
3. **Current Status of Submission:**
   * File [`forecast_backtest.csv`](../forecast_backtest.csv) is generated and verified with `validate_submission.py` with **0 errors, 0 warnings**.
   * All reports, slide decks, situation room dashboard, and API endpoints are built and tested.

---

## 2. Critical Constraints & Anti-Disqualification Rules

> [!CAUTION]
> **Any lookahead violation results in automatic score = 0.** Respect these rules at all times.

1. **Zero Lookahead Rule:**
   * At forecast origin $t$, you can **ONLY** use data published and available at or before $t$ (`first_usable_origin_utc <= t`).
   * Never use future actuals, future spot prices, or future imbalance prices.
   * Central filter: always use `src/data/available_at.py` (`available_at(data, origin_utc)`).
   * Unit test check: `.venv/bin/pytest tests/test_leakage.py` must pass.
2. **Training Cutoff Rule:**
   * No training or fitting on data after **4 October 2026 20:00 UTC** (`2026-10-04T20:00:00Z`).
   * Origin `2026-10-04T21:00:00Z` onwards is strictly out-of-sample backtest.
3. **Data Licensing Rule:**
   * Raw Nord Pool spot data is proprietary. **NEVER** commit `Dataset/`, `starter_package/`, `data/`, or `spot_nordpool*.csv` to git.
   * Verify with `git status --ignored` before committing.

---

## 3. Repository Architecture & Key Files

```
turku-energy-since-ai/
├── forecast_backtest.csv           # OFFICIAL SUBMISSION (26,920 rows, 0 validator errors)
├── pytest.ini                      # Python path configuration for test discovery
├── SOURCES.md                      # License audit & data publication delay audit
├── README.md                       # Main repo guide & quickstart
│
├── src/                            # CORE MACHINE LEARNING SOURCE CODE
│   ├── data/
│   │   ├── available_at.py         # Anti-leakage filter (enforces first_usable_origin_utc <= t)
│   │   ├── loader.py               # Robust multi-source CSV/Parquet loader
│   │   ├── reproduce_baseline.py   # Baseline persistence replication against score.py
│   │   └── fetchers/               # External fetchers (Open-Meteo wind, Fingrid reserves)
│   ├── features/
│   │   └── build_features.py       # 23 physical power grid features (Residual Load, Horizon Ramps)
│   ├── models/
│   │   ├── mixture.py              # Direction-Mixture CDF Model (inverts bimodal distribution)
│   │   ├── train_direct.py         # Direct LightGBM multi-quantile & classifier baseline
│   │   ├── compare_models.py       # Benchmark script across XGBoost, CatBoost, LightGBM, Mixture
│   │   ├── calibrate.py            # Pinball-optimal step-band quantile calibration
│   │   ├── evaluate_mixture.py     # Evaluation runner on validation period
│   │   └── selector.py             # Composite metric-optimal column blender
│   ├── explain/
│   │   └── shap_drivers.py         # TreeSHAP feature attributions & Naantali/Boiler advice
│   └── backtest/
│       └── generate_test_submission.py # Production script generating the final submission file
│
├── api/
│   └── main.py                     # FastAPI microservice (/origins, /forecast/{t}, /metrics)
├── app/
│   └── dashboard.py                # Streamlit Situation Room (time-travel, fan charts, risk strips)
├── automation/
│   └── imbalance_alert_workflow.json # n8n workflow (Featherless LLM brief, ElevenLabs voice)
├── docs/
│   ├── AGENT_HANDOUT.md            # THIS FILE (incoming agent guide)
│   ├── COMPARISON.md               # 5-LLM architecture consensus synthesis
│   └── IMPLEMENTATION_PLAN.md      # Detailed 6-phase engineering blueprint
├── reports/
│   ├── evaluation_report.md        # 7-section jury report with physical reasoning & ablation
│   ├── slides.md                   # 6-slide presentation deck
│   └── demo_video_script.md        # Timed 5:00 demo video walkthrough script
└── tests/
    └── test_leakage.py             # Automated unit tests for data availability compliance
```

---

## 4. The Modeling Core: Why It Beats Other Models

### The Market Phenomenon:
Electricity imbalance price in Finland equals:
$$\text{Imbalance Price}_t = \text{Spot Price}_t + \text{Gap}_t$$
* **Down-Regulation:** Grid has excess energy $\rightarrow$ TSO down-regulates $\rightarrow$ Gap is bounded and flat (median $-23.3$ €/MWh, std $\approx 38$).
* **Up-Regulation:** Grid has a deficit $\rightarrow$ TSO activates expensive thermal peakers $\rightarrow$ Gap is steep with extreme spikes (median $+30.7$ €/MWh, std $> 207$).

### Why Standard Regressors Fail:
Standard MSE/MAE regressors fit a single Gaussian-like bell curve over a bimodal distribution. They pull predictions toward 0, underpredicting spikes and overpredicting drops.

### Our Solution Stack:
1. **Direction-Mixture CDF (`src/models/mixture.py`):**
   Predicts the probability of direction first ($p_{\text{up}}, p_{\text{down}}, p_{\text{none}}$), models separate conditional quantile arms $F_{\text{up}}$ and $F_{\text{down}}$, and numerically inverts the combined cumulative distribution:
   $$F(y) = p_{\text{down}} F_{\text{down}}(y) + p_{\text{up}} F_{\text{up}}(y) + p_{\text{none}} \mathbf{1}(y \ge \text{spot})$$
2. **CatBoost Outlier Regularization:**
   CatBoost uses symmetric oblivious trees that are significantly more resistant to extreme positive outliers than standard LightGBM.
3. **The 60/40 Ensemble:**
   Blending 60% Direction-Mixture with 40% CatBoost drops MAE from 44.26 down to **`42.88 €/MWh`**.

---

## 5. Benchmark Performance Matrix (Validation Period)

Evaluated with the official competition scoring script (`score.py`):

| Scored Criterion (Weight) | Metric Key in Scorer | Official Baseline | Teammate Submitted Safety Model | Frank's Model (`final_capw`) | **Grand Champion Ensemble (`brainstorming-jim`)** |
|---|---|:---:|:---:|:---:|:---:|
| **Accuracy (30 pts)** | `mae_p50` | 66.20 €/MWh | 43.54 €/MWh | 42.34 €/MWh | **`41.71 €/MWh`** 🥇 (-37.0%) |
| **Calibration (20 pts)** | `calibration_pinball_mean` | 24.18 | 12.33 | 12.06 | **`12.04`** 🥇 (-50.2%) |
| **Spikes Risk (20 pts)** | `brier_spike_mean` | 0.1132 | 0.0945 | 0.0900 | **`0.0900`** 🥇 (-20.5%) |
| **Direction (10 pts)** | `brier_direction` | 0.4509 | 0.4294 | 0.3908 | **`0.3893`** 🥇 (-13.7%) |
| *P10–P90 Coverage* | *`coverage_p10_p90`* | *0.680* | *0.796* | *0.814* | **`0.775`** 🎯 (Target: 80%) |
| *Top Drivers Column* | *`top_drivers`* | *None* | *Empty* | *Empty* | **`TreeSHAP Built (100% Populated)`** |
| *Submission File* | *`forecast_backtest.csv`* | *Baseline* | *Safety (43.54)* | *Local* | **`VALIDATED (0 Errors, 26,920 rows)`** |

> [!TIP]
> **The Grand Champion Convergence:**
> Combines Fingrid real-time wind error nowcasting (`rt_wind`), step-band horizon splitting (`[1-4]`, `[5-8]`, `[9-16]`), autumn history direction prior (`0.6`), CatBoost outlier damping, and TreeSHAP driver attribution. Generated via `src/backtest/generate_grand_submission.py`.

---

## 6. Operational Runbook: How to Run Everything

### 1. Environment Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r Dataset/starter_package_v1/requirements.txt lightgbm catboost xgboost shap fastapi uvicorn streamlit plotly pytest httpx
```

### 2. Verify Anti-Leakage
```bash
.venv/bin/pytest tests/
```

### 3. Run Level 2 Situation Room Dashboard
```bash
.venv/bin/streamlit run app/dashboard.py
```

### 4. Run FastAPI Microservice
```bash
.venv/bin/uvicorn api.main:app --port 8000 --reload
```

### 5. Regenerate Submission File
```bash
.venv/bin/python src/backtest/generate_test_submission.py
```

### 6. Score Any Submission File Against Validation Actuals
```bash
.venv/bin/python Dataset/starter_package_v1/score.py \
    --submission forecast_backtest.csv \
    --actuals Dataset/starter_package_v1/data/actuals_validation.csv \
    --spike-margin 50 \
    --output-dir results/eval
```

---

## 7. Submission Checklist for Sunday 8 Nov, 10:00 AM

1. [x] **`forecast_backtest.csv`**: Generated, contains all 26,920 rows, passed official `validate_submission.py` with 0 errors.
2. [x] **Source Code & Startup Instructions**: Committed and pushed on branch `brainstorming-jim`.
3. [x] **Evaluation Report**: Complete in [`reports/evaluation_report.md`](../reports/evaluation_report.md).
4. [x] **Sources & Component Licenses**: Complete in [`SOURCES.md`](../SOURCES.md).
5. [x] **Presentation Deck**: 6 slides complete in [`reports/slides.md`](../reports/slides.md).
6. [x] **Demo Video Script**: Timed 5:00 speaker script ready in [`reports/demo_video_script.md`](../reports/demo_video_script.md).
7. [ ] **Video Recording**: Record a $\le 5$-minute screencast using `app/dashboard.py` and upload to Loom/YouTube.
8. [ ] **Platform Upload**: Upload CSV, video link, slide PDF, and GitHub repository URL via the Since AI app.

