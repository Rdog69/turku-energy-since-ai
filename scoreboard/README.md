# Team scoreboard

One shared log of every model's scores, so the team compares like with like and can see the winner at a glance. **Every person and every AI agent that scores a model logs it here, the same way.**

```bash
python scoreboard/leaderboard.py
```

That prints the current winner, the ranking and each month's scores.

---

## Log a model in four steps

Run everything from the repository root. The starter package is `starter_package/` on `master`; on some branches it is `starter_package/v1/starter_package_v1/`. The scripts find either one.

**1. Score September** (required) with the organisers' `score.py`, from the package folder:

```bash
python score.py --submission <your validation forecast_backtest.csv> --actuals data/actuals_validation.csv --spike-margin 50 --output-dir <your folder>/score
```

**2. Score August** (strongly recommended: a change should win in both months). First build the August actuals once:

```bash
python scoreboard/make_actuals.py --period fold_b
```

Then score your August file against `scoreboard/_local/actuals_fold_b.csv`, using the same `score.py` command as step 1.

**3. Log each month:**

```bash
python scoreboard/log_score.py --owner <Name> --model <model name> --period validation --summary <your folder>/score/score_summary.csv --pre-june no --sources package,fingrid_rt,ecmwf --description "one line: what the model is"
```

Repeat with `--period fold_b` and the August summary. Logging the same owner, model, period and scorer again replaces your entry.

**4. Commit only your entry files** and push them to `master`, or to your branch and open a pull request:

```bash
git add scoreboard/entries/<your files> && git commit -m "scores: <owner> <model>" && git push
```

---

## Rules

1. **The two months:**

   | `--period` | Forecast origins (UTC) | Train only on data published before | Templates |
   |---|---|---|---|
   | `validation` (September) | 2026-09-06T21:00 – 2026-10-04T20:00, 672 hourly origins | 2026-09-06T21:00Z | the organisers' validation templates (`make_templates.py --test-start 2026-09-07 --test-end 2026-10-04`) |
   | `fold_b` (August) | 2026-07-31T21:00 – 2026-08-31T20:00, 744 hourly origins | 2026-07-31T21:00Z | `make_templates.py --test-start 2026-08-01 --test-end 2026-08-31` |

2. **Never score or log the test month** (5 Oct – 1 Nov 2026). The organisers score it. Their README says its input data "must not be used for training", and choosing a model by its test score is tuning on the test set. `log_score.py` refuses it.
3. **No leaks:** every input row is used only from its `first_usable_origin_utc`. A leak scores 0.
4. **Official scores come from the organisers' `score.py`** (`--scorer official --summary ...`). Use `--scorer lab` only when you can't run it, and say why in `--notes`.
5. **Say truthfully whether training used data from before 1 June 2026** (`--pre-june yes/no`). It is allowed (organisers' Q&A answer, 7 Nov 2026), but older realised imbalance prices follow the old pricing rule.
6. **List the data sources** with the names below.
7. **Never commit spot prices, actuals, or files with spot columns.** Entries hold scores only. `scoreboard/_local/` is git-ignored for that reason.
8. **Log your own models.** If you log someone else's (for example from their committed forecast file), set `--logged-by` and say where the numbers come from in `--notes`. Don't edit other people's entries.

## Data source names

| Name | Meaning |
|---|---|
| `package` | The organisers' starter package (Fingrid series, spot, calendar, ENTSO-E neighbours) |
| `fingrid_rt` | Fingrid real-time series you downloaded (put the dataset ids in `--notes`) |
| `fingrid_198_186` | Fingrid real-time surplus/deficit (198, 186) |
| `ecmwf` / `icon_eu` | Weather forecast runs (Open-Meteo Single Runs) |
| `nordic_wind` | Weather in Sweden, Norway, Denmark or Estonia |
| `osm_capacity` | Installed capacity from OpenStreetMap |
| `wind_map` | A learned map from weather to wind production |
| `pre_june_history` | Training rows or models from before 1 June 2026 |
| `elering_spot` | 2025 spot prices from Elering |
| `other:<name>` | Anything else |

## How the winner is chosen

- **Each month:** the points-weighted percentage by which a model beats the organisers' baseline. The weights are the organisers' Level-1 points: MAE 30, pinball 20, spikes 20, direction 10 (starter-package README, "Level 1").
- **The August baseline** is the organisers' own `baseline.ipynb` code run on August (`scoreboard/baseline.py`). Run on September, the same script reproduces their official baseline file exactly.
- **Overall:** the average of September and August. Models scored on one month only rank after those with both.
- **One entry per month:** when a model has both an official and a lab entry for a month, the official one counts.
- **The real competition** gives points = weight × clip((B − T) / (B − best), 0, 1) against the best team on the test month. We can't see other teams, so the scoreboard ranks by the part we control: the gain over the baseline.

## Files

| File | What it does |
|---|---|
| `entries/*.json` | One file per owner, model, period and scorer. One file each means no merge conflicts. |
| `log_score.py` | Writes or replaces an entry |
| `leaderboard.py` | Winner, ranking, each month's scores; `--csv` exports every entry |
| `make_actuals.py` | Builds the actuals for August (or September) from the package |
| `baseline.py` | Runs and scores the organisers' baseline on a month |
| `common.py` | Shared settings: periods, points, paths |

## For AI agents

When you have a validation forecast (and ideally an August one) for a model that could change the team's choice:

1. Score it with the organisers' `score.py` (steps 1 and 2).
2. Log it with `log_score.py`, every flag filled in truthfully, with `--logged-by "<agent> for <owner>"`.
3. Run `leaderboard.py` and report the model's rank and its gap to the winner, in both months.
4. Commit only your new files in `scoreboard/entries/`. Don't change the scripts, this README, or other people's entries without asking the team.
