# Context: Turku Energia imbalance-price forecast (Since AI 2026)

We forecast the Finnish imbalance price 1-40 quarter-hours ahead from hourly origins. Four scored metrics, lower is better,
weighted 30/20/20/10: MAE of p50, mean pinball of p10/p90, spike Brier (|imbalance - spot| > 50), 3-class direction Brier.
Scoring is relative to the best team, so small consistent gains matter. Validation: fold A = Sep (organisers' window),
fold B = Aug. A gain only counts if it holds on BOTH folds (noise: ~0.2 MAE, ~0.005 spike Brier on B).

What a swarm of agents already established (all leak-checked):
- Regularised HGB beats defaults on every metric: hgb {"max_leaf_nodes": 15, "min_samples_leaf": 400, "max_iter": 150}.
- Separate models for step bands [[1,4],[5,8],[9,16]] help MAE/pinball/direction (step 1-4 MAE -7%).
- Mixture beats direct once regularised and banded. target "price" loses to "gap". Recency weights: unstable (help A, hurt B).
- Fingrid real-time: rt_wind (wind error) is the strongest; rt_misc adds on top; rt_imb alone is weak; rt_cons hurts fold B.
  package+rt_imb+rt_wind+rt_misc beats REF on all four metrics on both folds (gain mostly steps 1-4).
- Direction: `runs` / `dir` direction-history features + hist_blend 0.6 (history model from last year) give by far the best
  direction Brier (A 0.397 vs 0.437). History model as a feature (hist_full) is diluted; the blend works better.
- Outages (umm_trip): no gain on both folds. ifs_rev / wind_hat (weather model revisions) are new and still being evaluated.
- causal averaging with previous origins: small gain (~0.1-0.5%).
- Nobody has yet combined: regularised HGB + bands + real-time features + direction features + hist_blend. That is the
  most promising direction; then tune around it (bands, hgb, which feature sets, blend weight).
