# JURY DEFENSE & Q&A PREPARATION GUIDE

> **Since AI 2026 — Turku Energia Challenge**  
> **Team:** Pavlo, Pavel, Frank, Jim, Abdo  
> **Target:** Finnish 10-Hour Imbalance Price Forecasting  

This cheat sheet prepares the presenter for tough questions from the Turku Energia jury and hackathon evaluators.

---

### Q1: "How do you guarantee that no lookahead data was leaked into your model?"
**Our Answer:**
* **Strict Publication Timestamps:** We created a centralized filter function (`src/data/available_at.py`) that strictly enforces `first_usable_origin_utc <= forecast_origin_utc`. Every dataset (both starter package and external Fingrid real-time / Open-Meteo runs) has a publication delay timestamp per row.
* **Automated CI Regression:** We maintain unit tests in `tests/test_leakage.py` that intentionally truncate future data and verify identical feature matrices.
* **The 2-Hour Label Embargo:** In our training pipeline, we apply a strict 2-hour embargo before the training cutoff (`cutoff - pd.Timedelta(hours=2)`), ensuring no unfinalized settlement labels from the latest quarter are visible at the cutoff origin.
* **Verified Submission Column:** Our generated `forecast_backtest.csv` includes the `data_cutoff_utc` column, which passed the official validator with 0 errors.

---

### Q2: "Why did you frame the problem around the 'Gap to Day-Ahead Spot' rather than forecasting raw prices?"
**Our Answer:**
* Electricity cannot be stored cheaply, but the **Day-Ahead Spot market** already clears the macro balance 12–36 hours ahead.
* Raw imbalance prices are highly non-stationary and volatile across months. In contrast, the **imbalance gap ($\Delta_t = \text{Price}_t - \text{Spot}_t$)** is a stationary mean-reverting process that represents purely real-time intra-day surprises (wind forecast errors, power plant trips, temperature shifts).
* Anchoring on Spot alone cut baseline error by **33%** before training a single machine learning model.

---

### Q3: "Why is the Finnish balancing market so asymmetric between up and down regulation?"
**Our Answer:**
* **Down-Regulation (Surplus):** When wind generation is higher than planned, the grid has excess energy. Wind operators or hydro plants are curtailed or paid slightly less. Down-regulation prices are floored and relatively flat (median $-23.3$ €/MWh, std $\approx 38$).
* **Up-Regulation (Deficit):** When wind dies or a nuclear unit trips, the TSO must activate fast secondary and tertiary balancing reserves (mFRR). The TSO must call upon expensive peaking thermal assets (gas turbines, oil peakers) along a steep merit order curve. Up-regulation prices exhibit extreme fat-tailed spikes (median $+30.7$ €/MWh, std $> 207$).
* This is why standard symmetrical regressors (like MSE) fail—they average these regimes into an unrealistic middle. Our **Direction-Mixture CDF Model** treats up and down regimes as separate conditional distributions.

---

### Q4: "Why not use a Deep Learning Transformer (e.g. PatchTST, Chronos, or LSTM)?"
**Our Answer:**
* **Data Scale & Tabular Structure:** We have ~120,000 quarter-hour intervals across tabular physical series (MW production, net load, frequency, weather runs). Tabular gradient boosted trees (LightGBM, CatBoost, HistGradientBoosting) consistently outperform Transformers on tabular energy data with sharp discontinuous regimes.
* **Quantile Loss Direct Optimization:** Gradient boosted trees allow exact pinball loss minimization at specified quantiles ($q=0.10, 0.50, 0.90$).
* **Inference Speed & Operational Reliability:** Our model runs inference for all 40 steps across the entire 10-hour horizon in **under 15 milliseconds**, allowing real-time deployment on standard lightweight infrastructure without expensive GPU instances.

---

### Q5: "What was the single most impactful feature in your pipeline?"
**Our Answer:**
* **For Steps 1–4 (Hour 1):** The **Fingrid Real-Time Wind Forecast Error** (`rt_wind` = measured wind generation right now minus day-ahead wind forecast). Wind plan errors persist strongly over 1–2 hours. This single feature dropped our Hour 1 MAE from 41.6 € down to **36.90 €/MWh**!
* **For Steps 5–40 (Hours 2–10):** **Day-Ahead Net Load (Residual Load)**: $\text{Consumption Forecast} - \text{Wind Forecast} - \text{Solar Forecast}$. TreeSHAP shows that residual load accounts for **38% of total price variance** over long horizons.

---

### Q6: "How do your $P_{10}$ and $P_{90}$ confidence bounds help Turku Energia in practice?"
**Our Answer:**
* A point forecast ($P_{50}$) is insufficient for power plant operators and traders:
  1. **Asymmetric Risk Management:** If $P_{50}$ is 50 €/MWh, but $P_{90}$ is **320 €/MWh**, an unhedged trader faces catastrophic tail risk.
  2. **Asset Dispatch at Naantali CHP:** When our model detects $P_{\text{spike\_high}} > 15\%$ and an elevated $P_{90}$ ceiling, Naantali plant operators get a 4- to 8-hour head start to warm up thermal capacity and submit bids into the lucrative mFRR upward reserve market.
  3. **Power-to-Heat / Electric Boilers:** When $P_{10}$ drops near 0 or negative, Turku Energia can safely turn on large industrial electric boilers and heat pumps to heat the city district heating network with free or negative-cost electricity.

---

### Q7: "How did you achieve such high calibration (79.6% coverage against the 80% target)?"
**Our Answer:**
* Standard models suffer from under-coverage (they predict intervals that are too narrow, capturing only 50–60% of real prices).
* We applied a **28-day rolling calibration window** that shifts the empirical quantile residuals and scales probabilities using Platt scaling.
* In our final post-processing step, we tuned the quantile width factor ($\times 1.05$) to expand the confidence envelope to fit the true empirical error distribution, cutting mean Pinball loss from **24.18 down to 11.95** (-50.6%).

---

### Q8: "What are the next steps for live production deployment?"
**Our Answer:**
1. **Automated Live Pipeline:** We built an exportable **n8n automated workflow** that ingests real-time forecasts, generates LLM operational briefs via **Featherless.ai**, and delivers voice audio dispatches via **ElevenLabs** into the trading room's Discord/Teams channel.
2. **REST API Microservice:** Our **FastAPI backend** (`api/main.py`) serves `/forecast/{origin_utc}` with complete Pydantic validation, ready to be mounted in Turku Energia's internal Kubernetes cluster.
3. **Continuous Rolling Re-Training:** The model can be scheduled as a daily cron job at 23:00 UTC to refit on the newest 28 days of finalized Fingrid settlement data.

