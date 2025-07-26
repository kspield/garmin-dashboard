import json
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import datetime

# Load Kevin's data
with open("Kevin_Data.json") as f:
    data_kevin = json.load(f)

df_kevin = pd.DataFrame(data_kevin)
df_kevin["date"] = pd.to_datetime(df_kevin["date"])
df_kevin = df_kevin.sort_values("date")

# Try to load Simon's data
try:
    with open("Simon_Data.json") as f:
        data_simon = json.load(f)
    df_simon = pd.DataFrame(data_simon)
    df_simon["date"] = pd.to_datetime(df_simon["date"])
    df_simon = df_simon.sort_values("date")
    simon_available = True
except FileNotFoundError:
    simon_available = False

# App layout
st.set_page_config(page_title="Fat Boy Slim Competition", layout="wide")
st.title("Fat Boy Slim Competition")

# Create figure
fig = go.Figure()

# Plot Kevin's weight
fig.add_trace(go.Scatter(
    x=df_kevin["date"],
    y=df_kevin["weight"],
    mode="lines+markers",
    name="Kevin",
    yaxis="y1"
))

# Plot Simon's weight (if available)
if simon_available:
    fig.add_trace(go.Scatter(
        x=df_simon["date"],
        y=df_simon["weight"],
        mode="lines+markers",
        name="Simon",
        line=dict(color="green"),
        yaxis="y2"
    ))

# Shared goal line
goal_start_date = datetime.datetime(2025, 7, 20)
goal_end_date = datetime.datetime(2025, 12, 25)
goal_dates = pd.date_range(start=goal_start_date, end=goal_end_date, freq="D")
months = ((goal_dates - goal_start_date) / pd.Timedelta(days=30.437)).astype(float)

# Manually fixed starting weights
kevin_start_weight = 79
simon_start_weight = 100

kevin_goal_weights = kevin_start_weight * (1 - 0.015 * months)
simon_goal_weights = simon_start_weight * (1 - 0.015 * months)

# Show Kevin's goal line (visible legend)
fig.add_trace(go.Scatter(
    x=goal_dates,
    y=kevin_goal_weights,
    mode="lines",
    name="Goal Trendline",
    line=dict(dash="dot", color="gray"),
    yaxis="y1"
))

# Add Simon's goal (invisible legend, just to match y2 axis scale)
if simon_available:
    fig.add_trace(go.Scatter(
        x=goal_dates,
        y=simon_goal_weights,
        mode="lines",
        name=None,
        line=dict(dash="dot", color="gray"),
        yaxis="y2",
        showlegend=False
    ))

# Finalize layout
fig.update_layout(
    title="Weight Over Time",
    xaxis=dict(
        title="Date",
        range=[df_kevin["date"].min(), goal_end_date]
    ),
    yaxis=dict(
        title="Kevin",
        side="left",
        range=yaxis_range
    ),
    yaxis2=dict(
        title="Simon",
        overlaying="y",
        side="right",
        showgrid=False,
        range=yaxis_range  # force same scale
    ),
    legend=dict(
        x=0.99,
        y=0.01,
        xanchor="right",
        yanchor="bottom",
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    )
)

# Display chart
st.plotly_chart(fig, use_container_width=True)

# Split page below the chart
col1, col2 = st.columns(2)

# Kevin's stats
with col1:
    st.subheader("Kevin's Stats")
    latest_k = df_kevin.dropna(subset=["weight"]).iloc[-1]["weight"]
    loss_k = kevin_start_weight - latest_k
    loss_pct_k = 100 * loss_k / kevin_start_weight

    st.metric("Starting Weight", f"{kevin_start_weight:.1f} kg")
    st.metric("Latest Weight", f"{latest_k:.1f} kg")
    st.metric("Total Loss", f"{loss_k:.1f} kg ({loss_pct_k:.1f}%)")

# Simon's stats
if simon_available:
    with col2:
        st.subheader("Simon's Stats")
        latest_s = df_simon.dropna(subset=["weight"]).iloc[-1]["weight"]
        loss_s = simon_start_weight - latest_s
        loss_pct_s = 100 * loss_s / simon_start_weight

        st.metric("Starting Weight", f"{simon_start_weight:.1f} kg")
        st.metric("Latest Weight", f"{latest_s:.1f} kg")
        st.metric("Total Loss", f"{loss_s:.1f} kg ({loss_pct_s:.1f}%)")

#streamlit run dashboard.py