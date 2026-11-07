# Evaluation report: imbalance-price forecast for Turku Energia

**Submission:** one forecasting model, a gradient-boosting ensemble. Every full hour it forecasts all 40 quarter-hours of the next 10 hours; inside, two independently built components (`v7_rt` and `h_int4ss`) each make that forecast and the model averages them.

**Result on the organisers' validation month (7 Sep – 4 Oct 2026):**

| | Score |
|---|---|
| MAE | **40.19 €/MWh** (baseline 66.20) |
| Pinball p10/p90 | **11.07** (24.18) |
| Spike Brier | **0.0840** (0.1132) |
| Direction Brier | **0.3799** (0.4509) |
| Weighted by the challenge's points | **36.7 % better than the baseline** |

A second check on August, trained only on data before 1 August, gives 29.0 % better than the baseline.

---

## 1. The problem in one paragraph

Turku Energia's imbalance price is settled per 15 minutes. It equals the day-ahead (spot) price unless the grid needs balancing. When Finland is short of power (up-regulation), the price is pushed **above** spot; when it has a surplus (down-regulation), it is pushed **below**. Since 1 June 2026 the price in a balancing quarter is the volume-weighted average of the mFRR and aFRR energy prices in the dominant direction. A trader therefore needs four things for each coming quarter-hour:
1. the likely price;
2. how uncertain it is;
3. which way the grid will be balanced;
4. whether the price may jump more than 50 €/MWh away from spot.

## 2. Reasoning chain

1. **Spot is known in advance; forecast the gap.** The day-ahead price is published the afternoon before, so the real unknown is the *gap* = imbalance − spot. Forecasting "spot + a typical gap" alone cuts the baseline's error by about a third.
2. **The direction decides the sign of the gap.** About 60 % of quarters are down-regulated (price below spot) and 40 % up-regulated. The model predicts the direction probabilities first, then the gap. Spike probabilities are built as P(direction) × P(large gap | direction), so the band, the spike risk and the direction always agree with each other.
3. **What moves the gap, and when it is known:**
   - **The recent state:** the latest published gap and direction, and their 1–4 hour averages. These carry the most information for the first two hours.
   - **Real-time grid data (Fingrid):** the measured surplus or deficit, wind against its forecast, frequency, nuclear and hydro changes, electric boilers, CHP, cross-border flows. These matter in the first hours and turn into noise later.
   - **Weather-forecast revisions:** how the newest ECMWF and ICON-EU runs revise wind against the run the day-ahead forecast was based on, at wind-farm locations weighted by installed capacity. A wind forecast that is falling after the day-ahead market closed means a coming shortfall, so up-regulation and higher prices.
   - **The shape of the day-ahead price:** ramps, the day's peaks and troughs, the position in the day.
4. **Use 15 more months of history, rebuilt for the new price rule.** The package starts on 1 June 2026. The organisers allow earlier data (Q&A, 7 Nov), but before June the price followed an older rule (max/min of mFRR and aFRR instead of the volume-weighted average). We rebuilt the pre-June imbalance price with the June rule from Fingrid's mFRR and aFRR prices and volumes. The rebuild reproduces the official price on **99.5 % of Jun–Oct 2026 quarters** (MAE 0.09 €/MWh; the old rule gives 5.45). Training on Mar 2025 – Oct 2026 instead of four months improved both components on every score, most of all the uncertainty band.
5. **Calibrate on the most recent weeks.** Both components re-scale their probabilities and band widths on the last weeks before each forecast period, shrunk toward "no change" when those weeks hold little evidence, so a quiet spell cannot switch the spike warnings off.
6. **One model, built as an ensemble.** Its two components were built separately, with different features, horizon splits and calibration, so their errors only partly overlap. The model averages them with equal weights, so there are no fitted weights to overfit. The ensemble beats each component on all four scores in September and is best averaged over both months: 32.8 % better than the baseline, against 32.4 % for component `h_int4ss` alone and 30.9 % for component `v7_rt` alone.

## 3. Data (all used only from their `first_usable_origin_utc`)

| Data | Used for | Availability rule |
|---|---|---|
| Starter package: Fingrid imbalance price, mFRR/aFRR prices and volumes, direction, consumption, production, flows, day-ahead wind/solar/consumption forecasts; calendar | Target and core features | As given in the package |
| Nord Pool day-ahead price (package) | The anchor of every forecast | D-1 14:00 Finnish time |
| Fingrid Open Data, real-time 3-minute series (surplus/deficit, wind, frequency, nuclear, hydro, boilers, CHP, flows) | Short-horizon state | Quarter end + 30 min, rounded up to the hour |
| Fingrid Open Data, the package's series for Mar 2025 – May 2026, plus aFRR volumes | 15 months of extra training history; the June-rule price rebuild | Same rules as the package |
| Elering's Nord Pool price feed | Day-ahead prices before June 2026 (identical to the package's on all 14,824 overlapping quarters) | D-1 14:00 Finnish time |
| Open-Meteo Single Runs: ECMWF IFS and DWD ICON-EU forecast runs | Wind-forecast revisions at wind-farm locations, Nordic wind | Run time + 8 h (IFS) / + 5 h (ICON), measured |
| OpenStreetMap wind turbines | Capacity weights for the weather points | Static |

The full list with licences is in `sources/SOURCES_AND_LICENCES.md`.

## 4. The model and its two components

**Component A, `v7_rt`:**
- **Learner:** LightGBM quantile regressions for the gap's P10/P50/P90, plus classifiers for up-regulation and for large gaps given each direction.
- **Trees:** small and slow-learning (15 leaves, at least 800 rows per leaf), with settings chosen on training-only folds. Averaged over 5 seeds.
- **Horizons:** two sub-models, one for hours 1–2 with fresh real-time grid data, one for hours 3–10 without it.
- **Neighbour wind:** a twin model that sees Nordic wind supplies only the median.
- **Calibration:** on the last 28 days (Platt scaling for probabilities, a shift for the band).
- **Training:** 15 months of history, with Fingrid real-time series on the history rows too.

**Component B, `h_int4ss`:**
- **Mixture model:** P(up) × the gap's quantile grid given up, plus P(down) × the grid given down; every output is read from that one distribution.
- **Learner:** LightGBM, 7 leaves, 350 trees.
- **Horizons:** separate models for steps 1–4, 5–8 and 9–16, and one for the rest.
- **Features:**
  - the package's own series;
  - real-time imbalance, wind error and grid state;
  - direction-run features (run length, recent up-share, the same quarter the day before);
  - an estimate of the day-ahead wind error from ECMWF revisions;
  - the shape of the day-ahead price;
  - market-era flags (15-minute day-ahead products since 1 Oct 2025, the June 2026 price rule).
- **Calibration:** probabilities and band widths calibrated on the last 14 days, shrunk toward no change.
- **Smoothing:** a light smoothing with the previous hour's forecast.
- **Training:** Mar 2025 – Oct 2026.

**Combining the components:** an equal-weight average of all eight output columns. The quantiles are re-sorted, the direction probabilities renormalised, the spike probabilities capped so they sum to at most 1, and the freshest `data_cutoff_utc` of the two is used. `top_drivers` comes from component A's TreeSHAP.

## 5. Factors that drive the forecast

From the `top_drivers` column (TreeSHAP) of the September forecasts:

| Horizon | What leads |
|---|---|
| **Hours 1–2** | The **latest published gap** (first driver in 34 % of quarters), the **spot level** (45 %) and **grid frequency over the last hour** (9 %). The market's current state carries forward. |
| **Hours 3–10** | The **spot level** (72 %), then the **gap averaged over the last hour**, **wind in Sweden**, the **expected error of the day-ahead wind forecast**, and the **ICON wind revision**. |
| **Overall top-3 presence** | Spot level 78 %, gap in the last hour 44 %, latest gap 36 %, wind in Sweden 32 %, expected wind-forecast error 16 %, ICON wind revision 14 % |

**In words:** near term, momentum; further out, the day-ahead price level and how wrong the wind forecast behind it is turning out to be. Swedish wind matters because Finland trades heavily with SE1/SE3, and a Nordic shortfall pulls Finland into up-regulation.

## 6. Validation metrics

Organisers' `score.py` 0.1.1; MAE / pinball / spike Brier / direction Brier. In both months, training used only data published before the month began.

| Model | September 2026 (organisers' validation) | August 2026 (second check) |
|---|---|---|
| Organisers' baseline | 66.20 / 24.18 / 0.1132 / 0.4509 | 38.67 / 11.65 / 0.0792 / 0.4792 |
| Component A alone (`v7_rt`) | 40.64 / 11.20 / 0.0855 / 0.3892 | 27.67 / 6.56 / 0.0680 / 0.4378 |
| Component B alone (`h_int4ss`) | 40.55 / 11.28 / 0.0865 / 0.3844 | 27.15 / 6.16 / 0.0639 / 0.4219 |
| **Submitted model (the ensemble)** | **40.19 / 11.07 / 0.0840 / 0.3799** | **27.05 / 6.22 / 0.0648 / 0.4202** |
| Better than baseline, points-weighted | **36.7 %** | **29.0 %** |

Coverage of the P10–P90 band: 81.4 % in September and 82.4 % in August (target about 80 %).

**How we kept ourselves honest:**
- **Two check months.** Every change had to improve **both** September and August, each trained only on the data before it, and most of the weeks within them.
- **Fixed weights.** The components are weighted 50/50, not fitted. Ensemble weights and calibration factors were tested by cross-fitting (fit on one month, check on the other).
- **A shared scoreboard.** Every model on the team was scored the same way with the organisers' script.
- **Simplicity over a small gain.** A P90 stretch (×1.15) and a spike cap gained about 0.2 points on the same two months, but pushed band coverage to 84–85 %. We kept the simpler model.

## 7. No future data

Every input row is used only from its `first_usable_origin_utc`. External data got conservative publication delays, rounded up to the next full hour. Both components' pipelines have automated leak tests: they rebuild every feature for random forecast hours with all not-yet-published rows deleted and require identical values.

Training also leaves out the last two hours before each cutoff, whose prices were not yet published then (a label embargo).

## 8. What did not work

Each of these was tested on both months and dropped:
- recency weighting of old data;
- bigger trees;
- realised-volatility features;
- online self-recalibration from the forecast's own recent errors;
- outage messages (UMM);
- Estonian and Danish system data;
- FMI station observations;
- direction-run features in component A;
- a third ensemble component;
- per-output component weights.

`docs/EXPERIMENTS.md` (branch `brainstorming-abdo`) and `docs/RESULTS.md` (branch `brainstorming-frank`) list about 300 experiments.

## 9. Limitations and next steps

- **A few event days carry much of the error.** In September, three days carried a third of the MAE. The band and the spike risk are where the forecast says "this could go far"; the median will miss those days.
- **The heating season is barely in the training data.** The colder months' consumption pattern only begins to show in early October. A full winter of history (2025–26 is in our history set) is the natural next step for the hours 3–10 model.
- **Open data cannot see Turku Energia's own position.** The situational view therefore says "check this situation", never "trade this". Bringing in the company's own plant and position data is the step after that.
