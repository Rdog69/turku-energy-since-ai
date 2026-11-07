# Source code and instructions for running it

The forecast is built in three parts, each in the team repository. Data and API keys are not included (see "Data" below).

| Part | Branch and path | Command |
|---|---|---|
| Frank's `v7_rt` | `brainstorming-frank`: `src/` | `python -m src.backtest.run --period test --model v7_rt` |
| Abdo's `h_int4ss` | `brainstorming-abdo`: `experiments/lab/` (`submit.py`, `combo.py`, `features/`, `data.py`) and `src/data/external/` (data fetchers) | `LAB_HISTORY=1 python -m experiments.lab.submit --mode test --spec-file lumi/final/h_int4ss.json --tag h_int4ss` |
| The blend | `brainstorming-frank`: `submissions/tools/blend_period.py` | Writes `forecast_backtest.csv` from the two member files |

## Run order (Abdo's half; Frank's README has the same for his)

```bash
python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
# 1. external data (needs FINGRID_API_KEY in .env; Open-Meteo and Elering need no key)
python -m src.data.external.fingrid all                # package series history, real-time series
python -m src.data.external.fingrid history rt2 mfrr2
python -m src.data.external.elering_spot               # day-ahead prices before June 2026
python -m src.data.external.open_meteo ifs_hist        # ECMWF runs
# 2. the history table, with pre-June prices rebuilt under the June 2026 rule
python -m experiments.lab.build_history
# 3. the model's forecast file
LAB_HISTORY=1 python -m experiments.lab.submit --mode test --spec-file lumi/final/h_int4ss.json --tag h_int4ss
# 4. validation month, scored with the organisers' score.py
LAB_HISTORY=1 python -m experiments.lab.submit --mode val --spec-file lumi/final/h_int4ss.json --tag h_int4ss
```

## Leak tests

- Abdo's lab: every feature function is checked automatically before use (`experiments/lab/data.py: leakcheck`). It rebuilds the features for random forecast hours with every not-yet-published row deleted and requires identical values.
- Frank's pipeline: `python -m pytest`.

## Data

- The starter package (`starter_package/data/`) comes from the organisers.
- External data is downloaded by the commands above.
- Nord Pool spot prices are licensed for the hackathon only: keep them local and delete them after the event.

## Still to do before submitting

- [ ] Freeze both branches at the commits that produced the submitted files, and record the commit hashes here.
- [ ] Add one `requirements.txt` per pipeline with pinned versions.
- [ ] Exclude `.env`, `starter_package/data/` and any local caches from what is shared.
