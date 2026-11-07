# Data sources, services and components

Required deliverable: every data source, external service, ready-made model and software component we use, with its licence. For each data source we also say **when it counts as available** in the backtest (its `first_usable_origin_utc`). That's the rule the organisers check: data used before it was available scores 0.

## Data

| Source | What we use | Licence | Availability rule in the backtest |
|---|---|---|---|
| **Starter package: Fingrid Open Data** | Imbalance price (319), mFRR/aFRR prices and volumes, direction (369), consumption and production, cross-border flows, day-ahead consumption/wind/solar forecasts (165, 246, 247) | CC BY 4.0 | The package's `first_usable_origin_utc` per row (binding) |
| **Starter package: ENTSO-E Transparency Platform** | SE1/SE3/EE imbalance prices, load forecasts, FI–EE capacity | CC BY 4.0 | The package's `first_usable_origin_utc` per row |
| **Starter package: Nord Pool** | Finnish day-ahead spot price | Licensed to Turku Energia for hackathon use only; not redistributed, not in this repo; deleted after the event | The package's `first_usable_origin_utc` per row |
| **Starter package: calendar** | Local hour, weekday, holidays, DST | – | Known in advance |
| **Fingrid Open Data API** (downloaded by us, not in the package) | Real-time wind production (181), nuclear production (188), grid frequency (177), consumption (193); 1–3 min data averaged to quarter-hours | CC BY 4.0 | The organisers' rule for measured Fingrid data (availability.csv): 30 min after the end of the quarter, rounded up to the next full hour. Fingrid publishes these every 1–3 min, so this is conservative. |
| **Fingrid Open Data API, second batch** | Real-time hydro (191), total production (192), net import (194), electric boilers (371), district-heating and industrial CHP (201, 202), cross-border flows FI–SE1/SE3/EE/NO (87, 89, 180, 187) | CC BY 4.0 | Same 30-min rule. **Not used** without the organisers' OK: 397 "Calculated imbalance", 22/251 last activated bid prices, 400–402 real-time mFRR prices (near-copies of the target, which the package gives with a 60-min delay). |
| **OpenStreetMap** (Overpass API) | 1,865 wind turbines (355 farms after grouping) and 85 solar parks in Finland: location, capacity where tagged | ODbL, © OpenStreetMap contributors | Installed plants: static, no timing issue. Capacity tags cleaned (values above 20 MW per turbine were kW without a unit). Used to weight weather points by installed wind capacity and for the dashboard map. |
| **Open-Meteo Single Runs API**: ECMWF IFS 0.25° (`ecmwf_ifs025`), 14 points | Wind speed at 100 m, 2 m temperature, relative humidity at 14 points in Finland (8 in the main wind clusters, 6 more spread across the country), weighted by the installed wind capacity nearest to each point; runs 00/06/12/18 UTC, 72 h each. Weather data by [Open-Meteo.com](https://open-meteo.com/), based on ECMWF open data. | CC BY 4.0 (Open-Meteo); ECMWF open data CC BY 4.0 | **Our assumption:** run initialisation + 8 h, rounded up to the next full hour. Open-Meteo states a 00 UTC run is generally accessible from about 04–06 UTC, so 8 h is conservative. Each forecast uses the newest run usable at its origin. We do **not** use the Historical Forecast API, which stitches runs together and leaks future information. |
| **Open-Meteo Single Runs API**: DWD ICON-EU (`icon_eu`), 8 points | The same variables at the 8 wind-cluster points (equal weights), as a second weather model: its wind index, its revision since the day-ahead forecast, and how far it disagrees with ECMWF. Runs 25 May – 2 Nov 2026, 00/06/12/18 UTC, 72 h each (647 of 648 runs; 11 Jun 06 UTC missing). Table and features from Pavlo's branch (`femboystorming-pavlo`). Weather data by [Open-Meteo.com](https://open-meteo.com/), based on Deutscher Wetterdienst (DWD) open data. | CC BY 4.0 (Open-Meteo) | **Our assumption:** run initialisation + 5 h, rounded up to the next full hour. Open-Meteo's model metadata showed a 3.9 h delay for ICON-EU when measured on 6 Nov 2026, so 5 h is conservative. |
| **Open-Meteo Single Runs API**: ECMWF IFS 0.25° at 12 points in Sweden, Norway, Denmark and Estonia | Neighbouring areas' wind and its revision. **Used for the median (P50) only:** in September and August it improved the median but made the P10–P90 band worse, so the band and the probabilities come from the model without it. | CC BY 4.0 (Open-Meteo); ECMWF open data CC BY 4.0 | Same 8 h rule as the Finnish ECMWF runs. |

## Software

| Component | Use | Licence |
|---|---|---|
| Python 3.12 | Runtime | PSF |
| pandas, NumPy, PyArrow | Data handling | BSD-3 / BSD-3 / Apache-2.0 |
| LightGBM | Gradient-boosted models, TreeSHAP drivers | MIT |
| scikit-learn | Platt calibration | BSD-3 |
| pytest | Leakage tests | MIT |
| Organisers' `validate_submission.py`, `score.py`, `make_templates.py`, `baseline.ipynb` | Validation and scoring | Provided by the organisers |

## Services

| Service | Use | Notes |
|---|---|---|
| Featherless.ai, model `Qwen/Qwen2.5-32B-Instruct` (Apache-2.0) | 2–3 sentence briefings per forecast hour | Text only, downstream of the forecast; never a model input. Prompts contain no spot or absolute prices (checked in code). Every number in an answer must appear in the facts, or a template is used instead. |
| Lovable | Dashboard frontend ("Imbalance Situation Room") | The hosted preview only gets demo data with a synthetic spot curve; real data stays local. |
| n8n Cloud | "Imbalance alert relay" workflow: webhook → filter → format → data table | Receives spot-free payloads only. Export in `automation/`. |
