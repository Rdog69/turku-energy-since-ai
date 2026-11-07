# Swarm handoff: what we learned and how to build on it

> Branch `brainstorming-abdo`, night of 6–7 Nov. Six Claude agents and a Featherless LLM loop ran leak-checked experiments on one shared lab. **Start here**, then read the agent reports linked below.

## The current best model

Leaderboard name **"INT2 reg+bands+rt+dir+blend"**, score **+3.88**. Score = points-weighted % gain over the reference model, averaged over folds A (Sep) and B (Aug). It's better on all four metrics on both folds.

```json
{"features": ["package", "rt_imb", "rt_wind", "rt_misc", "runs", "dir"], "model": "mixture",
 "hgb": {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150},
 "bands": [[1,4],[5,8],[9,16]], "hist_blend": 0.6}
```

Reproduce it:

```bash
.venv/bin/python -m experiments.lab.combo '<that json + "name">'
```

For context, against the organisers' baseline on validation (official `score.py`, safety model):

| | MAE | Pinball | Spike Brier | Direction Brier |
|---|---:|---:|---:|---:|
| Baseline | 66.2 | 24.2 | 0.113 | 0.451 |
| Safety model | 43.5 | 12.3 | 0.095 | 0.429 |

The best lab models are about 2–3 % better again. Live ranking: `python -c "import sys; sys.path.insert(0,'tools'); import fl_lab; print(fl_lab.scored_board().head(20))"`.

## What works (holds on both folds)

| Component | Effect | Source |
|---|---|---|
| **Regularised trees** (15 leaves, min_samples_leaf 400, 150 iterations) | Better on every metric | [structure](structure.md) |
| **Separate models for steps 1–4 / 5–8 / 9–16** | Step 1–4 MAE −7 %; about +1.6 score points | [structure](structure.md) |
| **Direction mixture** (P(up) × conditional gap quantiles) over direct, once regularised | Spikes and pinball | [structure](structure.md) |
| **Fingrid real-time:** wind error (`rt_wind`) is the strongest; `rt_misc` (frequency, nuclear, net import) adds to it | MAE at steps 1–4 −3.5 %; direction Brier at steps 1–4 0.418 → 0.386 | [nowcast](nowcast.md) |
| **Direction history** (`runs`, `dir`) + **blending P(up) with a model trained on last year's Fingrid history** (`hist_blend` 0.6) | Direction Brier A 0.437 → 0.397 | [history](history.md), [probs](probs.md) |
| **Spike calibration that shrinks Platt when the calibration window holds few spikes** | Fixes fold-B collapse of p_lo (0.002 predicted vs 6.7 % observed) | [probs](probs.md) |
| **ECMWF wind revision** since the day-ahead forecast (`ifs_rev`, power curve fitted before 31 Jul) | Better on all four metrics on both folds alone (W2) | [weather](weather.md) |

## What doesn't (killed, so don't redo it)

- **Price target instead of gap:** loses MAE on both folds.
- **Recency weights:** help one fold and hurt the other.
- **Bigger trees:** worse.
- **UMM outage features:** no gain on both folds. Large trips (≥ 800 MW) don't occur in training; the only one is OL3 on 9 Sep, which is in validation. Keep only a rule-based override for fresh big trips. Planned-outage MW trends over time and acts as a date proxy. See [outages](outages.md).
- **Consumption/production-plan error (`rt_cons`):** hurts fold B.
- **Estonian/Danish neighbour data, month×hour priors:** weak or harmful.
- **Isotonic or per-band calibration, model blends for spikes, HMM smoothing, snapping prices to round numbers:** see [probs](probs.md) and [round 2](../COMPARISON_1.1.md).
- **Fingrid bid-stack datasets:** fg243 is all zeros, fg22 doesn't exist, fg251 covers only a few days.

## Drift warning for the test month (5 Oct – 1 Nov)

From [history](history.md):
- Last autumn behaved differently from this summer. In Oct 2025, up-regulation peaked **at midday**; in summer 2026, **in the evening**.
- Last autumn had far more high-demand hours.
- This is why the last-year history blend helps, and why calibration on the last 14 days of September may not transfer. probs found a 28-day calibration window much better on fold A.

## How to run experiments yourself

- **The lab:** [`experiments/lab/README.md`](../../../experiments/lab/README.md). It has leak-safe helpers, a `leakcheck` that recomputes features with every source truncated to its first-usable time (it catches a deliberately leaky feature), two folds, and a shared `leaderboard.csv`. Feature and post functions never see targets.
- **One spec, one experiment:** [`experiments/lab/combo.py`](../../../experiments/lab/combo.py). Its `REGISTRY` lists every leak-checked feature set.
- **The overnight loop:** [`tools/fl_lab.py`](../../../tools/fl_lab.py). Cheap Featherless models propose specs from the leaderboard, and they run 3 at a time.
  - Steer it live via `experiments/lab/loop_control.json` (`steer`, `per_round`, `workers`, `stop`).
  - History is in `loop_log.md` and `loop_state.jsonl`.
  - Models only choose from whitelisted options; they never write code.
- **Submission:**

  ```bash
  python -m experiments.lab.submit --mode val|test
  ```

  It uses the official templates, a 2 h label embargo, the official validator, and (in val mode) the official `score.py`. The safety submission `submissions/forecast_backtest_ref_mixture.csv` passes validation. It's the reference mixture; the final file should use the best combined model.

## Data

See [`SOURCES.md`](../../../SOURCES.md). All external data is in `external_data/` with a `first_usable_origin_utc` column per row:
- Fingrid real-time, extra datasets and history from Mar 2025;
- ECMWF IFS runs (ICON-EU still downloading);
- ERA5, FMI, UMM, Elering, Energinet.

The fetchers are in `src/data/external/`.

## Open items for the team

1. Make the best spec (or the loop's winner) the submission model in `submit.py`. It currently supports package features only; feature specs plus bands and post need wiring in.
2. **Organiser questions are still open:**
   - the Fingrid real-time delay (we assume 30 min);
   - pre-June history for training;
   - whether UMM is allowed.
3. **`top_drivers` column:** still empty (role 4).
