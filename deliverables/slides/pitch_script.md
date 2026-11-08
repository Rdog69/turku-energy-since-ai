# Tasehinta: 4-minute final pitch

About 520 spoken words, or 4:00 at a calm pace. **Bold** = say it with weight. [Brackets] = what to do on screen.

**Setup before you go on:** two windows ready. (1) The dashboard at tasehinta.lovable.app, set to *Validation*, scrolled to **Tue 9 Sep, 19:00**, paused. (2) The pitch deck (PDF) on slide 2. Start on the dashboard.

---

## 0:00–0:30 · Hook (dashboard, live)

[Dashboard at 9 Sep 19:00. Point at the spike-risk flag on the 20:30 quarter.]

> 9 September, seven in the evening. The spot price for 20:30 is 200 euros.
> **Tasehinta raises a flag: spike risk.**

[Press Play / scroll forward past 20:30. The real price line shoots up.]

> At 20:30 the imbalance price hit **4,000 euros**. Twenty times spot, and we saw it coming 90 minutes before.

*(pause one beat)*

## 0:30–1:00 · Problem (slide 2)

[Switch to the deck, slide 2]

> Every quarter-hour, any part of Turku Energia's plan that misses is settled at the imbalance price. It follows spot, until the grid runs short or into a surplus. Then it jumps. In September, **one quarter-hour in four** ended more than 50 euros from spot.
> Today Turku Energia buys this forecast from a vendor, and as you told us, you can't see *why* it says what it says.

## 1:00–1:40 · Solution (slide 3)

> Tasehinta means "imbalance price". Every hour it forecasts the next 40 quarter-hours, and for each one it answers four questions:
> **What will it cost?** A price with an honest range.
> **Which way is the grid going?** Up-regulation, down, or none.
> **Will it spike?** In either direction.
> **And why?** The few factors that moved the forecast.
> Then it shows only what's worth checking, and says what to check, never what to trade, because only you know your own position.

## 1:40–2:20 · How it works (slide 4)

> One model, built only from what was known at the time. Every input is used only from the moment it was published. We test for leaks automatically.
> Three ideas make it work. We forecast the **gap to spot**, not the price, because spot is already known. We predict the **direction first**, so price, range and spike risk tell one story. And we rebuilt 19 months of history under the June 2026 price rule, so the model learns from data that means the same thing.

## 2:20–2:55 · Results (slide 5)

> Scored with your own script on the validation month: **36.7 % better than the baseline**. The median error is 40 euros instead of 66, the uncertainty loss is halved, and it's better in **every single week**.
> On August, a month it never saw, it's still 29 % better. Every change we kept had to win both months.

## 2:55–3:30 · Dashboard (slide 6)

> For a trader or a shift supervisor, it's one screen. On top: what's worth checking right now. Below: price, direction and spike risk on one 15-minute time axis.
> And you can rewind to any past hour and see exactly what was known then. That's how we just replayed the 9th of September. It's live, in English and Finnish.

## 3:30–4:00 · Next and close (slides 7 → 8)

> Built on open data, Tasehinta can say **"check this."** With your own plant capacity, costs and position, the same forecast can say **"offer this."**
> [Slide 8] An in-house forecast you can actually see inside: 36.7 % better, and it saw the 4,000-euro quarter coming.
> **Kiitos.**

---

## Likely questions: short answers

- **"How did you get 36.7 %?"** The organisers' score.py on the validation month (7 Sep – 4 Oct): MAE 40.2 vs 66.2, pinball halved, better spike and direction scores, weighted by the challenge's points.
- **"Did it catch every spike?"** No. Spikes are rare and noisy. Its spike score beats the baseline by about 26 % in September, and the 80 % range held 81 % of real prices. For 9 Sep 20:30 the spike risk went 12 % → 45 % → 65 % as the quarter got closer.
- **"Why only 90 minutes of warning?"** The real-time grid signals (frequency, wind against forecast) arrive late. Most spikes can't be seen 8 hours out from open data. The range widens instead.
- **"Can you run it live?"** The same pipeline runs from Fingrid and weather APIs. Next step: schedule it hourly behind an API.
- **"Why one model if it's two components?"** It's one ensemble: two gradient-boosting parts averaged 50/50. Their errors partly cancel, so it beats either part alone.
- **"What would you need from us?"** Plant capacities, marginal costs and your position. That turns warnings into concrete capacity suggestions.

## Source of the hook numbers

`submissions/blend_v7_rt_h_int4ss_validation.csv`, delivery 2026-09-09 17:30 UTC (20:30 Finnish time): `p_spike_high` = 0.123 at the 08:00 UTC origin, 0.181 at 15:00, **0.446 at 16:00 (19:00 local, step 7)** and 0.652 at 17:00. The dashboard's spike-alert threshold is 40 %. Realised price 4,000 €/MWh against a spot price of 200 (organisers' validation data).
