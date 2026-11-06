# TL;DR (explain it like I'm five)

> The short version of [`PLAN.md`](PLAN.md). If something here disagrees with the plan, the plan wins.

## The problem in one breath

Every day, Finland **plans** how much electricity it will make and use tomorrow. Plans are always a bit wrong, mostly because **the wind doesn't do what the forecast said**. When the plan is wrong, the grid fixes it in real time, and whoever was "on the wrong side" pays the **imbalance price**.

We have to guess that price, **every hour, for the next 10 hours, in 15-minute slices**.

## The one trick that matters

The imbalance price is basically:

> **tomorrow's normal price (spot), which we already know + a jump up or down**

- Grid short of power → price jumps **up** (above spot)
- Grid has too much power → price drops **down** (below spot)

So we don't guess the price from scratch. We guess **the jump**. Just doing "spot minus a little" already beats the organisers' baseline by about a third.

## What decides the jump

| Matters a lot | Matters a bit | Doesn't matter (for this) |
|---|---|---|
| 🌬️ How much wind is forecast | Sweden and Estonia's prices | Gas prices, news headlines, the stock market |
| ⏰ Time of day (evenings are wild) | How wrong the consumption forecast was | Turku Energia's own power plants |
| 📈 Big price changes from one hour to the next | Recent imbalance (it's an hour old when we get it) | Every single Nordic power plant |

Why don't gas or headlines matter? Because they're **already inside spot**. We only care about what the plan *missed*.

## What we build

1. **The model (80 % of the score):** a CSV with 26,920 rows. For every 15 minutes it gives:
   - a best guess, plus a "probably between X and Y" range
   - the chance the grid goes up or down
   - the chance of a crazy spike (more than 50 €/MWh away from spot)
2. **The dashboard (20 %):** a "situation room" for Turku Energia's traders. It shows what's coming in the next 10 hours, warns about spikes, explains *why* in plain words, and lets you rewind time to see how good the forecast was.

## How we use AI

- **The forecast itself:** machine learning (LightGBM). That's the real AI part.
- **Explanations:** an LLM (Featherless) turns "wind −400 MW, evening ramp" into a sentence a human wants to read.
- **Alerts:** n8n pings Discord when spike risk jumps. ElevenLabs can read it out loud.

## The one rule that can kill us

> **Only use data that existed at the time of the forecast.**

Every data row says when it became available. If we peek at the future, **automatic score of 0**. They check the code, possibly with AI.

Also: **never commit the Nord Pool spot data** to the repo. It's licensed.

## Who does what

| Who | Job |
|---|---|
| Pavlo | Data: loading, the "no peeking" filter, wind and other extra data |
| Pavel | Models: making the forecast good |
| Frank | Dashboard: the API and the Lovable situation room |
| Jim | Explanations & alerts: the "why", the LLM text, n8n |
| Abdo | Story & quality: report, slides, video, hitting submit |

## When

- **Fri night:** data plumbing + first simple model
- **Sat:** better model, extra data, dashboard
- **Sun 10:00:** everything submitted. **Hard deadline.**
