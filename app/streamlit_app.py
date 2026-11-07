"""Local fallback "situation room" dashboard (Streamlit). Local demo only: never deploy publicly."""
import json
import os
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
TZ = "Europe/Helsinki"
# spike-probability thresholds for the status light
AMBER, RED = 0.20, 0.40

st.set_page_config(page_title="Imbalance situation room", layout="wide")


def default_dir() -> str:
    env = os.environ.get("DASHBOARD_DATA_DIR")
    if env:
        return env
    for p in (ROOT / "results/dashboard/test", ROOT / "app_demo_sample/test"):
        if p.exists():
            return str(p)
    return str(ROOT / "app_demo_sample/test")


@st.cache_data
def load_index(d):
    return json.loads((Path(d) / "index.json").read_text())


@st.cache_data
def load_origin(d, o):
    return json.loads((Path(d) / "origins" / f"{pd.Timestamp(o).strftime('%Y%m%dT%H')}.json").read_text())


@st.cache_data
def load_track(d):
    p = Path(d) / "track_record.json"
    return json.loads(p.read_text()) if p.exists() else []


def qframe(doc):
    df = pd.DataFrame(doc["quarters"])
    df["time"] = pd.to_datetime(df["t"], utc=True).dt.tz_convert(TZ)
    return df


def local(o):
    return pd.Timestamp(o).tz_convert(TZ).strftime("%a %d.%m. %H:%M")


# ---------------- sidebar / time travel ----------------
data_dir = st.sidebar.text_input("Data folder", default_dir())
try:
    index = load_index(data_dir)
except Exception as e:  # noqa: BLE001
    st.error(f"Cannot read {data_dir}/index.json: {e}")
    st.stop()
origins = index["origins"]
labels = [local(o) for o in origins]
if st.session_state.get("_dir") != data_dir:
    st.session_state["_dir"] = data_dir
    st.session_state["tt"] = labels[0]
if st.session_state.get("tt") not in labels:
    st.session_state["tt"] = labels[0]
pos = labels.index(st.session_state["tt"])

st.title("Imbalance price situation room")
c1, c2, c3 = st.columns([1, 1, 8])
if c1.button("< Prev", disabled=pos == 0):
    st.session_state["tt"] = labels[pos - 1]
    st.rerun()
if c2.button("Next >", disabled=pos == len(labels) - 1):
    st.session_state["tt"] = labels[pos + 1]
    st.rerun()
c3.select_slider("Time travel: viewing time (Helsinki)", options=labels, key="tt")
pos = labels.index(st.session_state["tt"])
origin = origins[pos]
doc = load_origin(data_dir, origin)
df = qframe(doc)
prev_df = qframe(load_origin(data_dir, origins[pos - 1])) if pos > 0 else None
if doc.get("demo") or index.get("demo"):
    st.caption("Demo data (sample). Forecast made at " + doc.get("origin_local", "") + " local; data cut-off "
               + local(doc["data_cutoff"]))

# ---------------- next 1-3 h strip ----------------
near = df.iloc[3:12]
mx = float(near[["p_spike_high", "p_spike_low"]].max().max())
level, colour = (("RED", "#c0392b") if mx >= RED else ("AMBER", "#e69f00") if mx >= AMBER else ("GREEN", "#2e8b57"))
a, b = st.columns([1, 3])
a.markdown(
    f"<div style='background:{colour};color:white;padding:14px;border-radius:8px;text-align:center'>"
    f"<div style='font-size:1.6em;font-weight:700'>{level}</div>"
    f"<div>max spike probability {mx:.0%} in the next 1-3 h</div></div>", unsafe_allow_html=True)
a.caption(f"Thresholds: green < {AMBER:.0%}, amber {AMBER:.0%}-{RED:.0%}, red >= {RED:.0%} "
          "(quarters 4-12 ahead, high or low spike).")
expl = (doc.get("explanation") or {}).get("text")
b.markdown("**Briefing**")
b.write(expl or "No briefing text for this origin.")
drv = doc.get("drivers") or []
if drv:
    b.markdown("**Main drivers:** " + ", ".join(d["label"] for d in drv[:4]))
for al in (doc.get("alerts") or [])[:3]:
    b.markdown(f"- {al['message']}")

# ---------------- fan chart ----------------
st.subheader("Next 10 h: imbalance price forecast (EUR/MWh)")
fig = go.Figure()
fig.add_trace(go.Scatter(x=df.time, y=df.p90, line=dict(width=0), showlegend=False, hoverinfo="skip"))
fig.add_trace(go.Scatter(x=df.time, y=df.p10, fill="tonexty", fillcolor="rgba(31,119,180,0.2)",
                         line=dict(width=0), name="P10-P90"))
fig.add_trace(go.Scatter(x=df.time, y=df.p50, name="P50", line=dict(color="#1f77b4", width=3)))
fig.add_trace(go.Scatter(x=df.time, y=df.spot, name="Spot", line=dict(color="#444", dash="dot")))
fig.update_layout(height=380, margin=dict(t=10, b=10), xaxis_title=f"Time ({TZ})", yaxis_title="EUR/MWh",
                  legend=dict(orientation="h"))
st.plotly_chart(fig, width="stretch")

# ---------------- probabilities ----------------
st.subheader("Regulation direction and spike risk per quarter")
left, right = st.columns(2)
f2 = go.Figure()
f2.add_bar(x=df.time, y=df.p_up, name="P(up-regulation)", marker_color="#d55e00")
f2.add_bar(x=df.time, y=df.p_down, name="P(down-regulation)", marker_color="#0072b2")
f2.update_layout(barmode="group", height=300, margin=dict(t=10, b=10), yaxis=dict(range=[0, 1], tickformat=".0%"),
                 legend=dict(orientation="h"))
left.plotly_chart(f2, width="stretch")
f3 = go.Figure(go.Heatmap(x=df.time, y=["Spike high", "Spike low"], z=[df.p_spike_high, df.p_spike_low],
                          colorscale="Reds", zmin=0, zmax=max(0.5, mx), colorbar=dict(tickformat=".0%")))
f3.update_layout(height=300, margin=dict(t=10, b=10))
right.plotly_chart(f3, width="stretch")

# ---------------- what changed ----------------
st.subheader("What changed vs. previous update")
if prev_df is None:
    st.info("First available origin: nothing to compare with.")
else:
    m = df.merge(prev_df[["time", "p50", "p_spike_high", "p_spike_low"]], on="time", suffixes=("", "_prev"))
    if m.empty:
        st.info("No overlapping quarters with the previous update.")
    else:
        m["dP50"] = m.p50 - m.p50_prev
        m["dSpikeHigh"] = m.p_spike_high - m.p_spike_high_prev
        m["dSpikeLow"] = m.p_spike_low - m.p_spike_low_prev
        big = (m.dP50.abs() >= 20) | (m.dSpikeHigh.abs() >= 0.10) | (m.dSpikeLow.abs() >= 0.10)
        st.caption(f"{int(big.sum())} quarter(s) with big moves (|dP50| >= 20 EUR/MWh or |d spike| >= 10 pp) are highlighted.")
        t = pd.DataFrame({"Time": m.time.dt.strftime("%H:%M"), "P50": m.p50.round(1),
                          "dP50 (EUR/MWh)": m.dP50.round(1), "d spike high (pp)": (m.dSpikeHigh * 100).round(1),
                          "d spike low (pp)": (m.dSpikeLow * 100).round(1)})
        bigv = big.values
        st.dataframe(t.style.apply(lambda r: ["background-color:#ffe9a8" if bigv[r.name] else "" for _ in r], axis=1),
                     width="stretch", hide_index=True, height=260)

# ---------------- track record ----------------
st.subheader("Track record")
tr = pd.DataFrame(load_track(data_dir))
if tr.empty:
    st.info("No track_record.json in this folder.")
else:
    tr["day"] = pd.to_datetime(tr["day"])
    tr["known"] = pd.to_datetime(tr["known_from"], utc=True)
    only_known = st.checkbox("Only days already known at the viewing time", value=True)
    if only_known:
        tr = tr[tr.known <= pd.Timestamp(origin)]
    if tr.empty:
        st.info("No finished days yet at this viewing time.")
    else:
        w = tr.tail(7)
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Last day MAE", f"{tr.mae.iloc[-1]:.1f}",
                  f"{tr.mae.iloc[-1] - tr.mae_spot_only.iloc[-1]:+.1f} vs spot-only", delta_color="inverse")
        k2.metric("Last 7 d MAE", f"{w.mae.mean():.1f}",
                  f"{w.mae.mean() - w.mae_spot_only.mean():+.1f} vs spot-only", delta_color="inverse")
        k3.metric("Last 7 d MAE persistence", f"{w.mae_persistence.mean():.1f}")
        k4.metric("P10-P90 coverage (7 d, nominal 80%)", f"{w.coverage.mean():.0%}")
        f4 = go.Figure()
        f4.add_bar(x=tr.day, y=tr.mae, name="Model MAE", marker_color="#1f77b4")
        f4.add_scatter(x=tr.day, y=tr.mae_spot_only, name="Spot-only", line=dict(color="#444", dash="dot"))
        f4.add_scatter(x=tr.day, y=tr.mae_persistence, name="Persistence", line=dict(color="#d55e00"))
        f4.update_layout(height=300, margin=dict(t=10, b=10), yaxis_title="MAE (EUR/MWh)", legend=dict(orientation="h"))
        cl, cr = st.columns(2)
        cl.plotly_chart(f4, width="stretch")
        f5 = go.Figure(go.Scatter(x=tr.day, y=tr.coverage, mode="lines+markers", line=dict(color="#1f77b4")))
        f5.add_hline(y=0.8, line_dash="dash", annotation_text="nominal 80%")
        f5.update_layout(height=300, margin=dict(t=10, b=10), yaxis=dict(range=[0, 1], tickformat=".0%"),
                         yaxis_title="P10-P90 coverage")
        cr.plotly_chart(f5, width="stretch")
vm = index.get("validation_metrics")
if vm:
    with st.expander("Validation metrics (from index.json)"):
        st.json(vm)

st.divider()
st.caption("Local demo only. Contains licensed Nord Pool spot data; do not deploy publicly.")
