# Turku Energia forecasting project — milestone audit

**Evidence freeze:** 7 November 2026, 13:40 UTC<br>
**Scope:** all seven repository branches available in the restored mirror, organiser rules and scorer, selected forecast artifacts, comparable research, data/leakage risks, deliverables, and next actions.<br>
**Companion documents:** [provider questions](PROVIDER_QUESTIONS_2026-11-07.md) · [prioritized roadmap](ROADMAP_2026-11-07.md)

> This is an audit, not a new training run. It contains aggregate metrics only: no raw actuals, spot-price rows, forecast rows, credentials, or licensed datasets. External results below are method evidence, not directly comparable scores.

## 1. Executive decision

1. **Provisional custom-scoreboard leader—not an officially resolved overall winner:** `team5050`, a 50/50 blend of Frank's `v4_n50` and Abdo's `P2 INT4+ss lgb7`.
   - Two-fold mean accuracy on the requested aggregate-exactness scale: **35.59%**.
   - September official-scorer reproduction: **MAE 40.973899**, **pinball 11.634608**, **spike Brier 0.086086**, **direction Brier 0.380346**, **coverage 80.06%**.
   - Its August score is lab-scored, rounded, and lacks a committed forecast artifact. The 0.2-point custom-index lead over `v6_hf` is therefore not a verified overall ranking.
2. **Best September official-metrics candidate:** `v6_hf` — September MAE **40.668296**, two-fold mean accuracy **35.34%**, and scoreboard-official entries for both months. Its entries have blank `forecast_file` fields and no committed scored CSV was found, so they still require artifact-level reproduction.
3. **September official-formula proxy:** using the current official non-baseline September entries as the comparison field gives **`v6_hf` 78.747183 automatic points versus `team5050` 78.592780**. This reverses the custom scoreboard order, but is not a final score because the organisers' accepted-team field is unknown.
4. **Material eligibility gate:** `team5050`, `v6_hf`, `P2`, and `final_greedy` are logged with `pre_june_data: true`. The organiser materials say to train only on **1 June–4 October 2026**. These candidates must not be called submission-safe without a written exception.
5. **Best current candidate under that explicit training-date cutoff:** `v4_n50`, with `pre_june_data: false` and scoreboard-official entries in both months; two-fold mean accuracy **34.71%**. External-data vintage/delay questions and artifact reproduction still apply.
6. **Final competition performance remains unknown.** Hidden October–November actuals and other teams' accepted scores are unavailable. A local validation rank is not a final leaderboard rank.
7. **The project needs one integrated submission, not another branch of isolated improvements.** Preserve a validated fallback, reconcile provenance, finish the report/UI/demo, and resolve provider questions before adding complexity.

## 2. What the official score actually measures

The locked materials define:

- **Total:** `0.8 × Level 1 + 0.2 × Level 2`, each level on a 0–100 scale.
- **Automatic Level 1 weights:** P50 MAE 30, P10/P90 mean pinball 20, spike Brier 20, direction Brier 10.
- **Reasoning:** another 20 Level 1 points, jury-assessed from the evaluation report, slides, and demo.
- **Level 2:** situational UI, current/historical views, time travel, usability, and inventiveness.
- **Per-metric automatic points:** `weight × clip((baseline − team) / (baseline − best_accepted_team), 0, 1)`.

Therefore:

- The scoreboard's **31.1%** for `team5050` is a custom points-weighted **baseline-relative improvement**, averaged across two months. It is **not 31.1% forecast accuracy** and not the organisers' final points.
- Coverage is informative, not a separately weighted automatic criterion.
- MAE, pinball, and Brier scores are lower-is-better; they are not percentages of exact forecasts.
- Spike labels use strict inequalities around spot ±50 €/MWh. Direction is the dominating mFRR direction, not simply the sign of the price gap.
- A row is usable at origin `t` only when `first_usable_origin_utc <= t`. The validator requires all **673 origins × 40 steps = 26,920 rows**.

Primary local references: `starter_package/README.md`, `starter_package/score.py`, `starter_package/validate_submission.py`, and `docs/brainstorm/round2/context/challenge_brief.txt` at the pinned master revision.

## 3. Evidence labels and audited revisions

### Labels

- **Independently reproduced:** the main auditor ran the locked scorer/validator and matched the logged result.
- **Scoreboard — official:** a machine-readable scoreboard entry labels the result `official`; not necessarily rerun by the main auditor.
- **Scoreboard — lab:** a lab result, potentially rounded or lacking a committed forecast artifact.
- **Documentation/claim:** prose, commit message, or an older agent report without equivalent current artifact proof.
- **Protected-evaluator verified:** passed the separate locked Vexa lane evaluator; this does not make cross-harness values exactly comparable.

### Branch heads available at the evidence freeze

| Branch | Commit | Evidence contained at that revision |
|---|---|---|
| `master` | `6864802d135768d3fde252cd99296097093b28a4` | Shared scoreboard and organiser/tooling lineage |
| `brainstorming-abdo` | `7b65d5cafeeb0d8682cf67863ae25a1574031d04` | Experiment lab, submissions, `team5050` lineage |
| `brainstorming-frank` | `e3e52726435846f4b07e675285c0a7d0b094bf53` | Frank models and shared scoreboard |
| `brainstorming-jim` | `7c777d0e48b155bfce80f54393073a2e6387a176` | UI/API/report updates |
| `femboystorming-pavlo` | `913b7ec0f49bbf219a9e45e7b49135c19b241996` | Reporting, reliability, alerts, and analysis side jobs |
| `brainstorming` | `5880ee7c03c2b081ed0383b28ed0922376b8dd31` | Planning and licensed-folder ignore cleanup |
| `vexa/overnight-20261107` | `af861f495c26b0c82f5649b38ec14984efdad1dc` | Protected-lane evidence through `lr003` |

The branches were moving during the audit. Scores below are pinned to their scoreboard entry commits and forecast content, not silently attributed to whatever a branch later contained.

## 4. Reconciled performance

### 4.1 Requested accuracy scale

For an intuitive scale where **100% means aggregate exact matching of P50 to actuals**, this report uses:

```text
accuracy_1_WAPE = 100 × (1 − sum(|actual − p50|) / sum(|actual|))
                  = 100 × (1 − MAE / mean(|actual|))
```

This is **1 − WAPE**, not classification accuracy, not the official score, and not a guarantee that individual rows match. Both MAE and each denominator use exactly the scorer's price-available joined rows: **26,700 of 26,880 submission rows** for September and **29,580 of 29,760 template rows** for August. The resulting `mean(|actual|)` denominators are **59.133797 €/MWh** and **45.808876 €/MWh**, respectively; only those aggregates are retained here.

| Candidate | Sep accuracy | Aug accuracy | Two-fold mean | Pre-June data | Evidence qualification |
|---|---:|---:|---:|---|---|
| **`team5050`** | **30.71%** | **40.47%** | **35.59%** | **Yes** | Sep independently reproduced; Aug lab/rounded |
| `v6_hf` | **31.23%** | 39.44% | 35.34% | **Yes** | Both months scoreboard-official |
| `P2 INT4+ss lgb7` | 29.79% | 40.46% | 35.13% | **Yes** | Sep scoreboard-official; Aug lab |
| **`v4_n50`** | 30.52% | 38.90% | **34.71%** | **No** | Both months scoreboard-official |
| `final_greedy` | 29.99% | — | — | **Yes** | September only; no August score |

### 4.2 Official metrics behind those percentages

| Candidate | Period | MAE ↓ | Pinball ↓ | Coverage | Spike Brier ↓ | Direction Brier ↓ | Scorer |
|---|---|---:|---:|---:|---:|---:|---|
| `team5050` | Sep | 40.973899 | 11.634608 | 80.06% | 0.086086 | **0.380346** | Independently reproduced |
| `team5050` | Aug | 27.27 | 6.57 | — | 0.0677 | 0.4281 | Lab, rounded |
| `v6_hf` | Sep | **40.668296** | **11.191676** | 77.13% | **0.085581** | 0.389186 | Official entry |
| `v6_hf` | Aug | 27.739992 | 6.586762 | 76.97% | 0.068004 | 0.438810 | Official entry |
| `P2 INT4+ss lgb7` | Sep | 41.517051 | 11.646904 | 78.70% | 0.088757 | 0.387396 | Official entry |
| `P2 INT4+ss lgb7` | Aug | 27.274 | 6.587970 | 86.13% | 0.066690 | 0.426180 | Lab |
| `v4_n50` | Sep | 41.084008 | 11.882837 | 79.70% | 0.087084 | 0.389906 | Official entry |
| `v4_n50` | Aug | 27.991456 | 7.000641 | 73.81% | 0.071040 | 0.446566 | Official entry |
| `final_greedy` | Sep | 41.398613 | 11.431823 | **81.61%** | 0.087937 | 0.384299 | Official entry |
| Organiser baseline | Sep | 66.203304 | 24.177618 | 68.29% | 0.113176 | 0.450907 | Official |
| Organiser baseline | Aug | 38.666068 | 11.645071 | 74.81% | 0.079174 | 0.479156 | Official entry |

### 4.3 Interpretation

- **By the scoreboard's custom weighted baseline-improvement index:** `team5050` 31.1%, `v6_hf` 30.9%, `P2` 30.7%, `v4_n50` 29.1%; `final_greedy` has only a September value of 34.7%. This index is `100 × Σ w(B−T)/B ÷ Σw`, with weights 30/20/20/10—not the organisers' gap-to-best formula. The two-fold leaders average **35.20%/26.90%** and **35.70%/26.04%** for September/August, respectively.
- **By the official September points formula applied to the current logged September field:** `v6_hf` scores **78.747183**, narrowly ahead of `team5050` at **78.592780**. This is a local proxy only; the final accepted-team `best` values are unknown.
- **By September MAE/pinball/spike:** `v6_hf` leads this table.
- **By September direction Brier:** `team5050` leads this table.
- **Overall:** the `team5050` versus `v6_hf` ranking is unresolved until `team5050` has a full official-scorer August artifact. Its rounded lab August value should not decide a 0.2-point custom-index lead.
- **By coverage:** `final_greedy` is highest, while `team5050` is almost exactly 80%; coverage alone does not establish better pinball or total score.
- **Without a pre-June exception:** `v4_n50` is the strongest currently logged candidate with scoreboard-official entries in both months that does not carry that specific conflict.
- August and September are different regimes. Never compare August MAE around 27–28 directly with September MAE around 40–41 as if the periods were equivalent.

Machine-readable sources: `scoreboard/entries/*.json` at master `6864802d`; generated ranking from `python scoreboard/leaderboard.py`. The points proxy uses `score.py`'s `criterion_points` formula and the best value per metric among the five current official non-baseline September entries.

## 5. Independent reproduction performed

At the Abdo worktree, the main auditor ran:

```bash
python starter_package/score.py \
  --submission submissions/validation_team5050.csv \
  --actuals starter_package/data/actuals_validation.csv \
  --spike-margin 50 \
  --output-dir <protected-output-directory>

python starter_package/validate_submission.py \
  --backtest submissions/forecast_backtest_team5050.csv \
  --origins starter_package/forecast_origins.csv
```

Observed results:

- Reproduced the logged `team5050` September metrics exactly, including **26,700 price-scored rows**.
- Test-backtest structural validation: **26,920 rows**, **673 origins**, **0 errors**, **0 warnings**. The validation and test counts differ because they are different origin sets and actual-availability edges, not because required test rows were dropped.
- Forecast content is identical at the resolvable evaluated commit `20b414d` and inspected head `7b65d5c`: validation SHA-256 `41c093ce62a71ee694b6ac5315667bfe513824a131c987726588662722f36abc`; test SHA-256 `1d217adc9885bceab153c0e644251a8e81cc91c08c6ab6dc7d275fa73ea9ba0f`.
- A supplementary direction-argmax hit rate of **71.83%** was computed, but it is not an official metric and should not replace direction Brier.

A validator pass proves schema and row constraints only. It does **not** prove forecast quality, training-date compliance, external-data as-of correctness, or a final organiser score.

## 6. What each branch contributes

| Branch | Strongest contribution | Main caveat / action |
|---|---|---|
| **Master** | Shared scoreboard, organiser rules, common data/source tooling | Private history includes licensed starter data on the audited lineage; do not make public or redistribute. Purge before any public/shareable export. |
| **Abdo** | Largest experiment inventory, current `team5050` and `P2` candidates, committed validation/test artifacts | Heavy September selection pressure; several leaders use pre-June history. Fold-B `team5050` is lab/rounded. Preserve exact recipe and artifact provenance. |
| **Frank** | Scoreboard-official entries for both months; `v4_n50` avoids pre-June data; availability tests and source documentation | Many variants were tried on September. External Fingrid/weather vintages/delays need evidence. `v6_hf` inherits the pre-June gate. Frank's `v4_n50`/`v6_hf` entries have blank `forecast_file` fields and no committed scored CSV was found; recover/regenerate those artifacts before relying on the entries as reproducible proof. |
| **Jim** | UI/API, evaluation report, slides, driver explanations, alerts; later convergence on the 50/50 idea | Older `src/` and final lab stacks must not be confused. Older audit found in-sample calibration, stale fixed lags, and post-hoc tuning in non-final paths; recheck before reuse. |
| **Pavlo** | Reliability, drift, alerts, error breakdown, case studies, report support | Useful analysis/UI support, not the source of the current leading model. Reconcile any older unanchored metrics before presentation. |
| **Vexa** | Protected-evaluator discipline and recoverable evidence for package-only candidates | `lr003` MAE 42.8088 is weaker than the current leaders; retain as evidence/fallback lineage, not the accuracy leader. |
| **Brainstorming** | Planning and cleanup of licensed-folder ignores | No independent model result to promote. |

### Older audit findings that remain useful—but are not current-head claims

- At older revisions, Frank's eight availability tests and Vexa's six tests passed against the real package; Jim's two synthetic leakage tests passed. These are useful historical checks, not a substitute for rerunning tests on the exact final integrated commit.
- Jim's older `src/models/train_direct.py` fitted quantile corrections on training predictions; its lab path used a more defensible holdout pattern. Do not import the older path blindly.
- Frank and Abdo had the strongest availability/as-of implementations in the reviewed snapshots, but external API revision history cannot be solved by a conservative delay alone.
- Older claims such as Abdo `ens3` or Frank `final_capw` being “best” are superseded by the newer scoreboard. They remain historical candidates, not the current recommendation.

## 7. External comparable evidence

### 7.1 Closest Finnish modelling evidence

A 2026 Finnish aFRR study compared LightGBM/XGBoost with deep models for 48-hour marginal reserve prices and reported LightGBM as the most robust under limited data. Its down/up MAE ranges were 17.5–17.8 and 55–60, respectively.[1]

**Transfer:** tree models and directional asymmetry are credible priorities.<br>
**Do not transfer:** those MAE values, the 48-hour horizon, or aFRR marginal-price performance directly to this 15-minute imbalance-price task.

Fingrid's own balance-model description confirms 15-minute imbalance settlement periods.[5]

### 7.2 Probabilistic forecasting and calibration

- GEFCom2014 formalised probabilistic load, price, wind, and solar tracks; it is useful methodological context for quantile forecasting and held-out evaluation, not a score comparator for Turku.[8]
- The HEFTcom2024 GEB solution used multiple-NWP “sister models” and online post-processing for distribution shift.[2] The first idea supports bounded weather/model ensembles; the second is **not permission** to adapt on test labels here.
- A French spot-price study found candidate probabilistic models behaved differently and none was reliably best throughout turbulent conditions; it motivates robust calibration and aggregation tests rather than faith in one model family.[4]
- LightGBM officially supports quantile regression, matching the P10/P50/P90 modelling approach, but that documentation is functionality evidence—not evidence of superiority on this dataset.[6]

### 7.3 Fresh information and horizon decay

A Great Britain intraday study reported pinball reductions of 20% at 30 seconds before gate closure and 7.5% at one hour before delivery after adding continuous-trade information.[3]

**Transfer:** fresh state can matter and its value decays with horizon. This is consistent with the repository's finding that real-time features help early steps more than late steps.<br>
**Do not transfer:** those percentages as an expected Turku gain; the market, features, and horizons differ.

### 7.4 Foundation models

Chronos-2's official repository documents zero-shot univariate, multivariate, and covariate-informed forecasting, with quantile output examples.[7] This makes an inference-only challenger technically possible, but provides no evidence of calibrated spike/direction gains on four months of Finnish imbalance data. It remains below calibration, leakage control, and deliverable integration in the roadmap.

### External-evidence bottom line

There is **no defensible cross-dataset “accuracy leaderboard”** for this task. Use external work to choose bounded experiments; use only the locked local scorer, identical periods, availability rules, and final organiser evaluation for model selection.

## 8. Factors and opportunities, separated by evidence status

### Achieved or directly measured in the project

- **Known spot + gap modelling:** the spot anchor explains a large share of the baseline improvement; model the imbalance-minus-spot gap rather than expecting a regressor to rediscover the known price level.
- **Early-horizon real-time state:** real-time features helped early steps in the reviewed experiments and could hurt later steps; keep horizon-specific ablations.
- **Direction-conditional spike modelling:** product/mixture approaches improved spike performance in multiple experiments.
- **Pre-June direction/history priors:** potentially useful, but currently blocked by the explicit training-date rule unless an exception is granted.
- **Recency weighting:** repeatedly traded probabilistic quality for small point gains; it is not a default improvement.
- **Post-hoc September-only tweaks:** high selection/overfitting risk, especially after many variants and cross-branch blending.

### Promising but requiring controlled validation

- Spike **distance-to-threshold** features in gap space.
- Global versus horizon-band calibration with shrinkage and frozen-versus-refit controls.
- Brier-matched probability heads and a carefully pooled `p_none`.
- A coherent direction-conditional mixture CDF producing quantiles and event probabilities together.
- Availability-safe wind/solar forecast **revisions and errors**, not just forecast levels.
- Versioned outage/UMM events, balancing-market state, and cross-border conditions—with publication-time and licence proof.
- Per-origin error slicing and paired moving-block uncertainty over origins, not IID tests over overlapping origin-step rows.

### Not current priorities

- Large deep architecture searches, 40 independent horizon models, or foundation-model fine-tuning.
- Adaptive conformal or online recalibration using test-period labels without explicit organiser approval.
- Any feature reconstructed from revised history as though it were the first-published vintage.

## 9. Submission and delivery priorities

1. **Resolve eligibility first:** obtain the pre-June exception or select the `v4_n50` lineage; retain a package-only fallback while external-data rules remain unresolved.
2. **Freeze one exact forecast artifact:** bind it to model recipe, commit, training cutoff, data hashes, scorer version, validator log, and forecast content hash.
3. **Integrate rather than stack branches:** current best candidate + Frank's two-fold/source discipline + Jim's UI/report + Pavlo's reliability/error analysis + Abdo's artifact inventory.
4. **Make fresh-clone reproduction work:** the UI/API and report must reference the same model and metrics; no stale hardcoded 43.05/41.71-era headlines.
5. **Finish jury-facing assets:** concise evaluation report, 5–8 slides, ≤5-minute demo, honest replay/time travel, negative results, and clear data/licensing provenance.
6. **Keep licensed material private and out of prompts/public artifacts:** do not publish the repository or upload spot/forecast-derived rows to hosted tools without a clear derived-output answer.

Detailed execution order and kill gates are in [ROADMAP_2026-11-07.md](ROADMAP_2026-11-07.md). Copy-ready organiser questions are in [PROVIDER_QUESTIONS_2026-11-07.md](PROVIDER_QUESTIONS_2026-11-07.md).

## 10. Limitations and non-claims

- Hidden test actuals and the accepted-team `best` values are unavailable; final points and rank are unknowable locally. The 78.747183/78.592780 comparison is only an official-formula proxy over the five current September entries.
- Both September and August influenced model selection. Two-fold evidence reduces but does not eliminate selection bias; neither fold is a fresh untouched test.
- The scoreboard's `official` label is preserved as provenance; only `team5050` September was independently rerun by the main auditor in this final reconciliation.
- August `team5050` and `P2` results are lab-scored; `team5050` is rounded, lacks coverage, and has no committed forecast artifact, so the overall `team5050`/`v6_hf` ranking is unresolved.
- Frank's `v4_n50` and `v6_hf` entries have blank `forecast_file` fields and no committed scored CSV was found. Their scoreboard-official labels are not artifact-level independent reproducibility.
- External-data publication delays, revised vintages, licences, and derived-output sharing remain open where identified in the provider questions.
- Historical subagent audits used older branch heads. Their architectural findings are included only as leads or explicitly labelled historical findings, not silently as current-code facts.
- No numeric “oracle ceiling” is asserted. The realistic target is better validated relative performance across all official criteria, not an invented universal accuracy goal.

## 11. Reproduction anchors

From the master worktree:

```bash
python scoreboard/leaderboard.py
```

From the Abdo worktree with the protected package present locally:

```bash
python starter_package/score.py \
  --submission submissions/validation_team5050.csv \
  --actuals starter_package/data/actuals_validation.csv \
  --spike-margin 50 \
  --output-dir /path/to/private/output

python starter_package/validate_submission.py \
  --backtest submissions/forecast_backtest_team5050.csv \
  --origins starter_package/forecast_origins.csv
```

Key scoreboard entries:

- `scoreboard/entries/abdo__team5050__validation__official.json` — forecast source commit `20b414d`
- `scoreboard/entries/abdo__team5050__fold_b__lab.json` — logged source commit `9e29812`
- `scoreboard/entries/frank__v6_hf__{validation,fold_b}__official.json` — source commit `fe230bf`
- `scoreboard/entries/frank__v4_n50__{validation,fold_b}__official.json` — source commit `67ab599`
- `scoreboard/entries/abdo__p2-int4-ss-lgb7__*.json` — source commits recorded per entry
- `scoreboard/entries/organisers__baseline__*.json` — common baselines

## Sources

[1] https://doi.org/10.1016/j.egyai.2026.100724 — Finnish aFRR price forecasting (Energy & AI, 2026)
    > "The models achieved mean absolute errors of 17.5–17.8 for Down-regulation and 55–60 for Up-regulation, with LightGBM delivering the most robust performance under limited data availability."
[2] https://github.com/BigdogManLuo/HEFTcom24 — HEFTcom2024 GEB solution
    > "2. **Online Post-Processing** model to address distribution shifts caused by increased solar capacity in the online test set."
[3] https://arxiv.org/abs/2611.03331 — Leveraging Continuous Trade Data for Intraday Imbalance Price Forecasting
    > "In a case study based on multiple years of data from Great Britain, our proposed approach reduced the Pinball Loss of state-of-the-art models by 20% for forecasts made 30 seconds before gate closure, and by 7.5% for forecasts made one hour before delivery."
[4] https://arxiv.org/abs/2405.15359 — Adaptive probabilistic forecasting of French electricity spot prices
    > "Benchmarking state-of-the-art PEPF on this data set highlights the difficulty of choosing a given model, as they all behave very differently in practice, and none of them is reliable."
[5] https://www.fingrid.fi/en/electricity-market/balance-service/description-of-balance-model — Fingrid — Description of balance model
    > "Imbalance of Balance Responsible Parties will be calculated in 15 minute imbalance settlement periods."
[6] https://lightgbm.readthedocs.io/en/latest/Parameters.html — LightGBM Parameters
    > "quantile , Quantile regression"
[7] https://github.com/amazon-science/chronos-forecasting — Chronos forecasting — official repository
    > "Chronos-2**: Our latest model with significantly enhanced capabilities. It offers zero-shot support for univariate, multivariate, and covariate-informed forecasting tasks."
[8] https://orbit.dtu.dk/en/publications/probabilistic-energy-forecasting-global-energy-forecasting-compet — GEFCom2014 and beyond — DTU
    > "A major portion of the paper is devoted to introducing the Global Energy Forecasting Competition 2014 (GEFCom2014), a probabilistic energy forecasting competition with four tracks on load, price, wind and solar forecasting, which attracted 581 participants from 61 countries."
