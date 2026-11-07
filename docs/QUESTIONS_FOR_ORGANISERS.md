# Questions for the Turku Energia experts (`#turku-energia`)

> Merged from our branches (Abdo's PLAN §12 and SOURCES.md; Frank's PLAN, TLDR and SOURCES). They're ordered by how much the final submission depends on the answer. Each one is written to paste into Discord as is. The experts are on site Sat 9:00–12:00 and 14:30–18:00.

## Critical: our best model depends on these

**1. Fingrid real-time data.**
May we use Fingrid's real-time 3-minute datasets (e.g. 181 wind, 192/193 production/consumption, 177 frequency, 188 nuclear, 198/186 surplus-deficit), averaged per quarter-hour?
- We treat each quarter as usable **30 minutes after it ends, rounded up to the next full hour**. That's the same rule `availability.csv` uses for measured Fingrid data.
- The values come from today's API, so they're the settled values. Is that acceptable for the backtest?

**2. Fingrid history before June 2026.**
May we train a component on Fingrid history from **March 2025 to May 2026**? That's the mFRR direction (369), mFRR prices and day-ahead forecasts, including last October–November.
- It's all before the 4 Oct cutoff.
- We only use it for the **direction** of balancing, which the June change in aFRR price mixing doesn't affect.
- The README says "train only on 1 Jun – 4 Oct". Does that just mean "not the test period", or strictly nothing earlier?

> **Answered (Turku Energia, 7 Nov):** "You can also use data from before June 1. The cutoff was only due to the pricing rule. You can use aFRR and mFRR price data from before June. However, you cannot directly validate your price forecast against the realized imbalance price, as the imbalance price calculation methodology changed to a volume-based approach. When using older data, take this change into account when evaluating your model."
> **What we do:** the pre-June imbalance price is recomputed with the June rule from mFRR/aFRR prices and volumes (reproduces the official price on 99.5 % of Jun–Oct 2026 quarters); the old-rule price is never a target. See `SOURCES.md` §11.

**3. Weather-model runs (Open-Meteo Single Runs).**
We use archived runs, which you recommended, at wind-farm locations. A run counts as usable only after Open-Meteo's measured publication delay, rounded up: ECMWF IFS init + 8 h, ICON-EU init + 5 h. Are these delays acceptable?

## Important: affects what we're allowed to add

**4. Real-time mFRR and imbalance datasets.**
Fingrid publishes some series close to the target in near real time:
- 397, "calculated imbalance";
- 22/251, the price of the last activated up/down bid;
- 400–402, real-time mFRR prices.

The package gives the imbalance and mFRR prices with a 60-minute delay. **Are these real-time series off limits** because they nearly copy the target, or allowed with their own publication delay? We haven't used them.

**5. Nord Pool UMM outage messages.**
May we use Nord Pool's public UMM API (planned and unplanned outages)? We use each message version from its own publication time. Currently only for a rule-based alert and the dashboard.

**6. Recalibration during the test period.**
At each test origin, may we use test-period imbalance prices that are already usable (`first_usable_origin_utc ≤ origin`) to adjust calibration? Or does "train only on data up to 4 Oct" rule that out? We don't do this now.

## Deliverables and licensing

**7. Code review and the spot data.**
For the code review, may we share a **private** repository that contains the starter package, including `spot_nordpool.csv`? Or should the repository you review contain the code only?

**8. Re-running our pipeline.**
Will you re-run our pipeline, or only read the code? Our pipeline downloads external data (Fingrid with an API key, Open-Meteo, UMM). Should we include the downloaded files with each row's publication timestamp, so the backtest can be reproduced offline?

**9. A public dashboard.**
May a publicly hosted dashboard (e.g. Lovable) show our **forecasts**? They're derived from spot but contain no spot values. Or must the Level 2 demo stay local?

**10. `top_drivers`.**
It's optional and not scored. Is a semicolon-separated list of feature names (from SHAP) enough, or would you like plain-language drivers?

**11. Last year's spot price (nice to have).**
Could you extend `spot_nordpool.csv` back to September 2025, so last autumn's imbalance–spot gap can be used? The free mirrors we found don't allow this use.
