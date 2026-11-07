# End-to-End Implementation Plan

> **Turku Energia Imbalance Price Challenge — Since AI 2026**  
> **Final Submission Deadline:** Sunday 8 November 2026, 10:00 AM (Hard deadline)  
> **Target:** Finnish 15-minute electricity imbalance price forecast, 1–40 steps (10 hours) ahead from every hourly origin.

---

## 1. Executive Summary & Scoring Rules

The challenge evaluates both an algorithmic backtest forecast (Level 1) and an operational trader situation room (Level 2):

$$\text{Total Score} = 0.8 \times \text{Level 1} + 0.2 \times \text{Level 2}$$

### Level 1 Breakdown (100 Points)
* **Accuracy (30 pts):** MAE of the point forecast ($p_{50}$).
* **Calibration (20 pts):** Mean pinball loss of $p_{10}$ and $p_{90}$ (target ~80% coverage).
* **Exceptional Prices / Spikes (20 pts):** Brier score of $p_{\text{spike\_high}}$ ($> \text{spot} + 50$) and $p_{\text{spike\_low}}$ ($< \text{spot} - 50$).
* **Direction (10 pts):** Three-class Brier score of $p_{\text{up}}, p_{\text{down}}, p_{\text{none}}$.
* **Reasoning Chain (20 pts):** Jury score on physical clarity, factor ablations, and data integrity.

### The Floor vs. The Edge
* **The Floor:** Predicting the **gap to spot** (`imbalance - spot`) using LightGBM. Just predicting `spot - 7.7` beats the official baseline MAE by 33% (44.2 vs. 66.2). Every serious team will discover this.
* **Our Edge:**
  1. **Direction-Mixture CDF architecture:** One consistent probability curve yielding all 8 submitted outputs without quantile crossing or probability sum errors.
  2. **"Pick-Per-Column" selection:** Picking between the Direct LightGBM and Mixture model per scored metric.
  3. **Real-time wind error nowcasting:** Using Fingrid's 3-minute generation data (~30 min delay) to replace the package's stale 60-minute imbalance price.
  4. **Open-Meteo NWP revisions:** Measuring wind forecast updates since yesterday's day-ahead plan.
  5. **Pinball- and Brier-optimal calibration per step band.**

---

## 2. The Physical Reasoning Chain (20 Jury Points)

Our models and evaluation report follow an unbroken physical narrative:

```
[NWP Weather Revision] ──► [Wind Forecast Error] ──► [System Net Imbalance]
                                                              │
                                                              ▼
[Imbalance Price] ◄── [Asymmetric Merit Order] ◄── [mFRR Direction & Volume]
```

1. **Weather Shifts:** Numerical weather updates on the west coast diverge from yesterday's day-ahead forecast.
2. **Wind Error:** Actual wind production deviates from scheduled generation.
3. **Net Imbalance:** The Finnish transmission grid experiences an instantaneous power deficit or surplus.
4. **mFRR Activation:** TSO activates secondary/tertiary balancing bids (up-regulation if short, down-regulation if long).
5. **Asymmetric Price Formation:** Up-regulation jumps steeply along the thermal merit order ($+8 \rightarrow +61$ €/MWh), while down-regulation is flat ($\approx -17$ €/MWh).

---

## 3. Data Strategy & Anti-Leakage Protocol

### The Zero-Leakage Rule
At forecast origin $t$, no feature may read data where `first_usable_origin_utc > t`. A single leak results in an automatic score of **0**.

* **`src/data/available_at.py`:** Central access layer strictly filtering rows by `first_usable_origin_utc <= origin_utc`.
* **Automated Unit Tests (`tests/test_leakage.py`):** Enforce zero lookahead across all series.
* **No Raw Data in Git:** `.gitignore` strictly ignores `Dataset/`, `starter_package*/`, and `spot_nordpool*.csv`.

### Data Sources
| Source | Data | Usable Lag | Purpose |
|---|---|---|---|
| **Starter Package** | Spot, DA wind/load/solar, past imbalance | Per row (60 min for imbalance) | Core baseline features |
| **Fingrid API (Key)** | Real-time wind, nuclear, frequency | 30 min | Real-time wind error & nowcasting |
| **Open-Meteo** | Single run wind at 100m (West Coast) | 3–6 h | Forecast revision since day-ahead |
| **Nord Pool UMM** | Outage messages (MW unavailable) | Publication timestamp | Outage timeline & tail spike explanations |
| **Elering API** | Real-time Estonian system balance | 15–30 min | Fresh neighbour signal |

---

## 4. Phase-by-Phase Roadmap

### Phase 0: Foundation & Safety Harness *(Fri Night)*
* [x] Isolate and git-ignore all licensed package directories.
* [x] Set up Python virtual environment (`.venv`) with `lightgbm`, `scikit-learn`, `pytest`, `pandas`, `pyarrow`.
* [x] Create project repository structure (`src/`, `api/`, `app/`, `automation/`, `tests/`, `reports/`).
* [x] Implement `src/data/available_at.py` and pass `tests/test_leakage.py`.
* [ ] Run `src/data/reproduce_baseline.py` to match official baseline metrics (MAE 66.20, Pinball 24.18, Spike Brier 0.1132, Direction Brier 0.4509).

### Phase 1: Direct LightGBM "Safety Submission" *(Sat Morning, $\le$ 12:00)*
* [ ] **Feature Engineering (`src/features/`):**
  * Day-ahead spot price at delivery quarter $k$.
  * Spot ramp across hour boundary and daily shape.
  * Day-ahead net position (residual load): $\text{Consumption} - \text{Wind} - \text{Solar}$.
  * Decaying recent imbalance gap (5 quarters old at step 1).
  * Calendar variables (hour, weekday, holiday, DST).
* [ ] **Train Baseline LightGBM:**
  * Direct quantile regression for $p_{10}, p_{50}, p_{90}$ on `gap = imbalance - spot`.
  * Binary classifier for direction ($p_{\text{up}}$ vs. $p_{\text{down}}$, with $p_{\text{none}} \approx 0.002$).
  * Conditional spike models for $p_{\text{spike\_high}}$ and $p_{\text{spike\_low}}$.
* [ ] **Generate & Validate Backtest CSV:**
  * Run `validate_submission.py` on the output. Confirm 0 errors.
  * Score on validation period (`score.py`). Confirm MAE drops below 45.

### Phase 2: The Physical Mixture Model & External Edge *(Sat Midday / Afternoon)*
* [ ] **Implement Mixture CDF (`src/models/mixture.py`):**
  * Train conditional gap models $F_{\text{up}}(\text{gap} \mid \text{up})$ and $F_{\text{down}}(\text{gap} \mid \text{down})$.
  * Form the full mixture distribution: $P(\text{price}) = P(\text{up}) \cdot F_{\text{up}} + P(\text{down}) \cdot F_{\text{down}}$.
  * Invert the CDF to produce $p_{10}, p_{50}, p_{90}$ and extract spike probabilities.
* [ ] **Fetch Fingrid Real-Time Wind & Frequency:**
  * Implement `src/data/fetchers/fingrid.py` with 30-min conservative delay.
  * Compute `current_wind_error = realised_wind - da_wind`.
* [ ] **Fetch Open-Meteo Revisions:**
  * Implement `src/data/fetchers/open_meteo.py` for west-coast coordinates.
  * Compute weather revision: $\Delta\text{Wind} = \text{Latest Run} - \text{Day-Ahead Run}$.
* [ ] **Per-Column Selector:**
  * Benchmark Direct LightGBM vs. Mixture CDF on validation and pick the winning model for each scored column.

### Phase 3: Explainability, API & Situation Room *(Sat Afternoon / Evening)*
* [ ] **SHAP Feature Drivers (`src/explain/`):**
  * Compute TreeSHAP per step to identify top 3 drivers.
  * Format into submission column `top_drivers` (e.g., `wind_fc_error;spot_ramp;net_load`).
* [ ] **Plain-Language Generation (Featherless.ai):**
  * Prompt template converting SHAP deltas into 2-sentence operator briefs.
  * Generate review prompts (e.g., *"Check Naantali CHP dispatch for 17:00–19:00"*).
* [ ] **FastAPI Replay Backend (`api/`):**
  * Endpoint `/forecast/{origin_utc}` returning 10h fan chart data, spike risks, and drivers.
* [ ] **Dashboard Frontend (`app/`):**
  * Lovable (or Streamlit fallback) situation room.
  * Interactive time-travel slider over historical test origins.
  * Conflicting signals warning box (e.g. weather vs. market price disagreement).
* [ ] **Automated Alerts (`automation/`):**
  * Exported n8n workflow monitoring spike risk jumps and posting alerts to Discord.

### Phase 4: Calibration, Stress-Testing & Story *(Sat Night)*
* [ ] **Probability & Quantile Calibration:**
  * Apply step-band adjustments to optimize empirical pinball loss and Brier score.
  * Apply 50% shrinkage toward global correction to avoid overfitting validation.
* [ ] **Stress Test CV:**
  * Train on June–August, evaluate on September (highest volatility month). Ensure models remain stable under seasonal shift.
* [ ] **Evaluation Report (`reports/evaluation_report.md`):**
  * Construct full ablation table: Spot only $\rightarrow$ + Net Load $\rightarrow$ + Mixture Model $\rightarrow$ + Real-time Wind.
* [ ] **Presentation Assets:**
  * 5–8 presentation slides.
  * Record $\le$ 5-minute replay video walkthrough.

### Phase 5: Final Verification & Submission *(Sun 06:00 – 10:00 AM)*
* [ ] Final retrain using all data up to **4 October 2026**.
* [ ] Generate final `forecast_backtest.csv` (26,920 rows).
* [ ] Run `python validate_submission.py --backtest forecast_backtest.csv --origins forecast_origins.csv`.
* [ ] Confirm output: `VALIDATION PASSED` (0 errors, 0 warnings).
* [ ] Final check of `SOURCES.md` and repository clean state.
* [ ] Submit via Since AI platform before 10:00 AM.

---

## 5. Team Roles & Ownership

| Person | Role | Deliverables |
|---|---|---|
| **Pavlo** | Data Engineering | `available_at()`, leakage tests, external fetchers (Fingrid, Open-Meteo, UMM), `features.parquet` |
| **Pavel** | Modeling | Direct LightGBM, Mixture CDF, per-column selection, calibration, `forecast_backtest.csv` |
| **Frank** | Dashboard | FastAPI backend, Lovable / Streamlit situation room, time-travel slider, UI panels |
| **Jim** | Explanations & Alerts | SHAP `top_drivers`, Featherless LLM texts, conflicting signal logic, n8n alert pipeline |
| **Abdo** | Story & Quality | Evaluation report, ablation table, slides, demo video recording, final submission checklist |

---

## 6. Pre-Submission Verification Checklist

* [ ] `forecast_backtest.csv` has exactly 26,920 rows and 13 columns.
* [ ] All 673 forecast origins are present with 40 steps each.
* [ ] Monotonicity holds: $p_{10} \le p_{50} \le p_{90}$ for every row.
* [ ] Direction probabilities sum to $1.0 \pm 0.001$: $p_{\text{up}} + p_{\text{down}} + p_{\text{none}} = 1.0$.
* [ ] Spike probabilities sum to $\le 1.001$: $p_{\text{spike\_high}} + p_{\text{spike\_low}} \le 1.0$.
* [ ] Data cutoff check: `data_cutoff_utc <= forecast_origin_utc`.
* [ ] `python validate_submission.py` returns return code `0`.
* [ ] No raw data or Nord Pool files are committed to git.

