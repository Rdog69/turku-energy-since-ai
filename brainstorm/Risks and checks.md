---
tags: [brainstorm, risks]
created: 2026-11-06
status: draft
---

# Risks and checks

Things that can quietly cost points or score us 0. Back to [[00 Brainstorm Hub]].

## Always have a valid submission

A file that fails validation scores **0**, and nothing can be fixed after Sun 10:00.

- [ ] **Fri night:** `forecast_backtest.csv` from spot − 7.7 (P10/P90 from training gap quantiles per step, probabilities from training shares). Run `validate_submission.py` on it and store it as `submissions/00_spot_anchor.csv` (outside git, since the CSV is ignored).
- [ ] Each time a better model passes validation, save it as the next numbered file. **Submit the newest one that passed, never an unvalidated one.**
- [ ] Sat night: full dry run of the test backtest (all 673 origins) with the current model.

## DST trap in the test period

- Finland moves from UTC+3 to UTC+2 on **Sun 25 Oct 2026**. All training data (1 Jun – 4 Oct) is UTC+3.
- Demand and the evening peak follow the **local** clock. A model that uses UTC hour learns "peak = 17 UTC", and from 25 Oct the real peak is at 18 UTC. That affects about 7 of the 28 test days.
- **Fix:** compute `hour_local`, `weekday_local` and `is_weekend_local` in `Europe/Helsinki`. Never use the UTC hour as a feature. Spot's daily shape also follows local delivery days.
- [ ] Check: plot the mean gap by `hour_local` for 5–24 Oct vs 25 Oct – 1 Nov (inputs only, never the actual target for the test period).

## Leakage traps

The rule is simple, but it's easy to break by accident:

| Trap | How it leaks | Guard |
|---|---|---|
| `pandas.shift()` for lags | A fixed shift ignores real publication delays | Every lag comes from the availability filter. Search the code for `.shift(` before submitting |
| Rolling features over the full series | `rolling().mean()` on the whole table then sampled at `t` uses rows not yet published | Compute rolling features **per origin** after filtering, or check that the window ends at the last usable row |
| Normalising or scaling on all data | Test-period means leak into training features | Fit scalers on training only (LightGBM doesn't need scaling, so skip it) |
| External sources without `first_usable_origin_utc` | No guard at all | Convert every source to the package's long format first ([[Data layer ideas#One format for everything]]) |
| `data_cutoff_utc` as the max timestamp | Spot and forecast rows have future timestamps | Use measured series only, clip to the origin (PLAN §5 already says this) |
| Fingrid "real-time" history | Stored values may have been corrected after first publication (☐) | Use a cautious delay and say so in the report |
| Open-Meteo Historical Forecast API | Mixes runs and leaks the future | Use only Single Runs with a `run init + delay ≤ origin` rule |

**Leakage test, "as-of check":** for ~50 random origins, build the features twice:
1. from the full dataset, and
2. from the dataset cut to rows with `first_usable_origin_utc ≤ t`.

The two must be **exactly equal**. If any feature differs, it reads data it shouldn't. This catches all the traps above with one test.

## Package datasets 246 and 247

☐ **Check this.** The plan warns that Fingrid's *hourly-updated* forecasts store only the latest version, so using their history leaks. Check which kind of forecast datasets 246 and 247 in the package actually are: day-ahead (fixed once a day) or hourly-updated. If they are hourly-updated and the organisers set `first_usable_origin_utc` to a day-ahead time, then the values are newer than that time claims. I don't remember Fingrid's ID mapping with confidence, so check the dataset pages on data.fingrid.fi and the package's `availability.csv` / quality report. If in doubt, ask in `#turku-energia`.

## Repo issues (fix before writing code)

- [ ] ⚠ **`.gitignore` rule `data/` also ignores `src/data/`**, where the availability layer is planned. Change it to `/data/` (or rely on `starter_package/`). Otherwise the most important code never reaches the repo, and the leakage review sees nothing.
- [ ] Same function, two names: README says `rows_available_at()`, PLAN says `available_at()`. Pick one and use it everywhere.
- [ ] README's repository layout is older than PLAN §9 (it's missing `api/`, `automation/`, `tests/`, `src/explain/`).
- [ ] `requirements.txt` and `SOURCES.md` don't exist yet but are linked from the README.
- [ ] `.obsidian/workspace.json` is committed and changes whenever someone opens the vault, which causes merge conflicts. Add it to `.gitignore`.
- [ ] Before submitting: `git log --all --stat | grep -iE "spot|nordpool|parquet|actuals"` to confirm no licensed data was ever committed, including in old commits.

## Scoring pitfalls

- Scores are **relative to the best team**. A small gain over spot + constant can be worth a lot of points, and so can a small loss. Don't ship a fancier model unless it beats the simple one on validation.
- Pinball loss rewards **coverage near 80 %**. A band that's too narrow costs more than one slightly too wide. If unsure, widen.
- Brier for spikes: base rates drift (see [[Model ideas#Recent-conditions features]]). An overconfident model under drift is worse than base rates.
