# State (Sat 7 Nov 2026, afternoon)

## NEW: history mode (pre-June data, confirmed allowed by the organisers)

- **What:** the lab now trains on **Mar 2025 – Oct 2026** (19 months, 556k rows instead of 119k). Set `LAB_HISTORY=1`.
  - The pre-June imbalance price is **recomputed with the 1 June rule**; it reproduces the official price on 99.5 % of Jun–Oct 2026 quarters. Data is in `SOURCES.md` §11.
  - The organisers' answer is in `docs/QUESTIONS_FOR_ORGANISERS.md` (question 2).
- **New fold C** = 5 Oct – 1 Nov 2025: last year's test weeks.
- **Results** are in `experiments/lab/leaderboard_hist.csv`; compare runs with `python -m experiments.lab.hist_compare "<ref name>"`.

**Same INT4 recipe, trained on the history (lab, lower is better):**

| Fold | Old INT4 (Jun–Oct 2026) | History INT4 |
|---|---|---|
| A (Sep) | 41.37 / 11.65 / 0.0887 / 0.3863 | **40.51 / 11.27 / 0.0866 / 0.3838** |
| B (Aug) | 27.27 / 6.59 / 0.0667 / 0.4262 | **27.12 / 6.16 / 0.0637 / 0.4210** |
| C (Oct 2025) | n/a | 50.74 / 15.67 / 0.1034 / 0.4601 (best of the history runs) |

**Blends with Frank's v4_n50** (`python -m experiments.lab.exp_hist_blends`; gain over team5050, challenge weights):

| Blend | Sep | Aug | Weeks won |
|---|---|---|---|
| ½ Frank + ½ history INT4 | +1.9 % | +2.1 % | 9/10 |
| **⅓ Frank + ⅓ history INT4 + ⅓ old INT4** | +1.7 % | +2.5 % | **10/10** |

**Other findings:**
- Training on all of 2025 hurts fold C a little for the simplest features. 2025 was a much wilder market: summer 2025 had about 20 % high spikes, against 3–13 % in summer 2026.
- Recency weights with a 240-day half-life gave a small win on all four scores on A and B; fold C is pending.
- The regime flags (15-min day-ahead, June price rule) help on A and B.

**Running / queued:**
- `vol_regime` features (realised volatility over 3/7/28 days, for calm vs wild months).
- Bigger trees, a weather-only history member, `cal_days` 28.
- RT2 and balancing-market data with history (`fingrid history` command).
- Local queue: `experiments/lab/queue.py` with `lumi/queue_hist.jsonl`. LUMI: `lumi/hist_watch.sh` submits `lumi/queue_lumi.jsonl` (40 jobs) when LUMI is back.

**For Frank:** `docs/handoff/FRANK_HISTORY.md`, how to retrain v4_n50 on the history (an extended starter package his loader reads unchanged).

**Submission:** `team5050` stays the safety net until a history blend has its test file and has passed all checks.

---

# Earlier state (Sat 7 Nov, late morning)

## Best results so far

**Lab scores** come from `tools/fl_lab.py` → `scored_board()`. Score = points-weighted % gain over the reference model, averaged over folds A and B. The best runs:

| Model | Score |
|---|---:|
| `P5 INT4+ss H7` | +6.17 |
| `P2 INT4+ss lgb leaves7` | +6.17 (most robust: worst fold +5.29) |
| `P2 INT4+ss+c2+wx lgb cal14` | +6.07 |
| `G rt+dir+wx B3 H15 eb50` | +5.76 |

Most of the top 20 are within noise of each other.

**Official validation** (organisers' `score.py`, Sep; files in `submissions/`):

| File | MAE | Pinball | Spike | Dir | Note |
|---|---:|---:|---:|---:|---|
| `team5050` = ½ Frank `v4_n50` + ½ our `m_int4ss_lgb7` | **40.97** | 11.63 | **0.0861** | **0.3803** | Current safety net; beats Sakibul's blend 9/10 weeks |
| Sakibul's 65/35 (our rebuild) | 40.95 | 11.78 | 0.0865 | 0.3822 | |
| `final_greedy` (9 members) | 41.40 | **11.43** | 0.0879 | 0.3843 | Best pinball |
| `cal_int4` | 41.51 | 11.88 | 0.0900 | 0.3889 | |

**Lab fold B (August):**

| Model | MAE | Pinball | Spike | Dir |
|---|---:|---:|---:|---:|
| `team5050` | 27.27 | 6.57 | 0.0677 | 0.4281 |
| Sakibul | 27.39 | 6.73 | 0.0689 | 0.4334 |
| Frank v4 alone | 27.99 | 7.00 | 0.0710 | 0.4466 |

## Key insights
- **Frank is stronger on September, we're stronger on August,** so blending works. The cross-fitted greedy ensemble (`experiments/lab/ens_greedy.py`) puts Frank's v4 into every output group. In-sample it's A +6.38 / B +8.23, but cross-fitted only +5.79, so it needs careful selection.
- **eb50 calibration** (`experiments/lab/calib_eb.py`) is the biggest single gain. Always use `"calib": "eb50"`.
- **MAE has a floor:** 3 event days carry 34 % of September's MAE. Remaining gains are in pinball, spikes and direction, and in model diversity.

## Running or lost when LUMI went down (round 5)
Batch IDs are in `~/frank/batch2_ids.txt` and `~/te/lumi/build2_ids.txt` on LUMI. Merge script: `lumi/merge_round5.sh`. Status unknown; maintenance may have killed or requeued them.
- **21 jobs:** Frank variants (`v3_bmi_n50`, `v4_eb`, `v4_wh`, `v4_b4`, `final_tuned`, `final_tuned_long`, `final_nordic`) × (validation, fold_b, test).
- **12 official builds** `lumi/final/x00..x11` (diverse top lab models), plus `y_*` (3 builds) and `m_int4ss_lgb7_s10` (10-seed core).
- **Phase 5a** (`lumi/specs_p5a.jsonl`, 13 diversity specs) and **phase 5b** (`lumi/specs_p5b.jsonl`, 10 specs testing the new Fingrid balancing data `mfrr2`/`dafcr`/`ace`).

When LUMI is back:
1. Check `squeue -u amojahid`.
2. Rerun anything that's missing.
3. Run `lumi/merge_round5.sh` (or `lumi/collect.sh` plus the Frank conversion inside it).

## Files and data on this laptop
- **Experiments:** `experiments/lab/leaderboard.csv` holds every run, about 219 experiments.
- **Predictions:** `experiments/lab/_cache/preds/*.npz`, for all runs (including `frank__final_capw`, `frank__v4_n50`). Git-ignored and local only.
- **Frank's outputs:** `external_data/_frank/` (`v4_n50_{validation,fold_b,test}.csv`, `frank_{foldA_val,foldB_val,test}.csv`).
- **Frank's code:** a worktree at the scratchpad path in `HOWTO.md`, checked out at `67ab599`.
