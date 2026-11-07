# Data sources, services and components

> This is the required deliverable "list of the data sources, external services, ready-made models and software components we used, with their licences". It is also the input to the organisers' leakage review.
>
> Conventions (same as the docs): ✔ checked in the repo or in the organisers' documents, ☐ assumption or not verified. Status words are used in a fixed sense:
>
> - **Used** = read by the current best model, `split_all` (`src/backtest/run.py`).
> - **Fetched, not used yet** = the data is in `external_data/` (or the fetcher exists), but `split_all` does not read it. Some of it is used in experiments only (`experiments/lab/`).
> - **Not used** = checked and rejected, or never fetched.
>
> **The rule for every row, package or external:** it may be used at forecast origin `t` only if `first_usable_origin_utc ≤ t`. Every external row carries that column, computed from a **conservative** publication delay and rounded **up** to the next full hour, like the starter package. The package's own column is binding for package rows.

## 1. Summary

| # | Source | Status | Licence |
|---|---|---|---|
| 1 | Starter package: Fingrid, ENTSO-E, Nord Pool spot, calendar | **Used** | CC BY 4.0 (Fingrid, ENTSO-E); Nord Pool spot is licensed data, see section 8 |
| 2 | Fingrid Open Data, real-time 3-min: wind (181), nuclear (188), frequency (177), consumption (193) | **Used** (steps 1–8 only) | CC BY 4.0 |
| 3 | Open-Meteo Single Runs: ECMWF IFS 0.25° (`ecmwf_ifs025`), main period | **Used** | CC BY 4.0 (Open-Meteo); ECMWF open data CC BY 4.0 ☐ |
| 4 | Fingrid real-time, other datasets: surplus/deficit (198, 186), production (192), hydro (191); also 194, 209 | **Used** (198, 186, 192, 191; steps 1–8 only, final model `split_all_rt_icon`); 194 and 209 not used | CC BY 4.0 |
| 5 | Fingrid "extra" series (BRP plans, wind capacity, mFRR bids, …) | **Used:** BRP production plans (242), for the plan error in steps 1–8. Others fetched, not used | CC BY 4.0 |
| 6 | Open-Meteo: ICON-EU, MET Nordic runs | ICON-EU single runs 25 May - 2 Nov 2026 (00/06/12/18 UTC, 647 of 648 runs; 11 Jun 06 UTC missing), first usable = init + 5 h, in `external_data/open_meteo/icon_eu.parquet`; used by `split_all_icon` and the final model `split_all_rt_icon` (small gain on both folds). MET Nordic: no data, not used | CC BY 4.0 |
| 7 | ERA5 reanalysis (via Open-Meteo) | Fetched, not used yet | Copernicus licence (attribution) ☐ |
| 8 | Nord Pool UMM outage messages | Fetched, not used yet | ☐ public REMIT data; terms unconfirmed |
| 9 | FMI 10-min observations | Fetched, not used yet | CC BY 4.0 |
| 10 | Elering (Estonia) system data | Fetched, not used yet | ☐ open data with attribution |
| 11 | Energinet `PowerSystemRightNow` (Denmark) | Fetched, not used yet | ☐ open data with attribution |
| 12 | **Pre-June history:** `last_autumn` (1 Sep – 30 Nov 2025) tables and `package_history` (Fingrid package series, 1 Mar 2025 – 1 Jun 2026) | Fetched, **not used until the organisers approve** | as the source of each table |

"Pre-June history" matters because the organisers' README says to train only on 1 Jun – 4 Oct 2026. We read that as "not the test period", but we have not had an answer (PLAN §12, question E1). Until we do, **no model that is submitted may read any `last_autumn` or `package_history` table**. `split_all` does not. ☐ The experiment lab (`experiments/lab/data.py`) can load these tables; its results are not part of the submission.

### Two fetcher families, and which file made which table

| Family | Code | Output in `external_data/` |
|---|---|---|
| **Frank's** (used by the model) | `src/data/fingrid.py` | `fingrid/fingrid_rt.parquet` (4 real-time series, main period) |
| | `src/data/open_meteo.py` | `open_meteo/ecmwf_ifs025.parquet` (ECMWF IFS runs, 29 May – 2 Nov by default ☐) |
| **Abdo's** (broader, mostly experiments) | `src/data/external/fingrid.py` | `fingrid/rt_main.csv.gz`, `rt_last_autumn.csv.gz` (10 real-time series), `extra_main.csv.gz`, `extra_last_autumn.csv.gz`, `package_history.csv.gz` |
| | `src/data/external/open_meteo.py` | `open_meteo/runs_ecmwf_ifs_last_autumn.csv.gz`, `era5_main.csv.gz`, `era5_last_autumn.csv.gz` |
| | `src/data/external/umm.py` | `umm/messages_main.csv.gz`, `messages_last_autumn.csv.gz` |
| | `src/data/external/fmi.py` | `fmi/obs_main.csv.gz`, `obs_last_autumn.csv.gz` |
| | `src/data/external/elering.py` | `elering/system_main.csv.gz`, `system_last_autumn.csv.gz` |
| | `src/data/external/energinet.py` | `energinet/power_system_main.csv.gz`, `power_system_last_autumn.csv.gz` |

Periods in Abdo's family (`src/data/external/common.py`): **`main`** = 25 May – 3 Nov 2026 (end exclusive) and **`last_autumn`** = 1 Sep – 1 Dec 2025 (end exclusive). Package-series history: 1 Mar 2025 – 1 Jun 2026.

The two families overlap on purpose (both fetch Fingrid wind, nuclear, frequency and consumption, and both fetch ECMWF IFS). The model reads **only Frank's two tables**. The tables differ in details (weather points, units, series names), so they must not be mixed in one model. Raw responses are cached under `external_data/**/raw/` and `external_data/_cache/` (git-ignored).

---

## 2. Starter package (used)

| Item | Detail |
|---|---|
| Access | Committed in `starter_package/` from the organisers' zip (private repo). Loaded by `src/data/load.py`. |
| Content | Fingrid imbalance price (319), mFRR/aFRR prices and volumes, mFRR direction (369), consumption, production, cross-border flows, day-ahead consumption/wind/solar forecasts (165, 246, 247); ENTSO-E imbalance prices (SE1, SE3, EE), load forecasts, FI–EE capacity; Nord Pool day-ahead spot; calendar (local hour, weekday, holiday, DST flag). |
| Licence | Fingrid: CC BY 4.0. ENTSO-E: CC BY 4.0 (only data on ENTSO-E's free re-use list; converted to UTC and 15-min series). Nord Pool spot: licensed, see section 8. (✔ package README §9) |
| Availability | The package's row-level `first_usable_origin_utc` (binding). Calendar rows are usable from the start of the data. |
| Code | `src/data/load.py`, `src/data/availability.py`, `src/features/build.py` |
| Status | **Used** |

## 3. Fingrid Open Data, real-time (used, 4 series)

| Item | Detail |
|---|---|
| Access | Free API key (`FINGRID_API_KEY` in `.env`, never committed). `https://data.fingrid.fi/api/datasets/{id}/data`. |
| Licence | CC BY 4.0 (✔ as stated by the organisers for Fingrid Open Data) |
| What `split_all` uses | Wind production (181), nuclear production (188), grid frequency (177, Nordic), consumption (193). 3-min values are averaged to quarter-hours (a quarter needs at least 3 samples). Features: wind and consumption error against the day-ahead forecasts, frequency deviation from 50 Hz, nuclear level and 6-hour change (`src/features/build.py`, `FINGRID_RT_COLUMNS`). |
| Availability rule | `first_usable_origin_utc = ceil_to_hour(quarter_end + 30 min)`. This is **our assumption**, copied from the organisers' own delay for measured Fingrid data (consumption, production, flows in `availability.csv`). Fingrid publishes every 1–3 min, so 30 min is conservative. ☐ We have not asked the organisers whether real-time series with our own documented delay are acceptable (PLAN §12). |
| Where it is used | Only for steps 1–8 (the first 2 hours). The long-horizon model never sees it. |
| Code | `src/data/fingrid.py` (fetch), `src/data/load.py::load_long_all` (merge), `src/features/build.py` |
| Table | `external_data/fingrid/fingrid_rt.parquet` |
| Status | **Used by `split_all`** |

Abdo's family also fetched six more real-time datasets into `rt_main.csv.gz` and `rt_last_autumn.csv.gz` (same 30-min rule, `RT_DELAY`, env `FINGRID_RT_DELAY_MIN`): production (192), net import/export (194), **surplus/deficit against the confirmed exchange plan (198)**, its cumulative form (186), hydro (191), power system state (209). Status: 198, 186, 192 and 191 are **used** by the live-imbalance features (`RT_IMBALANCE_COLUMNS` in `src/features/build.py`, short model only, final model `split_all_rt_icon`); 194 and 209 are not used (209 is constant).

## 4. Fingrid extra series and package-series history (mostly fetched, not used)

Only 242 (BRP production plans) is used: the plan error is measured production (192) minus the plan for the same quarter. Everything else in this section is not used.

`src/data/external/fingrid.py`; files `extra_main.csv.gz`, `extra_last_autumn.csv.gz`, `package_history.csv.gz`.

| ID | Dataset | Availability rule in the fetcher |
|---|---|---|
| 242 | Production plans from balance responsible parties (BRPs) | D-1 18:00 local; not revised |
| 268 | Wind capacity used in Fingrid's wind forecast | period end + 24 h |
| 243 | Sum of up-regulation bids | period end + 60 min |
| 22 / 251 | Price of the last activated up / down bid | ☐ period end + 60 min; coverage unverified |
| 176 | Imbalance power Finland–Sweden | ☐ period end + 60 min; unverified |
| 75 | Wind power, 15-min averages | period end + 30 min |

`package_history.csv.gz` holds the same 17 series as the starter package (319, 369, 244, 106, 375, 376, 347, 348, 124, 74, 61, 57, 60, 55, 165, 246, 247) for 1 Mar 2025 – 1 Jun 2026, with the package's delays (60 min for prices and volumes, 30 min for measured series, day-ahead forecasts at 13:00 local on D-1 ☐ verify against `availability.csv`). **Not used until the organisers approve** (see section 1). The imbalance-price formula changed on 1 Jun 2026, so older rows are for direction and wind-error models, not for price levels. The 2025 spot price is not available, so the 2025 gap cannot be computed.

Never used: Fingrid's continuously updated forecasts (245 wind, 241 production). Only the latest version is stored, so their history would leak.

## 5. Open-Meteo weather-model runs (used: ECMWF IFS)

| Item | Detail |
|---|---|
| Access | `https://single-runs-api.open-meteo.com/v1/forecast` (Single Runs API). No key. Free tier. |
| Licence | Open-Meteo data CC BY 4.0, based on ECMWF open data (CC BY 4.0 ☐). Attribution: weather data by [Open-Meteo.com](https://open-meteo.com/). ☐ The free API is for non-commercial use; we assume hackathon use is covered. |
| What `split_all` uses | Model `ecmwf_ifs025`, runs 00/06/12/18 UTC, 72 h each, at 8 points on Finland's west coast and the Bothnian Bay (Pori, Kristinestad, Kauhava–Lapua, Vaasa coast, Kokkola–Kalajoki, Raahe–Pyhäjoki, Oulu–Hailuoto, Simo–Tornio). Variables: 100 m wind speed, 2 m temperature, relative humidity. Derived: a wind power index (a hand-set generic turbine curve, not fitted to data), the **revision** of that index against the run available when Fingrid published the day-ahead wind forecast, temperature, and an icing proxy (−3 to +1 °C and humidity ≥ 90 %). |
| Availability rule | `first_usable_origin_utc = ceil_to_hour(run_init + 8 h)`. **Our assumption.** The measured init-to-availability delay on 6 Nov was about 7.1 h (from Open-Meteo's `meta.json`); Open-Meteo states that a 00 UTC run is generally accessible from about 04–06 UTC. At each origin the newest usable run is used. |
| Not used | The **Historical Forecast API**: it stitches runs together and leaks (the organisers advise against it). |
| Code | `src/data/open_meteo.py` (fetch), `src/data/weather.py` (index, features), `src/features/build.py::add_weather` |
| Table | `external_data/open_meteo/ecmwf_ifs025.parquet` |
| Status | **Used by `split_all`**, for all 40 steps |

Abdo's family (`src/data/external/open_meteo.py`) can also fetch IFS, ICON-EU and MET Nordic runs for seven wind clusters plus Helsinki, with 8 variables. Delays there: IFS 8 h, ICON-EU 5 h, MET Nordic 2 h (measured 7.1 / 3.9 / 0.8 h). In the repo only `runs_ecmwf_ifs_last_autumn.csv.gz` exists (pre-June: **not used until approved**); the ICON-EU table `icon_eu.parquet` is committed (5 h rule, used by the `*_icon` models, including the final `split_all_rt_icon`); no MET Nordic table (**not used**). Note: Frank's `PUBLICATION_DELAY` has MET Nordic at 3 h, Abdo's at 2 h; neither is used by the model.

**ERA5 reanalysis** (`archive-api`, `era5_main.csv.gz`, `era5_last_autumn.csv.gz`): actual weather at the same points, available about 5 days late (`first_usable_origin_utc = valid time + 6 days`). Intended for fitting mappings only (wind speed to wind power), never as a forecast-time feature. Status: **fetched, not used yet**.

## 6. Other fetched sources (not used yet)

| Source | Access and licence | What it adds | Availability rule in the fetcher | Code, table |
|---|---|---|---|---|
| **Nord Pool UMM** (outage messages) | `https://ummapi.nordpoolgroup.com/messages`, no key. ☐ Public REMIT data; use confirmed with nobody yet. | Planned and unplanned outages with publication times; areas FI, SE1, SE3, EE; all message versions | `ceil_hour(publicationDate)` per version; at an origin use the newest usable version | `src/data/external/umm.py`; `umm/messages_*.csv.gz` |
| **FMI open data** | WFS `fmi::observations::weather::simple`, no key, CC BY 4.0 | 10-min wind, gusts, temperature, humidity at 8 coastal stations | ☐ `ceil_hour(time + 20 min)` | `src/data/external/fmi.py`; `fmi/obs_*.csv.gz` |
| **Elering** | `dashboard.elering.ee/api/system`, no key. ☐ Open data, attribution. | Estonian production, consumption, system balance | ☐ `ceil_hour(time + 60 min)` | `src/data/external/elering.py`; `elering/system_*.csv.gz` |
| **Energinet** | `api.energidataservice.dk`, dataset `PowerSystemRightNow`, no key. ☐ Open data, attribution. | 1-min aFRR activation, DK–SE exchange, wind, averaged per quarter | ☐ `ceil_hour(quarter_start + 30 min)` (quarter end + 15 min) | `src/data/external/energinet.py`; `energinet/power_system_*.csv.gz` |

Energinet's `DayAheadPrices` (FI vs SE/EE price spread, PLAN edge E3) has **not been fetched**: Nord Pool–derived prices need a licence check first.

## 7. Checked and not used

| Source | Why not |
|---|---|
| Last year's spot price (needed for the 2025 gap) | Nord Pool data is licensed. The free mirror at api.energy-charts.info says "private and internal use only… external use prohibited". ☐ Ask the organisers whether they can extend the spot file back to Sep 2025. |
| ENTSO-E API | A token takes several working days |
| Fingrid 245 / 241 (updated forecasts) | Only the latest version is stored, so they leak |
| Open-Meteo Historical Forecast API | Leaks; not recommended by the organisers |
| Statnett, Svenska kraftnät | Live dashboards respond, but no verified history API |
| SMHI / MET Norway observations | Far from Finnish wind |
| NOAA GEFS ensembles | Large raw files; single runs cover the deterministic signal |
| eSett open data | Settlement data, published days later (ex-post) |
| News, gas/oil/CO₂ prices, sentiment | Already inside spot; leakage risk (PLAN §4) |

Kimi K3.1 Pro's suggestions for further sources: [`docs/data_sources/kimi_suggestions.md`](docs/data_sources/kimi_suggestions.md).

## 8. Licensed data: Nord Pool spot price

The Finnish day-ahead spot price (`starter_package/data/spot_nordpool.csv` and the `spot_price` column of `actuals_validation.csv`) is **licensed to Turku Energia**. The organisers' terms (✔ package README §9):

- It is shared with the teams **for use during the hackathon only**.
- **Do not share it further** and do not upload it to public repositories. Our code may be public; the data may not.
- **Delete it after the event.**

How we comply:

- The repo is **private** for this reason. It must not be made public without first purging `starter_package/data/` from the git history.
- No document, log or result file quotes spot values. `src/data/load.py` prints summaries only.
- `results/` (forecasts and dashboard JSON that contain spot) is git-ignored.
- The hosted Lovable preview gets demo data in which the spot curve is replaced by a synthetic one (`--demo` in `src/export/dashboard.py`); real data stays local.
- Prompts to Featherless and payloads to n8n are checked in code to contain no spot or absolute price (`assert_spot_free` in `src/explain/featherless.py`; a guard in `src/automation/replay.py`). ☐ We have asked no one whether forecasts derived from spot (expected gap, probabilities) may leave the machine; we send only gaps and probabilities.
- Everyone deletes their copy after the event. ☐ Owner: to be confirmed in the team's final checklist.

---

## 9. Software components

All are open source and installed from PyPI (`requirements.txt`, `tools/requirements.txt`). Licences are from our knowledge of each project; ☐ marks one we did not re-check against the installed package.

| Component | Use | Licence |
|---|---|---|
| Python 3.11+ (tested on 3.12) | Runtime | PSF |
| pandas (≥ 2.2) | Data handling, features | BSD-3-Clause |
| NumPy (≥ 1.26) | Arrays, vectorised lookups | BSD-3-Clause |
| PyArrow (≥ 14) | Parquet files | Apache-2.0 |
| tzdata (≥ 2024.1) | Time-zone data (Europe/Helsinki) for pandas | Apache-2.0 |
| LightGBM (≥ 4.3) | Quantile regression and classifiers; TreeSHAP drivers (`pred_contrib`) | MIT |
| scikit-learn (≥ 1.4) | Platt calibration (`LogisticRegression`); `HistGradientBoosting` in the experiment lab only | BSD-3-Clause |
| pytest (≥ 8) | Leakage and format tests | MIT |
| nbconvert (≥ 7), ipykernel (≥ 6) | Run the organisers' `baseline.ipynb` headless | BSD-3-Clause |
| `openai` Python SDK (≥ 1.40; `tools/requirements.txt`) | Client for Featherless' OpenAI-compatible API in `tools/kimi.py` (development tool) | Apache-2.0 ☐ |
| Streamlit | Fallback dashboard (being added; ☐ not yet in `requirements.txt`) | Apache-2.0 |
| Plotly | Charts in the fallback dashboard (being added; ☐ not yet in `requirements.txt`) | MIT |
| Organisers' `validate_submission.py`, `score.py`, `make_templates.py`, `baseline.ipynb` | Validation and scoring (in `starter_package/`) | Provided by the organisers ☐ licence not stated |

The Python standard library (`urllib`, `json`, …) does the HTTP calls; there is no `requests` dependency.

## 10. External services and ready-made models

| Service | Use | Terms |
|---|---|---|
| **Featherless.ai**, model `Qwen/Qwen2.5-32B-Instruct` (`src/explain/featherless.py`) | 2–3 sentence briefings per forecast hour on the dashboard | Hackathon credit (PLAN §7). Model licence Apache-2.0 ☐ (Qwen2.5-32B; other Qwen2.5 sizes use other licences). |
| Featherless.ai, model `moonshotai/Kimi-K3.1-Pro` (`tools/kimi.py`) | Development helper (review, drafting). Not part of the forecast or the dashboard. | Model licence ☐ not checked |
| **n8n Cloud** | "Imbalance alert relay" workflow: webhook → filter (alert in the next 3 h?) → format → log to a data table. Export in `automation/n8n_imbalance_alert_relay.json`. | Event licence (PLAN §7). Receives spot-free payloads only. |
| **Lovable** | Frontend of the dashboard ("Imbalance Situation Room") | Event licence. The hosted preview gets demo data with a synthetic spot curve only. |
| **Open-Meteo API** | ECMWF weather runs (section 5) | CC BY 4.0 data; free API |
| **Fingrid Open Data API** | Real-time series (section 3) | CC BY 4.0 data; free key |

Other event tools in PLAN §7 (ElevenLabs, Gemini API, Red Hat OpenShift) are ☐ **not used** as far as the repo shows.

**No pretrained forecasting model is used.** LightGBM models are trained from scratch on the competition data, inside this repo. We use no foundation model for time series (the planned Chronos/TimesFM challenger, PLAN E6, was not run ☐ nothing in the repo shows otherwise).

**What the LLM does and does not do.** The LLM writes explanation text only, after the forecast exists.

- It never sees raw data: no spot prices, no absolute price forecasts, no input series. The prompt holds a fact sheet built by deterministic rules: expected **gap to spot** (p50 minus spot, in €/MWh) per hourly block, probabilities of up-regulation and spikes, the width of the uncertainty range, rule-based alerts and "conflicting signal" messages, the labels of the main drivers, plain statements about grid state (wind vs forecast, weather revision, frequency, nuclear change) and "suggestions to review".
- It cannot change any forecast value: the scored CSV is written by the backtest before the LLM runs, and `top_drivers` comes from SHAP, not from the LLM.
- Its output is checked: every number in an answer must appear in the fact sheet, and degenerate text is rejected; otherwise a template briefing is used instead.

**AI coding assistants.** We used AI during development, and say so openly: Claude Code (coding, documentation, review) and LLM brainstorming sessions with several models (Kimi K3.1 Pro, Kimi K3, DeepSeek V4.1 Flash, GLM 5.3, Claude Opus 5.5; prompts and answers in `docs/brainstorm/`). Their suggestions were treated as ideas, tested on the validation period, and kept only if they helped. ☐ Exact tool versions are not recorded.
