# Data sources, services and components

> This is the required deliverable "list of the data sources, external services, ready-made models and software components we used, with their licences". It is also the input to the organisers' leakage review.
>
> Conventions (same as the docs): ✔ checked in the repo or in the organisers' documents, ☐ assumption or not verified. Status words are used in a fixed sense:
>
> - **Submission choice: `TODO(team): v6_hf or team5050`** (same open question as `reports/evaluation_report.md`). This file covers both candidates: `v6_hf` (section 1, first table) and `team5050` (the table "What `team5050` uses" below).
> - **Used** = read by a validated model: `v6_hf` or `split_all_rt_icon` in `src/backtest/run.py`, or either half of `team5050` (Abdo's `m_int4ss_lgb7` in `experiments/lab/`, Frank's `v4_n50` in `src/`).
> - **Fetched, not used yet** = the data is in `external_data/` (or the fetcher exists), but no model in `src/` reads it. Some of it is used in experiments only (`experiments/lab/`).
> - **Not used** = checked and rejected, or never fetched.
>
> **The rule for every row, package or external:** it may be used at forecast origin `t` only if `first_usable_origin_utc ≤ t`. Every external row carries that column, computed from a **conservative** publication delay and rounded **up** to the next full hour, like the starter package. The package's own column is binding for package rows.

## 1. Summary

### What `v6_hf` uses (`src/backtest/run.py`; candidate 1 of `TODO(team): v6_hf or team5050`)

| Source | What we use | Licence | Availability rule in the backtest |
|---|---|---|---|
| **Starter package: Fingrid Open Data** | Features read by the model: imbalance price (319) and direction (369) of the newest usable quarters, mFRR up/down activated volumes (375, 376), consumption (124, for the consumption error), cross-border flows (60, 61, 57, 55), day-ahead consumption/wind/solar forecasts (165, 246, 247). The imbalance price, direction and spot are also the training targets. mFRR prices (244, 106), aFRR prices (347, 348) and production (74) are in the loaded table but no feature column reads them. | CC BY 4.0 | The package's `first_usable_origin_utc` per row (binding) |
| **Starter package: ENTSO-E Transparency Platform** | Features read by the model: SE1/SE3/EE imbalance prices, long (17.1.g), and FI–EE / EE–FI day-ahead capacity (11.1). The load forecasts (6.1.b) and the short imbalance prices are in the loaded table but not read. | CC BY 4.0 | The package's `first_usable_origin_utc` per row |
| **Starter package: Nord Pool** | Finnish day-ahead spot price | Licensed to Turku Energia for hackathon use only; not redistributed; committed only in this private repo (section 8); deleted after the event | The package's `first_usable_origin_utc` per row |
| **Starter package: calendar** | Local hour, weekday, holidays, DST | – | Known in advance |
| **Fingrid Open Data API** (downloaded by us, not in the package) | Real-time wind production (181), nuclear production (188), grid frequency (177), consumption (193); 1–3 min data averaged to quarter-hours. Wind production (181) also fits the weights of our learned wind-production model (all steps), using only data published before each training cutoff. | CC BY 4.0 | The organisers' rule for measured Fingrid data (availability.csv): 30 min after the end of the quarter, rounded up to the next full hour. Fingrid publishes these every 1–3 min, so this is conservative. |
| **Fingrid Open Data API, second batch** | Downloaded: hydro (191), total production (192), net import (194), electric boilers (371), district-heating and industrial CHP (201, 202), cross-border flows FI–SE1/SE3/EE/NO (87, 89, 180, 187). **Read by `v6_hf` (short model, steps 1–8 only, `FINGRID_RT2_COLUMNS`):** 191, 194, 371, 201, 202, flows 89 (SE3) and 180 (EE). **Downloaded but not read by any model:** 192, 87, 187. | CC BY 4.0 | Same 30-min rule (`src/data/fingrid.py`: `ceil_hour(quarter_end + 30 min)`, at least 3 samples per quarter). **Not used** without the organisers' OK: 397 "Calculated imbalance", 22/251 last activated bid prices, 400–402 real-time mFRR prices (near-copies of the target, which the package gives with a 60-min delay). |
| **OpenStreetMap** (Overpass API) | 1,865 wind turbines (355 farms after grouping) and 85 solar parks in Finland: location, capacity where tagged | ODbL, © OpenStreetMap contributors | Installed plants: static, no timing issue. Capacity tags cleaned (values above 20 MW per turbine were kW without a unit). Used to weight weather points by installed wind capacity and for the dashboard map. |
| **Open-Meteo Single Runs API**: ECMWF IFS 0.25° (`ecmwf_ifs025`), 14 points | Wind speed at 100 m, 2 m temperature, relative humidity at 14 points in Finland (8 in the main wind clusters, 6 more spread across the country), weighted by the installed wind capacity nearest to each point; runs 00/06/12/18 UTC, 72 h each. Weather data by [Open-Meteo.com](https://open-meteo.com/), based on ECMWF open data. | CC BY 4.0 (Open-Meteo); ECMWF open data CC BY 4.0 | **Our assumption:** run initialisation + 8 h, rounded up to the next full hour. Open-Meteo states a 00 UTC run is generally accessible from about 04–06 UTC, so 8 h is conservative. Each forecast uses the newest run usable at its origin. We do **not** use the Historical Forecast API, which stitches runs together and leaks future information. |
| **Open-Meteo Single Runs API**: DWD ICON-EU (`icon_eu`), 8 points | The same variables at the 8 wind-cluster points (equal weights), as a second weather model: its wind index, its revision since the day-ahead forecast, and how far it disagrees with ECMWF. Runs 25 May – 2 Nov 2026, 00/06/12/18 UTC, 72 h each (647 of 648 runs; 11 Jun 06 UTC missing). Table and features from Pavlo's branch (`femboystorming-pavlo`). Weather data by [Open-Meteo.com](https://open-meteo.com/), based on Deutscher Wetterdienst (DWD) open data. | CC BY 4.0 (Open-Meteo) | **Our assumption:** run initialisation + 5 h, rounded up to the next full hour. Open-Meteo's model metadata showed a 3.9 h delay for ICON-EU when measured on 6 Nov 2026, so 5 h is conservative. |
| **Open-Meteo Single Runs API**: ECMWF IFS 0.25° at 8 Finnish towns | Shortwave radiation, cloud cover and 2 m temperature, for solar and heating-demand revisions. **Tested, not used in the submitted model:** no gain in both validation months (`docs/RESULTS.md`, round 5). The town table (`ecmwf_ifs025_solar.parquet`) is not in the repo ☐; `v6_hf` has the town flags off. | CC BY 4.0 (Open-Meteo); ECMWF open data CC BY 4.0 | Same 8 h rule as the other ECMWF runs. |
| **Pre-June history** (training only), package format, 1 Mar 2025 – 31 May 2026 | The package's Fingrid series (mFRR/aFRR prices and volumes, direction, consumption, production, flows, day-ahead forecasts) and the spot price, with the imbalance price recomputed under the 1 June 2026 volume-weighted rule (matches the official price on 99.5 % of Jun–Oct 2026 quarters). Table built by Abdo's `experiments/lab/build_history.py` (`brainstorming-abdo`). Allowed by the organisers (Q&A answer, 7 Nov 2026, [`QUESTIONS.md`](QUESTIONS.md) Q1). | Fingrid CC BY 4.0; spot from Elering's Nord Pool price API (originates from Nord Pool: team-internal use only; committed only in this private repo, `external_data/history/pkg_history.csv.gz` and `external_data/elering/fi_spot_history.csv.gz`) | Every measured row is usable no earlier than the package's own rule for the same minute of the hour (`load_history` in `src/data/load.py`); day-ahead rows keep their D-1 publication times. Only for training: every origin we forecast is after June. |
| **Open-Meteo Single Runs API**: ECMWF IFS 0.25° at 12 points in Sweden, Norway, Denmark and Estonia | Neighbouring areas' wind and its revision. **Used for the median (P50) only:** in September and August it improved the median but made the P10–P90 band worse, so the band and the probabilities come from the model without it. | CC BY 4.0 (Open-Meteo); ECMWF open data CC BY 4.0 | Same 8 h rule as the Finnish ECMWF runs. |

### What `team5050` uses (candidate 2 of `TODO(team): v6_hf or team5050`)

`team5050` is an equal-weight average, per output group (p50, band, spike, direction), of two forecast files (`experiments/lab/recipe_team5050.json`, `experiments/lab/combine.py`; scored file `submissions/forecast_backtest_team5050.csv`). It adds no data source of its own. Its halves read these:

| Half | Data it reads | Licence | Availability rule in the code |
|---|---|---|---|
| **Frank's half, `v4_n50`** (`src/`, member file `external_data/_frank/v4_n50_*.csv`, which is **not in the repo** ☐) | The same tables as `v6_hf` in the table above (package, Fingrid real-time batches 1 and 2, ECMWF 14 points, ICON-EU, Nordic wind for the median, learned wind production), **without the pre-June history**. So this half reads the starter package's ENTSO-E series too (neighbour imbalance prices and FI–EE / EE–FI capacity). | as the `v6_hf` rows | as the `v6_hf` rows |
| **Abdo's half, `m_int4ss_lgb7`** (spec `lumi/final/m_int4ss_lgb7.json`, features in `experiments/lab/features/`, member file `submissions/forecast_backtest_m_int4ss_lgb7.csv`) | **Starter package** (`pkg`): spot (also its day shape), calendar, day-ahead wind/consumption/solar forecasts (246, 165, 247), imbalance price (319) over the last 16 quarters, direction (369), mFRR up/down activated volumes (375, 376) and prices (244, 106), consumption (124), production (74), flows SE1/SE3/EE (60, 61, 55). **No ENTSO-E series at all**, and no NO4 flow. | CC BY 4.0 (Fingrid); spot see section 8 | The package's `first_usable_origin_utc` per row |
| | **Fingrid real-time** (`rt_main.csv.gz`, in every band and the pooled model, so at all horizons): surplus/deficit 198 and 186, wind 181 (error against the day-ahead forecast), frequency 177, nuclear 188, net import 194, hydro 191 | CC BY 4.0 | The file's `first_usable_origin_utc` (30 min after the quarter end, rounded up). The lab loader (`experiments/lab/data.py`) trusts the column and does not recompute it ☐. The repo loader's audit (`fu_audit`, `src/data/external_long.py`) reports no early rows for these files. |
| | **Fingrid extra series** (`extra_main.csv.gz`): wind capacity 268 (scales the wind error) and imbalance power FI–SE 176 | CC BY 4.0 | 268: period end + 24 h. 176: ☐ period end + 60 min, unverified (`DELAY_RULES`). Same trust in the file column. |
| | **ECMWF IFS runs** (`runs_ecmwf_ifs_main.csv.gz`, 7 wind-cluster points) for `wind_hat`: wind revision against the day-ahead forecast and a per-step-band estimate of the day-ahead wind error | CC BY 4.0 (Open-Meteo, ECMWF open data) | Run init + 8 h, rounded up (column in the file) |
| | **Fixed numbers fitted on pre-June data:** the wind power curve and the `wind_hat` coefficients are hard-coded in `experiments/lab/features/weather.py`. The curve was fitted once on last autumn's IFS runs and 25 May – 31 Jul 2026 deliveries (target: Fingrid 75 wind, scaled by 268 capacity; ERA5 as a cross-check), the coefficients on 2 Jun – 31 Jul 2026. Nothing is fitted on later data. | as the sources | Fit window ends 31 Jul 2026 21:00 UTC, before every fold |
| | **Fingrid package-series history** (`package_history.csv.gz`, 17 series, 1 Mar 2025 – 31 May 2026): a direction model is fitted on it and blended into P(up) at 60 % in logit space (`hist_blend`, `experiments/lab/exp_history.py`) | CC BY 4.0 | The package's rule for the same series; the code asserts that every history row is usable before the 31 Jul 2026 fitting cutoff. **Pre-June data, allowed on 7 Nov** (`QUESTIONS.md` Q1). |

Abdo's half trains on 2 Jun – 4 Oct 2026 only. It does **not** read: ICON-EU, Nordic wind, the real-time batch 2 (boilers, CHP, border flows), BRP plans (242), production (192), UMM, FMI, ERA5 (apart from the curve cross-check), Elering/Energinet system data, or the balancing-market internals. Lab experiments with those exist (`REGISTRY` in `experiments/lab/combo.py`) but are not in the spec.

**New history model** (Abdo, run on the laptop with `LAB_HISTORY=1`, `experiments/lab/data.py`): the code switch is committed, the result is not (pending). In that mode the lab trains from 5 Mar 2025 on `external_data/history/pkg_history.csv.gz` (package series, Elering spot, rebuilt imbalance price, see 6a), `fingrid/rt_history.csv.gz` (10 real-time series, 1 Mar 2025 – 24 May 2026, same 30-min rule) and market-era flags (`features/regime.py`). It also lists ECMWF history runs `open_meteo/runs_ecmwf_ifs_history_{a,b}.csv.gz`. **These two files are not in `external_data/`** (checked 7 Nov) ☐, so that part of the history model cannot run from this repo.

### Status of every fetched source

| # | Source | Status | Licence |
|---|---|---|---|
| 1 | Starter package: Fingrid, ENTSO-E, Nord Pool spot, calendar | **Used** | CC BY 4.0 (Fingrid, ENTSO-E); Nord Pool spot is licensed data, see section 8 |
| 2 | Fingrid Open Data, real-time 3-min: wind (181), nuclear (188), frequency (177), consumption (193) | **Used** as features in steps 1–8 only; 181 also fits the learned wind-production weights (all steps) | CC BY 4.0 |
| 2b | Fingrid real-time, second batch (Frank's download): 191, 194, 371, 201, 202, 89, 180 | **Used** by `v6_hf`, steps 1–8 only. 192, 87, 187 are in the same file but not read | CC BY 4.0 |
| 3 | Open-Meteo Single Runs: ECMWF IFS 0.25° (`ecmwf_ifs025`), main period | **Used** | CC BY 4.0 (Open-Meteo); ECMWF open data CC BY 4.0 ☐ |
| 4 | Fingrid real-time, other datasets: surplus/deficit (198, 186), production (192), hydro (191); also 194, 209 | **Used by `split_all_rt_icon`** (198, 186, 192, 191; steps 1–8 only). The submitted `v6_hf` does not read these master series: it reads hydro (191) and net import (194) from Frank's own download (row 2b). 192 is not read by `v6_hf` at all. 209 not used | CC BY 4.0 |
| 5 | Fingrid "extra" series (BRP plans, wind capacity, mFRR bids, …) | **Used:** BRP production plans (242), for the plan error in steps 1–8 (`split_all_rt_icon` only); wind capacity (268) and imbalance power FI–SE (176) by Abdo's half of `team5050`. Others fetched, not used (22/251 need organiser approval) | CC BY 4.0 |
| 6 | Open-Meteo: ICON-EU, MET Nordic runs | ICON-EU single runs 25 May - 2 Nov 2026 (00/06/12/18 UTC, 647 of 648 runs; 11 Jun 06 UTC missing), first usable = init + 5 h, in `external_data/open_meteo/icon_eu.parquet`; used by the submitted `v6_hf` and by `split_all_icon` / `split_all_rt_icon` (gain on both folds). MET Nordic: no data, not used | CC BY 4.0 |
| 7 | ERA5 reanalysis (via Open-Meteo) | Fetched, not used yet | Copernicus licence (attribution) ☐ |
| 8 | Nord Pool UMM outage messages | Fetched, not used yet | ☐ public REMIT data; terms unconfirmed |
| 9 | FMI 10-min observations | Fetched, not used yet | CC BY 4.0 |
| 10 | Elering (Estonia) system data | Fetched, not used yet | ☐ open data with attribution |
| 11 | Energinet `PowerSystemRightNow` (Denmark) | Fetched, not used yet | ☐ open data with attribution |
| 11b | **Balancing-market internals** (`fingrid/mfrr2_main.csv.gz`, 25 May – 2 Nov 2026, 18 series: mFRR need 377, bid volumes 373/374, aFRR volumes 349/350, mFRR exchange 381, scheduled/direct activations 385/386/389/390, day-ahead FCR prices 317/318/283, day-ahead transmission capacities 26/27/24/25, **calculated imbalance 397**) | Fetched; lab specs (`lumi/specs_p5b.jsonl`) are **result pending on LUMI**. Not in `v6_hf`, `team5050` or any `src/` model. **397 stays out until the organisers approve it** (near-copy of the target); the committed file contains it | CC BY 4.0 |
| 11c | **aFRR volumes 349/350, history** (`fingrid/afrr_vol_history.csv.gz`, 1 Mar 2025 – 31 May 2026) | Used only to rebuild the pre-June imbalance price (6a); read by `experiments/lab/build_history.py`, not by a model | CC BY 4.0 |
| 12 | **Pre-June history:** `last_autumn` (1 Sep – 30 Nov 2025) tables and `package_history` (Fingrid package series, 1 Mar 2025 – 1 Jun 2026) | **Allowed by the organisers on 7 Nov** (`QUESTIONS.md` Q1). The history the submitted `v6_hf` trains on is Abdo's package-format table (table above); these master tables are not read by any model | as the source of each table |

"Pre-June history" matters because the organisers' README says to train only on 1 Jun – 4 Oct 2026. **The organisers allowed pre-June data on 7 Nov** (`QUESTIONS.md` Q1). The submitted `v6_hf` trains on Abdo's package-format history (`config.HISTORY_PATH`, read by `load_history` in `src/data/load.py`, which never makes a row usable earlier than the package's own rule). The master `last_autumn` and `package_history` tables listed here are not read by any model in `src/`; `src/data/external_long.py` loads them only when asked explicitly.

### Two fetcher families, and which file made which table

| Family | Code | Output in `external_data/` |
|---|---|---|
| **Frank's** (used by the model) | `src/data/fingrid.py` | `fingrid/fingrid_rt.parquet` (14 real-time series, main period: the 4 of section 3 and the 10 of the second batch) |
| | `src/data/open_meteo.py` | `open_meteo/ecmwf_ifs025.parquet` (8 main points), `ecmwf_ifs025_extra.parquet` (6 more points), `ecmwf_ifs025_nordic.parquet` (12 points in SE/NO/DK/EE), `icon_eu.parquet` (8 points); runs 29 May – 2 Nov by default, ICON-EU from 25 May. Which fetcher call made `icon_eu.parquet` is not recorded in the code ☐ (its delay column is 5 h, as `PUBLICATION_DELAY`). |
| **Abdo's** (broader, mostly experiments) | `src/data/external/fingrid.py` | `fingrid/rt_main.csv.gz`, `rt_last_autumn.csv.gz` (10 real-time series), `extra_main.csv.gz`, `extra_last_autumn.csv.gz`, `package_history.csv.gz` |
| | `src/data/external/open_meteo.py` | `open_meteo/runs_ecmwf_ifs_last_autumn.csv.gz`, `era5_main.csv.gz`, `era5_last_autumn.csv.gz` |
| | `src/data/external/umm.py` | `umm/messages_main.csv.gz`, `messages_last_autumn.csv.gz` |
| | `src/data/external/fmi.py` | `fmi/obs_main.csv.gz`, `obs_last_autumn.csv.gz` |
| | `src/data/external/elering.py` | `elering/system_main.csv.gz`, `system_last_autumn.csv.gz` |
| | `src/data/external/energinet.py` | `energinet/power_system_main.csv.gz`, `power_system_last_autumn.csv.gz` |

Periods in Abdo's family (`src/data/external/common.py`): **`main`** = 25 May – 3 Nov 2026 (end exclusive) and **`last_autumn`** = 1 Sep – 1 Dec 2025 (end exclusive). Package-series history: 1 Mar 2025 – 1 Jun 2026.

The two families overlap on purpose (both fetch Fingrid wind, nuclear, frequency and consumption, and both fetch ECMWF IFS). For the weather tables and the first 14 real-time series the model reads **only Frank's tables**; Abdo's master Fingrid series are read only by the live-imbalance features (198, 186, 192, 191, 242) of `split_all_rt_icon`. `load_long_all` loads all of Abdo's main-period series (also 194, 75, 176, 209, 243, 251, 268) for every model that uses Fingrid data, but no feature of `v6_hf` reads them. The tables differ in details (weather points, units, series names), so they must not be mixed in one model. Raw responses are cached under `external_data/**/raw/` and `external_data/_cache/` (git-ignored).

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

## 3. Fingrid Open Data, real-time (used)

| Item | Detail |
|---|---|
| Access | Free API key (`FINGRID_API_KEY` in `.env`, never committed). `https://data.fingrid.fi/api/datasets/{id}/data`. |
| Licence | CC BY 4.0 (✔ as stated by the organisers for Fingrid Open Data) |
| What `split_all` uses | Wind production (181), nuclear production (188), grid frequency (177, Nordic), consumption (193). 3-min values are averaged to quarter-hours (a quarter needs at least 3 samples). Features: wind and consumption error against the day-ahead forecasts, frequency deviation from 50 Hz, nuclear level and 6-hour change (`src/features/build.py`, `FINGRID_RT_COLUMNS`). |
| Availability rule | `first_usable_origin_utc = ceil_to_hour(quarter_end + 30 min)`. This is **our assumption**, copied from the organisers' own delay for measured Fingrid data (consumption, production, flows in `availability.csv`). Fingrid publishes every 1–3 min, so 30 min is conservative. ☐ We have not asked the organisers whether real-time series with our own documented delay are acceptable (PLAN §12). |
| Where it is used | As features only for steps 1–8 (the first 2 hours). The long-horizon model never sees them, except that wind (181) fits the learned wind-production weights. |
| Second batch | `fingrid_rt.parquet` holds 10 more series from the same fetcher and the same rule: 191, 192, 194, 371, 201, 202, 87, 89, 180, 187. `v6_hf` reads 191, 194, 371, 201, 202, 89 and 180 in the short model (`FINGRID_RT2_COLUMNS`). 192, 87 and 187 are not read. |
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

`package_history.csv.gz` holds the same 17 series as the starter package (319, 369, 244, 106, 375, 376, 347, 348, 124, 74, 61, 57, 60, 55, 165, 246, 247) for 1 Mar 2025 – 1 Jun 2026, with the package's delays (60 min for prices and volumes, 30 min for measured series, day-ahead forecasts at 13:00 local on D-1 ☐ verify against `availability.csv`). Not read by any model in `src/` (the submitted `v6_hf` uses Abdo's separate history table, see section 1). The imbalance-price formula changed on 1 Jun 2026, so older rows are for direction and wind-error models, not for price levels. The 2025 spot price is not available, so the 2025 gap cannot be computed.

Balancing-market internals (`mfrr2_main.csv.gz`, group `MFRR2` in `src/data/external/fingrid.py`): period series (377, 373, 374, 349, 350, 381, 385, 386, 390, 389) use period end + 60 min, the same as the package's mFRR data. Day-ahead FCR prices (317, 318, 283) use D-1 23:00 local ☐ and day-ahead capacities (26, 27, 24, 25) D-1 18:00 local ☐. 397 is real-time (rt3, 30 min). These series are **not** in `DELAY_RULES`, so `src/data/external_long.py` does not load them, and the lab loader trusts the file column ☐. The second real-time batch also exists as Abdo's copy `rt2_main.csv.gz` (7 series, from 29 May 2026).

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

## 6a. Details from Abdo's branch

### Extended history, used by `v6_hf` for training (`experiments/lab/build_history.py`, `src/data/external/elering_spot.py`)

The package starts on 1 Jun 2026. To train on more data and to test on **last year's test weeks (5 Oct – 1 Nov 2025)**, we rebuilt the package series back to 1 Mar 2025:

| Series | Source | Check |
|---|---|---|
| 17 Fingrid package series (mFRR/aFRR prices and volumes, direction, flows, consumption, production, day-ahead forecasts) | Fingrid Open Data, same dataset ids as the package | Identical to the package on the overlap (values and `first_usable`) |
| `fi_spot_price` | Elering's Nord Pool price API (hourly before 1 Oct 2025, repeated per quarter) | Identical to `spot_nordpool.csv` on all 14,824 overlapping quarters, same D-1 14:00 availability |
| `fi_imbalance_price` | **Recomputed with the 1 Jun 2026 rule**: volume-weighted mFRR/aFRR price when both act in the dominating direction, else the mFRR price; spot when there is no direction. Uses aFRR volumes (Fingrid 349/350, `fingrid/afrr_vol_history.csv.gz`) | The rule reproduces the official price on 99.5 % of Jun–Oct 2026 quarters (MAE 0.09 €/MWh; the old rule gives 5.45). The raw old-rule price is kept as `fi_imbalance_price_oldrule` |
| calendar | computed like the package (Finnish holidays incl. Midsummer Eve) | |
| Fingrid real-time (198/186/181/…) | `fingrid/rt_history.csv.gz` (Mar–Aug 2025, Dec 2025 – May 2026; Sep–Nov 2025 is in `rt_last_autumn`) | Same delays as `rt_main`. **Lab only:** `load_history` keeps only series the package also has, so `v6_hf` does not read it |
| ECMWF IFS runs | `open_meteo/runs_ecmwf_ifs_history_{a,b}.csv.gz` (00/12 UTC) | Same 8 h delay. **Lab only** (`experiments/lab/data.py`); these two files are not in `external_data/` ☐. `v6_hf` does not read them |

**Price-rule change (Fingrid, 1 Jun 2026):** before, the up-regulation price was max(mFRR marginal, aFRR volume-weighted) and the down price the min. From June, the volume-weighted average of both. Training on old-rule prices would teach the model the wrong formula, so the history target uses the new rule. **Weather and real-time features are empty for history rows** (the weather and real-time tables start in late May 2026), so history only teaches the package-based features. **Not in the history:** the ENTSO-E neighbour series (SE1/SE3/EE imbalance prices, load forecasts, capacities). Our features do not use them.

The lab's history mode (`LAB_HISTORY=1`) uses all of it. It adds **fold C** (train < 5 Oct 2025, validate 5 Oct – 1 Nov 2025) and writes to `leaderboard_hist.csv`.

### Nord Pool UMM outage messages (`src/data/external/umm.py`)

`https://ummapi.nordpoolgroup.com/messages`, no key. We fetch areas FI, SE1, SE3 and EE, and **all versions** (`IncludeOutdated=true`). We save one row per message version × unit × time period. A version is usable at `ceil_hour(publicationDate)`; at each origin, use the **newest usable version** of each message.

> **Example (9 Sep 2026, the most volatile day in validation):** unit **B3 (Olkiluoto 3, 1,600 MW)** tripped at **16:42 UTC**. The message was published at 16:53, so it's usable from the **17:00 origin**. The imbalance price hit **2,640–4,000 €/MWh at 17:15–17:45**. Package-only models can't see this; UMM can.

**Quick check on training quarters** (unplanned Finnish generation outages that are active *and* already published):

| Outage | Quarters | High-spike rate | Mean gap |
|---|---:|---:|---:|
| None | 10,514 | 8.3 % | −3 |
| Any | 1,582 | 13.5 % | +12 |
| > 300 MW | 428 | 2.3 % | +16 |
| **> 800 MW** | 20 | **50 %** | **+527** |

⚠️ **Correction (outages agent, 7 Nov):** the "> 800 MW" row is **one event**, the 9 Sep OL3 trip, and it falls in the validation month. No training row has a fresh trip that large, so a model can't learn it, and none of the UMM feature sets beat the reference on both folds. Recommendation: keep UMM only for a rule-based **insurance override** (a fresh unplanned outage ≥ 800 MW raises spike probability, P(up) and p90) and for the dashboard.

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
