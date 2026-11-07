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
  * **38.1% MAE Error Reduction** vs. official baseline (40.97 vs. 66.20 €/MWh).
  * **52.0% Calibration Loss Reduction** (Pinball: 11.61 vs. 24.18, 80.1% coverage).
  * **24.0% Spike Brier Reduction** (0.0860 vs. 0.1132, with zero-parameter Kolmogorov direction envelope).
  * **Anti-Overfit Equal-Weight Architecture:** Wins **9 out of 10 individual weeks** across both August (+6.81) and September (+6.35).
  * **Validated Official Submission:** 26,920 rows verified with zero errors, 100% TreeSHAP physical drivers.
  * **Operational Situation Room:** Interactive UI with time travel, consensus monitoring, primary action window, and actuals audit.

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
| **Dual-NWP + Learned Wind (v4_n50)** | 41.08 | 11.88 | 0.0871 | 0.3899 | -37.9% MAE, -50.9% Pinball |
| **Grand Champion V1 (Static Fusion)** | 40.95 | 11.77 | 0.0865 | 0.3818 | -38.1% MAE, -51.3% Pinball |
| **Grand Champion V2 (Horizon-Banded)** | 40.73 | 11.76 | 0.0862 | 0.3812 | Single-month Sep tuning (overfit signature: +5.85 on Aug) |
| **🏆 GRAND CHAMPION FINAL (Anti-Overfit 50/50)** | **`40.97`** | **`11.61`** | **`0.0860`** | **`0.3803`** | **🏆 Best Overall (+6.81 on Aug, 9/10 wks won, 100% TreeSHAP)** |

* **Anti-Overfit Generalization:** Equal weighting of orthogonal models ($\frac{1}{2}$ Frank + $\frac{1}{2}$ Abdo) eliminates estimation variance (Clemen's theorem), beating tuned weights out-of-fold.
* **Physical Direction Envelope (Law 1D):** Monotonicity envelope ($p_{\text{spike\_high}} \le p_{\text{up}}$, $p_{\text{spike\_low}} \le p_{\text{down}}$) eliminates 387 contradictions with zero tuned parameters.
* **Short Horizon (Steps 1–4):** MAE drops to **36.25 €/MWh** (powered by Fingrid real-time nowcasting).
* **Long Horizon (Steps 37–40):** Governed by dual-NWP (ECMWF + ICON-EU) 22-station wind power curve.

---

## Slide 6: Level 2 Situational Room & Operational Decision Support
### From Model Predictions to Real-World Dispatch Decisions
* **Interactive Situation Room (`app/dashboard.py`):**
  * Time-travel slider over historical origins with real-time NWP vs telemetry consensus badge.
  * 10-hour probabilistic fan chart ($P_{10}$–$P_{90}$ 80% band, $P_{50}$ point forecast, spot anchor).
  * **Primary Action Window Box:** Highlighted 1h–3h pre-gate closure zone (Steps 4–12) for trader bids.
  * **Jury Verification Audit Mode:** Live overlay of realized actuals with window MAE & empirical coverage metrics.
* **Targeted Asset Suggestions:**
  * **Naantali CHP Plant:** Early warning prompts during high-spike regimes ($P > 20\%$) to hold uncommitted upward reserve capacity.
  * **Power-to-Heat / Electric Boilers:** Dispatched during negative/low-price periods to absorb cheap surplus power and avoid down-regulation penalties.
* **Dispatcher Automation (`automation/`):**
  * Automated n8n workflow streaming Featherless LLM plain-language briefs and ElevenLabs spoken dispatches directly to Discord/Teams.

