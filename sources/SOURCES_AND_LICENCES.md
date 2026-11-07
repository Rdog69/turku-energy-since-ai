# Data sources, external services, models and software

## Data used by the submitted forecast

| Source | What we use | Licence / terms |
|---|---|---|
| **Starter package** (Fingrid, ENTSO-E, calendar) | Imbalance price (the target), mFRR/aFRR prices and volumes, direction, consumption, production, cross-border flows, day-ahead wind/solar/consumption forecasts, neighbour imbalance prices, calendar | Fingrid and ENTSO-E data: CC BY 4.0 |
| **Nord Pool day-ahead price** (starter package) | The anchor of every forecast | Licensed to Turku Energia for the hackathon only: used inside the team, not redistributed or published, deleted after the event |
| **Fingrid Open Data API** ([data.fingrid.fi](https://data.fingrid.fi)) | Real-time 3-minute series (surplus/deficit, wind, frequency, nuclear, hydro, electric boilers, CHP, flows); the package's series for Mar 2025 – May 2026; aFRR activated volumes (datasets 349/350) to rebuild pre-June prices with the June 2026 rule | CC BY 4.0 |
| **Elering** Nord Pool price feed ([dashboard.elering.ee](https://dashboard.elering.ee)) | Finnish day-ahead prices before 1 June 2026 (history only) | The prices originate from Nord Pool: team-internal use only, not redistributed |
| **Open-Meteo Single Runs API** ([open-meteo.com](https://open-meteo.com)) | Archived ECMWF IFS and DWD ICON-EU forecast runs (wind, temperature) at Finnish wind-farm locations and Nordic points | CC BY 4.0 (Open-Meteo); ECMWF and DWD open data |
| **OpenStreetMap** | Wind-turbine locations, for capacity weights of the weather points | ODbL 1.0 |

Each source has a documented publication delay. Every row is used only from its `first_usable_origin_utc`, rounded up to the next full hour (see `SOURCES.md` on `brainstorming-abdo` and `brainstorming-frank`).

**Downloaded and tested, but not in the submitted forecast:** FMI station observations, ERA5 reanalysis, Nord Pool outage messages (UMM), Elering's Estonian system data, Energinet's Danish data, Fingrid's balancing-market internals. All are open data with attribution; see the report, section 8.

## Software

| Component | Use | Licence |
|---|---|---|
| Python 3, pandas, NumPy | Data handling | PSF, BSD-3 |
| LightGBM | The forecasting models | MIT |
| scikit-learn | Calibration, baselines | BSD-3 |
| LightGBM TreeSHAP contributions | `top_drivers` | MIT (part of LightGBM) |
| pyarrow | Reading the package | Apache-2.0 |
| React, Vite, TypeScript | The situational view | MIT, MIT, Apache-2.0 |
| Tailwind CSS, Radix UI / shadcn/ui | The situational view | MIT |
| d3-scale, d3-shape, lucide-react | Charts and icons | ISC |
| Source Sans 3 font | The situational view | SIL OFL 1.1 |

## External services and AI tools used in development

| Service | Use |
|---|---|
| Claude Code (Anthropic) | Coding assistant for the pipelines, the experiments and the situational view |
| Featherless AI (open-weight LLMs) | Brainstorming model ideas. No spot prices were ever sent |
| CSC LUMI supercomputer | Training and experiment runs (project 462001520) |
| Lovable | Early dashboard prototype (Frank) |

No ready-made forecasting model is used. Both models are trained from scratch on the data above.
