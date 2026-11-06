---
tags: [brainstorm, dashboard, story]
owner: Frank, Jim, Abdo
created: 2026-11-06
status: draft
---

# Dashboard and story ideas

Level 2 (20 % of the total) and the reasoning chain (20 jury points in Level 1). Back to [[00 Brainstorm Hub]]. Related: [[Feedback on the plan#§6 Level 2]].

## Who looks at it, and what they need

A shift supervisor or trader at Turku Energia, looking at the screen for **10 seconds**. Answer three questions in that order:

1. **Is anything unusual in the next 1–3 h?** (red / amber / green)
2. **Why?** (one sentence)
3. **What should I check?** (one suggestion, worded as "review", never "do")

Everything else (the fan chart, track record, history) sits below the fold.

## Panel ranking

| Priority | Panel | Why |
|---|---|---|
| Must | Next 10 h fan chart (P10/P50/P90 + spot) + up/down strip + spike heatmap | Core of the brief |
| Must | Time travel slider over origins | Explicitly asked for |
| Must | Track record: MAE vs baseline by day and week, coverage | "Past performance" in the brief |
| Should | What changed since the last origin + alerts | Extra credit |
| Should | "Why" text | Extra credit + jury |
| Should | 💡 € at stake | Inventiveness |
| Nice | Conflicting signals, outage feed, suggestions | Only if the musts are polished |

## € at stake

💡 Traders think in euros, not €/MWh errors. For each quarter, show **the expected cost per 1 MWh of imbalance**:

- If short 1 MWh: expected cost ≈ max(0, imbalance price − spot), i.e. how much worse than spot.
- If long 1 MWh: expected cost ≈ max(0, spot − imbalance price).

The model's P10/P50/P90 and direction probabilities give an **expected gap and a range**. A strip like "being short 16:00–18:00 could cost 40–120 € per MWh" is something a trader acts on.

For the **track record**: "if a 1 MWh position had been adjusted toward the forecast direction whenever `p_up` or `p_down` > 0.7, the hypothetical savings over the test month were X €". ⚠ Label it clearly as **illustrative**. We don't know Turku Energia's real positions, and the brief asks for suggestions, not instructions.

☐ This assumes the Finnish imbalance settlement uses a single price for both directions, as the README describes. Confirm the sign convention with the organisers before showing numbers.

## Explanations, template first

1. **Template:** turn SHAP drivers into fixed sentence pieces:
   `"Spike risk {up/down} for {time block}. Main drivers: {driver 1}, {driver 2}. Uncertainty: {low/medium/high}."`
   Use one shared dictionary of readable driver names (the same one used for the `top_drivers` column).
2. **LLM rewording (optional):** Featherless rewrites the template into the style of the brief's example. **Cache** the output per origin as JSON.
3. If the LLM fails or credits run out, the dashboard shows the template text, so the demo never breaks.

The LLM gets **only** the template and SHAP values, never raw data. This keeps "LLM output stays downstream" easy to show in the code review.

## Alerts

- Trigger when spike probability for any 1-hour block rises by more than X percentage points, or P50 moves by more than Y €/MWh, vs the previous origin. Tune X and Y on validation so we get **~1–3 alerts per day**. Alert fatigue is a real problem for operators, and saying so is a good point for the pitch.
- Show "alert precision" in the track record: how often an alert was followed by a real spike.

## Story for the jury (slides and video)

A possible 5-minute arc:

1. **The problem in one picture:** imbalance price vs spot, showing that the price is "spot + a jump".
2. **The key idea:** forecast the jump, not the price. The comparison table from [[Model ideas#Step-by-step comparison table (also the jury story)]].
3. **What drives the jump:** wind level, ramps, evening peak, with charts from PLAN §2.
4. **Live replay:** time travel to a day with a real spike in the test period (pick one in advance). Show the alert firing hours before, the "why" text and the € at stake.
5. **Honesty slide:** the data rule, the leakage test, and the limits (no plant data, illustrative €).
6. **Next steps:** real positions and plant data → real recommendations.

💡 **Pick the demo day on Saturday evening** from the validation forecasts, then confirm it with the test forecasts on Sunday. A good demo day has one clear spike that the model saw coming and one it missed (honesty scores points).
