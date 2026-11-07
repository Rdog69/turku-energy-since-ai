# How to run everything

Run all commands from the repo root: `/Users/abderahimmojahid/Studies/Åbo/SINCE AI/turku-energy-since-ai`.

## Lab experiment (both folds, leak-checked, appended to the leaderboard)
```bash
OMP_NUM_THREADS=4 .venv/bin/python -W ignore -m experiments.lab.combo '{"name": "my test", "agent": "me",
  "features": ["package", "rt_imb", "rt_wind", "rt_misc", "runs", "dir", "wind_hat", "spot_shape"],
  "model": "mixture", "engine": "lgb", "lgb": {"num_leaves": 7, "n_estimators": 350},
  "hgb": {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150},
  "bands": [[1,4],[5,8],[9,16]], "hist_blend": 0.6, "causal": 0.2, "calib": "eb50", "cal_days": 14}'
```

**Spec keys:**

| Key | Values |
|---|---|
| `features` | Any keys of `REGISTRY` in `experiments/lab/combo.py`: `package`, `rt_imb`, `rt_wind`, `rt_misc`, `rt_cons`, `rt2`, `runs`, `dir`, `hist_full`, `hist_da`, `umm_trip`, `ifs_rev`, `wind_err`, `ifs_now`, `wind_hat`, `fmi`, `temp`, `spot_shape`, `cal2`, `mfrr2`, `dafcr`, `ace` |
| `model` | `mixture` / `direct` |
| `engine` | `hgb` (default) / `lgb` / `cat` (CatBoost; installed on LUMI only) |
| `bands` | Separate models per step band |
| `short_features` | Feature sets used only in bands ending at step ≤ 8 |
| `hist_blend` | 0–0.9 |
| `causal` | 0–0.3 |
| `calib` | `"eb50"` |
| `cal_days` | Calibration window in days |
| `half_life_days` | Recency weighting |

**Ranking:**
```bash
.venv/bin/python -c "import sys; sys.path.insert(0,'tools'); import fl_lab; print(fl_lab.scored_board().head(25))"
```

**New feature sets** go in `experiments/lab/features/<name>.py` (signature `fn(base, data)`), use only the helpers in `experiments/lab/data.py`, and get registered in `combo.REGISTRY`. `run_experiment` leak-checks them automatically.

## LUMI
```bash
./lumi/sync.sh                                        # copy the repo to ~/te (excludes caches, .env)
.venv/bin/python lumi/make_grid_p2.py                 # example spec-grid generator -> lumi/specs_*.jsonl
ssh amojahid@lumi.csc.fi 'cd ~/te && sbatch --array=0-$((N-1))%60 --export=ALL,SPECS=lumi/specs_X.jsonl lumi/grid.sbatch'
./lumi/wait.sh <jobid,jobid>                          # robust wait (an ssh error means keep waiting)
./lumi/collect.sh                                     # fetch results + predictions, merge into the leaderboard
```

Official builds (validation scored with `score.py`, test run through the validator) of one spec, or a list:
```bash
ssh amojahid@lumi.csc.fi 'cd ~/te && sbatch --job-name=TAG --export=ALL,SPECFILE=lumi/final/TAG.json,TAG=TAG lumi/submit.sbatch'
rsync -az amojahid@lumi.csc.fi:te/submissions/ submissions/
```

Locally the same thing is:
```bash
OMP_NUM_THREADS=4 .venv/bin/python -W ignore -m experiments.lab.submit --mode val --tag TAG --spec-file lumi/final/TAG.json   # then --mode test
```

## Ensembles
```bash
OMP_NUM_THREADS=2 .venv/bin/python -W ignore -m experiments.lab.ens_greedy   # cross-fitted greedy over all saved runs (+ Frank)
.venv/bin/python -m experiments.lab.combine --recipe experiments/lab/recipe_team5050.json --tag NAME   # build from member files
```

Recipe format: `{"p50": [[member, weight], ...], "q": [...], "spike": [...], "dir": [...]}`.
- Members are the tags of built files in `submissions/`.
- `frank` = `final_capw`, `frank_v4` = `v4_n50`.

## Frank's code
- **Worktree:** `/private/tmp/claude-501/-Users-abderahimmojahid-Studies--bo-SINCE-AI-turku-energy-since-ai/ce30b3d5-78fc-4083-a944-60b3e24dbaf1/scratchpad/frank`. It may not survive a new session; recreate it with `git worktree add -f <dir> origin/brainstorming-frank` and symlink `starter_package`.
- **On LUMI:** `~/frank`, where `frank.sbatch` takes `PERIOD` (`validation` / `fold_b` / `test`) and `MODEL` (e.g. `v4_n50`).
- **Outputs:** `~/frank/results/<model>/<period>/forecast_backtest.csv`.
- **Converting to lab predictions:** see the Python block in `lumi/merge_round5.sh`.

## Teammates
```bash
git fetch origin brainstorming-frank brainstorming-jim && git log --oneline -5 origin/brainstorming-frank
```

On macOS there's no `timeout` command; don't use it.
