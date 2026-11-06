---
tags: [brainstorm, comparison]
compared: origin/frank @ 509435e "Plan: add how-we-beat-other-teams edge list"
created: 2026-11-06
status: draft
---

# Comparison with Frank's branch

Frank's branch adds **§0 "How we beat other teams"** to [[PLAN]]: edges E1–E7 and a "Ruled out" list. It also edits the source table, the order of work and the open questions, and adds a short section to [[TLDR]]. Back to [[00 Brainstorm Hub]].

Other branches, as of the last fetch (22:35, 6 Nov): `brainstorming` is already merged into master, so it has nothing new. Re-check after the next fetch.

## Summary

| Edge | Frank's idea | Verdict | Where it lands in our notes |
|---|---|---|---|
| Framing | "Spot + LightGBM is our floor, not our edge" | ✔ Agree | Same point as [[Feedback on the plan#§1–2 What the data told us]] |
| E1 | Train on Fingrid history back to Mar 2025 (incl. Oct–Nov 2025) | 💡 **New, good**. Use it for direction first; ask the organisers first | [[Model ideas#Pre-June history (from Frank's E1)]] |
| E2 | Grid frequency as a near-real-time signal | 💡 New. Test it, but **after** realised-wind error | [[Data layer ideas#Fingrid real-time]] |
| E3 | FI vs SE/EE day-ahead price spread (congestion) via Energinet | 💡 **New, and it changes our view**: we cut Energinet, Frank is right that this is different | [[Feedback on the plan#§4 Data sources]] |
| E4 | Win the probability scores with calibration | ✔ Agree, but it needs our retrain fix | [[Model ideas#Calibration after the final retrain]] |
| E5 | Few, meaningful features; week-by-week validation | ✔ Agree | [[Model ideas#Things not to spend time on]] |
| E6 | Chronos-2 / TimesFM challenger | ⚠ Disagree: stretch goal only | [[Model ideas#Things not to spend time on]] |
| E7 | Jury: comparison table, honest leakage handling, user-centred dashboard | ✔ Agree | [[Dashboard and story ideas]] |
| Ruled out | Random APIs, news/LLM price prediction, ensemble spread | ✔ Agree | Our ECMWF vs ICON spread is the leak-free substitute for ensemble spread |

## Where Frank adds something we missed

- **E1, pre-June history.** We never considered data before 1 Jun. Oct–Nov 2025 is the same season as the test, and it includes a DST change (26 Oct 2025). That would help the [[Risks and checks#DST trap in the test period|DST problem]] if features use local hour.
- **E3, day-ahead price spread.** We cut Energinet because of PLAN finding 6, but finding 6 is about **neighbour imbalance prices** that arrive ~9 quarters late. Frank's spread is **day-ahead** and covers all 40 steps, which fits our own argument that day-ahead features count for more of the score. We were wrong to cut it.
- **"Ruled out: ensemble spread".** It's a good catch that the Open-Meteo ensemble archive is stitched together after the fact and leaks future information.

## Where our notes are stronger

- **E4 + retrain.** "Calibrate on the most recent weeks" combined with "retrain on everything up to 4 Oct" makes those weeks in-sample, so the band ends up too narrow. Our rolling time-split fixes that.
- **E6 is scope creep.** Frank expects it to lose and lists no reason other teams would miss it. The context window also has to be cut by the availability filter, not by timestamp, which is a new leakage risk. Do it only if everything else is done on Sunday morning, and drop it otherwise.
- **Order of work.** Frank's order still has Elering last and UMM in the model path. Ours cuts Elering and keeps UMM for the dashboard only.
- **Missing from his list**, all cheap: local-hour features + All Saints' Day (DST trap), recent-conditions rolling features, spike product calibration, Open-Meteo revision through a power curve + ECMWF/ICON spread, the as-of leakage test, the validated safety submission.

## Problems in Frank's diff

Suggest these to Frank before his branch is merged:

1. **"40 of the 80 automatic points" for probability scores.** Spike Brier (20) + direction Brier (10) = **30**. With pinball loss (20) it's **50**. Neither adds up to 40.
2. **E1, "the June change only affects aFRR mixing".** That change alters the **imbalance price itself** (volume-weighted mFRR + aFRR when both are in the dominating direction). So pre-June **gap sizes and spike tails** come from a different distribution. Pre-June data is safest for the **direction** model; use it for quantiles and spike tails only if validation agrees.
3. **E1 also needs FI spot for 2025** to compute the gap. The package starts on 1 Jun 2026, so that spot would come from Energinet, with the same Nord Pool licence question as E3.
4. **E3 promises an EE spread**, but the Energinet row lists FI, SE1–4, NO, DK, DE, with **no EE**. Either find an EE source or drop EE from the edge.
5. **Unmarked claims** go against the plan's ✔/☐ convention: the 0.76 / ~0.2 correlations (E2), dataset IDs 369 / 244 / 106 (E1) and the Mar 2025 start date. Mark them ☐ until someone checks.
6. **The quote "train only on this data (1 Jun – 4 Oct)"** is not in our README. If it's from the organisers' brief, cite it as such.

## Leakage notes for Frank's new sources

- **E1:** every pre-June row needs its own `first_usable_origin_utc`, using the **same delay the package uses** for that series. Keep it out of the pipeline completely until there's a written yes in `#turku-energia`.
- **E2:** don't set the delay to 3 min just because data arrives every 3 min. Use a conservative margin rounded up to the hour, and check that stored history isn't revised.
- **E3:** same availability rule as package spot. Never use Energinet FI prices to fill gaps in package spot for test origins. Never commit fetched prices (Nord Pool licence).
