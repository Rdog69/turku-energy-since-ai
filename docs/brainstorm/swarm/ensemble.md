# Ensemble of saved lab predictions

Code: `experiments/lab/ensemble.py` (run `python -m experiments.lab.ensemble`); triple search was a throwaway script. 43 runs had both folds at the time of the scan. Score = same formula as `scored_board` (30/20/20/10 weighted relative gain over REF mixture, averaged over folds).

## Results (cross-fitted = weights fitted on the other fold, applied to this one)
| method | score |
|---|---|
| best single (INT5) | +3.90 |
| equal avg top-2 / top-3 / top-5 (by score) | +3.90 / +3.89 / +3.93 |
| top-5 with median-of-models p50 | +3.94 (no real difference vs mean) |
| convex weights per group, 12 candidates, cross-fitted | **+4.62** |
| greedy <=3 members per group, cross-fitted | +4.57 (<=2: +4.37) |
| convex + step bands (1-4, 5-16, 17-40) | +4.49 (worse; too little data per band) |
| greedy3 + bands | +4.52 |

Top-k by score barely helps: the top runs are near-copies (INT family). Gains come from diverse members: **weather W6 (`W6 W2 + hat regHGB`)** and **INT4 (`int2+wind_hat`)** plus INT1/INT9/S_final. Equal-weight triples chosen on one fold and scored on the other: about +4.5 (vs +3.9), but triple choice is mildly optimistic. Best in-sample equal triple: W6 + S_final + INT4 = +4.93.

## Recommended ensemble (<=3 members, equal weights, all groups)
`weather W6 (W2 + hat regHGB)` + `fl-GLM-5.3 INT4 (int2+wind_hat)` + one of `fl-seed INT1 (reg+bands+rt)` / `fl-Kimi INT9 (int5+temp)` (cross-fitted-style estimate ~+4.5 to +4.9).
Per-group pooled greedy variant (+4.57 honest): p50 = INT9, W6, INT4; p10/p90 = INT1, W6, INT4; spike = INT6, W6, S_final; direction = INT1 x1/3 + INT4 x2/3.

## What the submission must reproduce
Every member must be retrained on the test period with its exact spec: W6, INT4, and INT1 (or INT9) (S_final/INT6 only for the per-group variant). Combine: average p10/p50/p90 per column and probabilities; then enforce p10<=p50<=p90, normalise direction probs to 1, and hi+lo<=1. Note INT4 alone fails the "better on both folds" check (all_better_both False), and W6 alone scores +3.45; the blend is what is good, so do not ship either alone as a fallback unless the blend can't be built. Fallback: the single INT5.
