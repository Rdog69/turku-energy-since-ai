# Experiment lab (shared by the agent swarm)

**Goal:** beat the reference rows in [`leaderboard.csv`](leaderboard.csv) on the four automatic metrics of the Turku Energia challenge: MAE of p50, mean pinball of p10/p90, spike Brier, and direction Brier. Lower is better for all four. Results must hold on **both folds**:

- **Fold A:** train on deliveries before 7 Sep, validate 7 Sep – 4 Oct. This is the organisers' window.
- **Fold B:** train on deliveries before 1 Aug, validate August.

## Rules (non-negotiable)

1. **No leakage.** A feature for row `(origin, step)` may only use source rows with `fu ≤ origin`, where `fu` is the first-usable time. Read sources **only** through the helpers in `data.py`:
   - `asof(series, origins, lags)`: newest usable quarter and older lags
   - `asof_window(...)`
   - `at_delivery(series, base, offset_q)`: value at the delivery quarter, only if already published
   - `per_origin(base, df)`: broadcast per-origin values to rows
   - `nwp_latest(nwp, base, var, point, nth)`: newest usable weather-model run at the delivery hour

   `run_experiment` runs `leakcheck` on every feature function. It recomputes features with all sources truncated to `fu ≤ origin` and fails on any difference. **Never bypass it.** Targets (`imb`, `gap`, `dir`) are never features.
2. **Anything fitted inside a feature** (a power curve, a lookup table) must be fitted only on deliveries before **31 Jul 21:00Z**, the start of fold B's validation. Hard-code that cutoff.
3. **Don't edit the shared files** (`data.py`, `models.py`, `run.py`, `features/package.py`). Put your code in `experiments/lab/features/<agent>.py` and `experiments/lab/exp_<agent>.py`.
4. Prefix commands with `OMP_NUM_THREADS=2` (6 agents share 10 cores), run from the repo root, and use `.venv/bin/python -W ignore`.
5. **Never print or export rows of `fi_spot_price`** (licensed), and never send data to external services.
6. Don't commit to git; the coordinator does that.

## API

```python
from experiments.lab.data import threads; threads(2)          # before sklearn is imported
from experiments.lab.run import run_experiment, board
from experiments.lab.features.package import package_features  # reference set (35 features)
from experiments.lab.data import Data, asof, asof_window, at_delivery, per_origin, nwp_latest, U

def my_features(base, data):            # base: origin, step, delivery (+ targets, never use them)
    o = base["origin"].drop_duplicates().sort_values().reset_index(drop=True)
    s = data.series("fg_rt", "fg198_surplus_deficit_rt")    # long: series_id, ts, value, fu
    a = asof(s, o, lags=(0, 1, 2, 3)); a.index = U(o)        # per origin
    return per_origin(base, a.add_prefix("rt198_"))

run_experiment("rt198 lags", agent="nowcast", feature_fns=[package_features, my_features],
               model="mixture",       # or "direct"
               target="gap",          # or "price"
               calibrate=True, notes="...",
               hgb=None,              # HistGradientBoosting overrides
               weight_fn=None,        # f(train_rows) -> weights
               post=None,             # f(pred, va_rows, X_va) -> pred
               drop=None)             # feature names to drop
```

**Sources** (`data[...]`, loaded lazily):

| Key | Content |
|---|---|
| `pkg` | The starter package in long form, including spot (`fi_*`, `se1_*`, `cal_*`) |
| `fg_rt` | Fingrid real-time series, averaged per quarter: `fg181_wind_rt`, `fg192_production_rt`, `fg193_consumption_rt`, `fg194_net_import_rt`, `fg198_surplus_deficit_rt`, `fg186_surplus_deficit_cum_rt`, `fg177_frequency_rt`, `fg188_nuclear_rt`, `fg191_hydro_rt`, `fg209_power_system_state_rt`. Usable 30 min after quarter end, so the newest is 3 quarters before step 1. |
| `fg_extra` | `fg75_wind_15min`, `fg268_wind_capacity`, `fg242_production_plan_da` (BRP plans, published 18:00 on D-1), `fg243_mfrr_up_bids_sum`, `fg22_mfrr_last_up_bid_price`, `fg251_mfrr_last_down_bid_price`, `fg176_imbalance_power_fi_se` |
| `fg_hist` | Package series from Fingrid, Mar 2025 – May 2026 (may still be downloading) |
| `umm` | Nord Pool outage messages: one row per message version × unit × period. Columns: `publicationDate`, `unavailabilityType` (1 = unplanned, 2 = planned), `unit_kind`, `area`, `in_area`/`out_area`, `fuel_type`, `unavailable_mw`, `event_start_utc`, `event_stop_utc`, `fu` |
| `ifs` / `icon` / `metno` | Open-Meteo weather-model runs: `model`, `run_init_utc`, `point`, `valid_utc`, `wind_speed_100m`, … with `fu`. ICON and MET Nordic may still be downloading. |
| `era5` | Reanalysis. `fu` = valid time + 6 days, so it's only usable for fitting mappings, before the cutoff in rule 2 |
| `fmi` | 10-min station observations (`station`, `time_utc`, `ws_10min`, …, `fu`) |
| `elering` / `energinet` | Estonian and Danish system data with `fu` |

The non-long sources (`umm`, NWP, `fmi`, `elering`, `energinet`) don't fit `asof` directly. Filter them with `fu <= origin` per origin yourself (e.g. `merge_asof` on `fu`), and **always** let `leakcheck` verify. Event sources: use the newest message version with `fu ≤ origin`.

`board("A")` shows the leaderboard. Predictions are saved in `_cache/preds/`.

## Reporting

Write `docs/brainstorm/swarm/<agent>.md`:
- a results table (copied from the leaderboard),
- what helped and what didn't, **on both folds**,
- the features or settings you recommend for the final model,
- anything suspicious.

Be honest: a null result is a result.
