# Glossary

Terms used in the report and the situation room. Drafted by a Featherless worker (Qwen3-30B), checked and corrected against the code and the organisers' README.

| Term | Meaning |
|---|---|
| **aFRR** | Automatic Frequency Restoration Reserve: a market-based reserve activated automatically to restore grid frequency. When dominant, it contributes to the imbalance price alongside mFRR. |
| **Brier score** | A metric for evaluating the accuracy of probabilistic forecasts. Lower values indicate better-calibrated probabilities. Used here for direction and spike predictions. |
| **BRP production plan** | Production plans that balance responsible parties (BRPs) send to Fingrid by 18:00 the day before (dataset 242). Measured production minus the plan shows how far the plan is off right now. |
| **calibration** | The quality of a model’s uncertainty estimates. A well-calibrated model produces confidence intervals that match observed frequency (e.g., 80% intervals should contain the true value 80% of the time). |
| **calibration drift** | A drop in calibration quality over time, often due to changing system conditions (e.g., seasonal shifts). The model may become overconfident or underconfident in later periods. |
| **coverage** | The proportion of actual values that fall within the forecast’s 80% interval (P10–P90). Target is 0.80; values below indicate under-coverage. |
| **day-ahead forecast** | The forecast of consumption, wind, and solar generation published the day before delivery, used in the Nord Pool day-ahead market. |
| **delivery_start_utc** | The timestamp marking the start of a 15-minute delivery period in UTC. Used to align forecasts with actual imbalance price periods. |
| **dominating direction** | The direction (up, down or none) of the mFRR balancing energy activated in a quarter-hour. It decides whether the imbalance price is above, below or equal to spot. |
| **down-regulation** | A situation where the grid has excess power. The imbalance price is below the day-ahead spot. |
| **DST** | Daylight Saving Time. The test period includes a 25-hour day (25 Oct 2026), which the model handles via local calendar features. |
| **ECMWF** | European Centre for Medium-Range Weather Forecasts. The source of high-resolution weather model runs used to improve wind and solar forecasts. |
| **exceptional price** | A price that deviates significantly from the day-ahead spot—defined here as more than 50 €/MWh above or below. The model forecasts the probability of such events. |
| **Fingrid** | The Finnish transmission system operator. Provides real-time data on consumption, production, cross-border flows, and imbalance prices. |
| **Fingrid 186 / 198** | Fingrid real-time datasets: 198 is Finland's surplus/deficit, i.e. measured net import minus the confirmed exchange plan (Finland's live imbalance); 186 is the same accumulated over the hour. |
| **first usable time** | The earliest time at which a data row can be used for forecasting. Must be ≤ the forecast origin time to avoid leakage. |
| **forecast origin_utc** | The time at which a forecast is made (every full hour). All predictions are made from this point for the next 10 hours. |
| **gap** | The imbalance price minus the day-ahead spot price. A positive gap indicates up-regulation; a negative gap indicates down-regulation. |
| **gap to spot** | The difference between the imbalance price and the day-ahead spot price. The core quantity modeled: it reflects the plan’s deviation from actuals. |
| **grid frequency** | A real-time indicator of grid stability. Low frequency indicates a shortage of power; high frequency indicates surplus. Used as a real-time signal. |
| **high spike** | An imbalance price more than 50 €/MWh above the day-ahead spot. The model forecasts the probability of such an event. |
| **leakage** | Using data before it was available at the forecast origin. Violates the data availability rule and results in a score of 0. |
| **low spike** | An imbalance price more than 50 €/MWh below the day-ahead spot. The model forecasts the probability of such an event. |
| **MAE** | Mean Absolute Error. Measures the average magnitude of forecast errors (P50 vs actual). Lower is better. |
| **mFRR** | Manual Frequency Restoration Reserve: a manually activated reserve used to correct imbalances. When dominant, it sets the imbalance price direction. |
| **model calibration** | The process of adjusting a model’s uncertainty estimates (e.g., P10/P90) to match historical coverage. Done here via holdout calibration. |
| **open-meteo** | A public weather API. We use only its Single Runs API (archived runs of ECMWF IFS and ICON-EU, each usable a few hours after the run starts); its Historical Forecast API is avoided because it leaks. |
| **P10 / P50 / P90** | The 10th, 50th (median), and 90th percentiles of the predicted imbalance price distribution. Together, they define an 80% interval. |
| **p_spike_high / p_spike_low** | The forecasted probabilities of an exceptionally high or low imbalance price (±50 €/MWh from spot). Sum ≤ 1. |
| **P_up / P_down / P_none** | The forecasted probabilities of up-regulation, down-regulation, or no dominating direction. Sum to 1. |
| **pinball loss** | A metric for evaluating quantile forecasts. Lower values indicate better-calibrated uncertainty intervals. |
| **real-time data** | Fingrid’s measured data (wind, consumption, frequency, etc.) updated every 1–3 minutes. Used only if available at the forecast origin. |
| **SHAP / drivers** | SHAP (SHapley Additive exPlanations) values identify which features most influenced a forecast. `top_drivers` lists the top 3 by |
| **spike** | An extreme imbalance price, defined as >50 €/MWh from spot. The model forecasts the probability of such events. |
| **split_all model** | A hybrid forecasting model: short-term (steps 1–8) uses real-time data; long-term (9–40) uses only weather and package data. |
| **spot anchor** | A baseline model that sets the imbalance price as the spot price plus a constant gap. Serves as a strong starting point. |
| **spot price** | The day-ahead electricity price from Nord Pool. Known at every forecast origin and used as the base for imbalance price. |
| **step** | A 15-minute interval within the forecast horizon. The forecast is made for 40 steps (10 hours) ahead from each origin. |
| **uncertainty band** | The 80% prediction interval (P10–P90) around the median forecast. Reflects the model’s confidence. |
| **up-regulation** | A situation where the grid needs more power. The imbalance price is above the day-ahead spot. |
| **weather model run** | One forecast of the weather (e.g. wind speed at 100 m) made by a numerical weather model such as ECMWF IFS or ICON-EU, started at a fixed time (00, 06, 12, 18 UTC). |
