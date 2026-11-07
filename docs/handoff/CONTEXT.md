# Context

## The task
- **What we forecast:** the Finnish **imbalance price** for 1–40 quarter-hours ahead (10 h), from every full-hour origin.
- **Test period:** 5 Oct – 1 Nov 2026: 673 origins × 40 steps = 26,920 rows.
- **Training data:** up to 4 Oct only.
- **What we submit per row:**
  - p10 / p50 / p90;
  - p_up / p_down / p_none: the dominating mFRR direction;
  - p_spike_high / p_spike_low: imbalance > spot + 50, or < spot − 50;
  - optionally `data_cutoff_utc` and `top_drivers`.
- **Scoring (Level 1, automatic):** MAE of p50 (30 pts), mean pinball of p10/p90 (20), mean spike Brier (20), and 3-class direction Brier (10). Each one is scored **relative to the best team**: the baseline gets 0, the best team gets full points.
- **Baseline (validation):** 66.20 / 24.18 / 0.1132 / 0.4509.
- **Also scored by the jury:** the reasoning chain (20 pts) and the Level 2 dashboard (20 % of the total).
- **Data rule:** a row is usable at origin t only if `first_usable_origin_utc ≤ t`. **A leak means a score of 0.**

## Hard rules (the user's)
- **Optimise for the TEST month, never for validation.** A change counts only if it wins on **both** lab folds (A = Sep, B = Aug), ideally in most weeks. Choose ensembles by cross-fitting. Prefer equal weights and simplicity when differences are within noise. (This is saved in memory: `optimize-for-test-not-validation`.)
- **Never leak.** All features go through the lab helpers plus `leakcheck`.
- **Nord Pool spot data is licensed:** never send rows to any third-party API. The repo is private, and the starter package is committed on purpose.
- **Don't drift into "submission mode":** the user wants experiments and improvements until the day is over.
- **The user wants:** many parallel experiments on LUMI, short status updates, honest numbers, and pushes to `brainstorming-abdo` so teammates (and their agents) can learn from them.
- **Commits:** end messages with the `Co-Authored-By` line from the system reminder. Push to `brainstorming-abdo`.

## The team
- **Abdo** (the user): this branch, story and quality.
- **Frank:** `brainstorming-frank`. His LightGBM pipeline is strong. His best is `v4_n50` (Sep 41.08 / 11.88 / 0.0871 / 0.3899).
- **Sakibul ("Jim"):** `brainstorming-jim`. His "grand champion" = 65 % Frank v4_n50 + 35 % our CAL INT4 eb50.
- **Pavlo, Pavel:** other branches.
- **Contacts:** Turku Energia experts in `#turku-energia` on Discord.

## Compute
- **Laptop:** 10 cores, 17 GB RAM. Use `.venv` (Python 3.15: pandas, scikit-learn, LightGBM 4.7 via Homebrew libomp).
- **LUMI supercomputer:**
  - user `amojahid`, project `project_462001520`;
  - `small` CPU partition, 128 cores per node, no per-user job cap (we ran 60 in parallel);
  - repo synced to `~/te` (private home, `chmod 700`); Frank's code in `~/frank`;
  - SSH works without a password from this laptop.
  - **It was under maintenance at the time of writing.** Check with `ssh amojahid@lumi.csc.fi hostname`.
- **Featherless and Claude subagents:** Featherless was dropped (compute was the bottleneck, not ideas). Sonnet subagents work but hit usage limits; use them sparingly.
