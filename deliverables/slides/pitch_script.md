# Tasehinta: 4-minute final pitch

**Deck:** open [`tasehinta_pitch_live.html`](tasehinta_pitch_live.html) in Chrome and press **F** for full screen. `tasehinta_demo_clip.mp4` must sit in the same folder. **→ / space / click** = next build, **←** = back. Every number on screen is real (validation month).

**▶** = press → at that word. About 530 words, roughly 3:50.

---

**01 · One evening in September** (0:00–0:30)

> Monday, 21st of September. Seven in the evening. *(the spot line and the past draw in)*
> Spot price for eight o'clock: **thirty-six euros**.
> ▶ Tasehinta says: **seventy percent chance of a spike.** *(the range and the risk bars rise, 70 % counts up)*
> ▶ At eight, the price was **seven hundred and thirty**. *(the pink line shoots up)*
> Twenty times spot. And we saw it coming.

*(one-second pause)*

**02 · The imbalance price** (0:30–0:55)

> ▶ That's the imbalance price. Every fifteen minutes, whatever misses Turku Energia's plan is settled at it.
> On the ninth of September: spot two hundred, imbalance **four thousand**.
> ▶ And it's not rare. *(the September barcode fills in, day by day)* **One quarter-hour in four** landed more than fifty euros off spot.

**03 · Today** (0:55–1:10)

> ▶ Today you buy this forecast from a vendor, and you told us yourselves: you can't see *why* it says what it says.
> ▶ **So we built one you can see inside.**

**04 · Four answers** (1:10–1:45)

> ▶ Every hour, Tasehinta looks ten hours ahead, forty quarter-hours, and answers four questions. Same quarter, same evening:
> **What will it cost?** Seventy-seven euros, with an honest range.
> ▶ **Which way is the grid going?** Seventy-nine percent: short of power.
> ▶ **Will it spike?** Seventy percent.
> ▶ **And why?** Grid frequency, the latest gap, hydro output.
> ▶ And it **stays quiet** unless something matters. It tells you what to *check*, never what to *trade*.

**05 · How it works** (1:45–2:20)

> ▶ Rule number one: **no peeking.** Every number enters only from the moment it was published. Automated tests enforce it.
> ▶ We forecast the **gap to spot**, not the price, because spot is already known.
> ▶ We predict the **direction first**. Short: above spot. Surplus: below.
> ▶ And the price rule changed in June, so we rebuilt **nineteen months** of history under it, a 99.5 % exact match.

**06 · Results** (2:20–2:55)

> ▶ Scored with **your own script**: **thirty-six point seven percent better** than the baseline.
> ▶ Less error on every score: median error, uncertainty, spikes, direction.
> ▶ August, a month it never saw: **twenty-nine percent**. And better in every single week.
> A model tuned to one month is **a model tuned to luck**. Every idea had to win both.

**07 · One screen** (2:55–3:25) *(the demo clip starts by itself)*

> ▶ This is the real dashboard, on that same evening. Hover the eight o'clock quarter: seventy-seven euros, seventy percent spike risk.
> ▶ **What's worth checking**, on top. ▶ Price, direction and spike risk on **one timeline**.
> ▶ And you can **rewind** to any past hour, exactly as it looked then. Step forward, and there's the spike.

**08 · Next** (3:25–3:45)

> ▶ On open data, Tasehinta says **"check this."**
> ▶ Give it your plant capacity, your costs, your position, and it says **"offer this."**

**09 · Close** (3:45–4:00)

> ▶ Two hundred euros planned. Four thousand paid.
> ▶ **Next time, you'll see it coming.** Tasehinta. **Kiitos!**

---

## Likely questions: short answers

- **"How did you get 36.7 %?"** The organisers' score.py on the validation month (7 Sep – 4 Oct): MAE 40.2 vs 66.2, pinball halved, better spike and direction scores, weighted by the challenge's points.
- **"Did it catch every spike?"** No. Spikes are rare and noisy. The spike score beats the baseline by about 26 % in September, and the 80 % range held 81 % of real prices. On 21 Sep the risk for 20:00 was already 45 % at noon, 8 hours ahead.
- **"Can you run it live?"** The same pipeline runs from Fingrid and weather APIs. Next step: schedule it hourly behind an API.
- **"Why one model if it's two components?"** It's one ensemble: two gradient-boosting parts averaged 50/50. Their errors partly cancel, so it beats either part alone.
- **"What would you need from us?"** Plant capacities, marginal costs and your position. That turns warnings into concrete capacity suggestions.

## Sources of the on-screen numbers

- **21 Sep, 20:00 quarter (17:00 UTC):** spot 36.4, realised 730.4 (dashboard payload, validation actuals). Forecast at 19:00: p50 77, 80 % range −0.8…164, up-regulation 79 %, spike-high 70 % (0.695), drivers `rt_freq_dev_last4; last_gap; rt_hydro`. Spike-high was 45 % at the 12:00 origin. Source: `submissions/blend_v7_rt_h_int4ss_validation.csv`.
- **9 Sep, 20:30 quarter:** spot 200, realised 4,000.
- **1 in 4:** 24 % of validation quarter-hours were more than 50 € from spot.
- **Score bars:** improvement vs baseline per score, Sep 39/54/26/16 %, Aug 30/47/18/12 %.
- **Demo clip:** recorded from the real offline dashboard (`frontend/bundle.html`), validation period, 21 Sep 19:00 → 22:00.
