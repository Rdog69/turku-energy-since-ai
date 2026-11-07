# Data sources

> All data we use, how we get it, its licence, and **when each row becomes usable**. This is the deliverable "list of data sources … and their usage rights", and it's also the input to the leakage review.
>
> **The rule for every row, package or external:** it may be used at forecast origin `t` only if `first_usable_origin_utc ≤ t`. Every fetcher in [`src/data/external/`](src/data/external/) writes that column, computed from a **conservative** publication delay and rounded **up** to the next full hour, exactly like the starter package. ☐ marks a delay or licence we have assumed and still need to confirm.

## Overview

| # | Source | Status | Licence | What it adds | Value ☐ |
|---|---|---|---|---|---|
| 1 | **Starter package** (Fingrid, ENTSO-E, Nord Pool spot, calendar) | ✅ In `starter_package/` | CC BY 4.0; spot licensed to Turku Energia | Everything in the package README | Core |
| 2 | **Fingrid Open Data**: real-time 3-min system data | ⏳ **Needs `FINGRID_API_KEY`**; the fetcher is ready | CC BY 4.0 | Finland's **real-time imbalance** (198/186), wind, production, consumption, nuclear, frequency | **Highest**: a fresh state signal |
| 3 | **Fingrid Open Data**: package series from Mar 2025 | ⏳ Needs the key | CC BY 4.0 | Last autumn and winter for the direction and wind-error models | High |
| 4 | **Fingrid Open Data**: extra series | ⏳ Needs the key | CC BY 4.0 | BRP production plans (242), wind capacity (268), mFRR bid sum (243), last bid prices (22/251) | Medium–high |
| 5 | **Open-Meteo Single Runs**: ECMWF IFS, ICON-EU, MET Nordic | ✅ / ⏳ Downloading | CC BY 4.0 (Open-Meteo) | Archived weather-model runs: wind-forecast **revisions** after the day-ahead forecast | High |
| 6 | **ERA5 reanalysis** (via Open-Meteo) | ✅ / ⏳ | Copernicus (attribution) | Actual weather, **training only** (published ~5 days late) | Support |
| 7 | **Nord Pool UMM** (outage messages) | ✅ | ☐ Public REMIT data; confirm use with the organisers | Planned and **unplanned outages** with publication times | Medium–high (see the OL3 example) |
| 8 | **FMI open data**: 10-min observations | ✅ / ⏳ | CC BY 4.0 | Measured wind and temperature at coastal stations | Medium |
| 9 | **Elering**: Estonian system data | ✅ | ☐ Open data with attribution | Estonia's real-time system balance | Low |
| 10 | **Energinet** Energi Data Service | ✅ | ☐ Open data with attribution | DK aFRR activation, DK2–SE exchange | Low |
| 11 | **Extended history** (Mar 2025 – May 2026) in package format | ✅ `external_data/history/pkg_history.csv.gz` | Fingrid CC BY 4.0; spot from Elering (originates from Nord Pool: team-internal use only, never redistributed) | 15 months of training data instead of 4, and a fold on last year's test weeks | ☐ Being tested |

Periods fetched: **`main`** = 25 May – 2 Nov 2026 (training + test + one week for lags) and **`last_autumn`** = 1 Sep – 30 Nov 2025, the closest seasonal analogue of the test period. The Fingrid package series are fetched continuously from 1 Mar 2025.

---

## 2–4. Fingrid Open Data (`src/data/external/fingrid.py`)

**Access:** a free API key (instant sign-up at [data.fingrid.fi](https://data.fingrid.fi)), stored as `FINGRID_API_KEY` in `.env`. Rate limit: 1 call per 2 s and 10,000 per day. We use the same settings as the organisers' `build_dataset.py`.

```bash
python -m src.data.external.fingrid check        # prints the official name of every ID (verify before use)
python -m src.data.external.fingrid fetch all    # rt | package | extra | all
```

**Real-time 3-min datasets.** They're averaged per quarter-hour. A quarter is usable at `ceil_hour(quarter_end + RT_DELAY)`, with **RT_DELAY = 30 min by default** ☐ (`FINGRID_RT_DELAY_MIN`). This is the same delay the package uses for measured data; ask the organisers whether a shorter delay is acceptable.

| ID | Dataset | Why it matters |
|---|---|---|
| **198** | Electricity production, surplus/deficit (real time): "difference between measured net import/export and the **confirmed net exchange program**" | **This is Finland's imbalance against its plan, measured live.** It's the state the package only shows 75 min late through prices |
| **186** | Surplus/deficit, cumulative (real time) | The same, accumulated over the hour |
| 181 | Wind power production (real time) | **Wind forecast error** = 181 − day-ahead forecast 246 |
| 192 / 193 | Production / consumption (real time) | Consumption error vs forecast 165 |
| 194 | Net import/export (real time) | Flow state |
| 188 / 191 | Nuclear / hydro (real time) | Reactor trips show up within minutes (see the OL3 example) |
| 177 | Frequency (real time, Nordic) | An instantaneous Nordic imbalance signal |
| 209 | Power system state (real time) | The operating state of the Finnish system (five levels) |

**Package series history** (319, 369, 244, 106, 375, 376, 347, 348, 124, 74, 61, 57, 60, 55, 165, 246, 247), 1 Mar 2025 – 1 Jun 2026, with the same delays as `availability.csv`.
- The imbalance-price **formula changed on 1 Jun 2026**. Use the older rows for the **direction** and **wind-error** models, not for price magnitudes.
- Last year's **spot price isn't available** (see "Not used"), so the 2025 gap to spot can't be computed.

**Extra series:**

| ID | Dataset | Availability rule |
|---|---|---|
| **242** | Production plans from balance responsible parties (BRPs), "published daily by 18:00 for the next day", not revised | D-1 18:00 local. **The plan**: measured production − plan = plan error |
| 268 | Wind capacity used in Fingrid's wind forecast (manual) | Period end + 1 day. Lets us normalise wind by capacity |
| 243 | Sum of up-regulation bids in the balancing energy market | Hour h published at h+2. Shows how deep the merit order is |
| 22 / 251 | Price of the last activated up / down bid (real time "when Finland is a separate regulation area") | ☐ Period end + 60 min. Check coverage under the Nordic mFRR market |
| 176 | Imbalance power between Finland and Sweden (hourly) | ☐ Delay unverified |
| 75 | Wind power generation, 15-min averages | Period end + 30 min |

⚠️ **Never** use Fingrid's continuously updated forecasts (e.g. 245 wind, 241 production): only the latest version is stored, so their history leaks.

## 5–6. Open-Meteo (`src/data/external/open_meteo.py`)

No key; free tier: 600 calls per minute, 5,000 per hour, 10,000 per day. We request 8 locations per call. **Single Runs API only**: the Historical Forecast API leaks and is not recommended by the organisers.

| Model | Runs fetched | Archive | Measured delay (6 Nov) | Our delay |
|---|---|---|---|---|
| `ecmwf_ifs` (IFS HRES 9 km) | `main`: 00/06/12/18 UTC; `last_autumn`: 00/12 | since Mar 2024 | 7.1 h | **8 h** |
| `icon_eu` | `main`: 00/06/12/18 | since 2 Apr 2026 | 3.9 h | **5 h** |
| `metno_nordic` (MET Nordic, 10 m wind only) | `main`: 00/06/12/18 | since 2 Apr 2026 | 0.8 h | **2 h** |

The measured delays come from each model's `/data/<model>/static/meta.json`; our delays round them up. Rows are usable at `ceil_hour(run_init + delay)`. Each run covers 48 h ahead (24 h for MET Nordic).

**Locations** (`POINTS` in `common.py`): seven wind clusters (Kristiinankaupunki, Vaasa, Kokkola, Lestijärvi, Kalajoki, Raahe–Pyhäjoki, Ii–Simo) and Helsinki for load. **Variables:** 100 m and 10 m wind speed, 100 m wind direction, gusts, temperature, humidity (for an icing proxy), shortwave radiation, cloud cover.

**ERA5** (`archive-api`) at the same points. It's reanalysis, available about 5 days late, so `first_usable_origin_utc` = valid time + 6 days. **Use it only to fit mappings** (e.g. wind speed → wind power), never as a forecast-time feature.

## 7. Nord Pool UMM (`src/data/external/umm.py`)

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

## 8. FMI open data (`src/data/external/fmi.py`)

WFS stored query `fmi::observations::weather::simple`, no key, CC BY 4.0. 10-min wind speed, direction, gusts, temperature and humidity at Vaasa, Kokkola, Kalajoki, Raahe, Oulunsalo, Kemi, Pori and Helsinki. Usable at `ceil_hour(time + 20 min)` ☐.

## 9–10. Elering and Energinet (low priority)

- **Elering** `dashboard.elering.ee/api/system`: Estonian production, consumption and **system balance**, 15-min in 2026. Usable at time + 60 min ☐. Since Feb 2025 Estonia is synchronised with Continental Europe, so its frequency is not Nordic.
- **Energinet** `api.energidataservice.dk/dataset/PowerSystemRightNow`: 1-min DK aFRR activation, DK–SE exchange and wind, averaged per quarter. Usable at quarter end + 15 min ☐.

## 11. Extended history (`experiments/lab/build_history.py`, `src/data/external/elering_spot.py`)

The package starts on 1 Jun 2026. To train on more data and to test on **last year's test weeks (5 Oct – 1 Nov 2025)**, we rebuilt the package series back to 1 Mar 2025:

| Series | Source | Check |
|---|---|---|
| 17 Fingrid package series (mFRR/aFRR prices and volumes, direction, flows, consumption, production, day-ahead forecasts) | Fingrid Open Data, same dataset ids as the package | Identical to the package on the overlap (values and `first_usable`) |
| `fi_spot_price` | Elering's Nord Pool price API (hourly before 1 Oct 2025, repeated per quarter) | Identical to `spot_nordpool.csv` on all 14,824 overlapping quarters, same D-1 14:00 availability |
| `fi_imbalance_price` | **Recomputed with the 1 Jun 2026 rule**: volume-weighted mFRR/aFRR price when both act in the dominating direction, else the mFRR price; spot when there is no direction. Uses aFRR volumes (Fingrid 349/350, `fingrid/afrr_vol_history.csv.gz`) | The rule reproduces the official price on 99.5 % of Jun–Oct 2026 quarters (MAE 0.09 €/MWh; the old rule gives 5.45). The raw old-rule price is kept as `fi_imbalance_price_oldrule` |
| calendar | computed like the package (Finnish holidays incl. Midsummer Eve) | |
| Fingrid real-time (198/186/181/…) | `fingrid/rt_history.csv.gz` (Mar–Aug 2025, Dec 2025 – May 2026; Sep–Nov 2025 is in `rt_last_autumn`) | Same delays as `rt_main` |
| ECMWF IFS runs | `open_meteo/runs_ecmwf_ifs_history_{a,b}.csv.gz` (00/12 UTC) | Same 8 h delay |

**Price-rule change (Fingrid, 1 Jun 2026):** before, the up-regulation price was max(mFRR marginal, aFRR volume-weighted) and the down price the min. From June, the volume-weighted average of both. Training on old-rule prices would teach the model the wrong formula, so the history target uses the new rule. **Not in the history:** the ENTSO-E neighbour series (SE1/SE3/EE imbalance prices, load forecasts, capacities). Our features do not use them.

The lab's history mode (`LAB_HISTORY=1`) uses all of it. It adds **fold C** (train < 5 Oct 2025, validate 5 Oct – 1 Nov 2025) and writes to `leaderboard_hist.csv`.

## Checked and not used (yet)

| Source | Why not |
|---|---|
| **Last year's spot price** (needed for the 2025 gap) | Nord Pool data is licensed. The free mirror at api.energy-charts.info says "private and internal use only… external use prohibited". ☐ **Ask the organisers** whether they can extend the spot file back to Sep 2025. |
| ENTSO-E API | A token takes several working days |
| Fingrid 245 / 241 (updated forecasts) | Only the latest version is stored, so they leak |
| Open-Meteo Historical Forecast API | Leaks; not recommended by the organisers |
| Statnett, Svenska kraftnät | Live dashboards respond, but no verified history API |
| SMHI / MET Norway observations | Available, but far from Finnish wind |
| NOAA GEFS ensembles | Large raw files; Open-Meteo's single runs cover the deterministic signal |
| eSett open data | Settlement data, published days later (ex-post) |

Kimi K3.1 Pro's suggestions for further sources: [`docs/data_sources/kimi_suggestions.md`](docs/data_sources/kimi_suggestions.md).

## Components (software)

Python, pandas, NumPy, pyarrow, scikit-learn / LightGBM (MIT / BSD / Apache 2.0). LLM text in the dashboard: Featherless.ai (open-weight models), downstream of the forecast only.
