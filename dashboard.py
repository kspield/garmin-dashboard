import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import datetime
import firebase_admin
from firebase_admin import credentials, firestore

# --- Firebase Setup ---
if not firebase_admin._apps:
    firebase_secrets = st.secrets["firebase"]
    cred = credentials.Certificate({
        "type": firebase_secrets["type"],
        "project_id": firebase_secrets["project_id"],
        "private_key_id": firebase_secrets["private_key_id"],
        "private_key": firebase_secrets["private_key"].replace("\\n", "\n"),
        "client_email": firebase_secrets["client_email"],
        "client_id": firebase_secrets["client_id"],
        "auth_uri": firebase_secrets["auth_uri"],
        "token_uri": firebase_secrets["token_uri"],
        "auth_provider_x509_cert_url": firebase_secrets["auth_provider_x509_cert_url"],
        "client_x509_cert_url": firebase_secrets["client_x509_cert_url"]
    })
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- Load Data ---
def load_data(user: str) -> pd.DataFrame:
    docs = db.collection(f"{user}_weight").stream()
    records = [{"date": doc.id, **doc.to_dict()} for doc in docs]
    df = pd.DataFrame(records)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
    return df

df_kevin = load_data("kevin")
df_simon = load_data("simon")
simon_available = not df_simon.empty

# --- Layout ---
st.set_page_config(page_title="Fat Boy Slim Competition", layout="wide")
st.title("Fat Boy Slim Competition")

# --- Start values and goal ---
kevin_start_weight = 78
simon_start_weight = 100
goal_end_date = datetime.datetime(2025, 12, 25)
kevin_start_date = df_kevin["date"].min()
goal_dates_kevin = pd.date_range(start=kevin_start_date, end=goal_end_date, freq="D")
months_kevin = ((goal_dates_kevin - kevin_start_date) / pd.Timedelta(days=30.437)).astype(float)
kevin_goal_weights = kevin_start_weight * (1 - 0.015 * months_kevin)
kevin_goal_weight = kevin_goal_weights.iloc[-1]

if simon_available:
    simon_start_date = df_simon["date"].min()
    goal_dates_simon = pd.date_range(start=simon_start_date, end=goal_end_date, freq="D")
    months_simon = ((goal_dates_simon - simon_start_date) / pd.Timedelta(days=30.437)).astype(float)
    simon_goal_weights = simon_start_weight * (1 - 0.015 * months_simon)
    simon_goal_weight = simon_goal_weights.iloc[-1]

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

# --- Y Axis Scaling ---
kevin_range_padding = 3
fig.update_layout(
    yaxis=dict(title="Kevin", side="left", range=[
        kevin_goal_weight - kevin_range_padding,
        kevin_start_weight + kevin_range_padding]),
    yaxis2=dict(title="Simon", overlaying="y", side="right", showgrid=False,
                range=[simon_goal_weight - kevin_range_padding * (simon_start_weight / kevin_start_weight),
                       simon_start_weight + kevin_range_padding * (simon_start_weight / kevin_start_weight)]
                if simon_available else None),
    legend=dict(x=0.99, y=0.01, xanchor="right", yanchor="bottom",
                bgcolor="rgba(255,255,255,0.7)", bordercolor="black", borderwidth=1),
    xaxis=dict(title="Date", range=[min(kevin_start_date, simon_start_date if simon_available else kevin_start_date), goal_end_date])
)

st.plotly_chart(fig, use_container_width=True)

# --- Stats ---
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