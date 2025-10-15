import streamlit as st
import streamlit.components.v1 as components
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
import urllib.parse

query_params = st.experimental_get_query_params()
if "refresh" in query_params:
    st.cache_data.clear()


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

@st.cache_data(ttl=1800)  # cache for 1/2 hour
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

if refresh_flag:
    st.cache_data.clear()   # invalidate cache when ?refresh=1 is called

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

# --- Detect Mobile Device and Adjust Default Range ---
import streamlit.components.v1 as components

if "device_checked" not in st.session_state:
    components.html(
        """
        <script>
        const isMobile = window.innerWidth < 768;
        const range = isMobile ? "Last 30 Days" : "Competition Timeline";
        window.parent.postMessage({type: 'SET_RANGE', value: range}, '*');
        </script>
        """,
        height=0,
    )
    st.session_state["device_checked"] = True

# Set a safe default for initial load (no internal API usage)
if "time_range" not in st.session_state:
    st.session_state["time_range"] = "Last 30 Days"

# --- UI State Defaults (for controls rendered later) ---
if "show_trendlines" not in st.session_state:
    st.session_state["show_trendlines"] = True
if "trend_type" not in st.session_state:
    st.session_state["trend_type"] = "Smooth (LOWESS)"

# Use session state values throughout the script
time_range = st.session_state["time_range"]
show_trendlines = st.session_state["show_trendlines"]
trend_type = st.session_state["trend_type"]


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
    mode="lines+markers", name="Kevin", yaxis="y1", connectgaps=True, showlegend=True
))

fig.add_trace(go.Scatter(
    x=goal_dates_kevin, y=kevin_goal_weights,
    mode="lines", name="Goal Trendline",
    line=dict(dash="dot", color="gray"),
    yaxis="y1",
    showlegend=False
))


if simon_available:
    fig.add_trace(go.Scatter(
        x=df_simon["date"], y=df_simon["weight"],
        mode="lines+markers", name="Simon", yaxis="y2", line=dict(color="green"), connectgaps=True, showlegend=True
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
        yaxis="y1",
        showlegend=False
    ))

# Add Simon linear trendline
if show_trendlines and simon_available and len(simon_trend_x) > 0:
    fig.add_trace(go.Scatter(
        x=simon_trend_x, y=simon_trend_y,
        mode="lines",
        line=dict(dash="dot", color="green"),
        name="Simon Linear Trend",
        yaxis="y2",
        showlegend=False
    ))

# --- Utility: Aligned Axis Ranges ---
def aligned_ranges_from_goals(x1, x2, goal1_x, goal1_y, goal2_x, goal2_y, df_kevin, df_simon):
    """
    Compute y-axis ranges so Kevin’s and Simon’s goal lines align perfectly
    between x1 and x2, with proportional scaling and margin.
    """
    # Validate inputs
    if len(goal1_x) == 0 or len(goal2_x) == 0:
        print("⚠️ Empty goal arrays — cannot compute alignment.")
        return None, None

    # Ensure timestamps
    x1, x2 = pd.Timestamp(x1), pd.Timestamp(x2)

    # Convert goal x-values safely to ordinal form (skip NaT)
    goal1_ord = np.array([pd.Timestamp(xx).toordinal() for xx in goal1_x if not pd.isna(xx)])
    goal2_ord = np.array([pd.Timestamp(xx).toordinal() for xx in goal2_x if not pd.isna(xx)])

    # Interpolate goal weights at window edges
    y1_start, y1_end = np.interp([x1.toordinal(), x2.toordinal()], goal1_ord, goal1_y)
    y2_start, y2_end = np.interp([x1.toordinal(), x2.toordinal()], goal2_ord, goal2_y)

    # Compute spans (weight differences over the range)
    span1 = y1_end - y1_start
    span2 = y2_end - y2_start
    if abs(span2) < 1e-9:
        span2 = 1e-9  # avoid div-by-zero

    # Scale factor to align Simon’s line visually to Kevin’s
    scale = span1 / span2

    # Align Simon’s goal line so that start and end visually match Kevin’s
    y1_range = y1_start - y1_end
    y2_range = y2_start - y2_end

    # Determine max visible weight for Kevin in selected range
    mask = (df_kevin["date"] >= x1) & (df_kevin["date"] <= x2)
    if not df_kevin.loc[mask].empty:
        max_value = df_kevin.loc[mask, "weight"].max()
    else:
        max_value = max(y1_start, y1_end)

    mask = (df_kevin["date"] >= x1) & (df_kevin["date"] <= x2)
    if not df_kevin.loc[mask].empty:
        min_value = df_kevin.loc[mask, "weight"].min()
        min_value = min(min_value, y1_end)
    else:
        min_value = min(y1_start, y1_end)

    margin1 = max_value - y1_start + 0.2
    margin2 = y1_end - min_value + 0.2

    # Apply proportional margins
    y1_margin1 = margin1
    y1_margin2 = margin2
    y1_min = y1_end - y1_margin2
    y1_max = y1_start + y1_margin1

    y2_margin1 = y2_range/y1_range * y1_margin1
    y2_margin2 = y2_range/y1_range * y1_margin2
    y2_min = y2_end - y2_margin2
    y2_max = y2_start + y2_margin1

    # # Debug output in Streamlit
    # st.write(f"🧭 **Debug Info:** {x1.date()}–{x2.date()}")
    # st.write(f"Kevin goals: {y1_start:.2f} → {y1_end:.2f}")
    # st.write(f"Simon goals: {y2_start:.2f} → {y2_end:.2f}")
    # st.write(f"Computed aligned y1: [{y1_min:.2f}, {y1_max:.2f}], y2: [{y2_min:.2f}, {y2_max:.2f}]")
    # st.write("---")

    return [y1_min, y1_max], [y2_min, y2_max]

import numpy as np  # ensure np is imported for proportional zoom

# --- X-axis range ---
min_date = (
    min(df_kevin["date"].min(), df_simon["date"].min())
    if simon_available and not df_simon.empty
    else df_kevin["date"].min()
)

today = pd.Timestamp.today()



if time_range == "Last 14 Days":
    x_min = (today - pd.Timedelta(days=14)).normalize()
    x_max = (today + pd.Timedelta(days=7)).normalize()
elif time_range == "Last 30 Days":
    x_min = (today - pd.Timedelta(days=30)).normalize()
    x_max = (today + pd.Timedelta(days=10)).normalize()
else:  # "Competition Timeline"
    x_min = goal_start_date
    x_max = goal_end_date

x1 = x_min
x2 = x_max
# Recompute aligned y-ranges for the selected window using GOAL lines (not trendlines)
y1_range, y2_range = aligned_ranges_from_goals(
    x1, x2, goal_dates_kevin, kevin_goal_weights, goal_dates_simon, simon_goal_weights, df_kevin, df_simon
)
x_range = [x_min, x_max]



# --- Layout ---
fig.update_layout(
    showlegend=False,
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
        type="date"
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



st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# --- Controls & Legend BELOW chart ---
st.markdown("### Display Options")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    time_range = st.radio(
        "Time Range",
        options=["Last 14 Days", "Last 30 Days", "Competition Timeline"],
        index=2,
        horizontal=True,
        key="time_range"
    )

with col3:
    show_trendlines = st.checkbox("Show Trendlines", value=True, key="show_trendlines")
    if show_trendlines:
        trend_type = st.radio(
            "Trendline Type",
            options=["Linear", "Smooth (LOWESS)"],
            index=1,
            horizontal=False,
            key="trend_type"
        )
    else:
        trend_type = None

st.markdown("---")

# --- Legend below controls ---
st.markdown("### Legend")
st.markdown("""
| Symbol | Description |
|:--|:--|
| 🟦 | **Kevin** |
| 🟩 | **Simon** |
""")

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
