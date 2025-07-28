import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# --- Firebase Setup ---
if not firebase_admin._apps:
    cred = credentials.Certificate({k: v.replace("\\n", "\n") if k == "private_key" else v for k, v in st.secrets["firebase"].items()})
    firebase_admin.initialize_app(cred)
db = firestore.client()

# --- Load Data from Firestore ---
def load_data(user: str) -> pd.DataFrame:
    docs = db.collection("users").document(user).collection("weight_data").stream()
    records = []
    for doc in docs:
        entry = doc.to_dict()
        if "date" in entry:
            records.append(entry)

    df = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.groupby("date").agg({
            "weight": "mean",
            "bodyFat": "mean"
        }).reset_index().sort_values("date")
    return df

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

# --- Constants ---
kevin_start_weight = 79
goal_start_date = datetime.datetime(2025, 7, 24)
goal_end_date = datetime.datetime(2025, 12, 25)
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

# --- Plot ---
fig = go.Figure()

fig.add_trace(go.Scatter(
    x=df_kevin["date"], y=df_kevin["weight"],
    mode="lines+markers", name="Kevin", yaxis="y1", connectgaps=True
))

fig.add_trace(go.Scatter(
    x=goal_dates_kevin, y=kevin_goal_weights,
    mode="lines", name="Kevin Goal", line=dict(dash="dot", color="gray"), yaxis="y1"
))

if simon_available:
    fig.add_trace(go.Scatter(
        x=df_simon["date"], y=df_simon["weight"],
        mode="lines+markers", name="Simon", yaxis="y2", line=dict(color="green"), connectgaps=True
    ))
    fig.add_trace(go.Scatter(
        x=goal_dates_simon, y=simon_goal_weights,
        mode="lines", name="Simon Goal", line=dict(dash="dot", color="gray"), yaxis="y2"
    ))

# --- Utility: Aligned Axis Ranges ---
def aligned_ranges(goal1, data1, goal2, data2, margin_ratio=0.05):
    # Y1 range: Kevin
    all1 = pd.concat([data1, pd.Series(goal1)])
    min1, max1 = all1.min(), all1.max()
    margin1 = (max1 - min1) * margin_ratio
    y1_min, y1_max = min1 - margin1, max1 + margin1

    # Position of Kevin's goal line in y1 range
    goal1_value = goal1[-1]
    norm_goal_y1 = (goal1_value - y1_min) / (y1_max - y1_min)

    # Y2 range: Simon
    all2 = pd.concat([data2, pd.Series(goal2)])
    goal2_value = goal2[-1]
    range2_span = all2.max() - all2.min()
    margin2 = range2_span * margin_ratio

    # Now shift y2 range so that Simon's goal appears at the same relative height
    y2_total_range = (all2.max() - all2.min()) + 2 * margin2
    y2_min = goal2_value - norm_goal_y1 * y2_total_range
    y2_max = goal2_value + (1 - norm_goal_y1) * y2_total_range

    return [y1_min, y1_max], [y2_min, y2_max]

y1_range, y2_range = aligned_ranges(
    kevin_goal_weights, df_kevin["weight"],
    simon_goal_weights, df_simon["weight"] if simon_available else pd.Series()
)

# --- X-axis range ---
min_date = min(
    df_kevin["date"].min(),
    df_simon["date"].min() if simon_available and not df_simon.empty else goal_start_date
)

# --- Layout ---
fig.update_layout(
    yaxis=dict(
        title="Kevin",
        side="left",
        range=y1_range,
        showgrid=True,
        tickformat=".1f"
    ),
    yaxis2=dict(
        title="Simon",
        overlaying="y",
        side="right",
        range=y2_range,
        showgrid=False,
        tickformat=".1f",
        anchor="x",
        matches=None  # ensure independence
    ),
    xaxis=dict(
        title="Date",
        range=[min_date, goal_end_date]
    ),
    legend=dict(
        x=0.99, y=0.01, xanchor="right", yanchor="bottom",
        bgcolor="rgba(255,255,255,0.7)", bordercolor="black", borderwidth=1
    )
)
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
st.subheader("Manual Weight Entry for Simon")

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
    latest_k = df_kevin.dropna(subset=["weight"]).iloc[-1]["weight"]
    loss_k = kevin_start_weight - latest_k
    loss_pct_k = 100 * loss_k / kevin_start_weight
    st.metric("Starting Weight", f"{kevin_start_weight:.1f} kg")
    st.metric("Latest Weight", f"{latest_k:.1f} kg")
    st.metric("Total Loss", f"{loss_k:.1f} kg ({loss_pct_k:.1f}%)")

if simon_available and simon_start_weight is not None:
    with col2:
        st.subheader("Simon's Stats")
        latest_s = df_simon.dropna(subset=["weight"]).iloc[-1]["weight"]
        loss_s = simon_start_weight - latest_s
        loss_pct_s = 100 * loss_s / simon_start_weight
        st.metric("Starting Weight", f"{simon_start_weight:.1f} kg")
        st.metric("Latest Weight", f"{latest_s:.1f} kg")
        st.metric("Total Loss", f"{loss_s:.1f} kg ({loss_pct_s:.1f}%)")

if simon_available and simon_start_weight is None:
    st.warning("Simon's starting weight could not be determined. No data near the goal start date.")

st.markdown('</div>', unsafe_allow_html=True)

