import os
import json
import datetime
import logging
from pathlib import Path
from dotenv import load_dotenv
from withings_api import WithingsApi, WithingsAuth, AuthScope
from withings_api.common import Credentials
from firebase_admin import credentials as fb_credentials, firestore, initialize_app
from google.cloud.firestore_v1.base_query import FieldFilter
from datetime import datetime as dt, time

# Configure debug logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logger.disabled = False

# Load .env
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# Withings API credentials
client_id = os.getenv("WITHINGS_CLIENT_ID")
client_secret = os.getenv("WITHINGS_CLIENT_SECRET")
callback_uri = os.getenv("WITHINGS_CALLBACK")

# Firebase setup
cred_path = Path(__file__).parent / "firebase_key.json"
cred = fb_credentials.Certificate(cred_path)
initialize_app(cred)
db = firestore.client()

# Choose user
user_id = "simon"  # or "kevin", or dynamic later

# Token storage path
TOKEN_FILE = Path(__file__).parent / "withings_tokens.json"

# OAuth flow
auth = WithingsAuth(
    client_id=client_id,
    consumer_secret=client_secret,
    callback_uri=callback_uri,
    scope=(AuthScope.USER_METRICS,),
)

# Load or generate credentials
if Path(TOKEN_FILE).exists():
    logger.info("🔁 Loading saved Withings credentials...")
    with open(TOKEN_FILE, "r") as f:
        saved = json.load(f)
        credentials = Credentials(
            access_token=saved["access_token"],
            token_expiry=saved["token_expiry"],
            token_type=saved["token_type"],
            refresh_token=saved["refresh_token"],
            userid=saved["userid"],
            client_id=client_id,
            consumer_secret=client_secret,
        )
else:
    print("🌐 Authorize with Withings:")
    print(auth.get_authorize_url())
    code = input("🔑 Paste the 'code' from the redirect URL: ").strip()
    credentials = auth.get_credentials(code)
    with open(TOKEN_FILE, "w") as f:
        json.dump({
            "access_token": credentials.access_token,
            "token_expiry": credentials.token_expiry,
            "token_type": credentials.token_type,
            "refresh_token": credentials.refresh_token,
            "userid": credentials.userid,
        }, f)
    print("💾 Credentials saved.")

# Create API and refresh tokens
api = WithingsApi(credentials)
try:
    api.refresh_token()
    refreshed = api.get_credentials()
    with open(TOKEN_FILE, "w") as f:
        json.dump({
            "access_token": refreshed.access_token,
            "token_expiry": refreshed.token_expiry,
            "token_type": refreshed.token_type,
            "refresh_token": refreshed.refresh_token,
            "userid": refreshed.userid,
        }, f)
    logger.info("🔄 Token refreshed and saved.")
except Exception as e:
    logger.error(f"❌ Failed to refresh token: {e}")
    exit()

# Get last Withings sync date
meta_ref = db.collection("users").document(user_id).collection("meta").document("withings_sync")
doc = meta_ref.get()

if doc.exists:
    last_sync_date = doc.to_dict().get("last_date")
    start_date = datetime.date.fromisoformat(last_sync_date)
    logger.info(f"🔁 Last Withings sync: {start_date}")
else:
    start_date = datetime.date.today() - datetime.timedelta(days=300)
    logger.info(f"📆 No previous sync found. Starting from {start_date}")

end_date = datetime.date.today()
end_timestamp = int(dt.now().timestamp())

start_timestamp = int(dt.combine(start_date, time.min).timestamp())

# Fetch measurements
try:
    measures = api.measure_get_meas(
        startdate=start_timestamp,
        enddate=end_timestamp,
        lastupdate=None
    )
    logger.info(f"✅ Found {len(measures.measuregrps)} measurement groups.")
except Exception as e:
    logger.error(f"❌ Error fetching data: {e}")
    exit()

if not measures.measuregrps:
    logger.error("⚠️ No new Withings data found.")
    exit()

# Track latest date scraped
latest_scraped_date = start_date

# Parse and upload
for group in measures.measuregrps:
    date = group.date.date().isoformat()
    weight = None
    fat_percent = None

    for measure in group.measures:
        value = measure.value * (10 ** measure.unit)
        if measure.type == 1:  # Weight
            weight = value
        elif measure.type == 6:  # Fat %
            fat_percent = value

    if weight is not None:
        try:
            db.collection("users").document(user_id).collection("weight_data").document(date).set({
                "date": date,
                "weight": weight,
                "bodyFat": fat_percent
            })
            logger.info(f"📤 Uploaded {date}: {weight:.2f} kg, fat: {fat_percent}")
            # Track latest scraped date
            if date > latest_scraped_date.isoformat():
                latest_scraped_date = datetime.date.fromisoformat(date)
        except Exception as e:
            logger.error(f"❌ Upload failed for {date}: {e}")

# Update sync marker
try:
    meta_ref.set({"last_date": latest_scraped_date.isoformat()})
    now = datetime.datetime.now()
    print(f"{now.strftime('%Y-%m-%d %H:%M:%S')}: Withings Scraper - ✅ Sync marker at: {latest_scraped_date}")
except Exception as e:
    logger.error(f"❌ Failed to update sync marker: {e}")
