# Data sources, external services, models and software

> Pre-filled from `brainstorming-abdo` `SOURCES.md`. Merge Frank's list (OpenStreetMap turbines, his weather points) and check every row against what the final code actually uses.

## Data

| Source | What we use | Licence / terms |
|---|---|---|
| Starter package (Fingrid, ENTSO-E, calendar) | Imbalance price, mFRR/aFRR, consumption, production, flows, day-ahead forecasts | CC BY 4.0 |
| Nord Pool spot price (starter package) | Day-ahead price | Licensed to Turku Energia for the hackathon only; not redistributed; deleted after the event |
| Fingrid Open Data API | Real-time 3-min data, balancing-market series, package series back to Mar 2025 | CC BY 4.0 |
| Elering Nord Pool price feed | Finnish day-ahead prices before 1 Jun 2026 (history) | Originates from Nord Pool; team-internal use only |
| Open-Meteo Single Runs API (ECMWF IFS, ICON-EU) | Archived weather-forecast runs at wind-farm locations | CC BY 4.0 (Open-Meteo) |
| OpenStreetMap | Wind-turbine locations for capacity weights (Frank) | ODbL |
| TODO | FMI, ERA5, UMM, Energinet: list only if the final code uses them | |

## Software

| Component | Licence |
|---|---|
| Python, pandas, NumPy, scikit-learn, LightGBM | PSF / BSD / BSD / BSD / MIT |
| React, Vite, Tailwind CSS, Radix UI / shadcn/ui, d3-scale, d3-shape, lucide-react | MIT / MIT / MIT / MIT / ISC / ISC |
| Source Sans 3 font | SIL OFL 1.1 |
| TODO | Frank's and Jim's extra packages (FastAPI, SHAP, ...) |

## External services and ready-made models used in development

| Service | Use |
|---|---|
| Claude Code (Anthropic) | Coding assistant |
| Featherless (Kimi, Qwen) | Brainstorming; Frank's LLM briefings (Qwen2.5-32B), facts only, no spot prices sent |
| CSC LUMI supercomputer | Training runs (project 462001520) |
| Lovable | Frank's dashboard prototype |
