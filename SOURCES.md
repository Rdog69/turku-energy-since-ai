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
| **Open-Meteo Single Runs API**: ECMWF IFS 0.25° (`ecmwf_ifs025`) | Wind speed at 100 m, 2 m temperature, relative humidity at 8 points across Finland's wind clusters; runs 00/06/12/18 UTC, 72 h each. Weather data by [Open-Meteo.com](https://open-meteo.com/), based on ECMWF open data. | CC BY 4.0 (Open-Meteo); ECMWF open data CC BY 4.0 | **Our assumption:** run initialisation + 8 h, rounded up to the next full hour. Open-Meteo states a 00 UTC run is generally accessible from about 04–06 UTC, so 8 h is conservative. Each forecast uses the newest run usable at its origin. We do **not** use the Historical Forecast API, which stitches runs together and leaks future information. |

## Software

| Component | Use | Licence |
|---|---|---|
| Python 3.12 | Runtime | PSF |
| pandas, NumPy, PyArrow | Data handling | BSD-3 / BSD-3 / Apache-2.0 |
| LightGBM | Gradient-boosted models, TreeSHAP drivers | MIT |
| scikit-learn | Platt calibration | BSD-3 |
| pytest | Leakage tests | MIT |
| Organisers' `validate_submission.py`, `score.py`, `make_templates.py`, `baseline.ipynb` | Validation and scoring | Provided by the organisers |

## Services (planned)

| Service | Use | Notes |
|---|---|---|
| Featherless.ai | LLM text for explanations | Output is text only, downstream of the forecast; never a model input |
| Lovable | Dashboard frontend | Hosted builds never contain spot data |
| n8n | Alert workflow | – |
