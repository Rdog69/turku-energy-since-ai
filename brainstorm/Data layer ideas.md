---
tags: [brainstorm, data]
owner: Pavlo
created: 2026-11-06
status: draft
---

# Data layer ideas

Ideas for the data role (PLAN §11, role 1). Back to [[00 Brainstorm Hub]]. Related: [[Risks and checks]], [[Model ideas]].

## Order of work

1. Fix `.gitignore` (`data/` → `/data/`). See [[Risks and checks#Repo issues (fix before writing code)]].
2. Loader that reads the package's long format into one table.
3. `available_at(df, t)` + the as-of leakage test.
4. **Feature table v0 from package data only.** Hand it to the models role.
5. Open-Meteo: **coverage check first**, then the fetcher, then the feature.
6. Fingrid real-time wind (+ nuclear).
7. UMM, for the dashboard only.

Steps 1–4 are Friday night and early Saturday. Everything after that is a bonus on top of a working pipeline.

## One format for everything

Store every external source in the **same long format as the package**:

```
series_id, source, dataset_id, timestamp_utc, value, unit, first_usable_origin_utc
```

Then:
- one function (`available_at`) guards all data,
- one leakage test covers all sources,
- adding a source is just "write a fetcher that outputs these columns",
- `SOURCES.md` can be generated from the distinct `source` values, each with its delay rule.

For external rows: `first_usable_origin_utc = ceil_to_hour(publication_time + safety_margin)`.

## Feature table contract (v0)

One row per (origin, step). Agree the names on Friday night, then only **add** columns and never rename them, so the models role's code keeps working.

| Column | Type | Source | Notes |
|---|---|---|---|
| `origin_utc` | timestamp | – | Hourly, 2 Jun – 1 Nov |
| `step` | int 1–40 | – | |
| `delivery_start_utc` | timestamp | – | `origin + 15 min × (step − 1)` |
| `target_gap` | float | imbalance − spot | **Training rows only**; NaN for test origins |
| `target_dir` | {up, down, none} | mFRR direction | Training only |
| `spot` | float | Nord Pool | At the delivery quarter |
| `spot_ramp_q` | float | | Spot change vs the previous quarter |
| `spot_ramp_h` | float | | Change across the hour boundary |
| `spot_rel_day` | float | | Spot / that local day's mean (daily shape) |
| `wind_fc_da` | float | 246 ☐ | At delivery |
| `wind_share` | float | | Wind ÷ consumption forecast |
| `cons_fc_da`, `solar_fc_da` | float | 165, 247 ☐ | |
| `hour_local`, `dow_local`, `is_weekend_or_holiday` | int | calendar | **Local time**; see [[Risks and checks#DST trap in the test period]] |
| `last_gap` | float | | Newest usable gap (≈ 5 quarters before step 1) |
| `last_gap_age_q` | int | | Quarters between the last usable gap and delivery; lets the model fade it |
| `last_dir_up_share_4q` | float | | Up share in the last 4 usable quarters |
| `roll_absgap_7d`, `roll_spike_hi_7d`, `roll_spike_lo_7d`, `roll_up_share_7d` | float | | Recent conditions; see [[Model ideas#Recent-conditions features]] |
| `se1_last`, `se3_last`, `ee_last` | float | ENTSO-E | Cheap; keep only if the ablation shows a gain |
| *Later:* `om_wind_rev_mw`, `om_model_spread`, `fg_wind_err_mw`, `fg_nuclear_delta_mw`, `umm_out_mw` | float | external | NaN until they exist |

Also: `split` ∈ {train, valid, test}, so nobody filters by date by hand.

Rough size: ~3,600 hourly origins × 40 steps ≈ 145k rows, which fits in memory easily.

## Open-Meteo

**Coverage check first (about 15 min):** request one west-coast point for 1 Jun, 1 Jul and 1 Aug runs, for both ECMWF IFS and ICON. If June–August runs are missing, the feature covers only part of the training period. Then decide whether it's still worth doing, perhaps training only on September onwards.

💡 **Convert wind speed to power before taking differences.** Turbine output depends on wind speed roughly cubically between cut-in (~3 m/s) and rated speed (~12–13 m/s), then flattens. A 1 m/s revision at 7 m/s changes power a lot; at 14 m/s it changes almost nothing. Run 100 m wind speed through a generic power curve, then compute the revision in "capacity-share" units. ☐ The thresholds are typical turbine values; check one published curve.

💡 **Which run the day-ahead plan was based on:** we can't know which run Fingrid's day-ahead forecast used. Use "the latest run usable before day-ahead gate closure (12:00 CET on D−1)" as the reference. Then:
`om_wind_rev = power(latest usable run) − power(reference run)` at delivery time.

💡 **Weighting the points:** start with ~5–8 west-coast points (for example Vaasa, Kokkola, Pori, Raahe, Oulu area) plus 2–3 inland points, with equal weights. Weighting by installed capacity is better but needs a wind farm list (☐ the Finnish Wind Power Association publishes one). Do that only if time allows.

💡 **Model disagreement:** `om_model_spread = |ECMWF power − ICON power|` at delivery. When the models disagree, the uncertainty is higher, so the P10–P90 band should widen. This is cheap once both are downloaded, and it suits pinball loss.

**Delay:** take the conservative end of the plan's estimates (ECMWF IFS +7 h, ICON +4 h after init), and round up to the next hour.

## Fingrid real-time

- Free API key; request it on **Friday night** in case sign-up is slow.
- Dataset IDs ☐: the plan guesses 181 wind, 188 nuclear, 191 hydro. Confirm them on data.fingrid.fi.
- 💡 **`fg_wind_err_mw`** = realised wind − day-ahead wind forecast over the last 4 usable quarters (average). A wind shortfall that has lasted an hour tends to continue into the next few hours, and it points to up-regulation. This probably matters most for steps 1–8.
- 💡 **`fg_nuclear_delta_mw`** = nuclear output now − 3 h ago. A large drop means a trip, and that tells us about up-regulation before anything else does. Rare, but it explains big spikes, which is good for the dashboard.
- Rate limits: download the history **once** to a local file (git-ignored) and build features from that file, never from live API calls during the backtest.
- ⚠ Corrected history: see [[Risks and checks#Leakage traps]]. Use a delay of at least 30 min and mention it in the report.

## UMM (dashboard first)

- Store each **message version** with its `publicationDate`. At origin `t`, use the latest version published ≤ `t`.
- Dashboard: a timeline of active outages in the next 10 h.
- Model: `umm_out_mw` (total unavailable MW for Finland during the delivery quarter). Only add it if there's time; outages are rare in ~4 months of training data.

## Handoff

- `python -m src.features.build --split all` writes `features.parquet` to a local git-ignored folder. Anyone can run it from their own `starter_package/`.
- Each new feature group gets one line in a changelog note in this vault (e.g. `brainstorm/Feature changelog.md`), so the models role knows what to re-test.
