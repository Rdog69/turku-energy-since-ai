# Repository hygiene scan (side job S16)

Scope: the whole git history reachable from `--all` (54 commits at the time of the scan, branch `worktree-agent-a160b6411a7ab7e4e` based on the integration branch). Secret values are never printed here: only file, commit and pattern name.

## Secrets

Patterns searched in every added line of every commit: `api_key`, `FINGRID_API_KEY=`, `FEATHERLESS*=`, `sk-` tokens, `Bearer <token>`, and `key/token/secret/password = "<24+ chars>"`.

| Pattern | File | Commits | Verdict |
|---|---|---|---|
| `api_key` | `README.md`, `SOURCES.md`, `src/data/fingrid.py`, `src/data/external/fingrid.py`, `src/explain/featherless.py`, `tools/kimi.py`, `starter_package/README.md`, `starter_package/build_dataset.py` | b210caa, 48d4534, b35e68e, b4db775, a786f81, 9c84ba1 | Code and documentation that mention a key by name (reading it from the environment or `.env`). No value found. |
| `FEATHERLESS_API_KEY=` | `src/explain/featherless.py` | b210caa | Placeholder in a docstring or error text, not a token. |
| `FEATHERLESS_KEYS=` | `tools/README.md`, `tools/kimi.py` | a786f81 | Placeholder `key1,key2,...` (character shape of the value: `aaa9,aaa9,...`). |
| key/token/secret = long string | `.obsidian/plugins/obsidian-git/main.js` | e27192c | Minified third-party plugin code ("vault backup" commits), not a project credential. |
| `sk-`, `Bearer <token>` | none | none | No hits. |

`.env` is not tracked in any commit (`git ls-files` and a history scan for `.env`, `secret`, `credential`, `*.pem`, `*.key` paths return nothing).

## Large files

| File | Size | Note |
|---|---|---|
| `starter_package/data/inputs.csv` | 39 MB | The only tracked file above 20 MB. Organisers' data (includes Nord Pool spot), committed on purpose. |

Next largest tracked files: `external_data/fingrid/package_history.csv.gz` (4.8 MB), two `submissions/*_ref_mixture.csv` (3.4 MB each), `starter_package/data/inputs.parquet` (2.6 MB).

## .gitignore coverage

`git check-ignore` confirms that `results/`, `.claude/`, `.venv/` and `.env` are ignored. Also ignored: `*.parquet` (with two explicit exceptions for open data), `actuals_*.csv`, `forecast_backtest*.csv`, `spot_nordpool*.csv`, `app_demo_data/`, `external_data/**/raw/`.

## Findings that need a decision

1. **Licensed Nord Pool data is in git history.** `starter_package/data/` (`spot_nordpool.csv`, `inputs.csv`, `inputs.parquet`, `actuals_validation.csv`, quality reports) is committed. The `.gitignore` header already says this is acceptable only while the repository stays private. Before any push to a public remote or fork, purge `starter_package/data/` from history (e.g. `git filter-repo --path starter_package/data --invert-paths`) and re-check `submissions/`.
2. **`submissions/*_ref_mixture.csv`** are forecast files with a `forecast_backtest*` name pattern that is ignored by `.gitignore`, yet two are tracked (added before the rule or force-added). They contain forecasts, which are derived from spot prices; confirm they may be published, or untrack them.
3. **`.obsidian/` (8 tracked files, "vault backup" commits)** is editor state and a third-party plugin bundle. It is not a secret, but it does not belong in the submission repository; add `.obsidian/` to `.gitignore` and `git rm -r --cached .obsidian`.

## Recommendations

- Keep the repository private until the history purge in finding 1 has been done and the result checked with `git log --all -- starter_package/data` (empty).
- Add `.obsidian/` to `.gitignore`.
- Before the final push, re-run this scan (it takes seconds) on the final branch.
