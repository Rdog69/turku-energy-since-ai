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

---

### Q9: "Why did you choose an equal 50/50 blend instead of tuning horizon-band weights on the validation set?"
**Our Answer:**
* **The Overfitting Trap:** In our ablation study, we built *Grand Champion V2*, which optimized 16 horizon-band simplex weights and an additive width shift specifically on September's validation window. While it shaved 0.20 € off September MAE, it degraded Pinball, Spikes, and Direction, and when evaluated on unseen August, its score completely collapsed (dropping from +6.81 down to +5.85).
* **The Physics Reason:** September was characterized by high volatility (std 141 €/MWh) and the Olkiluoto 3 nuclear trip. Tuning weights on September simply memorized that specific outage regime.
* **Clemen's Equal-Weight Theorem:** When combining two orthogonal, high-performing model families (Frank's Dual-NWP physical wind model + Abdo's Fingrid real-time telemetry model), estimated weights introduce high estimation variance ($\text{Var}(w)$). An un-tuned 50/50 equal-weight prior has zero estimation variance, winning **9 out of 10 individual weeks** across both August and September.

---

### Q10: "Where does your model struggle in practice, and what are the top ways to improve it?"
**Our Answer:**
* **Top 3 Bottlenecks:**
  1. *Horizon Decay (Hours 5–10):* Fingrid's real-time nowcasting decays exponentially after 2–3 hours. Long-horizon steps rely primarily on day-ahead weather, making MAE rise from 36.90 € in Hour 1 to 42.79 € in Hours 5–10.
  2. *Extreme Spike Quantiles ($>+300$ €/MWh):* Tree-based quantile regression suffers from leaf shrinkage and cannot extrapolate past historical thresholds. While our spike classifier detects high spike probability ($>60\%$), $p_{90}$ systematically under-predicts the true magnitude of extreme crisis spikes.
  3. *Hourly Spot Ramps:* The day-ahead market clears in hourly blocks, producing artificial step-discontinuities at the top of each hour.
* **Top 3 Engineering Solutions:**
  1. *Extreme Value Theory (EVT):* Fit a Generalized Pareto Distribution (GPD) above the 85th percentile of positive residuals for $p_{90}$ to extrapolate fat tails without distorting the median.
  2. *Intraday Market Continuous (Elbas / XBID):* Ingest live intraday order book VWAP 1–4 hours before delivery to track merchant reactions to updated wind forecasts.
  3. *PCHIP Spline Interpolation:* Smooth hourly day-ahead spot into continuous 15-minute ramps weighted by historical load curves.

---

### Q11: "Why did you enforce the physical envelope $p_{\text{spike\_high}} \le p_{\text{up}}$ and $p_{\text{spike\_low}} \le p_{\text{down}}$?"
**Our Answer:**
* Under the Nordic imbalance pricing rules (effective 1 June 2026), an upward price spike ($>+50$ €/MWh above spot) is physically impossible without the TSO activating upward balancing reserves (mFRR).
* If a model predicts $p_{\text{spike\_high}} = 0.25$ while $p_{\text{up}} = 0.15$, it violates **Kolmogorov's monotonicity axiom** of probability ($A \subseteq B \implies P(A) \le P(B)$).
* By clamping $p_{\text{spike\_high}} \le p_{\text{up}}$ and $p_{\text{spike\_low}} \le p_{\text{down}}$, we eliminated **387 physical contradictions** in the test predictions and improved the Spike Brier score from **0.086086 to 0.086034** with **zero tuned parameters**.

---

### Q12: "How does your Level 2 Situation Room assist a Turku Energia intraday trader in the primary action window?"
**Our Answer:**
* **Primary Action Window (1h–3h Pre-Gate Closure):** The UI explicitly shades Steps 4–12 on the Plotly fan chart where intraday traders must make their binding Elbas / mFRR bid decisions before delivery gate closure.
* **Consensus Strip (Weather vs Telemetry):** The system continuously computes the divergence between Frank's NWP wind model and Abdo's Fingrid real-time nowcast ($\Delta p_{50}$). When divergence is $<15$ €, it shows a 🟢 High Consensus badge. If divergence exceeds $\ge 15$ €, it displays a 🟡 Telemetry Divergence alert, warning traders that live grid dynamics are breaking away from day-ahead forecasts.
* **Live Settled Actuals Audit:** With one click (`☑️ Overlay Realized Actuals`), jury evaluators can overlay true settled prices as diamond markers and verify window MAE and empirical $P_{10}$–$P_{90}$ coverage in real time.

