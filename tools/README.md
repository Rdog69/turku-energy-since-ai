# tools/kimi.py: Kimi workers via Featherless

`kimi.py` sends tasks to `moonshotai/Kimi-K3.1-Pro` through Featherless's OpenAI-compatible API. It spreads the tasks over a pool of API keys and runs one request per key at a time, in parallel.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install -r tools/requirements.txt
```

Create `.env` in the repo root (it is git-ignored, so never commit it):

```
FEATHERLESS_BASE_URL=https://api.featherless.ai/v1
FEATHERLESS_MODEL=moonshotai/Kimi-K3.1-Pro
FEATHERLESS_KEYS=key1,key2,key3,key4
```

## Usage

```bash
# Check every key
.venv/bin/python tools/kimi.py ping

# One task: text, a file, or stdin; add files as context with -c
.venv/bin/python tools/kimi.py ask -p "Review this function for leakage" -c src/data/available.py
.venv/bin/python tools/kimi.py ask task.md -o answer.md

# Many tasks in parallel: every DIR/*.md is one task; answers go to DIR/out/<name>.md
.venv/bin/python tools/kimi.py batch work/report_sections/ -c docs/PLAN.md

# Calls and tokens per key (from .kimi/usage.jsonl)
.venv/bin/python tools/kimi.py usage
```

Useful options:

- `--system FILE`: a custom system prompt.
- `--max-tokens N` (default 16000).
- `--per-key N`: run more than one request per key at a time, if your Featherless plan allows it.
- `--force`: re-run tasks that already have output. `batch` skips finished tasks by default, so you can simply re-run an interrupted batch.

Rate limits (429) and server errors are retried with backoff. Logs name keys by index only, never by value.

## Data guard: what is never sent

Nord Pool spot data is licensed to Turku Energia for hackathon use only, so it must not go to a third-party API. Before anything is sent:

- **Context files are refused** if they are organiser data: `spot_nordpool*`, `actuals_*`, `inputs.csv/.parquet`, `*.parquet`, `forecast_backtest*`, anything in `starter_package*/data/` or `TurkuEnergia_SinceAI2026/`.
- **Prompts are refused** if they contain spot markers (`fi_spot_price`, `spot_price,` …) together with data rows.
- **Prompts with 3 or more raw timestamped data rows are refused** by default. Pass `--allow-data` only for non-spot data.

Send code, schemas and aggregate numbers instead. Treat Kimi's output as a draft and review it before it lands in the repo, especially anything that touches the data availability rule.
