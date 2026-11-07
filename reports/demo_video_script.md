# Demo Video Script: Turku Energia Imbalance Price Situation Room

> **Target Length:** $\le$ 5:00 minutes  
> **Speaker:** Abdo / Jim  
> **Screens:** Browser showing `app/dashboard.py` (Streamlit / Lovable) & Slides in `reports/slides.md`

---

### [0:00 – 0:45] Introduction & The Problem
**Visual:** Slide 1 (Title) then switch to live Dashboard (`http://localhost:8501`).
* **Speaker:**  
  *"Hello everyone. For Turku Energia, buying and generating power profitably depends on staying on the right side of the Finnish imbalance settlement. When the grid is short, up-regulation prices climb steeply along the thermal merit order; when the grid has surplus, prices plunge.*  
  *Today, we present our physics-informed 10-hour imbalance price forecast and operational Situation Room.*  
  *Instead of treating electricity prices as an opaque black box, our model forecasts deviations from the day-ahead spot price driven by weather revisions, net system balance, and secondary reserves."*

---

### [0:45 – 1:45] The 10-Hour Forecast Fan Chart & Probabilities
**Visual:** Point cursor to the main Plotly fan chart on the dashboard.
* **Speaker:**  
  *"Here on the dashboard, we see the next 10 hours in 15-minute resolution—exactly 40 quarter-hours.*  
  *The orange dashed line represents tomorrow's Nord Pool day-ahead spot price, which anchors the market.*  
  *The solid blue line is our median point forecast ($p_{50}$). Surrounding it is the shaded 80% confidence interval from $p_{10}$ to $p_{90}$.*  
  *Notice how our intervals are physically calibrated: when regulation direction is uncertain, our Direction-Mixture CDF Model expands the interval to capture both possible regimes, guaranteeing monotonic quantiles without quantile crossing.*  
  *Below the fan chart, we display the dominating regulation direction probabilities—green for down-regulation, red for up-regulation—alongside tail spike risk probabilities for prices exceeding $\pm 50$ €/MWh."*

---

### [1:45 – 2:45] TreeSHAP Drivers & Conflicting Signals
**Visual:** Scroll down to the Step-by-Step Table and the Operator Action cards.
* **Speaker:**  
  *"A critical requirement from Turku Energia was explainability: why is the price moving?*  
  *Using TreeSHAP on our gradient-boosted trees, we extract the top 3 physical drivers for every single quarter-hour.*  
  *In the early steps, the forecast is driven by decaying recent state and hourly spot boundary ramps. In the later steps, day-ahead residual load—consumption minus wind and solar—and wind ramp differentials dominate.*  
  *Our system also flags conflicting signals: for example, when the direction model predicts up-regulation but the point forecast is temporarily depressed, or when the $P_{10}$–$P_{90}$ spread exceeds 120 €/MWh, signaling extreme market uncertainty."*

---

### [2:45 – 3:45] Asset Dispatch Suggestions & Alert Automation
**Visual:** Highlight the blue and red Operational Suggestion cards at the top.
* **Speaker:**  
  *"We translate numbers into actionable dispatch suggestions for Turku Energia's operators:*  
  *When our spike risk model detects an upward spike probability exceeding 20%, an alert prompts the dispatcher to review the Naantali CHP production plan for upward reserve flexibility.*  
  *Conversely, when negative price risks appear, the system recommends dispatching district heating electric boilers and heat pumps to absorb cheap power and avoid downward penalties.*  
  *Furthermore, our exported n8n workflow monitors incoming origin forecasts, calls Featherless.ai for a two-sentence plain-language summary, generates a 20-second ElevenLabs spoken dispatch, and posts embeds directly to Discord operations channels."*

---

### [3:45 – 4:45] Time-Travel Replay & Performance Track Record
**Visual:** Click the 3 Golden Bookmark buttons at the top (`🔴 High Spike Warning`, `🔵 Wind Surplus Trap`, `⚡ Sudden Revision`) and show the dashed revision line ($t - 1\text{h}$) with the revision alert banner.
* **Speaker:**  
  *"The brief requested a historical time-travel replay feature. Above the time slider, we built three one-click Golden Scenario Bookmarks: jumping directly into an evening peak spike, a windy Sunday surplus trap, or a sharp forecast revision.*  
  *On the fan chart, notice the grey dotted line—that is the forecast from one hour earlier ($t - 1\text{h}$). When the market revises sharply, a warning banner instantly flags the shift and highlights the root TreeSHAP driver.*  
  *Across all 26,700 evaluated quarter-hours of the validation window:*  
  *- Our MAE dropped from 66.20 down to **40.97 €/MWh**—a **38.1% error reduction**.*  
  *- Mean pinball loss dropped from 24.18 down to **11.63**—a **51.9% uncertainty improvement** with **80.1% empirical coverage**.*  
  *- Tail spike Brier dropped to **0.0861** (-24.0%) and direction Brier to **0.3803** (-15.7%).*  
  *- On independent August holdout data, our anti-overfit architecture scores **+6.81 points**, winning **9 out of 10 individual weeks** across both months.*  
  *Our official submission file, `forecast_backtest.csv` (26,920 rows), passes all validation checks with zero errors and 100% TreeSHAP driver coverage."*

---

### [4:45 – 5:00] Closing & Team Sign-Off
**Visual:** Switch to Slide 6 or show repository structure.
* **Speaker:**  
  *"By grounding machine learning in the physical realities of the Nordic power grid, our solution delivers both competitive predictive accuracy and transparent decision support for Turku Energia. Thank you!"*

