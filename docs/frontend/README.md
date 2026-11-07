# Feeding Abdo's frontend (`origin/front-end`) the current candidate

Checked Sat 7 Nov 2026, evening, against `origin/front-end` commit `891f536`.

## What the frontend reads

`frontend/scripts/build_data.py` takes **two member files** in the submission format and blends them itself:

| Member | Path it looks for (in its worktree or `TE_DATA_ROOT`) | Now | Should be |
|---|---|---|---|
| `frank` | `external_data/_frank/v4_n50_{validation,test}.csv` | old `v4_n50` | `v7_rt`: `submissions/v7_rt_validation.csv`, `submissions/v7_rt_test.csv` on `brainstorming-frank` |
| `ours` | `submissions/{validation,forecast_backtest}_h_int4ss.csv` | `h_int4ss` | unchanged |

Columns it uses: `forecast_origin_utc`, `step`, the eight forecast columns, `data_cutoff_utc` and `top_drivers` (from the `frank` member).

## Compatibility check

Our `v7_rt` files fit as they are:
- rows align one-to-one with `h_int4ss` (26,880 September, 26,920 test), so its `members misaligned` assertion passes;
- `top_drivers` is filled on every row (1,657 / 1,495 distinct combinations);
- its own 50/50 `blend()` reproduces `submissions/blend_v7_rt_h_int4ss_*.csv` exactly.

The one gap: the candidate now stretches P90 ×1.15 away from P50 (`submissions/MANIFEST.md`), which `blend()` doesn't do. Unpatched, the dashboard's upper band would be up to 43 €/MWh lower than the submitted forecast.

## The patch

[`build_data_v7rt.patch`](build_data_v7rt.patch) changes only `frontend/scripts/build_data.py`:
1. The `frank` member points at `external_data/_frank/v7_rt_{validation,test}.csv`.
2. `blend()` applies `P90_STRETCH = 1.15` after re-sorting the quantiles.
3. The payload's model label becomes `v7_rt + h_int4ss, P90 x1.15`.

With it, the blend matches `submissions/blend_hi15_validation.csv` and `blend_hi15_test.csv` exactly: the dashboard then shows the forecast we submit.

```bash
git show origin/brainstorming-frank:submissions/v7_rt_validation.csv > external_data/_frank/v7_rt_validation.csv
git show origin/brainstorming-frank:submissions/v7_rt_test.csv > external_data/_frank/v7_rt_test.csv
git show origin/brainstorming-frank:docs/frontend/build_data_v7rt.patch | git apply
python frontend/scripts/build_data.py
```

**Alert side effect:** the wider band triggers the "very wide uncertainty" alert (P10–P90 ≥ 250 €/MWh for 4+ quarters) in 12.0 % of test hours instead of 8.2 % (September: 10.7 % instead of 7.4 %). That is inside the 10–15 % the script's own comment aims for, so the threshold can stay.

The payload still holds Nord Pool spot prices: keep it local, as the frontend README says.
