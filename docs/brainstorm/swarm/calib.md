# Agent `calib`: EB50 calibration inside combo.py

Code: `experiments/lab/calib_eb.py` (`calibrate_eb`: EB-shrunk Platt for p_hi/p_lo, s = m/(m+50), plus multiplicative p10/p90 width per step band then additive offset). `combo.py` spec keys: `"calib": "eb50"` (pooled model via `pool_post` and inside `band_post`) and `"cal_days"` (default 14). Defaults unchanged.

| spec | score | MAE A/B | pinball A/B | spike A/B | dir A/B |
|---|---|---|---|---|---|
| INT2 (REF calib) | +3.88 | 41.806 / 27.748 | 12.011 / 6.801 | .0907 / .0745 | .3895 / .4308 |
| INT4 (REF calib) | +3.08 (fails both-folds) | 41.509 / 27.422 | 12.049 / 6.710 | .0903 / .0843 | .3887 / .4290 |
| CAL INT2 eb50 | +4.93 | 41.806 / 27.748 | 11.799 / 6.744 | .0903 / .0686 | .3895 / .4308 |
| **CAL INT4 eb50** | **+5.49** (both better) | 41.509 / 27.422 | 11.853 / 6.658 | .0898 / .0676 | .3887 / .4290 |
| CAL INT4 eb50 cal28 | +4.33 (fails both-folds) | 41.509 / 27.422 | 11.742 / 7.223 | .0895 / .0706 | .3896 / .4360 |

cal_days=28 helps fold A pinball but hurts fold B (its inner model has only one month of data); keep 14. MAE is unchanged because calibration does not touch p50.

Best spec: `{"name":"CAL INT4 eb50","features":["rt_imb","rt_wind","rt_misc","runs","dir","wind_hat"],"model":"mixture","target":"gap","hgb":{"max_leaf_nodes":15,"min_samples_leaf":400,"max_iter":150},"bands":[[1,4],[5,8],[9,16]],"hist_blend":0.6,"calib":"eb50"}`
