import streamlit as st
import pandas as pd
import numpy as np
import os
import plotly.graph_objects as go
import datetime
import firebase_admin
from google.cloud import firestore
from google.api_core.exceptions import GoogleAPIError
from firebase_admin import credentials, firestore
from scipy.stats import linregress
from statsmodels.nonparametric.smoothers_lowess import lowess


# Firebase init
if not firebase_admin._apps:
    print("☁️ Running in Streamlit Cloud. Loading st.secrets['firebase']")
    try:
        firebase_secret = st.secrets["firebase"]
        cred_dict = {k: v.replace("\\n", "\n") if k == "private_key" else v for k, v in firebase_secret.items()}
        cred = credentials.Certificate(cred_dict)
    except Exception as e:
        st.error(f"❌ Failed to load secrets: {e}")
        raise

    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- Load Data from Firestore ---

def load_data(user):
    try:
        docs = db.collection("users").document(user).collection("weight_data").stream()
        records = [doc.to_dict() for doc in docs]
        df = pd.DataFrame(records)

        if not df.empty and "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.groupby("date").agg({
                "weight": "mean",
                "bodyFat": "mean"
            }).reset_index().sort_values("date")

        #st.success(f"✅ Loaded {len(df)} entries for '{user}'.")
        return df

    except GoogleAPIError as e:
        st.error(f"❌ Firestore error for '{user}': {e}")
        return pd.DataFrame()

    except Exception as e:
        st.error(f"❌ Unexpected error for '{user}': {e}")
        return pd.DataFrame()

# Load user data
df_kevin = load_data("kevin")

# Load Simon's data and average it per day
df_simon_raw = load_data("simon")
simon_available = not df_simon_raw.empty

if simon_available:
    df_simon = (
        df_simon_raw.groupby("date", as_index=False)
        .agg({"weight": "mean", "bodyFat": "mean"})
        .sort_values("date")
    )
else:
    df_simon = pd.DataFrame()

# --- UI Layout ---
st.set_page_config(page_title="Fat Boy Slim Competition", layout="wide")
st.title("Fat Boy Slim Competition")

# --- Date Filter Selection ---
time_range = st.radio(
    "Select Time Range:",
    options=["Last 14 Days", "Last 30 Days", "Competition Timeline"],
    index=2,
    horizontal=True
)

# --- Constants ---
kevin_start_weight = 78
goal_start_date = datetime.datetime(2025, 7, 24)
goal_end_date = datetime.datetime(2025, 12, 25)

# Convert to pandas.Timestamp and normalize
goal_start_date = pd.to_datetime(goal_start_date).normalize()
goal_end_date = pd.to_datetime(goal_end_date).normalize()
kevin_range_padding = 1

# Default fallback if no data is available
simon_start_weight = None

if not df_simon.empty:
    # Find the entry closest to the defined start date
    df_simon["days_diff"] = (df_simon["date"] - goal_start_date).abs()
    closest_row = df_simon.loc[df_simon["days_diff"].idxmin()]
    simon_start_weight = closest_row["weight"]

# --- Goal Computation ---
def compute_goal_weights(start_weight, start_date):
    goal_dates = pd.date_range(start=start_date, end=goal_end_date, freq="D")
    months = ((goal_dates - start_date) / pd.Timedelta(days=30.437)).astype(float)
    goal_weights = start_weight * (1 - 0.015 * months)
    return goal_dates, goal_weights

kevin_start_date = goal_start_date
goal_dates_kevin, kevin_goal_weights = compute_goal_weights(kevin_start_weight, kevin_start_date)
kevin_goal_weight = kevin_goal_weights[-1]

if simon_available and simon_start_weight is not None:
    simon_start_date = goal_start_date
    goal_dates_simon, simon_goal_weights = compute_goal_weights(simon_start_weight, simon_start_date)
    simon_goal_weight = simon_goal_weights[-1]

try:
    if simon_goal_weights is not None and len(simon_goal_weights) > 0:
        simon_goals = simon_goal_weights
    else:
        simon_goals = None
except NameError:
    simon_goals = None


# --- Filter to competition timeline for Trendline---
df_kevin_comp = df_kevin[(df_kevin["date"] >= goal_start_date) & (df_kevin["date"] <= goal_end_date)]
df_simon_comp = df_simon[(df_simon["date"] >= goal_start_date) & (df_simon["date"] <= goal_end_date)] if simon_available else pd.DataFrame()

show_trendlines = st.checkbox("Show Trendlines", value=True)

if show_trendlines:
    trend_type = st.radio(
        "Trendline Type:",
        options=["Linear", "Smooth (LOWESS)"],
        index=1,
        horizontal=True
    )
else:
    trend_type = None

# --- Compute Linear Trendline for Kevin ---
def compute_trendline(df, goal_end_date, trend_type="Smooth (LOWESS)"):
    if df.empty:
        return [], []

    x = df["date"].map(datetime.datetime.toordinal).to_numpy()
    y = df["weight"].to_numpy()

    mask = (
        ~np.isnan(x) & ~np.isnan(y) &
        np.isfinite(x) & np.isfinite(y)
    )
    x = x[mask]
    y = y[mask]

    if len(x) < 3:
        return [], []

    try:
        if trend_type == "Linear":
            coeffs = np.polyfit(x, y, deg=1)
            m, b = coeffs
            end_x = goal_end_date.toordinal()
            trend_x = np.array([x[0], end_x])
            trend_y = m * trend_x + b
            trend_x_dates = [datetime.date.fromordinal(int(d)) for d in trend_x]
            return trend_x_dates, trend_y
        else:
            # LOWESS smoothing
            smoothed = lowess(y, x, frac=0.3, it=0)
            last_x, last_y = smoothed[-2:, 0], smoothed[-2:, 1]
            local_slope = (last_y[1] - last_y[0]) / (last_x[1] - last_x[0])
            end_x = goal_end_date.toordinal()
            extend_x = np.linspace(smoothed[-1, 0], end_x, 30)
            extend_y = smoothed[-1, 1] + local_slope * (extend_x - smoothed[-1, 0])
            full_x = np.concatenate([smoothed[:, 0], extend_x])
            full_y = np.concatenate([smoothed[:, 1], extend_y])
            trend_x = [datetime.date.fromordinal(int(xx)) for xx in full_x]
            trend_y = full_y
            return trend_x, trend_y
    except Exception as e:
        print(f"⚠️ Trendline error: {e}")
        return [], []

kevin_trend_x, kevin_trend_y = compute_trendline(df_kevin_comp, goal_end_date, trend_type)
simon_trend_x, simon_trend_y = compute_trendline(df_simon_comp, goal_end_date, trend_type)

# --- Plot ---
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df_kevin["date"], y=df_kevin["weight"],
    mode="lines+markers", name="Kevin", yaxis="y1", connectgaps=True
))

fig.add_trace(go.Scatter(
    x=goal_dates_kevin, y=kevin_goal_weights,
    mode="lines", name="Goal Trendline",
    line=dict(dash="dot", color="gray"),
    yaxis="y1",
    showlegend=True
))


if simon_available:
    fig.add_trace(go.Scatter(
        x=df_simon["date"], y=df_simon["weight"],
        mode="lines+markers", name="Simon", yaxis="y2", line=dict(color="green"), connectgaps=True
    ))

    # Simon goal trendline — do NOT include in legend
    fig.add_trace(go.Scatter(
        x=goal_dates_simon, y=simon_goals,
        mode="lines",
        line=dict(dash="dot", color="gray"),
        yaxis="y2",
        showlegend=False  # hide from legend
    ))

# Add Kevin linear trendline
if show_trendlines and len(kevin_trend_x) > 0:
    fig.add_trace(go.Scatter(
        x=kevin_trend_x, y=kevin_trend_y,
        mode="lines",
        line=dict(dash="dot", color="blue"),
        name="Kevin Linear Trend",
        yaxis="y1"
    ))

# Add Simon linear trendline
if show_trendlines and simon_available and len(simon_trend_x) > 0:
    fig.add_trace(go.Scatter(
        x=simon_trend_x, y=simon_trend_y,
        mode="lines",
        line=dict(dash="dot", color="green"),
        name="Simon Linear Trend",
        yaxis="y2"
    ))

# --- Utility: Aligned Axis Ranges ---
def aligned_ranges(goal1, data1, goal2, data2, margin_ratio=0.05):
    # Kevin's Y-axis
    all1 = pd.concat([data1, pd.Series(goal1)])
    min1, max1 = all1.min(), all1.max()
    margin1 = (max1 - min1) * margin_ratio
    y1_min = min1 - margin1
    y1_max = max1 + margin1

    # Return only y1 range if Simon data is missing
    if goal2 is None or len(goal2) == 0 or data2 is None or data2.empty:
        return [y1_min, y1_max], None

    # Kevin's normalized positions
    k_start, k_end = goal1[0], goal1[-1]
    norm_start = (k_start - y1_min) / (y1_max - y1_min)
    norm_end   = (k_end - y1_min) / (y1_max - y1_min)

    # Simon's goal line values
    s_start, s_end = goal2[0], goal2[-1]

    # Solve system of equations:
    # (s_start - y2_min) / (y2_max - y2_min) = norm_start
    # (s_end - y2_min) / (y2_max - y2_min) = norm_end

    if norm_start == norm_end:
        # Avoid division by zero in edge cases (e.g., flat goal line)
        y2_min = min(s_start, s_end) - 1
        y2_max = max(s_start, s_end) + 1
    else:
        y2_min = (s_end * norm_start - s_start * norm_end) / (norm_start - norm_end)
        y2_max = y2_min + (s_start - y2_min) / norm_start

    return [y1_min, y1_max], [y2_min, y2_max]

y1_range, y2_range = aligned_ranges(
    kevin_goal_weights, df_kevin["weight"],
    simon_goals if simon_goals is not None and len(simon_goals) > 0 else None,
    df_simon["weight"] if simon_available and not df_simon.empty else None
)

# --- X-axis range ---
min_date = (
    min(df_kevin["date"].min(), df_simon["date"].min())
    if simon_available and not df_simon.empty
    else df_kevin["date"].min()
)

today = pd.Timestamp.today()

if time_range == "Last 14 Days":
    x_min = today - pd.Timedelta(days=14)
    x_max = today
elif time_range == "Last 30 Days":
    x_min = today - pd.Timedelta(days=30)
    x_max = today
else:  # "Competition Timeline"
    x_min = goal_start_date
    x_max = goal_end_date

x_range = [pd.to_datetime(x_min).normalize(), pd.to_datetime(x_max).normalize()]

# --- Layout ---
fig.update_layout(
    height=500,
    yaxis=dict(
        title="Kevin",
        side="left",
        range=y1_range,
        showgrid=True,
        tickformat=".1f"
    ),
    xaxis=dict(
        title="Date",
        range=x_range,  # Keep manual range logic
        rangeslider=dict(visible=True),
        rangeselector=dict(
            buttons=list([
                dict(count=14, label="14d", step="day", stepmode="backward"),
                dict(count=30, label="30d", step="day", stepmode="backward"),
                dict(step="all", label="All")
            ])
        ),
        type="date"
    ),
    legend=dict(
        x=0.99, y=0.01, xanchor="right", yanchor="bottom",
        bgcolor="rgba(255,255,255,0.7)", bordercolor="black", borderwidth=1
    )
)

if y2_range is not None:
    fig.update_layout(
        yaxis2=dict(
            title="Simon",
            overlaying="y",
            side="right",
            range=y2_range,
            showgrid=False,
            tickformat=".1f",
            anchor="x",
            matches=None
        )
    )

# fig.update_yaxes(autorange=True)

st.plotly_chart(fig, use_container_width=True)

# --- Show message if Simon's data is missing or invalid ---
if simon_available and simon_start_weight is None:
    st.markdown(
        "<div style='color: red; font-size: 16px; margin-top: 20px;'>"
        "⚠️ No suitable starting weight found for Simon near the defined start date. "
        "Simon’s trendline and statistics may be unavailable until data is entered."
        "</div>",
        unsafe_allow_html=True
    )
elif not simon_available:
    st.markdown(
        "<div style='color: orange; font-size: 16px; margin-top: 20px;'>"
        "ℹ️ No data available for Simon yet. Please enter weight data to begin tracking."
        "</div>",
        unsafe_allow_html=True
    )


# --- Simon Manual Entry Section ---
with st.expander("➕ Add Manual Weight Entry for Simon"):
    with st.form("simon_data_entry"):
        weight = st.number_input("Weight (kg)", value=100.0, min_value=30.0, max_value=200.0, step=0.01, format="%.2f")
        body_fat = st.number_input("Body Fat (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
        date = st.date_input("Date of Measurement", value=datetime.date.today())

        submitted = st.form_submit_button("Submit Data")

        if submitted:
            try:
                date_str = date.isoformat()  # e.g., "2025-07-28"
                body_fat_cleaned = None if body_fat == 0.0 else round(body_fat, 1)
                weight_cleaned = round(weight, 2)

                # Get current UTC timestamp
                timestamp = datetime.datetime.utcnow().isoformat()

                # Query existing entries for that day
                collection_ref = db.collection("users").document("simon").collection("weight_data")
                existing_docs = collection_ref.where("date", "==", date_str).stream()
                count = sum(1 for _ in existing_docs)

                # Create doc ID like "2025-07-28_1", "2025-07-28_2", ...
                doc_id = f"{date_str}_{count + 1}"

                doc_ref = collection_ref.document(doc_id)
                doc_ref.set({
                    "date": date_str,
                    "weight": weight_cleaned,
                    "bodyFat": body_fat_cleaned,
                    "entryTime": timestamp
                })

                st.success(f"✅ Entry saved for {date_str} as #{count + 1}")

                if hasattr(st, "experimental_rerun"):
                    st.experimental_rerun()

            except Exception as e:
                st.error(f"❌ Failed to save data: {e}")

# --- Stats Section ---
st.markdown('<div class="stats-container">', unsafe_allow_html=True)
# --- Custom Style for Smaller Font ---
st.markdown("""
    <style>
    .small-font .stMetric {
        font-size: 16px !important;
    }
    .small-font .stMetricLabel {
        font-size: 13px !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- Stats Section with Streamlit Columns ---
st.markdown('<div class="small-font">', unsafe_allow_html=True)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Kevin's Stats")
    latest_k = df_kevin.dropna(subset=["weight"])["weight"].iloc[-1]
    loss_k = kevin_start_weight - latest_k
    loss_pct_k = 100 * loss_k / kevin_start_weight
    st.metric("Starting Weight", f"{kevin_start_weight:.1f} kg")
    st.metric("Latest Weight", f"{latest_k:.1f} kg")
    st.metric("Total Loss", f"{loss_k:.1f} kg ({loss_pct_k:.1f}%)")
    st.metric("Goal Weight", f"{kevin_goal_weight:.1f} kg")  # ✅ Added

if simon_available and simon_start_weight is not None:
    with col2:
        st.subheader("Simon's Stats")
        latest_s = df_simon.dropna(subset=["weight"])["weight"].iloc[-1]
        loss_s = simon_start_weight - latest_s
        loss_pct_s = 100 * loss_s / simon_start_weight
        st.metric("Starting Weight", f"{simon_start_weight:.1f} kg")
        st.metric("Latest Weight", f"{latest_s:.1f} kg")
        st.metric("Total Loss", f"{loss_s:.1f} kg ({loss_pct_s:.1f}%)")
        st.metric("Goal Weight", f"{simon_goal_weight:.1f} kg")  # ✅ Added

if simon_available and simon_start_weight is None:
    st.warning("Simon's starting weight could not be determined. No data near the goal start date.")

st.markdown('</div>', unsafe_allow_html=True)