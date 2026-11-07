# Repository hygiene scan (refresh, job H1)

Scope: full history of the merged branch at `bf529b9` (all commits reachable from it, including the Frank, Abdo and Vexa merges). No values are printed here, only paths, commits and pattern names. Header and `series_id` checks only for data files.

## 1. Secrets

Every added line of every commit (`git log -p`) was tested against the patterns below. The patterns need a literal value of realistic length, so code that only mentions a key by name does not match.

| Pattern | Hits (file, commit) |
|---|---|
| `rc_` + 24 or more hex characters (Featherless key shape) | none |
| `sk-` token | none |
| `Bearer <20+ chars>` | none |
| `ghp_` token | none |
| `BEGIN ... PRIVATE KEY` | none |
| `API_KEY` / `api_key` `=` or `:` followed by a 16+ character value | none |
| `FEATHERLESS_KEYS=` followed by a value | none |
| `.env` file in any commit (any directory) | none |

The earlier scan listed files that mention `api_key` by name (fetchers, `tools/kimi.py`, docs). Those are still variable names only. The minified `.obsidian/plugins/obsidian-git/main.js` is third-party code, not a credential.

## 2. Licensed spot data in the current tree

Checked: CSV and CSV.GZ headers plus the `series_id` column, parquet column names and string tables, JSON key names.

| Path | What it holds | Real spot? |
|---|---|---|
| `starter_package/data/spot_nordpool.csv` | `fi_spot_price` series (Nord Pool) | Yes, licensed |
| `starter_package/data/quality_report.csv` | has `fi_spot_price` rows (coverage statistics) | Name only; check whether it has values before any release |
| `starter_package/data/actuals_validation.csv` | `spot_price` column (organisers' actuals) | Yes, licensed |
| `external_data/elering/fi_spot_history.csv.gz` | `fi_spot_price` series, 2025 (Elering, from Nord Pool) | Yes |
| `external_data/history/pkg_history.csv.gz` | `fi_spot_price` series, Mar 2025 - May 2026 | Yes |
| `app_demo_sample/test/` (51 files) | `spot` key in every origin file, `p50_minus_spot`, `latest_imbalance_vs_spot`, `mae_spot_only` | No. `index.json` and the origin files carry `"demo": true`. `src/export/dashboard.py --demo` replaces spot with a synthetic curve (`55 + 20 sin(...) + 8 sin(...)`), shifts p10/p50/p90 by the same amount and drops `last_imb`. `track_record.json` holds error statistics only. |
| `submissions/*.csv` (28 forecast and validation files) | no spot column; absolute p10/p50/p90 are spot plus a forecast gap, so they are derived from spot | Derived, not raw. Needs a licence decision |
| `external_data/fingrid/*`, `elering/system_*`, `energinet/*`, `fmi/*`, `open_meteo/*`, `osm/*` | no spot column or series (parquet strings and headers checked) | No |
| `starter_package/data/inputs.csv`, `inputs.parquet` | no `fi_spot_price` series (spot ships separately) | No spot, but contains Nord Pool-era package data and is the 39 MB file below |
| `experiments/` | JSON, CSV and Python only, no spot columns or series | No |

Note: `.gitignore` lists `external_data/history/` and `spot_nordpool*.csv`, but both are tracked (force-added), so the ignore rule does not protect them.

## 3. Large files

| Where | File | Size |
|---|---|---|
| Current tree | `starter_package/data/inputs.csv` | 39 MB |
| Any blob in history reachable from `bf529b9` | `starter_package/data/inputs.csv` | 39 MB (only one) |

No other file or blob is above 20 MB.

## 4. .gitignore coverage

Verified with `git check-ignore -v`:

| Path | Ignored by |
|---|---|
| `results/` | `.gitignore:29` |
| `.claude/` | `.gitignore:67` |
| `.venv/` | `.gitignore:35` |
| `.env` | `.gitignore:37` |
| `scoreboard/_local/` | `scoreboard/.gitignore:2` |

Not ignored: `.obsidian/` (still tracked, editor state and a plugin bundle; add it to `.gitignore` and `git rm -r --cached .obsidian`).

## Purge list before any public release

Every path below has been committed at some point and holds, or is derived from, licensed spot data. Remove all of them from history (for example `git filter-repo --invert-paths` with each `--path`), then check `git log --all -- <path>` is empty.

1. `starter_package/data/` (whole directory: `spot_nordpool.csv`, `inputs.csv`, `inputs.parquet`, `actuals_validation.csv`, `quality_report.csv`, `quality_report.md`)
2. `external_data/elering/fi_spot_history.csv.gz`
3. `external_data/history/pkg_history.csv.gz`
4. `submissions/` (all `forecast_backtest_*.csv`, `validation_*.csv` and `score_*/`), unless the organisers confirm forecasts may be published
5. `.obsidian/` (not licensed, but should not ship)

Also scrub mentions: nothing else in history carries spot values, and `app_demo_sample/` can stay (synthetic spot).
