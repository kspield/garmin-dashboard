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

# Metric selection – must come first!
metric = st.radio("Choose metric", ["weight", "bodyFat"])

# Create figure
fig = go.Figure()

# Plot Kevin's data
fig.add_trace(go.Scatter(
    x=df_kevin["date"],
    y=df_kevin[metric],
    mode="lines+markers",
    name="Kevin",
    yaxis="y1"
))

# === Goal Line Setup ===
goal_start_date = datetime.datetime(2025, 7, 20)
goal_end_date = datetime.datetime(2025, 12, 25)
goal_dates = pd.date_range(start=goal_start_date, end=goal_end_date, freq="D")
months = ((goal_dates - goal_start_date) / pd.Timedelta(days=30.437)).astype(float)

if metric == "weight":
    kevin_start_weight = 79
    simon_start_weight = 100

    kevin_goal_weights = kevin_start_weight * (1 - 0.015 * months)
    simon_goal_weights = simon_start_weight * (1 - 0.015 * months)

    # Kevin's goal trendline
    fig.add_trace(go.Scatter(
        x=goal_dates,
        y=kevin_goal_weights,
        mode="lines",
        name="Goal Trendline",
        line=dict(dash="dot", color="gray"),
        yaxis="y1",
        showlegend=True
    ))

    # Simon's actual weight
    if simon_available:
        fig.add_trace(go.Scatter(
            x=df_simon["date"],
            y=df_simon["weight"],
            mode="lines+markers",
            name="Simon",
            yaxis="y2",
            line=dict(color="green")
        ))

        # Simon's goal trendline (hidden from legend)
        fig.add_trace(go.Scatter(
            x=goal_dates,
            y=simon_goal_weights,
            mode="lines",
            name=None,
            line=dict(dash="dot", color="gray"),
            yaxis="y2",
            showlegend=False
        ))

else:
    # Plot Simon's bodyFat on same axis
    if simon_available:
        fig.add_trace(go.Scatter(
            x=df_simon["date"],
            y=df_simon["bodyFat"],
            mode="lines+markers",
            name="Simon",
            line=dict(color="green"),
            yaxis="y1"
        ))

# Finalize layout
fig.update_layout(
    title=f"{metric.capitalize()} Over Time",
    xaxis=dict(
        title="Date",
        range=[df_kevin["date"].min(), goal_end_date]
    ),
    yaxis=dict(
        title="Kevin",
        side="left"
    ),
    yaxis2=dict(
        title="Simon",
        overlaying="y",
        side="right",
        showgrid=False
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

st.plotly_chart(fig, use_container_width=True)

# Split page below the chart
col1, col2 = st.columns(2)

# Kevin's stats (left)
with col1:
    st.subheader("Kevin's Stats")
    start_k = 79
    latest_k = df_kevin.dropna(subset=["weight"]).iloc[-1]["weight"]
    loss_k = start_k - latest_k
    loss_pct_k = 100 * loss_k / start_k

    st.metric("Starting Weight", f"{start_k:.1f} kg")
    st.metric("Latest Weight", f"{latest_k:.1f} kg")
    st.metric("Total Loss", f"{loss_k:.1f} kg ({loss_pct_k:.1f}%)")

# Simon's stats (right)
if simon_available:
    with col2:
        st.subheader("Simon's Stats")
        start_s = 100
        latest_s = df_simon.dropna(subset=["weight"]).iloc[-1]["weight"]
        loss_s = start_s - latest_s
        loss_pct_s = 100 * loss_s / start_s

        st.metric("Starting Weight", f"{start_s:.1f} kg")
        st.metric("Latest Weight", f"{latest_s:.1f} kg")
        st.metric("Total Loss", f"{loss_s:.1f} kg ({loss_pct_s:.1f}%)")

#streamlit run dashboard.py