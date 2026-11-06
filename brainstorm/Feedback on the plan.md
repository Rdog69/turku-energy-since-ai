---
tags: [brainstorm, review]
created: 2026-11-06
status: draft
---

# Feedback on the plan

A section-by-section review of [[PLAN]]. Back to [[00 Brainstorm Hub]].

**Overall:** the framing is right. Forecasting **the gap to spot** is the key idea, and the plan backs its claims with data. Its main weakness is **scope**: too many data sources, dashboard panels and side tools for about 36 hours. Points come from the 4 automatic metrics (80 of the 100 Level 1 points), and everyone else will find the spot anchor too. So the effort should go to what beats *spot + constant*, not to more panels.

## §1–2 What the data told us

✔ **Keep:**
- The gap framing (findings 1 and 10).
- The spike = direction × tail model (finding 11).
- The "None is almost never" simplification (finding 8).
- Marking ✔/☐ on every claim. Keep doing this; it doubles as material for the reasoning chain.

⚠ **Change or add:**
- **Finding 1, use a better simple anchor.** Spot − 7.7 is one constant. Use a median gap per (local hour × wind quintile) instead: a 24 × 5 lookup table. It takes 30 minutes and uses findings 3 and 5 directly. It becomes the next step in the comparison table (spot → spot + constant → spot + lookup → LightGBM), and the jury can follow each step.
- **Finding 2, the ½ weight was tuned on validation.** The plan says so already, which is good. Make sure the report shows the number from a model trained up to 6 Sep, not 43.0.
- **Finding 9, drift is the main threat for the test.** Validation already had higher spike shares than training (12.1 / 13.0 % vs 9.0 / 7.3 %). Late October and November are likely different again, with more wind, almost no solar and colder weather (☐ guess). This deserves more than "recency weights". See [[Model ideas#Recent-conditions features]].
- **Missing: the DST change.** See [[Risks and checks#DST trap in the test period]].
- **Missing: holidays in the test.** All Saints' Day (Pyhäinpäivä) is **Sat 31 Oct 2026**. Training has only Midsummer. A holiday flag learned from one holiday is close to noise, so treat holidays like a weekend instead.

## §3 Briefing claims

✔ Good table. One addition: "decisions are made 1–2 h before gate closure" is not a scoring rule, but it should still shape **where we spend data effort**. Fresh real-time data (Fingrid) only helps steps 1–8 or so. All 40 steps count equally, so the day-ahead features improve far more of the score.

## §4 Data sources

⚠ **Too many sources.** The list has 12 rows. Each external source costs a fetcher, a publication delay you can defend, a leakage test, a `SOURCES.md` entry and an ablation row. Realistic limit:

| Keep | Why |
|---|---|
| Starter package | Required, and it already beats the baseline |
| Open-Meteo Single Runs | Covers **all 40 steps** (forecast revisions); highest expected value |
| Fingrid real-time wind (+ nuclear) | Strongest short-step signal; also shows unplanned outages |
| UMM | **Dashboard only** ("why" and the outage feed). Add to the model only if there's time |
| *4th, conditional:* Energinet day-ahead prices (FI vs SE spread) | From Frank's E3 ([[Comparison with Frank's branch]]). Day-ahead, so it covers all 40 steps. Only after Open-Meteo and Fingrid wind are in, **and** only if the Nord Pool licence question is cleared |

**Cut:** Elering, FMI, Statnett, Mimer, eSett, and Energinet's Danish system data. Finding 6 already shows that neighbours' **imbalance prices** carry little signal about the gap, so fresher neighbour data is unlikely to change that.

✏ *Revised after comparing with Frank's branch:* I first cut Energinet completely. But finding 6 is about late-arriving neighbour imbalance prices, not day-ahead price spreads, so it doesn't rule out E3.

☐ **Open-Meteo coverage is the biggest unknown.** Only Sept and Oct runs were tested. If runs before ~September aren't available, the feature exists for only part of the training period. Check June runs first, before writing any feature code. See [[Data layer ideas#Open-Meteo]].

## §5 Level 1 model

✔ Good: LightGBM quantiles on the gap, step as a feature, sorting the quantiles, the ablation chain.

⚠ **Calibration and the final retrain don't fit together yet.** See [[Model ideas#Calibration after the final retrain]].

⚠ **Spike = P(up) × P(tail | up)**: if both parts are slightly off, the product is off by more. Fit a final isotonic or Platt calibration on the **product**, using time-split residuals. See [[Model ideas#Spike probabilities]].

💡 **Direction score**: the baseline Brier of 0.4509 looks like a 3-class sum (☐ check in `score.py`). If so, putting `p_none` at the training share (~0.002) is the right move. Never let it be 0, since one wrong 0 costs little but adds nothing.

💡 **`top_drivers`**: SHAP from the P50 model only is fine. Map feature names to readable names (`wind_fc_da` → "day-ahead wind") in one shared dictionary, so the dashboard, the CSV and the LLM text all use the same words.

## §6 Level 2

⚠ **Seven panels is too many for one dashboard owner.** Rank them:

1. **Must have:** next 10 h fan chart + up/down strip + spike heatmap (panel 1), time travel, track record (panel 4).
2. **Should have:** "what changed" alerts (panel 2), "why" text (panel 3).
3. **Nice to have:** suggestions (5), conflicting signals (6), outage feed (7).

💡 Add the **"€ at stake"** idea. See [[Dashboard and story ideas#€ at stake]]. It is the most useful thing for a trader, and it suits the jury's "inventiveness" criterion.

⚠ **Lovable risk:** export, run locally, wire to the API. That's many moving parts for one person. Set a **go/no-go at Sat 14:00**: if Lovable doesn't show real data from the API by then, switch to Streamlit for the demo.

## §7 Event tools

✔ "LLM output stays downstream" is the right rule.

⚠ **n8n + ElevenLabs + Gemini + Red Hat** together are a lot of side work. The plan already says "decide Saturday evening", which is good. Also: write **template text first** (no LLM), and let the LLM only reword it. Then the demo never depends on an API call working. See [[Dashboard and story ideas#Explanations, template first]].

## §10 Timeline

⚠ Friday night lists five goals. Two of them matter: the **availability filter + leakage test**, and the **spot-anchor submission that passes the validator**. Request the Fingrid key in two minutes. Start the Open-Meteo download only after the June coverage check.

⚠ **Sun 06–09 is the only window for the final test run.** Do a full test backtest dry run on **Saturday night** with whatever model exists, and validate it. Sunday morning should only re-run a pipeline that already works.

## §11 Roles

✔ Clear owners and file handoffs.

⚠ **Data is the critical path.** Models, explanations and the dashboard all wait on `features.parquet`. To unblock them:
- Agree the **column contract** on Friday night ([[Data layer ideas#Feature table contract (v0)]]).
- Ship **v0 from package data only** by Sat ~09:00. Add external features as new columns, never by renaming existing ones.

⚠ `*.parquet` is git-ignored, so the handoff needs another channel: a shared drive, or `python -m src.features.build` that everyone runs locally from their own `starter_package/`.

## §12 Open questions

Add these:
- [ ] Is `score.py`'s direction Brier a 3-class sum? (Affects how much `p_none` matters.)
- [ ] Are datasets 246 and 247 in the package **day-ahead** versions, or Fingrid's hourly-updated series with a day-ahead availability time? ☐ See [[Risks and checks#Package datasets 246 and 247]].
- [ ] Does Open-Meteo Single Runs serve **June 2026** runs for ECMWF IFS and ICON?
