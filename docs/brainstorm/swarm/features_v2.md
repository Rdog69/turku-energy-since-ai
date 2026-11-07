# Features v2 (agent `v2`)

Code: `experiments/lab/features/v2.py`, runner `experiments/lab/exp_v2.py` (registers the sets in `combo.REGISTRY`, no edit to `combo.py`).
Each set was added to INT5 (score +3.90) one at a time. All pass `leakcheck`.

| Set | Score | Fold A | Fold B | Verdict |
|---|---:|---|---|---|
| INT5 reference | +3.90 | | | |
| `spot_shape` (rank in day, dist to day max/min, spread, +-1h ramps, ramp direction) | **+4.21** | pinball 11.96, MAE 41.66 | pinball 6.66, MAE 27.60 | helps both folds; pinball best of all runs |
| `cal2` (weekend x hour; DST-day flag) | +4.34 | MAE 41.71, dir Brier 0.3890 | MAE 27.87 (worse than INT5 27.73), spike Brier 0.0710 | score is higher, but gain is spike/direction only; not MAE on B. The DST flag is constant 0 in the data (transition is 25 Oct, after training ends), so this is just weekend x hour. Treat as noise-level |
| `icon_ifs` (ICON vs IFS 100 m wind, diff, abs diff) | +3.42 | slightly better | worse (pinball 6.84) | rejected |
| `netpos` (net position vs day mean/max/min) | +3.17 | worse | worse | rejected |
| `capw` (OSM-capacity-weighted wind speed, cube-mean) | +3.02 | | spike Brier 0.083 | rejected, not better on both folds |

Notes
- OSM farms from Frank's branch were copied to `external_data/osm/farms.json`; each farm was assigned to the nearest IFS wind point (missing capacity = 3 MW x turbines).
- `icon_ifs` needed the ICON file; ICON covers only the main period.
- The planned combos (spot_shape + cal2, spot_shape + icon_ifs) were not run: the shared CPU made each run take ~15+ min.

Recommendation: add `spot_shape` to INT5 (`"features": [..., "dir", "spot_shape"]`, register via `exp_v2.py`). `cal2` is worth one more check combined with `spot_shape`.
