# State (Sat 7 Nov 2026, late morning)

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
