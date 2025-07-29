import os
import datetime
from dotenv import load_dotenv
from withings_api import WithingsApi, WithingsAuth, AuthScope
from firebase_admin import credentials, firestore, initialize_app

# Load environment variables
load_dotenv()

# Withings credentials from .env
client_id = os.getenv("WITHINGS_CLIENT_ID")
client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
callback_uri = os.getenv("WITHINGS_CALLBACK")

# Firebase setup
cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH")
cred = credentials.Certificate(cred_path)
initialize_app(cred)
db = firestore.client()

# OAuth setup
auth = WithingsAuth(
    client_id=client_id,
    consumer_secret=client_secret,
    callback_uri=callback_uri,
    scope=(AuthScope.USER_METRICS,),
)

# Step 1: Authorize the app
authorize_url = auth.get_authorize_url()
print("➡️  Visit this URL and authorize access:")
print(authorize_url)

# Step 2: Paste code from redirect
code = input("\n🔑 Paste the 'code' value from the redirect URL: ")

# Step 3: Exchange code for credentials
credentials = auth.get_credentials(code)
api = WithingsApi(credentials)

# Step 4: Fetch measurements
start_date = datetime.date.today() - datetime.timedelta(days=100)
measures = api.measure_get_meas(startdate=start_date)

for group in measures.measuregrps:
    date = datetime.datetime.fromtimestamp(group.date).date().isoformat()
    for measure in group.measures:
        if measure.type == 1:  # 1 = Weight
            weight = measure.value * (10 ** measure.unit)
            print(f"{date}: {weight:.2f} kg")

            # Upload to Firebase
            db.collection("withings_weight").document(date).set({
                "date": date,
                "weight_kg": weight,
            })