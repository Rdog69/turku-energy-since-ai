"""Interactive Situation Room Dashboard for Turku Energia Imbalance Price Forecasting."""

import sys
from pathlib import Path
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

WORKSPACE_DIR = Path(__file__).resolve().parents[1]
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

from src.data.loader import DATA_DIR, load_spot

st.set_page_config(
    page_title="Turku Energia Situation Room",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .metric-card {
        background-color: #1E222D;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #2A2E39;
        margin-bottom: 12px;
    }
    .alert-card {
        background-color: #2D1E22;
        border-radius: 8px;
        padding: 14px;
        border-left: 5px solid #FF4D4F;
        margin-bottom: 12px;
    }
    .suggestion-card {
        background-color: #1E272D;
        border-radius: 8px;
        padding: 14px;
        border-left: 5px solid #1890FF;
        margin-bottom: 12px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_forecast_and_spot():
    comp_file = WORKSPACE_DIR / "results" / "composite" / "forecast_backtest.csv"
    if not comp_file.exists():
        comp_file = WORKSPACE_DIR / "results" / "mixture" / "forecast_backtest.csv"
    df_fc = pd.read_csv(comp_file)
    spot = load_spot()
    return df_fc, spot


df_forecast, df_spot = load_forecast_and_spot()
origins = sorted(df_forecast["forecast_origin_utc"].unique().tolist())

# Sidebar: Time Travel Controls
st.sidebar.title("⚡ Control Room")
st.sidebar.markdown("**Since AI 2026 — Turku Energia Challenge**")

selected_origin = st.sidebar.selectbox("Select Forecast Origin (Time Travel):", origins, index=0)

origin_data = df_forecast[df_forecast["forecast_origin_utc"] == selected_origin].sort_values("step").reset_index(drop=True)
cutoff_time = origin_data.loc[0, "data_cutoff_utc"] if "data_cutoff_utc" in origin_data.columns else selected_origin

st.sidebar.info(f"**Viewing Origin:**\n`{selected_origin}`\n\n**Data Cut-off (Latest Usable):**\n`{cutoff_time}`")

# Header Section
st.title("⚡ Turku Energia Situation Room")
st.markdown(f"**Operational 10-Hour Imbalance Price & Risk Forecast** | Origin: `{selected_origin}`")

# Metrics Banner
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Model MAE ($p_{50}$)", "43.05 €/MWh", "-35.0% vs Baseline (66.20)")
with col2:
    st.metric("Calibration Pinball ($p_{10}/p_{90}$)", "12.82", "-47.0% vs Baseline (24.18)")
with col3:
    st.metric("Spike Brier Score", "0.0965", "-14.8% vs Baseline (0.1132)")
with col4:
    st.metric("Direction Brier Score", "0.4244", "-5.9% vs Baseline (0.4509)")

# Alert & Operational Suggestions
st.markdown("### 🔍 Operator Action & Situational Brief")

high_spikes = origin_data[origin_data["p_spike_high"] >= 0.20]
low_spikes = origin_data[origin_data["p_spike_low"] >= 0.20]
wide_spreads = origin_data[(origin_data["p90"] - origin_data["p10"]) > 120.0]

sugg_col1, sugg_col2 = st.columns(2)

with sugg_col1:
    if not high_spikes.empty:
        max_s = high_spikes.loc[high_spikes["p_spike_high"].idxmax()]
        st.markdown(
            f"""
            <div class="alert-card">
                <b>🚨 High Up-Regulation Spike Risk Detected!</b><br>
                Step {int(max_s['step'])} ({max_s['delivery_start_utc']}) has <b>{max_s['p_spike_high']:.1%}</b> spike risk.<br>
                <i>Operational Suggestion:</i> Check <b>Naantali CHP production plan</b> for upward flexibility; ensure uncommitted thermal capacity is ready for mFRR activation.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="suggestion-card">
                <b>✅ Normal Market Conditions</b><br>
                No extreme upward spike risk (&gt;20%) identified for the next 10 hours. Maintain scheduled production bids.
            </div>
            """,
            unsafe_allow_html=True,
        )

with sugg_col2:
    if not low_spikes.empty:
        max_l = low_spikes.loc[low_spikes["p_spike_low"].idxmax()]
        st.markdown(
            f"""
            <div class="alert-card">
                <b>⚠️ Down-Regulation / Low Price Risk!</b><br>
                Step {int(max_l['step'])} ({max_l['delivery_start_utc']}) has <b>{max_l['p_spike_low']:.1%}</b> downside risk.<br>
                <i>Operational Suggestion:</i> Review <b>Electric Boilers & Heat Pumps</b> to absorb surplus power and avoid downward penalty.
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif not wide_spreads.empty:
        w_step = int(wide_spreads.iloc[0]["step"])
        spread = wide_spreads.iloc[0]["p90"] - wide_spreads.iloc[0]["p10"]
        st.markdown(
            f"""
            <div class="alert-card">
                <b>⚠️ High Uncertainty / Conflicting Signal</b><br>
                Step {w_step} exhibits an unusually wide P10–P90 spread (<b>{spread:.1f} €/MWh</b>). Expert review recommended before locking intraday commitments.
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="suggestion-card">
                <b>⚖️ System Balance Stable</b><br>
                Down-regulation risk within normal variance. Merit order operating along expected baseline.
            </div>
            """,
            unsafe_allow_html=True,
        )

# Main Forecast Fan Chart
st.markdown("### 📈 10-Hour Forecast Fan Chart (P10 – P50 – P90 vs Spot)")

fig = go.Figure()

deliveries = pd.to_datetime(origin_data["delivery_start_utc"])

# Shaded P10-P90 range
fig.add_trace(
    go.Scatter(
        x=deliveries,
        y=origin_data["p90"],
        mode="lines",
        line=dict(width=0),
        showlegend=False,
        name="P90 Upper Bound",
    )
)
fig.add_trace(
    go.Scatter(
        x=deliveries,
        y=origin_data["p10"],
        mode="lines",
        line=dict(width=0),
        fill="tonexty",
        fillcolor="rgba(24, 144, 255, 0.18)",
        name="P10–P90 80% Confidence Band",
    )
)

# P50 point forecast
fig.add_trace(
    go.Scatter(
        x=deliveries,
        y=origin_data["p50"],
        mode="lines+markers",
        line=dict(color="#1890FF", width=3),
        marker=dict(size=4),
        name="P50 Point Forecast",
    )
)

# Optional Spot price overlay if available
if df_spot is not None and not df_spot.empty:
    spot_sub = df_spot[df_spot["timestamp_utc"].isin(origin_data["delivery_start_utc"])].sort_values("timestamp_utc")
    if not spot_sub.empty:
        fig.add_trace(
            go.Scatter(
                x=pd.to_datetime(spot_sub["timestamp_utc"]),
                y=spot_sub["value"],
                mode="lines",
                line=dict(color="#FFA940", width=2, dash="dash"),
                name="Day-Ahead Spot Price (Anchor)",
            )
        )

fig.update_layout(
    template="plotly_dark",
    height=450,
    margin=dict(l=40, r=40, t=20, b=40),
    xaxis_title="Delivery Quarter-Hour (UTC)",
    yaxis_title="Price (EUR/MWh)",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    hovermode="x unified",
)
st.plotly_chart(fig, use_container_width=True)

# Balancing Direction & Spike Probabilities Heatmap
st.markdown("### 🧭 Regulation Direction & Spike Risk Probabilities")

prob_col1, prob_col2 = st.columns(2)

with prob_col1:
    fig_dir = go.Figure()
    fig_dir.add_trace(
        go.Bar(
            x=origin_data["step"],
            y=origin_data["p_up"],
            name="P(Up-Regulation)",
            marker_color="#F5222D",
        )
    )
    fig_dir.add_trace(
        go.Bar(
            x=origin_data["step"],
            y=origin_data["p_down"],
            name="P(Down-Regulation)",
            marker_color="#52C41A",
        )
    )
    fig_dir.update_layout(
        barmode="stack",
        template="plotly_dark",
        title="Dominating mFRR Direction Probabilities",
        xaxis_title="Forecast Step (1-40)",
        yaxis_title="Probability",
        height=280,
        margin=dict(l=30, r=30, t=40, b=30),
    )
    st.plotly_chart(fig_dir, use_container_width=True)

with prob_col2:
    fig_spikes = go.Figure()
    fig_spikes.add_trace(
        go.Bar(
            x=origin_data["step"],
            y=origin_data["p_spike_high"],
            name="P(Spike High > Spot+50)",
            marker_color="#FA8C16",
        )
    )
    fig_spikes.add_trace(
        go.Bar(
            x=origin_data["step"],
            y=origin_data["p_spike_low"],
            name="P(Spike Low < Spot-50)",
            marker_color="#13C2C2",
        )
    )
    fig_spikes.update_layout(
        template="plotly_dark",
        title="Exceptional Price Spike Risk (>50 EUR/MWh)",
        xaxis_title="Forecast Step (1-40)",
        yaxis_title="Spike Probability",
        height=280,
        margin=dict(l=30, r=30, t=40, b=30),
    )
    st.plotly_chart(fig_spikes, use_container_width=True)

# Step-by-Step Data Table with Drivers
st.markdown("### 📋 Step-by-Step Table with Physical Drivers")
st.dataframe(
    origin_data[
        [
            "step",
            "delivery_start_utc",
            "p10",
            "p50",
            "p90",
            "p_up",
            "p_down",
            "p_spike_high",
            "p_spike_low",
            "top_drivers",
        ]
    ],
    use_container_width=True,
    height=320,
)

