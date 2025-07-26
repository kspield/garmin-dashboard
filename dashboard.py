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

# Start weights (fixed)
kevin_start_weight = 78
simon_start_weight = 100
goal_end_date = datetime.datetime(2025, 12, 25)

kevin_range_padding = 3  # in kg

# Individual start dates
kevin_start_date = df_kevin["date"].min()
goal_dates_kevin = pd.date_range(start=kevin_start_date, end=goal_end_date, freq="D")
months_kevin = ((goal_dates_kevin - kevin_start_date) / pd.Timedelta(days=30.437)).astype(float)
kevin_goal_weights = kevin_start_weight * (1 - 0.015 * months_kevin)
kevin_goal_weight = kevin_goal_weights[-1]

if simon_available:
    simon_start_date = df_simon["date"].min()
    goal_dates_simon = pd.date_range(start=simon_start_date, end=goal_end_date, freq="D")
    months_simon = ((goal_dates_simon - simon_start_date) / pd.Timedelta(days=30.437)).astype(float)
    simon_goal_weights = simon_start_weight * (1 - 0.015 * months_simon)
    simon_goal_weight = simon_goal_weights[-1]

# Create figure
fig = go.Figure()

# Kevin trace
fig.add_trace(go.Scatter(
    x=df_kevin["date"],
    y=df_kevin["weight"],
    mode="lines+markers",
    name="Kevin",
    yaxis="y1"
))

fig.add_trace(go.Scatter(
    x=goal_dates_kevin,
    y=kevin_goal_weights,
    mode="lines",
    name="Goal Trendline",
    line=dict(dash="dot", color="gray"),
    yaxis="y1"
))

# Simon trace
if simon_available:
    fig.add_trace(go.Scatter(
        x=df_simon["date"],
        y=df_simon["weight"],
        mode="lines+markers",
        name="Simon",
        yaxis="y2",
        line=dict(color="green")
    ))

    fig.add_trace(go.Scatter(
        x=goal_dates_simon,
        y=simon_goal_weights,
        mode="lines",
        name=None,
        showlegend=False,
        line=dict(dash="dot", color="gray"),
        yaxis="y2"
    ))

# Layout with synchronized relative ranges

fig.update_layout(
    yaxis=dict(
        title="Kevin",
        side="left",
        range=[
            kevin_goal_weight - kevin_range_padding,
            kevin_start_weight + kevin_range_padding,
        ]
    ),
    yaxis2=dict(
        title="Simon",
        overlaying="y",
        side="right",
        showgrid=False,
        range=[
            simon_goal_weight - kevin_range_padding * (simon_start_weight / kevin_start_weight),
            simon_start_weight + kevin_range_padding * (simon_start_weight / kevin_start_weight),
        ]
    ),
    legend=dict(
        x=0.99,
        y=0.01,
        xanchor="right",
        yanchor="bottom",
        bgcolor="rgba(255,255,255,0.7)",
        bordercolor="black",
        borderwidth=1
    ),
    xaxis=dict(
        title="Date",
        range=[min(kevin_start_date, simon_start_date if simon_available else kevin_start_date), goal_end_date]
    )
)

st.plotly_chart(fig, use_container_width=True)

# Stats columns
col1, col2 = st.columns(2)

with col1:
    st.subheader("Kevin's Stats")
    latest_k = df_kevin.dropna(subset=["weight"]).iloc[-1]["weight"]
    loss_k = kevin_start_weight - latest_k
    loss_pct_k = 100 * loss_k / kevin_start_weight
    st.metric("Starting Weight", f"{kevin_start_weight:.1f} kg")
    st.metric("Latest Weight", f"{latest_k:.1f} kg")
    st.metric("Total Loss", f"{loss_k:.1f} kg ({loss_pct_k:.1f}%)")

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