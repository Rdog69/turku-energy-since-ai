---
tags: [brainstorm, hub]
branch: femboystorming-pavlo
created: 2026-11-06
status: draft
---

# Brainstorm Hub

Brainstorm and review of the current plan ([[PLAN]], [[TLDR]], [[README]]). **[[PLAN]] is still the source of truth.** These notes suggest changes. Nothing in them is decided until it moves into the plan.

Legend: ⚠ issue in the current plan · 💡 new idea · ☐ unverified, check before relying on it · ✔ checked.

## Notes

| Note | What's in it |
|---|---|
| [[Feedback on the plan]] | A review of the plan, section by section: what to keep, cut or change |
| [[Risks and checks]] | Leakage traps, repo problems and things that can quietly cost points |
| [[Data layer ideas]] | Availability filter, feature table contract, external sources (data role) |
| [[Model ideas]] | Improvements beyond "spot + LightGBM gap" |
| [[Dashboard and story ideas]] | Level 2 and the reasoning-chain story for the jury |
| [[Comparison with Frank's branch]] | Frank's "how we beat other teams" edges (E1–E7) compared with these notes, and problems to raise with him |

## Top 5 changes I'd make to the plan

1. **Make a safe submission on Friday night.** Write a `forecast_backtest.csv` from the spot anchor (spot − 7.7) that passes the validator, and keep it. If everything else breaks, we still score well above 0. See [[Risks and checks#Always have a valid submission]].
2. **Use local (Helsinki) hour, not UTC hour.** Clocks go back on **25 Oct 2026**, inside the test period. Training never sees that change. With UTC hour, the evening-peak pattern is off by one hour for the last week of the test. See [[Risks and checks#DST trap in the test period]].
3. **Fix the calibration plan.** The plan calibrates on validation and then retrains on everything up to 4 Oct. After that, the validation data is in-sample and the calibration offsets come out too narrow. See [[Model ideas#Calibration after the final retrain]].
4. **Use at most 3 external sources, plus one conditional fourth.** Package → Open-Meteo → Fingrid real-time wind. Use UMM only for the dashboard. Add Frank's FI–SE day-ahead price spread only once those work and the licence is cleared. Cut Elering, FMI, Statnett and Mimer. See [[Feedback on the plan#§4 Data sources]].
5. **Agree the feature table format on Friday night.** The data role is the critical path, so the models role needs the column names before the data exists. See [[Data layer ideas#Feature table contract (v0)]].

## Ideas board

Impact is a rough guess at Level 1 points or jury value. Effort is in person-hours.

| Idea | Impact | Effort | Owner | Note |
|---|---|---|---|---|
| Safe spot-anchor submission | Insurance | 1 h | Pavel | [[Risks and checks]] |
| Local-hour features (DST) | Medium | 0.5 h | Pavlo | [[Risks and checks]] |
| Hour × wind lookup anchor | Medium | 1 h | Pavel | [[Model ideas]] |
| Recent-conditions features (rolling spike share, rolling \|gap\|) | Medium–high (drift) | 2 h | Pavlo | [[Model ideas]] |
| Fingrid realised-wind error | High for steps 1–8 | 3 h | Pavlo | [[Data layer ideas]] |
| Open-Meteo revision through a power curve | Medium–high | 4 h | Pavlo | [[Data layer ideas]] |
| ECMWF vs ICON disagreement → wider band | Medium (pinball) | 1 h once both are downloaded | Pavlo | [[Data layer ideas]] |
| Calibrate the spike product directly | Medium (20 pts) | 1 h | Pavel | [[Model ideas]] |
| "€ at stake" panel | High (jury) | 2 h | Frank / Abdo | [[Dashboard and story ideas]] |
| Template-first explanation text, LLM second | Lower risk | 1 h | Jim | [[Dashboard and story ideas]] |
| Pre-June Fingrid history (Frank E1), direction model first | High, **if the organisers allow it** | 3 h | Pavlo / Pavel | [[Model ideas]] |
| FI–SE day-ahead price spread (Frank E3) | Medium, all 40 steps | 2 h | Pavlo | [[Data layer ideas]] |
| Grid frequency (Frank E2) | Low–medium, steps 1–8 | 1 h after the Fingrid fetcher | Pavlo | [[Data layer ideas]] |
| Pretrained time-series model (Frank E6) | Low | 1–3 h | – | Stretch only |
| Elering / FMI / Statnett | Low | 3+ h each | – | Cut |
