import os
import datetime
from dotenv import load_dotenv
from withings_api import WithingsApi, WithingsAuth, AuthScope
from firebase_admin import credentials, firestore, initialize_app

# Load environment variables from .env
load_dotenv()

# Get Withings API credentials
client_id = os.getenv("WITHINGS_CLIENT_ID")
client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
callback_uri = os.getenv("WITHINGS_CALLBACK")

# Firebase setup
cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
cred = credentials.Certificate(cred_path)
initialize_app(cred)
db = firestore.client()

# OAuth authorization setup
auth = WithingsAuth(
    client_id=client_id,
    consumer_secret=client_secret,
    callback_uri=callback_uri,
    scope=(AuthScope.USER_METRICS,),
)

# Step 1: Authorization
authorize_url = auth.get_authorize_url()
print("\n➡️  Open this URL in your browser to authorize:")
print(authorize_url)

code = input("\n🔑 Paste the 'code' from the redirected URL: ").strip()

# Step 2: Exchange code for credentials
credentials = auth.get_credentials(code)
api = WithingsApi(credentials)

# Step 3: Fetch measurements
start_date = datetime.date.today() - datetime.timedelta(days=30)
end_date = datetime.date.today()
print(f"\n📆 Fetching data from {start_date} to {end_date}...")

try:
    measures = api.measure_get_meas(
        startdate=start_date,
        enddate=end_date,
        lastupdate=None  # 🔑 This prevents empty results
    )
    print(f"✅ Found {len(measures.measuregrps)} measurement groups.")
except Exception as e:
    print(f"❌ Error fetching data from Withings: {e}")
    exit()

if not measures.measuregrps:
    print("⚠️ No data returned. Check your Withings app to verify recent sync.")
    exit()

# Step 4: Process and upload measurements
for group in measures.measuregrps:
    date = group.date.date().isoformat()
    print(f"\n📍 Data from {date}:")
    for measure in group.measures:
        print(f"  ↪️ type: {measure.type}, value: {measure.value}, unit: {measure.unit}")
        if measure.type == 1:  # 1 = Weight
            weight = measure.value * (10 ** measure.unit)
            print(f"  🏋️ Weight: {weight:.2f} kg")

            # Upload to Firebase
            try:
                db.collection("withings_weight").document(date).set({
                    "date": date,
                    "weight_kg": weight,
                })
                print(f"  ✅ Uploaded to Firebase.")
            except Exception as e:
                print(f"  ❌ Firebase upload failed: {e}")
