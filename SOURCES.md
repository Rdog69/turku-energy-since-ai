# Data Sources and Software Components

> **Since AI 2026 — Turku Energia Challenge**  
> **Team:** Pavlo, Pavel, Frank, Jim, Abdo  
> **Project:** `turku-energy-since-ai`

---

## 1. Data Sources

All external data sources and package files follow the **data availability rule**: at forecast origin $t$, data was used only if its publication delay satisfies $\text{first\_usable\_origin\_utc} \le t$.

| Source Name | Provider | Content & Datasets | Licence / Terms | Publication Delay Rule |
|---|---|---|---|---|
| **Starter Package (`inputs.parquet`)** | Fingrid / ENTSO-E / Since AI | Imbalance price (319), mFRR direction (369), mFRR prices (244/106), day-ahead wind/solar/consumption forecasts (165, 246, 247), cross-border flows (55, 57, 60, 61), ENTSO-E load and prices | CC BY 4.0 / Open Data (Fingrid & ENTSO-E) | Row-level `first_usable_origin_utc` in package (binding) |
| **Day-Ahead Spot Price (`spot_nordpool.csv`)** | Nord Pool | Day-ahead spot price for Finland (`fi_spot_price`, 15-min resolution) | **Proprietary / Licensed.** Distributed under competition terms. Strictly excluded from version control (`.gitignore`) and not republished. | Published D-1 at 14:00 local time (11:00 / 12:00 UTC) |
| **Open-Meteo Single Runs** | Open-Meteo / ECMWF / DWD | 100m wind speed, gusts, temperature, humidity across Finnish west-coast clusters (Ostrobothnia, Satakunta, Oulu) | CC BY 4.0 (Open-Meteo free tier) | NWP run availability delay (~3–6 hours after model initialization) |
| **Fingrid Open Data API** | Fingrid Oyj | Real-time 3-minute generation (wind 181, nuclear 188, hydro 191) and grid frequency (177) | CC BY 4.0 (Fingrid Open Data Licence) | Assumed 30 minutes after quarter-hour end, rounded up to next full hour |
| **Nord Pool UMM API** | Nord Pool | Urgent Market Messages on planned/unplanned power plant and transmission outages | Public REMIT outage feed | Version publication timestamp (`publicationDate`) |
| **Elering API** | Elering AS (Estonian TSO) | Estonian real-time production, consumption, and system balance | Public open data | Assumed 30 minutes after quarter-hour end |

---

## 2. Software Libraries & Components

All open-source software libraries utilized in the solution are permissive (MIT, BSD, Apache 2.0):

| Component | Version | Licence | Purpose |
|---|---|---|---|
| **Python** | 3.13.1 | PSF Licence | Execution runtime |
| **LightGBM** | 4.7.0 | MIT Licence | Gradient boosted trees for quantile regression and classification |
| **Scikit-learn** | 1.9.1 | BSD 3-Clause | Preprocessing and metric evaluations |
| **Pandas** | 3.1.1 | BSD 3-Clause | Tabular data manipulation and time-series alignment |
| **PyArrow** | 26.0.1 | Apache 2.0 | High-performance Parquet serialization |
| **NumPy** | 2.5.4 | BSD 3-Clause | Vectorized linear algebra and interpolation |
| **SciPy** | 1.18.1 | BSD 3-Clause | 1D numerical interpolation for mixture CDF inversion |
| **SHAP** | 0.54.1 | MIT Licence | TreeSHAP feature attribution and driver extraction |
| **FastAPI** | 0.162.0 | MIT Licence | Asynchronous REST API microservice for dashboard |
| **Uvicorn** | 0.54.0 | BSD 3-Clause | ASGI server |
| **Streamlit** | 1.67.0 | Apache 2.0 | Interactive Situation Room frontend |
| **Plotly** | 7.1.0 | MIT Licence | Interactive probabilistic fan charts and heatmaps |
| **Pytest** | 9.2.0 | MIT Licence | Automated anti-leakage test harness |
| **Requests / HTTPX** | 2.34.2 / 0.28.1 | Apache 2.0 / BSD 3-Clause | HTTP fetchers |

---

## 3. Data Governance & Anti-Leakage Compliance

1. **Centralized Data Filtering:** All training and inference routines access data through `src/data/available_at.py`, which strictly filters out any observation where $\text{first\_usable\_origin\_utc} > t$.
2. **Automated Leakage Testing:** Verified by unit tests in `tests/test_leakage.py`.
3. **Data Cut-off Tracking:** The submission file `forecast_backtest.csv` includes the verified `data_cutoff_utc` column indicating the newest measured data timestamp used at each origin ($\le \text{forecast\_origin\_utc}$).
4. **Git Cleanliness:** Raw package folders, ZIP files, parquet data, and licensed spot CSVs are strictly ignored in `.gitignore`.

