# Questions for the Turku Energia experts (Q&A)

**Goal:** find out which data is off-limits and what we can actually use. The questions are ordered by how much the answer would change our submission. Each one says why we ask and what we do now, so whoever asks can follow up.

**Short on time? Ask Q1, Q2, Q3 and Q4.**

Sources: "README" is the organisers' starter-package README (section numbers as in the file); `availability.csv` is the package's table of publication delays.

## Status, 7 Nov evening

| Question | Status |
|---|---|
| Pre-June data (Q1 below) | **Answered:** allowed (organisers' Q&A announcement). |
| Fingrid API history = today's corrected values, not first-published ones | **Answered** (TE_Ville, Since AI Q&A, 7 Nov 2026, 17:45): if we can't verify what value was available at forecast time, we may use the values the dataset provides. He adds that in real operations only the data available at that moment can be used, so a later correction (for example the next day) couldn't have been in the original forecast. **How we handle it:** the Fingrid Open Data API serves only the current values, so we can't verify first-published ones; we keep them with the 30-minute rule. Caveat: our September and August scores may be slightly optimistic where Fingrid corrected a series afterwards. |
| Weather-run delays (8 h ECMWF, 5 h ICON-EU) | **Decided, not asked:** both are longer than the delays actually measured (7.1 h for ECMWF by Abdo; 3.9 h for ICON-EU in Open-Meteo's metadata, 6 Nov), so they're conservative. |
| Fingrid real-time surplus/deficit (198, 186) | **Decided, not asked:** it is measured real-time data like wind (181), so the package's own rule for measured Fingrid data applies: 30 min after the quarter, rounded up to the hour (`availability.csv`). The 60-min rule belongs to the imbalance price, which is computed after the fact. Same revision caveat as all API history. |
| Sharing spot-based outputs | **Decided:** forecasts, scores and charts can be shown. The raw Nord Pool spot series itself stays out of public places (README §9). |
| Submission details, dashboard requirements | **Not asked:** handled by the team. |

---

## A. The big ones (they change the model)

### Q1. May we use data from before 1 June 2026?

**Ask:** "README §3 says to train only on 1 Jun – 4 Oct 2026. Does that also rule out older public data, for example Fingrid's mFRR direction and prices since 2025, if we only use it:
- (a) to train the model,
- (b) as a seasonal prior, such as how often up-regulation happened last autumn, or
- (c) to fit a fixed physical mapping, such as a wind power curve from older weather data?"

- **Why:** This is the biggest open edge. Last autumn behaved differently from this summer: for example, up-regulation peaked at midday in October 2025 and in the evening in summer 2026 (`brainstorming-abdo`, `docs/brainstorm/swarm/README.md`). A teammate's model that uses this history would improve our validation score by roughly 1 %.
- **Follow-up:** README §5.2 says the pricing rule changed on 1 June 2026. Is that the reason for the cut-off, so that only the target before June is off-limits and not inputs such as weather?

> **Answered (organisers' announcement after the first Q&A session, 7 Nov 2026):** "You can use aFRR and mFRR price data from before June." They add that older realised imbalance prices can't be used directly to validate a price forecast, because the price calculation changed to a volume-based approach; take that into account when evaluating.
> - **How we handle the rule change:** the history's imbalance price is recomputed with the 1 June 2026 volume-weighted rule. It matches the official price on 99.5 % of Jun–Oct 2026 quarters (Abdo's `experiments/lab/build_history.py` and `SOURCES.md`, `brainstorming-abdo`). We still evaluate only on August and September 2026, against the package's prices, never on pre-June prices.
> - **Scope:** the answer names aFRR and mFRR prices, and its last sentence covers "older data" in general. We read that as covering the other pre-June series a history-trained model needs: mFRR direction and volumes, consumption, production, flows, day-ahead forecasts and the 2025 spot price.
> - **Licence:** the 2025 spot price comes from Elering and originates from Nord Pool. It's for team-internal use only and never committed.
> - **Now:** our submitted model `v6_hf` trains on this history too: +2.3 % (September) and +3.1 % (August) weighted by points ([`docs/RESULTS.md`](docs/RESULTS.md), round 6).

### Q2. Fingrid data that is almost the target: which delay applies?

**Ask:** "Fingrid publishes some balancing data much faster than the package's 60-minute rule for the imbalance price. Examples: real-time mFRR prices (400–402), the calculated imbalance (397), and the real-time surplus/deficit (198, 186). May we use them with Fingrid's own publication timing? Must they follow the package's 60-minute rule? Or are they off-limits?"

- **Why:** The package makes the imbalance price, mFRR/aFRR and direction usable 60 min after the quarter (`availability.csv`). Data that reveals the price earlier would be a big gain, or a rule break. We'd rather ask than guess.
- **Now:** we don't use 397, 22/251 or 400–402.

### Q3. Real-time Fingrid series we download ourselves: is our 30-minute rule OK?

**Ask:** "We use Fingrid Open Data real-time series that the package doesn't include: wind (181), nuclear (188), frequency (177), consumption (193), hydro (191), production (192), net import (194), electric boilers (371), CHP (201, 202) and cross-border flows. Fingrid publishes them every 1–3 minutes. We treat each value as usable 30 minutes after its quarter ends, rounded up to the next full hour, which is the package's rule for measured data in `availability.csv`. Is that acceptable?"

- **Why:** These series carry most of our gain in the first 2 hours. If a stricter delay is required, we need to know now.

### Q4. During the test period, may we recalibrate with prices that are already public?

**Ask:** "At a test-period origin, imbalance prices from earlier in the test period are already usable (`first_usable_origin_utc ≤ origin`). May we use them to update the calibration, for example shifting the uncertainty band or re-scaling probabilities? Or does README §3, 'input data is in the package but must not be used for training', forbid that?"

- **Why:** Calibration on recent weeks is where much of our probability-score gain comes from (`docs/RESULTS.md`).
- **Now:** we calibrate on the last 28 days before 5 Oct and don't touch test-period targets, except as inputs such as the last known price, which the baseline does too.

---

## B. Our own data sources: delays and licences

### Q5. Weather-model runs from Open-Meteo: are our publication delays acceptable?

**Ask:** "README §8 allows the Open-Meteo Single Runs API, adding the publication delay to the run's start time. We use 8 h for ECMWF IFS and 5 h for DWD ICON-EU, rounded up to the hour. Open-Meteo's own metadata showed about 7.1 h and 3.9 h on 6 Nov. Is that acceptable evidence? Is there a reference delay you want us to use?"

- **Follow-up:** "May we use ERA5 reanalysis, which is only published days later, to fit a fixed mapping such as a power curve, using training-period data only and never as a model input?"

### Q6. Static data downloaded today

**Ask:** "We weight weather points by the installed wind capacity in OpenStreetMap, downloaded on 6–7 Nov. That snapshot may include turbines built after some test origins. Is a static snapshot OK, or must reference data be as of each origin?"

- **Why:** It's a small effect, but it's exactly the kind of thing a code review could flag.

### Q7. Nord Pool outage messages (UMM)

**Ask:** "Is the public Nord Pool UMM feed (power plant and grid outages) allowed, using each message's publication time? What is its licence?"

- **Now:** not used.

### Q8. Other areas' day-ahead prices

**Ask:** "May we use the day-ahead prices of SE1, SE3, EE and other areas, for example from Energinet's public API or ENTSO-E? They originate from Nord Pool. If yes, does the same D-1 14:00 rule as the Finnish spot price apply?"

- **Why:** The price spread to the neighbours shows when Finland is cut off and must balance alone (`docs/PLAN.md`, edge E3).
- **Now:** not used, because of the licence question.

### Q9. Delays for ENTSO-E and neighbouring TSOs' data

**Ask:** "`availability.csv` gives ENTSO-E neighbour data a 120-minute delay, marked as an assumption to be checked. ENTSO-E and the Elering (Estonia) and Energinet (Denmark) APIs don't say when a value was published. Which delays should we use?"

### Q10. Cross-border flows "only as realised values"

**Ask:** "README §8 says to use commercial cross-border flows only as realised values. Does that rule out day-ahead scheduled flows, which are known after the D-1 auction just like the spot price?"

---

## C. Licensed spot data and what we may show

### Q11. Can the demo video, the slides and a public dashboard show real forecast prices?

**Ask:** "README §9's Nord Pool terms cover `spot_nordpool.csv` and the `spot_price` column. Our forecast price is the spot price plus a predicted gap, so it's derived from that data. May the demo video, the slides and a public dashboard show real forecast and spot values? Or must they use synthetic spot as our hosted demo does now?"

- **Why:** The video is a deliverable and the Level 2 jury judges it, so we need to know what it may show.

### Q12. External services and AI tools

**Ask:** "Is it OK to send spot-free derived data, such as the forecast gap, alerts and drivers, to hosted services like an LLM API, n8n or Lovable? And may AI coding assistants read the package files during development, or should they only see code?"

- **Now:** nothing containing spot or absolute prices goes to Featherless, n8n or the hosted Lovable app (checked in code).

### Q13. "Delete after the event": what exactly?

**Ask:** "README §9 says not to share the Nord Pool data further, not to upload it to public repositories, and to delete it after the event. Does the deletion also cover copies in a private team repository's git history? For the source-code deliverable: we leave all package files out and expect reviewers to use their own copy of the package. Is that right?"

---

## D. Already clear: no need to ask

- **Training window:** train on data up to 4 Oct 2026, and the validation month 7 Sep – 4 Oct is part of it (README §3 and §4). Pre-June aFRR and mFRR price data is allowed too, with the caveat in Q1.
- **Test period:** its inputs may be used as inputs at each origin, but not for training (README §3).
- **Availability:** a row is usable only if `first_usable_origin_utc ≤ origin`, and the row-level value is binding. Anything else scores 0 (README §4). Top solutions' code is reviewed, possibly with AI tools (README §2.5).
- **Where to ask:** the Turku Energia channel of the Since AI Discord (README §11). Questions the Q&A doesn't cover can go there.
- **Weather:** Open-Meteo Single Runs is allowed with a publication delay; the Historical Forecast API is not recommended because it leaks future information (README §8).
- **FMI:** weather observations are allowed if we fetch them ourselves (README §8).
- **Licences:** we're responsible for the licences of the data we add and must list every source (README §8). Ours are in [`SOURCES.md`](SOURCES.md).
- **Scoring:** quarter-hours after the test period, up to 2 Nov 06:45 UTC, are scored too (README §3).
