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
        entry["date"] = doc.id  # doc ID is the date string
        records.append(entry)

    df = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df

# Load user data
df_kevin = load_data("kevin")
df_simon = load_data("simon")
simon_available = not df_simon.empty

# --- UI Layout ---
st.set_page_config(page_title="Fat Boy Slim Competition", layout="wide")
st.title("Fat Boy Slim Competition")

# --- Constants ---
kevin_start_weight, simon_start_weight = 79, 100
goal_end_date = datetime.datetime(2025, 12, 25)
goal_start_date = datetime.datetime(2025, 7, 25)
kevin_range_padding = 3

# --- Goal Computation ---
def compute_goal_weights(start_weight, start_date):
    goal_dates = pd.date_range(start=start_date, end=goal_end_date, freq="D")
    months = ((goal_dates - start_date) / pd.Timedelta(days=30.437)).astype(float)
    goal_weights = start_weight * (1 - 0.015 * months)
    return goal_dates, goal_weights

kevin_start_date = goal_start_date
goal_dates_kevin, kevin_goal_weights = compute_goal_weights(kevin_start_weight, kevin_start_date)
kevin_goal_weight = kevin_goal_weights[-1]

if simon_available:
    simon_start_date = goal_start_date
    goal_dates_simon, simon_goal_weights = compute_goal_weights(simon_start_weight, simon_start_date)
    simon_goal_weight = simon_goal_weights[-1]

# --- Plot ---
fig = go.Figure()

fig.add_trace(go.Scatter(x=df_kevin["date"], y=df_kevin["weight"],
                         mode="lines+markers", name="Kevin", yaxis="y1"))
fig.add_trace(go.Scatter(x=goal_dates_kevin, y=kevin_goal_weights,
                         mode="lines", name="Goal Trendline", line=dict(dash="dot", color="gray"), yaxis="y1"))

if simon_available:
    fig.add_trace(go.Scatter(x=df_simon["date"], y=df_simon["weight"],
                             mode="lines+markers", name="Simon", yaxis="y2", line=dict(color="green")))
    fig.add_trace(go.Scatter(x=goal_dates_simon, y=simon_goal_weights,
                             mode="lines", showlegend=False, line=dict(dash="dot", color="gray"), yaxis="y2"))

# --- Axis and Layout ---
fig.update_layout(
    yaxis=dict(title="Kevin", side="left", range=[
        kevin_goal_weight - kevin_range_padding,
        kevin_start_weight + kevin_range_padding
    ]),
    yaxis2=dict(title="Simon", overlaying="y", side="right", showgrid=False,
                range=[
                    simon_goal_weight - kevin_range_padding * (simon_start_weight / kevin_start_weight),
                    simon_start_weight + kevin_range_padding * (simon_start_weight / kevin_start_weight),
                ] if simon_available else None),
    legend=dict(x=0.99, y=0.01, xanchor="right", yanchor="bottom",
                bgcolor="rgba(255,255,255,0.7)", bordercolor="black", borderwidth=1),
    xaxis=dict(title="Date", range=[
        min(kevin_start_date, df_simon["date"].min() if simon_available else kevin_start_date),
        goal_end_date
    ])
)

st.plotly_chart(fig, use_container_width=True)

# --- Responsive layout with custom CSS ---
st.markdown("""
<style>
@media (max-width: 768px) {
    .mobile-column {
        display: block !important;
        width: 100% !important;
    }
}
</style>
""", unsafe_allow_html=True)

# --- Stats Section ---
st.markdown('<div class="mobile-column">', unsafe_allow_html=True)
with st.container():
    st.subheader("Kevin's Stats")
    latest_k = df_kevin.dropna(subset=["weight"]).iloc[-1]["weight"]
    loss_k = kevin_start_weight - latest_k
    loss_pct_k = 100 * loss_k / kevin_start_weight
    st.metric("Starting Weight", f"{kevin_start_weight:.1f} kg")
    st.metric("Latest Weight", f"{latest_k:.1f} kg")
    st.metric("Total Loss", f"{loss_k:.1f} kg ({loss_pct_k:.1f}%)")

if simon_available:
    st.markdown('</div><div class="mobile-column">', unsafe_allow_html=True)
    with st.container():
        st.subheader("Simon's Stats")
        latest_s = df_simon.dropna(subset=["weight"]).iloc[-1]["weight"]
        loss_s = simon_start_weight - latest_s
        loss_pct_s = 100 * loss_s / simon_start_weight
        st.metric("Starting Weight", f"{simon_start_weight:.1f} kg")
        st.metric("Latest Weight", f"{latest_s:.1f} kg")
        st.metric("Total Loss", f"{loss_s:.1f} kg ({loss_pct_s:.1f}%)")
    st.markdown('</div>', unsafe_allow_html=True)


# --- Simon's Manual Entry Form ---
st.subheader("Manual Weight Entry (Simon only)")

with st.form("simon_data_entry"):
    weight = st.number_input("Weight (kg)", min_value=30.0, max_value=200.0, step=0.01, format="%.2f")
    body_fat = st.number_input("Body Fat (%)", min_value=0.0, max_value=100.0, step=0.1, format="%.1f")
    date = st.date_input("Date of Measurement", value=datetime.date.today())

    submitted = st.form_submit_button("Submit Data")

    if submitted:
        try:
            date_str = date.isoformat()
            body_fat_cleaned = None if body_fat == 0.0 else round(body_fat, 1)
            weight_cleaned = round(weight, 2)

            doc_ref = db.collection("users").document("simon").collection("weight_data").document(date_str)
            doc_ref.set({
                "weight": weight_cleaned,
                "bodyFat": body_fat_cleaned
            })
            st.success(f"✅ Entry saved for {date_str} in Firestore")
        except Exception as e:
            st.error(f"❌ Failed to save data: {e}")