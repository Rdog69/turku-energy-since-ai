# For Frank: retrain v4_n50 on Mar 2025 – Oct 2026

**Why:** the organisers confirmed that data before 1 June may be used (the cutoff was only about the price rule). Training our INT4 model on 19 months instead of 4 improved it on every score on both folds. Its pinball and spike scores already beat team5050's on August. Your half has not seen this history yet.

| Lab, Sep (fold A) | MAE | pinball | spike | dir |
|---|---|---|---|---|
| team5050 (½ v4_n50 + ½ our old INT4) | 40.90 | 11.63 | 0.0860 | 0.3798 |
| ½ v4_n50 + ½ our history INT4 | 40.19 | 11.26 | 0.0846 | 0.3789 |

August (fold B): 27.27 / 6.57 / 0.0677 / 0.4281 → 27.12 / 6.29 / 0.0657 / 0.4243.

## Steps (your branch, your code unchanged except one constant)

1. On `brainstorming-abdo`, run `python -m experiments.lab.build_package_ext`. It writes `external_data/history/package_ext/`: the starter package plus history back to 1 Mar 2025, in the same files and types. The folder is git-ignored because it holds licensed spot data. Your `load_long()` reads it as is (checked: 1,413,429 rows, no duplicates).
   - The history's `fi_imbalance_price` is **recomputed with the 1 June rule** (volume-weighted mFRR/aFRR). It reproduces the official price on 99.5 % of Jun–Oct 2026 quarters.
   - Spot before June comes from Elering's Nord Pool feed. It's identical to the package spot on all 14,824 overlapping quarters. Team use only.
2. `export TE_PACKAGE_DIR=<repo>/external_data/history/package_ext`
3. `src/config.py`: `DATA_START = pd.Timestamp("2025-03-05T00:00:00Z")`.
4. Refetch your external tables from 1 Mar 2025:
   - Fingrid real-time: `python -m src.data.fingrid --start 2025-03-01`.
   - ECMWF IFS points, the extra points and Nordic: your `src.data.open_meteo`, from 2025-03-01. The IFS archive goes back to 2024.
   - **ICON-EU only exists from 2 Apr 2026.** Its features will be empty before that. LightGBM handles that, but the learned wind map and ICON disagreement may need a "fit on rows with ICON" guard.
5. Rerun `v4_n50` for `validation`, `fold_b` and `test`, and send us the three CSVs as before. We'll score ½ yours + ½ ours on both folds and week by week before anything replaces team5050.

Training has about 4.5× the rows, so expect roughly 4× the run time. If time is short, run `test` first, then `validation`.

In our lab, the recency-weight and volatility-regime variants are still running (`docs/handoff/STATE.md` will have the results).
