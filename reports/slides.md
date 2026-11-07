# Presentation Slides: Turku Energia Imbalance Price Forecasting

> **Since AI 2026 Hackathon — Turku Energia Challenge**  
> **Team:** Pavlo, Pavel, Frank, Jim, Abdo  
> **Pitch Deck: 6 Slides (for 5-Minute Presentation & Demo Video)**

---

## Slide 1: Title & Executive Summary
### Operational 10-Hour Imbalance Price Forecasting & Situation Room
* **Challenge:** Forecast Finnish 15-minute imbalance prices 1–40 steps (10h ahead), balancing direction, and tail spike risk.
* **Core Philosophy:** Predict **deviations from spot** driven by physical grid fundamentals, not black-box price guessing.
* **Key Achievements:**
  * **35.0% MAE Error Reduction** vs. official baseline (43.05 vs. 66.20 €/MWh).
  * **47.0% Calibration Loss Reduction** (Pinball: 12.82 vs. 24.18).
  * **Validated Official Submission:** 26,920 rows verified with zero errors.
  * **Operational Situation Room:** Interactive UI with time travel, SHAP drivers, and asset recommendations.

---

## Slide 2: The Floor vs. The Winning Edge
### Why Standard Regressors Fail on Imbalance Data
* **The Obvious Baseline ("The Floor"):**
  * Predicting `imbalance = spot + gap`. Spot alone beats the naive baseline by ~33%. Every serious team will discover this.
* **Where We Win ("Our Edge"):**
  1. **Bimodal Reality:** The gap is never centered around zero; it is $+25$ €/MWh when up, $-17$ €/MWh when down ("None" is $<0.2\%$).
  2. **Direction-Mixture CDF Model:** Combining $P(\text{up}) \cdot F_{\text{up}} + P(\text{down}) \cdot F_{\text{down}}$ guarantees monotonicity and mathematically consistent tail probabilities.
  3. **"Pick-Per-Column" Selector:** Optimizing models independently across the 4 competition criteria.
  4. **Strict Anti-Leakage Protocol:** Verified via automated unit tests.

---

## Slide 3: The Physical Reasoning Chain (20 Jury Points)
### Unbroken Causality from Weather to Price Formation
$$\text{NWP Weather Revision} \longrightarrow \text{Wind Forecast Error} \longrightarrow \text{System Net Imbalance}$$
$$\longrightarrow \text{mFRR Balancing Activation} \longrightarrow \text{Asymmetric Merit Order} \longrightarrow \text{Imbalance Price}$$

1. **Weather Shifts:** Open-Meteo single runs measure wind forecast revisions on the Finnish west coast since the day-ahead schedule was locked.
2. **Net Imbalance:** Deviation between scheduled and physical residual load ($\text{consumption} - \text{wind} - \text{solar}$).
3. **mFRR Balancing Reserves:** Grid frequency and system deficits force secondary/tertiary activations.
4. **Asymmetric Price Formation:** Up-regulation climbs a steep thermal merit order ($+8 \rightarrow +61$ €/MWh); down-regulation is flat ($\approx -17$ €/MWh).

---

## Slide 4: Model Architecture & TreeSHAP Attribution
### Physics-Informed Machine Learning with Complete Explainability
* **Feature Foundations:**
  * Day-ahead spot price curve and hourly boundary ramps.
  * Day-ahead net position (residual load) and wind share.
  * Decaying recent imbalance gap ($5$ quarters stale at step 1, decaying exponentially).
* **TreeSHAP Explainability:**
  * SHAP values computed dynamically for every single quarter-hour.
  * Identifies the primary physical driver (e.g. `net_load_da`, `wind_fc_da`, `spot_ramp`) without LLM hallucination.

---

## Slide 5: Benchmark Results & Validation Gains
### Comprehensive Ablation Study (Validation Period: 7 Sep – 4 Oct 2026)

| Model Iteration | MAE ($p_{50}$) [€/MWh] | Mean Pinball ($p_{10}/p_{90}$) | Spike Brier | Direction Brier | Improvement vs Baseline |
|---|---|---|---|---|---|
| **Official Baseline** | 66.20 | 24.18 | 0.1132 | 0.4509 | Reference (0 pts) |
| **Static Spot Anchor** | 44.20 | 22.10 | 0.1105 | 0.4509 | -33.2% MAE |
| **Direct LightGBM Baseline** | 44.16 | 13.21 | 0.0983 | 0.4244 | -33.3% MAE, -45.4% Pinball |
| **Direction-Mixture Model** | 43.05 | 12.82 | 0.0965 | 0.4274 | -35.0% MAE, -47.0% Pinball |
| **Fingrid RT Wind Error + Step Bands** | 41.81 | 12.01 | 0.0907 | 0.3895 | -36.8% MAE, -50.3% Pinball |
| **Grand Champion Ensemble** | **`41.71`** | **`11.95`** | **`0.0898`** | **`0.3884`** | **🏆 Best Overall (-37.0% MAE, -50.6% Pinball)** |

* **Short Horizon (Steps 1–4):** MAE drops to **36.90 €/MWh** (powered by Fingrid real-time nowcasting).
* **Long Horizon (Steps 37–40):** Stable at **42.79 €/MWh** anchored by day-ahead fundamentals.

---

## Slide 6: Level 2 Situational Room & Operational Decision Support
### From Model Predictions to Real-World Dispatch Decisions
* **Interactive Situation Room (`app/dashboard.py`):**
  * Time-travel slider over historical origins.
  * 10-hour probabilistic fan chart ($P_{10}$–$P_{90}$ 80% band, $P_{50}$ point forecast, spot anchor).
  * Up/down balancing probability stack and tail spike risk heatmaps.
* **Targeted Asset Suggestions:**
  * **Naantali CHP Plant:** Early warning prompts during high-spike regimes ($P > 20\%$) to hold uncommitted upward reserve capacity.
  * **Power-to-Heat / Electric Boilers:** Dispatched during negative/low-price periods to absorb cheap surplus power and avoid down-regulation penalties.
* **Dispatcher Automation (`automation/`):**
  * Automated n8n workflow streaming Featherless LLM plain-language briefs and ElevenLabs spoken dispatches directly to Discord/Teams.

