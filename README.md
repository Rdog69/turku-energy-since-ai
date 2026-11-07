# Turku Energia imbalance-price forecast: submission

What we hand in on the Since AI platform, one folder per deliverable (challenge brief, section 07). Deadline: **Sun 8 Nov 2026, 10:00**. Each folder's README says what goes in it and what is still missing.

| # | Deliverable | Folder | Status | Owner |
|---|---|---|---|---|
| 1 | Forecast file `forecast_backtest.csv` (validated) | [`forecast/`](forecast/) | Candidate in place: ½ Frank `v7_rt` + ½ Abdo `h_int4ss` | Team decision |
| 2 | Source code and instructions for running it | [`code/`](code/) | Placeholder | Abdo + Frank |
| 3 | Short evaluation report: reasoning chain, drivers, validation metrics | [`report/`](report/) | Skeleton with the validation numbers | Jim (draft on `brainstorming-jim`) |
| 4 | Data sources, external services, models, software, licences | [`sources/`](sources/) | Pre-filled list | Abdo |
| 5 | 5–8 presentation slides | [`slides/`](slides/) | Placeholder | Jim (draft on `brainstorming-jim`) |
| 6 | Demo video, at most 5 minutes | [`video/`](video/) | Placeholder (script outline) | Team |
| L2 | Situational view (dashboard) | [`dashboard/`](dashboard/) | Built: branch `front-end` | Abdo + Frank |

## Scoring reminders (challenge brief, section 06)

- Total = 0.8 × Level 1 + 0.2 × Level 2. Level 1: accuracy (MAE) 30, calibration (pinball) 20, exceptional prices (spike Brier) 20, direction (Brier) 10, **reasoning chain 20 (jury: report + slides + video)**.
- The source code of the best solutions is reviewed for leakage (AI-assisted): every input row must be used only from its `first_usable_origin_utc`.
- **Nord Pool spot prices** are licensed for the hackathon only: no publication in public repositories; delete after the event. Nothing in this branch contains spot prices.
