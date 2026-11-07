# Questions for the Turku Energia challenge provider

**Prepared:** 7 November 2026<br>
**Status:** not sent; no provider answer is assumed or invented.<br>
**Order:** Q0–Q5 first, Q8 next if the UI scope is unclear, then Q7; Q6 must not block the safety submission.<br>
**Companion documents:** [milestone audit](MILESTONE_2026-11-07.md) · [prioritized roadmap](ROADMAP_2026-11-07.md)

The repository already resolves the scorer formulas, row weighting, availability rule, spike/direction labels, baseline design, validation/test edge handling, and required artifact list. The questions below cover only decisions that can materially change eligibility, leakage risk, submission acceptance, or jury-facing work.

## Short copy-ready version

> **Q0 — Pre-June training exception.** The rules say to train only on 1 June–4 October 2026. May we use externally sourced imbalance history from March 2025–May 2026 if older prices are recomputed with the 1 June 2026 pricing rule and every feature respects its original availability time? Please answer separately for (a) direction-history features/priors and (b) price/quantile model training. If not, we will use the `v4_n50` lineage with `pre_june_data: false`.
>
> **Q1 — External Fingrid history.** May we use externally fetched realised wind, production, system-state, and frequency series in scored backtests? For each permitted series, what conservative publication delay should apply to an hourly origin? When today's API returns a corrected historical value, may we use it with that delay, or must we reconstruct the first-published vintage? If original vintages are required but unavailable, must the series be excluded?
>
> **Q2 — Open-Meteo Single Runs.** Is a run eligible when `ceil_to_hour(run_init + publication_delay) <= forecast_origin`? What publication-delay evidence is acceptable for ECMWF IFS and ICON, can archived runs be overwritten, and should a missing run remain missing or may we fall back to an older eligible run? Is coverage for 1 June–2 November 2026 our own validation responsibility?
>
> **Q3 — Fixed features versus test-period adaptation.** With all fitted model/calibration/hyperparameter parameters frozen after 4 October, may the model compute at each test origin, only from rows already passing `first_usable_origin_utc`: (a) trailing imbalance/direction/spike statistics, and (b) errors of our own earlier forecasts against already usable actuals? Does either count as prohibited test training or adaptive recalibration?
>
> **Q4 — Nord Pool-derived outputs and hosted tools.** For forecasts or analysis computed using the licensed Nord Pool spot, please answer `public / private submission only / prohibited` for: forecast quantiles and gaps; actual spot curves; aggregate metrics/charts; SHAP/top-driver labels; and dashboard screenshots/video. May any of these be sent to hosted Lovable, Featherless, n8n, Discord, or Teams, or must spot-derived outputs remain local?
>
> **Q5 — Submission mechanics.** What is the current official upload deadline with timezone, and the size/format limits for CSV, report, slides, and video? Should code/UI be supplied as ZIP, public or organiser-accessible private repository, and/or live URL? Has any official deadline extension or removal been granted?
>
> **Q8 — UI/API and replay.** Is a working UI required for eligibility or only Level 2 credit? Is an API mandatory for Level 2? Do (a) local historical replay over precomputed test origins and (b) static per-origin JSON consumed by the UI satisfy the demo/API expectations without live integration?
>
> **Q7 — Jury rubric.** What scoring increments and sub-weights apply to reasoning clarity/consistency/inventiveness across report, slides, and video, and to Level 2 clarity/usability, two horizons, time travel, and inventiveness? Are alerts/review suggestions capped inside Level 2 or additive? May the same demo evidence support both reasoning and Level 2?
>
> **Q6 — UMM and Energinet.** Are versioned Nord Pool UMM outage messages, filtered by each version's `publicationDate`, and Energinet `DayAheadPrices` permitted for model/dashboard features? Please identify any attribution/storage restrictions, or confirm that third-party permission remains entirely our responsibility.

---

## Q0 — Pre-June history and the current leading candidates

**Priority:** P0 — training eligibility / model selection

### Exact question

> The starter rules state: “1 Jun – 4 Oct 2026. Train your model only on this data.” May we use external imbalance history before 1 June if (1) the values are recomputed to reflect the 1 June 2026 mFRR+aFRR pricing rule, (2) no test-period data are used, and (3) all features respect their original publication/availability timestamps? Please answer separately for direction-only priors and for price/quantile target training.

### Why it is necessary now

The shared scoreboard marks `team5050`, `v6_hf`, `P2 INT4+ss lgb7`, and `final_greedy` as using pre-June data. `v4_n50` is marked `pre_june_data: false`. The scorer can evaluate either kind of file; a successful scorer run does not settle training eligibility.

### Safe interim

- Treat pre-June training as **not allowed unless a written exception is granted**.
- Keep `v4_n50` as the leading two-fold official candidate without this particular conflict.
- Do not describe pre-June price reconstruction as automatically permitted merely because external data are generally allowed.

Local references: `starter_package/README.md` training-cutoff sections; `docs/brainstorm/round2/context/briefing_transcript.txt`; `scoreboard/entries/*.json`.

## Q1 — External Fingrid values, delays, and revisions

**Priority:** P0 — leakage / external-feature go/no-go

### Exact question

> For scored backtests, may we use externally fetched Fingrid real-time series for realised wind, nuclear/hydro production, system state, and frequency? For each permitted series: (a) what fixed publication delay should we add before an hourly origin; and (b) when today's API returns a historically corrected value, may we use that value with a conservative delay, or must we reconstruct the first-published vintage? If original vintages are required but unavailable, must the series be excluded?

### Why

Package rows have binding availability timestamps, but external API history can contain later corrections. The repository's 15–30-minute assumptions are conservative only about timing; they do not prove that the value itself was the first-published version.

### Safe interim

Exclude externally fetched revised histories from scored features until answered, or retain a package-only fallback. Do not treat an open licence or a conservative delay as proof of as-of correctness.

## Q2 — Open-Meteo Single Runs eligibility and missing runs

**Priority:** P0 — weather-feature leakage / coverage

### Exact question

> For an Open-Meteo Single Runs archive fetched today, is a run eligible when `ceil_to_hour(run_init + publication_delay) <= forecast_origin`? Please specify acceptable publication-delay evidence for ECMWF IFS and ICON, whether archived runs can be overwritten, and what to do when a run is absent: emit a missing feature or fall back to an older eligible run? Can you confirm archive coverage for 1 June–2 November 2026, or is coverage our own validation responsibility?

### Why

The organiser materials permit Single Runs but do not provide a complete numeric delay/revision/coverage policy. The team's +7/+8-hour and +4/+5-hour variants are assumptions unless independently evidenced. The Historical Forecast API is not a safe substitute for a missing eligible run.

### Safe interim

No weather feature without per-run eligibility and coverage checks. Missing runs stay missing or use only an older run that independently passes the same cutoff; never borrow a later run.

## Q3 — Fixed target-derived features versus online adaptation

**Priority:** P0 — test-period training boundary

### Exact question

> We understand that no model, calibration, or hyperparameter fitting may use data after 4 October. Please confirm separately whether a completely fixed fitted model may compute, at each test origin and only from rows already passing `first_usable_origin_utc`: (a) trailing imbalance/direction/spike statistics; and (b) features based on errors of our own earlier forecasts against already usable actuals. Does either count as prohibited test training or adaptive recalibration?

### Why

Ordinary availability-safe lag features and online residual adaptation are different operations. A blanket “external/test features allowed” answer would not resolve the second. Adaptive conformal and learned error corrections depend on this boundary.

### Safe interim

Keep model and calibration frozen; use only established availability-safe lag features. Do not update calibration or learn from test-period residuals without explicit approval.

## Q4 — Nord Pool-derived forecasts, public UI, and hosted services

**Priority:** P0 — licence / repository / demo go/no-go

### Exact question

> Please answer `allowed publicly / private submission only / prohibited` for each artifact computed using licensed Nord Pool spot: (a) forecast P10/P50/P90 and imbalance-minus-spot values; (b) the actual spot curve; (c) aggregate validation metrics and charts; (d) SHAP values/top-driver labels; and (e) public dashboard screenshots/video. May any of (a), (c), or (d) be sent to hosted Lovable, Featherless, n8n, Discord, or Teams, or must all spot-derived outputs remain local?

### Why

The supplied terms clearly restrict raw spot sharing, but the derived-output boundary is not explicit. Current workflows include forecasts, hosted UI/briefing tools, and a private repository with starter data in parts of its history.

### Safe interim

Keep the repository private; keep spot, forecasts, derived charts, and LLM prompts local; submit required artifacts only through the approved private channel. Do not make the repository public or purge only the latest files while leaving restricted history.

## Q5 — Current deadline and submission mechanics

**Priority:** P0 — submission acceptance

### Exact question

> What is the current official upload deadline, including timezone, and the file-size/format limits for the CSV, report, slides, and video? Should code/UI be uploaded as a ZIP, public repository link, private repository with organiser access, and/or a live URL? Has any deadline extension or removal been officially granted?

### Why

The main README says Sunday 8 November at 10:00, while the internal automation handoff says “deadline was removed.” The latter may refer only to the internal research loop. The starter README delegates exact mechanics to event instructions.

### Safe interim

Prepare for the earlier repository-stated deadline until the provider explicitly says otherwise.

## Q6 — UMM and Energinet reuse

**Priority:** P1 — optional external-data value / licence

### Exact question

> From the challenge-rules perspective, are (a) versioned Nord Pool UMM outage messages allowed in the model/dashboard when filtered by each version's `publicationDate`, and (b) Energinet `DayAheadPrices` allowed for FI–SE day-ahead spreads? Please state any attribution/storage restriction beyond keeping raw licensed data out of Git. If you cannot grant third-party rights, please confirm that these sources are simply our own licensing responsibility.

### Why

These optional sources could add outage and cross-border context, but only versioned publication times can prevent hindsight leakage; their third-party reuse terms are separate from the starter-package permission.

### Safe interim

UMM is optional dashboard context until its version and publication handling is implemented. Omit Energinet-derived features until licensing and as-of handling are documented. Do not imply that Energinet provides an EE area if its listed areas do not include EE.

## Q7 — Reasoning-chain and Level 2 jury rubric

**Priority:** P1 — allocation of jury-facing work

### Exact question

> Please provide the jury rubric: (a) are 0–5 scores assigned in half-point steps or another increment; (b) what sub-weights apply to reasoning clarity, consistency, and inventiveness, and to the evaluation report, slides, and video; (c) what sub-weights apply to Level 2 clarity/usability, two time horizons, time travel, and inventiveness; (d) are alerts and review suggestions inside the Level 2 0–100 cap or additive extra credit; and (e) may the same demo evidence contribute to both reasoning and Level 2?

### Why

Official materials identify the criteria and overall scales but not all operational sub-weights. The response should drive report/UI effort, not last-minute model changes.

## Q8 — UI/API eligibility and acceptable replay implementation

**Priority:** P1 — Level 2 / required-deliverable scope

### Exact question

> Is a working UI required for submission eligibility or only for Level 2 credit? Is an API mandatory for Level 2, given that the Level 1 forecast API is optional? Please answer yes/no whether (a) a locally run historical replay over precomputed test origins and (b) static per-origin JSON served/read by the UI satisfy the demo and API expectations, with no live integration.

### Why

The answer determines whether UI/API work is a submission blocker or a Level 2 investment, and whether a deterministic historical replay is sufficient without claiming a live integration.

### Safe interim

Build a deterministic local replay and clearly label demo/static data. Do not imply live production integration or plant dispatch capability.

---

## Already resolved — do not spend provider time again

- **Automatic metrics:** unweighted P50 MAE; arithmetic mean of P10/P90 pinball; mean of high/low binary Brier; three-class direction Brier without division by three.
- **Points:** per-metric baseline-to-best accepted-team gap closure with clipping; coverage is not a separate automatic gate.
- **Overall weights:** 80% Level 1 and 20% Level 2; Level 1 also includes 20 reasoning points.
- **Availability:** package rows require `first_usable_origin_utc <= forecast_origin_utc`.
- **Spike boundaries:** strictly above spot +50 or strictly below spot −50; exact ±50 is neither class.
- **Direction:** Fingrid's dominating mFRR direction, not the gap sign.
- **Test rows:** all 673 × 40 rows are required, including the final scored edge deliveries.
- **Default training cutoff:** 1 June–4 October 2026, subject only to a specific written exception such as Q0.
- **Packaged forecasts:** supplied Fingrid 165/246/247 are day-ahead forecasts updated once daily; external API revision history remains Q1/Q2.
- **Required artifacts:** validated forecast CSV, code/run instructions, short evaluation report, rights/source list, about 5–8 slides, and a demo video of at most five minutes.
- **Production scope:** no real plant control or production-trading integration is required; wording should remain “review suggestion,” not an autonomous dispatch command.

## Repository fixes that do not require waiting

- Freeze an evidence-linked results table with model ID, source commit, forecast hash, cutoff, period, scorer, and artifact path.
- Remove or reconcile stale dashboard/report metrics and distinguish implemented features from proposals.
- Rename the internal “baseline gbm…” to “internal reference/champion”; it is not the organiser persistence baseline.
- Correct any statement that spike+direction are 40 points: they are **30**; including pinball makes **50**.
- Say “Level 1 including reasoning is 80%,” not “the model alone is 80%.”
- Keep all operating suggestions conditional and supported by available plant/market data.
- Ensure a fresh clone can regenerate or privately receive the exact validated forecast and UI input artifact.
