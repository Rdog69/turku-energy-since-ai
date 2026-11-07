# Experiment backlog (prioritised)

Every idea must win on **both folds** (and most weeks) to count. Prefer ideas that add **diversity** or **new information** over retuning the same model on September.

## A. Finish round 5 (as soon as LUMI is back)
1. **Check what survived the maintenance;** resubmit the rest:
   - phase 5a/5b specs (`lumi/specs_p5a.jsonl`, `specs_p5b.jsonl`);
   - Frank variants (`frank.sbatch`);
   - the x/y/s10 builds (`lumi/final/*.json`).
2. **Phase 5b answers:** does the new Fingrid balancing data (`mfrr2`: mFRR need, bid volumes, aFRR volumes, mFRR exchange, scheduled vs direct activations) help on both folds? `ace` (real-time calculated imbalance) is pending organiser approval.
3. **CatBoost engine** (`"engine": "cat"`, LUMI only) for diversity: try it on INT4+ss, W6+ss and LEAD+ss with eb50.

## B. Ensembles with Frank (highest expected value)
4. **Frank variants as extra members:** add his other models (round 5) to the pool. Test simple, equal-weight blends of **2–4 diverse members** (ours + his). Gate: beats `team5050` on both folds and in ≥ 7/10 weeks.
5. **Per-output equal-weight blends:** e.g. `team5050` for p50/dir/spike, plus our best pinball members (`final_greedy`'s q group) for p10/p90. Its pinball 11.43 vs 11.63 is a real gap. Check it on both folds before adopting.
6. **Ask Frank** (or rerun his code) for `v4_n50` with different seeds, or his `fold_b` runs of other variants, to estimate noise.

## C. Port Frank's strongest ideas into our models (new information)
7. **ICON-EU done his way:** a capacity-weighted wind index from ICON + its revision since the day-ahead forecast + ECMWF–ICON disagreement. Our raw-wind version failed; his works on both months. ICON runs are in `external_data/open_meteo/runs_icon_eu_main.csv.gz`; Frank's code is `src/data/weather.py` on his branch.
8. **Learned wind map:** non-negative weights for about 22 weather points (ECMWF + ICON), fitted to Fingrid 181 measured wind, using pre-cutoff data only. Features: predicted MW, its gap to the day-ahead forecast, its revision. See Frank's `src/models/wind_power.py`.
9. **Nordic wind for p50 only:** wind in SE/NO/DK/EE helped Frank's median but hurt the band. Our per-group ensembles can use it for p50 only.
10. **Hyperparameters tuned on training-only folds** (like Frank's 26 Jul – 6 Sep folds) instead of on Sep/Aug, to cut selection optimism.

## D. Other ideas not yet tried
11. **Real-time mFRR prices (400–402) and last-bid prices (22/251):** potentially big, but **only if the organisers allow it** (question 4). They nearly copy the target.
12. **ECMWF ensemble spread** (if Open-Meteo archives ensemble runs): uncertainty for pinball.
13. **Stacking meta-model** (which member to trust per regime): high overfitting risk; strict cross-fitting only.
14. **`top_drivers`:** reuse Frank's TreeSHAP drivers from his `v4_n50` file, or compute SHAP for our members. Optional and not scored, but good for the jury.

## Don't redo
See `docs/EXPERIMENTS.md` §4: price target, recency weights, big trees, RT2, `rt_cons`, UMM features, saturation/decoupling, bid snapping, raw ICON disagreement, Elering/Energinet, month × hour priors, fixed recalibration layers, Featherless recipe loops.
