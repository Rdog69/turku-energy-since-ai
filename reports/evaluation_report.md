# Evaluation Report: Finnish 10-Hour Imbalance Price Forecasting

> **Since AI 2026 — Turku Energia Challenge**  
> **Author Team:** Pavlo, Pavel, Frank, Jim, Abdo  
> **Date:** November 2026  
> **Code Repository:** `turku-energy-since-ai`  
> **Validated Submission:** `forecast_backtest.csv` (26,920 rows)

---

## 1. Executive Summary

Electricity imbalance prices in Finland reflect the marginal cost of resolving real-time mismatches between scheduled generation/consumption and physical grid reality. Because trading decisions at Turku Energia are evaluated against the Nord Pool day-ahead spot price, we formulate the forecasting task around the **deviation from spot**:

$$\text{Imbalance Price}_t = \text{Spot Price}_t + \Delta_t$$

Rather than predicting raw prices with black-box regression, we model the physical mechanisms governing $\Delta_t$:
1. Day-ahead weather forecast errors drive **wind production deviations**.
2. Wind deviations alter Finland's **net system balance** (residual load).
3. The TSO activates **mFRR balancing reserves** in a dominating direction (up or down).
4. Prices form along an **asymmetric merit order**: up-regulation jumps steeply along thermal generation costs (median $+25$ €/MWh), whereas down-regulation is relatively flat (median $-17$ €/MWh).

By constructing a **Direction-Mixture CDF Model** and selecting optimal estimators per scored metric, our solution beats the official competition baseline by **35.0% on MAE** and **47.0% on calibration pinball loss**, while strictly complying with all data availability and anti-leakage constraints.

---

## 2. The Physical Reasoning Chain

Our modeling choices reflect the physical causality of the Nordic power system:

```
┌─────────────────────────────────┐
│ Numerical Weather Prediction    │  Open-Meteo ECMWF/ICON revisions
│ (100m Wind Speed on West Coast) │
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Wind Forecast Error & Net Load  │  Realised vs DA Wind; Residual Load
│ (Residual Load = Cons - Wind)   │  (Consumption - Wind - Solar)
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ System Balance & mFRR Direction │  Dominating Direction: Up vs Down
│ (Secondary / Tertiary Reserves) │  (Grid Frequency proxy)
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Asymmetric Merit Order Pricing  │  Up-regulation: Steep thermal curve
│ (Volume-to-Price Mapping)       │  Down-regulation: Flat floor
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│ Imbalance Price Distribution    │  P10, P50, P90 Quantiles
│ (Bimodal Mixture CDF)           │  Spike Probabilities (>50 EUR/MWh)
└─────────────────────────────────┘
```

---

## 3. Step-by-Step Ablation Study

Every feature group and architectural improvement was evaluated on the official validation dataset (7 September – 4 October 2026, 672 origins, 26,880 rows) using the competition's locked `score.py` script:

| Model Iteration | MAE ($p_{50}$) [€/MWh] | Mean Pinball ($p_{10}/p_{90}$) | Spike Brier | Direction Brier | Key Insight |
|---|---|---|---|---|---|
| **0. Official Naive Baseline** | 66.20 | 24.18 | 0.1132 | 0.4509 | Ignores spot price; persistence decays rapidly. |
| **1. Static Spot Anchor** (`spot - 7.7`) | 44.20 | 22.10 | 0.1105 | 0.4509 | Spot price alone captures ~33% of variance. |
| **2. Direct LightGBM Baseline** | 44.16 | 13.21 | 0.0983 | 0.4244 | Net load + decaying recent gap anchors short steps. |
| **3. Step-Band Pinball Calibration** | 44.16 | 13.22 | 0.0983 | 0.4244 | Empirical residual shifting regularizes tails. |
| **4. Standalone CatBoost Regressor** | 43.32 | 13.15 | 0.0980 | 0.4244 | Symmetric oblivious trees resist extreme upward outliers. |
| **5. Direction-Mixture Model** | 43.05 | 12.82 | 0.0965 | 0.4274 | Inverting bimodal CDF expands P10-P90 coverage. |
| **6. Mixture (0.60) + CatBoost (0.40) Ensemble** | **42.88** | **12.80** | **0.0965** | **0.4244** | **🏆 Best Overall Score (-35.2% MAE, -47.1% Pinball).** |

### Net Score Improvement Over Baseline:
* **Accuracy (MAE):** Reduced by **23.33 €/MWh (-35.23%)**
* **Calibration (Pinball):** Reduced by **11.38 (-47.1%)**
* **Exceptional Price Spikes (Brier):** Improved by **-14.8%**
* **Balancing Direction (Brier):** Improved by **-5.9%**

---

## 4. Performance Across the 10-Hour Forecast Horizon

The model demonstrates strong temporal adaptation: short steps benefit from decaying real-time state features, while long steps remain securely anchored by day-ahead fundamentals:

| Horizon | Steps | MAE ($p_{50}$) [€/MWh] | Pinball Loss ($p_{10}/p_{90}$) | P10–P90 Coverage | Spike Brier | Direction Brier |
|---|---|---|---|---|---|---|
| **Hour 1** | 1–4 | **41.58** | 12.38 | 66.1% | 0.0926 | 0.4032 |
| **Hour 2** | 5–8 | 42.38 | 12.60 | 64.5% | 0.0937 | 0.4152 |
| **Hour 3** | 9–12 | 43.01 | 12.74 | 64.1% | 0.0951 | 0.4286 |
| **Hour 4** | 13–16 | 42.97 | 12.78 | 65.1% | 0.0953 | 0.4266 |
| **Hour 5** | 17–20 | 43.10 | 12.81 | 65.2% | 0.0963 | 0.4295 |
| **Hour 6** | 21–24 | 43.15 | 12.89 | 64.5% | 0.0968 | 0.4284 |
| **Hour 7** | 25–28 | 43.31 | 12.92 | 64.3% | 0.0976 | 0.4296 |
| **Hour 8** | 29–32 | 43.60 | 12.96 | 64.2% | 0.0987 | 0.4349 |
| **Hour 9** | 33–36 | 43.78 | 13.04 | 64.2% | 0.0996 | 0.4372 |
| **Hour 10** | 37–40 | **43.67** | 13.10 | 63.8% | 0.0998 | 0.4347 |

---

## 5. TreeSHAP Driver Attribution

To satisfy Level 1 explainability and avoid black-box obscurity, feature importance is calculated per quarter-hour using **TreeSHAP**:

1. **`net_load_da` (Residual Load):** Accounts for 38% of total variance. Higher residual load reliably shifts the grid into up-regulation.
2. **`spot_ramp` (Cross-Hour Differential):** Explains abrupt jumps across hourly settlement boundaries.
3. **`wind_fc_da` (Wind Generation Level):** Top wind quintiles exhibit near-zero spike risks; bottom quintiles show high upward tail variance.
4. **`shrunk_last_gap` (Decaying Lag):** Dominates steps 1–3, decaying exponentially as horizon increases.

---

## 6. Data Integrity & Anti-Leakage Compliance

* **Zero-Leakage Guarantee:** All feature pipelines consume data exclusively through `src/data/available_at.py`, which filters rows by `first_usable_origin_utc <= origin_utc`.
* **Automated Regression Suite:** Tested continuously via `pytest tests/test_leakage.py`.
* **Cut-Off Timestamp:** Optional `data_cutoff_utc` column is populated strictly with the latest timestamp of measured data used, verifying $\text{data\_cutoff\_utc} \le \text{forecast\_origin\_utc}$.
* **Licensing Compliance:** No proprietary Nord Pool spot data is tracked or committed in git.

---

## 7. Level 2 Integration: Trader Situation Room

Our machine learning pipeline integrates directly with operational trading workflows:
* **FastAPI Microservice (`api/main.py`):** Delivers probabilistic forecasts, SHAP drivers, and anomaly flags.
* **Interactive Control Room (`app/dashboard.py`):** Enables time-travel replay over historical origins with fan charts, spike alerts, and conflicting signal diagnostics.
* **Asset-Specific Recommendations:**
  * *Naantali CHP:* Early warning prompts for upward reserve commitment during high-spike regimes ($P > 20\%$).
  * *Power-to-Heat / Electric Boilers:* Dispatched during negative price risks to absorb cheap energy and avoid down-regulation penalties.
* **Event Automation (`automation/`):** n8n webhook workflow triggering Featherless LLM plain-language briefs and ElevenLabs spoken dispatches for dispatchers.

