import json
import pandas as pd
import streamlit as st
import plotly.express as px
import datetime

# Load JSON data
with open("Kevin_Data.json") as f:
    data = json.load(f)

# Convert to DataFrame
df = pd.DataFrame(data)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values("date")

# App layout
st.set_page_config(page_title="Kevin's Body Tracker", layout="wide")
st.title("Kevin's Body Composition Tracker")

# Select metric
metric = st.radio("Choose metric", ["weight", "bodyFat"])

# Plot
fig = px.line(df, x="date", y=metric, markers=True, title=f"{metric.capitalize()} Over Time")
st.plotly_chart(fig, use_container_width=True)

# Latest values
latest = df.dropna(subset=["weight"]).iloc[-1]
st.metric("Latest Weight", f"{latest['weight']} kg")
st.metric("Latest Body Fat", f"{latest['bodyFat']} %")

# Determine final x-axis limit
x_range_end = datetime.datetime(2025, 12, 25)

# Update x-axis range
fig.update_layout(
    xaxis=dict(range=[df["date"].min(), x_range_end])
)