# Deliverables: submission checklist

Everything we must hand in, where each requirement comes from, and where it is met. **Deadline: Sun 8 Nov 2026, 10:00 Finnish time, through the Since AI platform.** The team freezes the model in the 06:00–09:00 window.

The submitted documents themselves live on the team branch **`deliverables`** (one folder per item, maintained by Abdo; links below are to that branch). This folder is the checklist that ties them to the rules. Last checked: Sat 7 Nov 2026, late evening.

**Sources of the requirements:**
- **Brief:** `starter_package/TurkuEnergia_SinceAI2026/1_Turku_Energia_Challenge_Brief_EN.pdf`, sections 02 (deliverables), 06 (scoring) and 07 (submission format).
- **Starter README:** `starter_package/v1/starter_package_v1/README.md`, sections 1, 2, 5.1 and 10.
- **READ_ME_FIRST:** `starter_package/TurkuEnergia_SinceAI2026/READ_ME_FIRST.txt` (the spot-data terms).
- **MLH:** the DevRelay knowledge base, guide `mlh-hackers` (verified 30 Sep 2026, sourced from mlh.com and github.com/MLH/mlh-policies). Only applies if Since AI 2026 is an MLH Member Event, which we have not confirmed.

Status: ✅ done and checked · 🟡 exists, needs a final step · ❌ missing · ❓ needs an answer from the organisers

## 1. Level 1: what the submission must include (brief §07)

| # | Requirement | Status | Where | Still to do |
|---|---|---|---|---|
| 1 | Machine-readable forecast file in the starter-package format, **checked with the validation script** | ✅ | `deliverables` branch: `forecast/forecast_backtest.csv`. SHA-256 `923d508e…ae30eb`, byte-identical to `submissions/blend_v7_rt_h_int4ss_test.csv` here. Validator: 26,920 rows, 0 errors, 0 warnings | Re-run the validator on the exact file uploaded; upload it named `forecast_backtest.csv` |
| 2 | Source code and instructions for running it | 🟡 | `deliverables`: `code/README.md` (run order for both halves and the blend); code on `brainstorming-frank` (`src/`, `submissions/tools/`) and `brainstorming-abdo` (`experiments/lab/`) | Record the final commit hashes of both branches in `code/README.md` at the freeze |
| 3 | Short evaluation report: reasoning chain, factors affecting the forecast, validation-period metrics | 🟡 | `deliverables`: `report/evaluation_report.md`, `model/README.md` | Merge Jim's points (planned); check the numbers match the final blend (Sep 40.19 / 11.07 / 0.0840 / 0.3799) |
| 4 | Data sources, external services, ready-made models and software components, with their usage rights | ✅ | `deliverables`: `sources/SOURCES_AND_LICENCES.md` (covers the package, Fingrid, Open-Meteo, Elering, OSM, LightGBM, React/Vite/d3/lucide, Source Sans 3, Featherless, Claude) | Add any source used after 7 Nov (for example ECMWF HRES, if `v10_hres` makes it in) |
| 5 | About 5–8 presentation slides | ❌ | `deliverables`: `slides/README.md` is a placeholder; Jim's draft on `brainstorming-jim`: `reports/slides.*` | Finish and export `slides/slides.pdf` |
| 6 | Demo video, **at most 5 minutes**: the next 10 h in 15-minute periods, the uncertainty, significant deviations, the main factors | ❌ | `deliverables`: `video/README.md` has an outline; Jim's script on `brainstorming-jim`: `reports/demo_video_script.md` | Record it. Update the outline: the dashboard now has one **Overview** page (not Simple/Trader), scrolling in 15-minute steps, a period slider under the graph |

## 2. Level 2: added value if the demo shows it (brief §02, §06, §07)

| Requirement | Status | Where |
|---|---|---|
| A user interface showing only the situations that matter (spike risk up, up/down regulation expected, forecast changed materially, conflicting models, worth an expert review) | ✅ | `frontend/` (here) and `front-end` branch: "Worth checking" items, alerts for each of those five situations |
| Two time horizons: now and the next 10 hours, plus hindsight (previous day, week or month) | ✅ | Overview page; hindsight panel under "Show details" |
| Moving the review point into the past | ✅ | Period slider, scrolling and drag in 15-minute steps, Play |
| Reasoned "check this" suggestions (never trading instructions) | ✅ | Side panel per item ("Check the intraday position for…"); Production view |
| **"Plus an API from which this information can be retrieved"** (brief §02, Level 2) | 🟡 | Not in the submitted dashboard. Jim has a FastAPI backend on `brainstorming-jim` (`api/main.py`) that reads an older forecast file | Decide: point Jim's API at the final file and mention it, or leave it out (it is described as part of the Level 2 result, not a Level 1 must) |
| The dashboard shows the **submitted** forecast | ✅ | `frontend/scripts/build_data.py` reads `submissions/blend_v7_rt_h_int4ss_*.csv` and checks that the two halves reproduce it exactly |

## 3. Rules we must not break

| Rule | Source | Status | Evidence |
|---|---|---|---|
| A row is used only from its `first_usable_origin_utc`; a leak scores 0. The best solutions' code is reviewed (AI-assisted) | Brief §06; starter README §4 | ✅ | `tests/test_availability.py` and the rest: 21 tests pass. Weather runs: run time + 8 h (ECMWF) / + 5 h (ICON). Fingrid real-time: 30-min rule |
| Train on data up to 4 Oct only; test-period inputs must not be used for training | Starter README periods table | ✅ | Training cutoff in `src/config.py`; organisers' Q&A allows pre-June data (`QUESTIONS.md` Q1) |
| Run the validator before submitting | Starter README §2, §10 | ✅ | See item 1 |
| One forecast file, no example forecast | Starter README §10 | ✅ | Only `forecast_backtest.csv` |
| Nord Pool spot data: hackathon use only, no redistribution, no public repository, delete after the event | READ_ME_FIRST.txt | ✅ / ⏳ | The repository is private (anonymous access returns 404). `frontend/public/payload.json` and `frontend/bundle.html` hold spot prices and are git-ignored; the `deliverables` branch holds none. **After the event: delete the package, `external_data/history/` and both front-end files** |
| Present the dashboard locally, not hosted | READ_ME_FIRST.txt | ✅ | Offline `frontend/bundle.html`, git-ignored |

## 4. Since AI platform

| Item | Status |
|---|---|
| Deadline Sun 8 Nov 10:00 | ✅ known; plan to upload by 09:00 |
| File size limits and the exact upload fields | ❓ "given in the Since AI event instructions" (starter README §10): not in the repository. Check the event instructions or ask in the Turku Energia channel on Discord |
| Who uploads | ❓ no single designated submitter yet: agree who presses submit, and send them the file and its SHA-256 |

## 5. If Since AI 2026 is an MLH Member Event (unconfirmed)

Standard MLH submission fields and rules, per the DevRelay `mlh-hackers` guide. Check with the organisers whether they apply here.

| MLH expectation | Conflict or action |
|---|---|
| Every team member registered and added to the project | Check all five of us are on the platform's project |
| **Public code link**, kept public after the event | ❓ Conflicts with the spot-data licence (no public repository). The spot data is not in git, but the repository was never cleared for publishing. Ask the organisers before making anything public |
| **State which generative AI tools were used, and how** (MLH's recommended rule: undisclosed AI use can disqualify) | Say it on the submission form: Claude Code (code, analysis), Featherless (LLM briefings in the earlier dashboard). `sources/SOURCES_AND_LICENCES.md` already lists them |
| "Built with" list of technologies | Python, LightGBM, pandas, React, Vite, Tailwind, d3, Open-Meteo, Fingrid API |
| No work before the event | Work started on 6 Nov (first commit `c1e90f3`, 6 Nov 20:14) |
| No new features after the deadline | Freeze at 09:00 |

## 6. Final-hour sequence

1. Freeze both branches; write the commit hashes into `code/README.md`.
2. `sha256sum forecast_backtest.csv` → must be `923d508ef1738ecd7daf8b10caf1abfd1ec47c240269d3a636ffcba097ae30eb`.
3. `python validate_submission.py --backtest forecast_backtest.csv --origins forecast_origins.csv` → 0 errors.
4. Upload the forecast, the slides PDF, the video (or its link) and links to the report, sources and code on the Since AI platform.
5. Screenshot the confirmation.
