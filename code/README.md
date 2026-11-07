# Source code and instructions for running it

**Placeholder.** Before submitting, this folder gets the code that reproduces `forecast/forecast_backtest.csv`, without data and keys. The final layout is still to be decided: a copy here, or a pointer to a tagged commit.

The forecast is built in three parts:

| Part | Where it lives now | Reproduces |
|---|---|---|
| Abdo's history-trained model `h_int4ss` | `brainstorming-abdo`: `experiments/lab/` (`submit.py`, `combo.py`, `features/`, `data.py`), `src/data/external/` (fetchers), spec `lumi/final/h_int4ss.json` | `LAB_HISTORY=1 python -m experiments.lab.submit --mode test --spec-file lumi/final/h_int4ss.json --tag h_int4ss` |
| Frank's `v7_rt` | `brainstorming-frank`: `src/` (`python -m src.backtest.run --period test --model v7_rt`) | his half |
| The blend | `brainstorming-frank`: `submissions/tools/blend_period.py` | `forecast_backtest.csv` |

## To do before submitting

- [ ] One README with the exact commands, Python version and `requirements.txt`, in order: fetch the external data, then build the history, then each model, then the blend, then validate.
- [ ] Leak tests runnable in one command: the lab's `leakcheck` and Frank's `pytest`.
- [ ] Remove anything with keys (`.env`) or licensed data (`starter_package/data`, Elering spot copies), plus private test-period scripts (`experiments/lab/_cache/`).
- [ ] State the data cutoff: training on data published before 4 Oct 2026 21:00 UTC, and pre-June history allowed (organisers' answer of 7 Nov).
