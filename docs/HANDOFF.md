# Handoff: femboystorming-pavlo (Sat 7 Nov 2026, evening)

Read `CLAUDE.md` first. Deadline Sun 8 Nov 10:00.

## State

- Branch `femboystorming-pavlo`, local only: **nothing is pushed yet**. The user approved pushing this branch (never `master`, never teammates' branches) once the steps below are done.
- Everything is merged in: Frank's branch (his code won every conflict, our live-imbalance features, models `split_all_rt*`/`split_all_icon`, leak hardening and tests were ported on top), Abdo's branch, Vexa's branch, master (scoreboard), and all agent work.
- The user's own uncommitted edits stay uncommitted: `.obsidian/workspace.json`, `brainstorm/00 Brainstorm Hub.md`, `docs/TLDR.md` (has a stray "/").
- Last full test run (before the latest docs-only merges): 69 passed, 2 skipped, 0 failed; the history test passes since Abdo's merge. Newer tests added since: `tests/test_models_registry.py` (passes).

## Not finished

1. **`v6_hf` reproduction after the merge** (agent M1, stopped mid-run). Run `OMP_NUM_THREADS=4 .venv/bin/python -m src.backtest.run --period validation --model v6_hf` (long, about 1 h+). Expect Frank's 40.67 / 11.19 / 0.771 / 0.0856 / 0.3892. Features of `split_all` were verified identical across pre-merge, Frank's branch and the tip, so a match is expected.
2. Then: `reports/drivers_v6_hf.md` (top-driver shares from `results/v6_hf/validation/forecast_full.parquet`, by steps 1–8 vs 9–40), and `python tools/pick_demo_moments.py --model v6_hf --forecast results/v6_hf/validation/forecast_full.parquet` → `reports/demo_moments_v6_hf.md`.
3. Full `pytest`, `git fetch` (merge any new teammate pushes, Frank's code wins), then `git push origin femboystorming-pavlo`.
4. Remove the agent worktrees in `.claude/worktrees/` (all their commits are merged) and delete their `worktree-agent-*` branches.

## Open team decisions (don't decide them alone)

- Which file is submitted: `v6_hf` (Frank) or `team5050` (Abdo); marked `TODO(team)` in the report, slides, Q&A and SOURCES. The team data map mentions a newer ½ Frank + ½ history-model candidate.
- Spot prices are committed (starter package, `external_data/elering/fi_spot_history.csv.gz`, `external_data/history/pkg_history.csv.gz`): the repo must stay private. Purge list: `reports/repo_hygiene.md`.
- Demo video draws spot as a line: use Option B (gap only) in `reports/demo_script.md` until the organisers answer Q11.
- Open organiser questions: `QUESTIONS.md` (only Q1 answered).
- `runs_ecmwf_ifs_history_{a,b}.csv.gz` (needed by Abdo's history model) are not in the repo.
- The Featherless API key was pasted in chat: rotate it.

## Key findings this session

- Scoreboard (points-weighted vs baseline, avg of Sep and Aug): team5050 31.1 %, v6_hf 30.9 %, split_all_rt_icon 27.6 %.
- Post-merge `split_all` moved 42.53 → 42.71 MAE: cause is the LightGBM seed now fixed at 0 (checked), not the merge. Seed noise ≈ 0.2 MAE.
- Paired day-block bootstrap (`reports/uncertainty.md`): ~1 % gains between variants are noise; team5050's +4.1 % over split_all_rt_icon is not.
- Leakage review (`reports/leakage_review.md`): no risks found.
