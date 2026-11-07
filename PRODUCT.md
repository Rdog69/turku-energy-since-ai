# Product

> Copied from Abdo's `origin/front-end` (commit `891f536`, updated to `69cee5a`) into `brainstorming-frank` on 7 Nov 2026 and pointed at the current submission.

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + TypeScript + Tailwind CSS + shadcn/ui (the web-artifacts-builder stack), bundled into one offline HTML file (`frontend/bundle.html`). A Python script builds the page's data from the team's forecast files. Chosen by the user on 7 Nov 2026.

## Users

Primary: an **electricity trading specialist at Turku Energia**. During the day they manage the company's intraday position. Any part of the forecast error they do not trade away is settled at the imbalance price, so they need to know early when the imbalance price is likely to move far from the day-ahead (spot) price, and in which direction.

Secondary (named in the challenge brief): the production shift supervisor, who decides whether to change the production plan or offer flexible capacity to reserve markets. Suggestions are phrased so that they also serve this role, but the first screen is designed for the trader.

Evaluators: the Turku Energia jury (trading, production, AI/data experts) judge the page in the demo video and live demo.

## Product Purpose

Turns the team's imbalance-price forecast into a situational view: what is worth checking now and over the next 10 hours (40 quarter-hours), and how well the forecast has done in hindsight. Success: the trader spots spike risk and the balancing direction early, understands why (drivers), sees how uncertain the forecast is, and trusts it because past performance is visible.

## Positioning

- The forecast is a mixture: P(up-regulation) × the price gap if up + P(down-regulation) × the gap if down, so direction, spike risk and the price band come from one consistent model.
- It blends two independent models (Frank's v7_rt and Abdo's history-trained h_int4ss, half each, with the upper band widened ×1.15 and spike risk capped by the balancing direction). When the two disagree, that disagreement is shown as a "conflicting signals" warning rather than hidden.
- Every forecast uses only data published before the forecast time, and the page can replay any past hour exactly as it would have looked then.

## Operating Context

- Imbalance prices are settled per 15-minute period in Finland. Spot (day-ahead) prices are known from D-1 14:00 Finnish time.
- A "spike" means the imbalance price is more than 50 €/MWh above (high) or below (low) the spot price.
- Direction = the dominant mFRR balancing direction (Fingrid dataset 369): up, down or none.
- Forecasts are made every full hour for the next 40 quarter-hours. The replay covers the validation period (7 Sep – 4 Oct 2026), August 2026 (the second check month) and the test period (5 Oct – 1 Nov 2026). Times are shown in Finnish time (Europe/Helsinki); 25 Oct 2026 has a repeated hour (DST ends).
- The jury criteria (challenge brief, Level 2): the clarity of the view for an energy expert; two time horizons (now and the next 10 h, plus hindsight over the previous day, week or month); moving the review point into the past; alerts when the price or balancing forecast changes materially; insight that is new to energy experts; "check this situation" suggestions.

## Capabilities and Constraints

- Per quarter-hour: p10/p50/p90 price, P(up)/P(down)/P(none), P(spike high)/P(spike low), top drivers, data cutoff time.
- Alerts: spike risk raised since the previous hour; expected up/down regulation; forecast changed materially since the previous hour; the two models disagree; wide uncertainty that is worth an expert review.
- Hindsight: forecasts vs realised prices, with MAE, band coverage and spike hits over the last day, week and month, using only prices published by the review time.
- **Licensing:** Nord Pool spot prices are licensed for hackathon use only. No hosting, no public repositories, deleted after the event. The bundle with real data stays local and git-ignored.
- Suggestions are prompts to review ("check your intraday position for 16:00–18:00"), never trading or plant instructions. Open data does not show Turku Energia's capacity, costs or commitments.
- Undecided: whether a live API is served next to the page (Jim's FastAPI exists on his branch).

## Brand Commitments

- Language: English with a Finnish toggle (all interface strings in both languages).
- No brand assets were provided. The team dashboard on Frank's branch is called VAAKA; this page does not have to reuse it.

## Evidence on Hand

- Forecast files (brainstorming-frank): the submitted `submissions/blend_hi15_env_{validation,august,test}.csv` and its members `submissions/v7_rt_*.csv` and Abdo's `h_int4ss` files (read from `origin/brainstorming-abdo` if no local copy exists). Recipe and hashes: `submissions/MANIFEST.md`.
- Realised prices, spot and direction: starter package (`starter_package/data/`), usable only after each row's `first_usable_origin_utc`.
- Validation metrics (organisers' scorer, Sep 2026): baseline MAE 66.20, pinball 24.18, spike Brier 0.1132, direction Brier 0.4509; submitted blend MAE 40.19, pinball 11.03, spike 0.0835, direction 0.3799 (August: 27.05 / 6.15 / 0.0648 / 0.4202).
- No user testimonials or trading P&L figures exist; do not invent any.

## Product Principles

1. Show only what deserves attention; quiet hours stay quiet.
2. Every warning says why (drivers) and how sure we are (band, probability).
3. Never show information the forecast could not have known at the review time.
4. Suggest what to check, never what to trade.
5. Earn trust with visible hindsight.

## Accessibility & Inclusion

Readable on a laptop and a large trading-desk monitor. Probabilities and directions are never shown by colour alone. Keyboard operable; respects reduced motion.
