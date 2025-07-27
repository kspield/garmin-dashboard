import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore

# --- Setup Firebase from local JSON ---
cred_path = "C:/Users/KSpieldiener/fatboyslim-a061f-firebase-adminsdk-fbsvc-aa42e736d1.json"  # ✅ Update this!
cred = credentials.Certificate(cred_path)

if not firebase_admin._apps:
    firebase_admin.initialize_app(cred)

db = firestore.client()

# --- Firestore Test ---
st.title("🔍 Firestore Data Read Test")

try:
    users_collection = db.collection("users").stream()
    user_ids = [doc.id for doc in users_collection]

    if not user_ids:
        st.warning("No users found under 'users/' collection.")
    else:
        for user_id in user_ids:
            st.subheader(f"📁 User: {user_id}")
            weights_ref = db.collection("users").document(user_id).collection("weights")
            weight_docs = list(weights_ref.stream())

            if not weight_docs:
                st.info(f"No weight entries for user: {user_id}")
                continue

            for doc in weight_docs:
                st.write(f"📄 Doc ID: {doc.id}")
                st.json(doc.to_dict())

except Exception as e:
    st.error(f"❌ Error reading from Firestore: {e}")


test = 1