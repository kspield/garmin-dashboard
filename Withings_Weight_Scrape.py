import datetime
import json
import os

import firebase_admin
from firebase_admin import credentials, firestore

# Third-party library for Withings API
try:
    from withings_api import WithingsApi, MeasuresType, MeasureGetMeasGroupCategory
    from withings_api.common import Credentials
except ImportError:  # pragma: no cover - library might not be available during linting
    WithingsApi = None
    MeasuresType = None
    MeasureGetMeasGroupCategory = None
    Credentials = None


# Path to service account key for Firebase
cred_path = os.getenv("FIREBASE_KEY_PATH")
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

db = firestore.client()

# Path where Withings OAuth tokens are stored
TOKEN_FILE = os.getenv("WITHINGS_TOKEN_FILE", "withings_tokens.json")

# Default start date if no data exists locally
DEFAULT_START_DATE = datetime.date(2025, 7, 24)

def load_tokens(path: str) -> Credentials:
    """Load Withings credentials from a JSON file."""
    with open(path, "r") as f:
        data = json.load(f)
    return Credentials(
        access_token=data["access_token"],
        token_expiry=datetime.datetime.fromtimestamp(data["token_expiry"]),
        token_type=data["token_type"],
        refresh_token=data["refresh_token"],
        userid=data["userid"],
        client_id=data.get("client_id"),
        consumer_secret=data.get("consumer_secret"),
    )

def save_tokens(path: str, creds: Credentials) -> None:
    """Save Withings credentials back to JSON file."""
    data = {
        "access_token": creds.access_token,
        "token_expiry": int(creds.token_expiry.timestamp()),
        "token_type": creds.token_type,
        "refresh_token": creds.refresh_token,
        "userid": creds.userid,
        "client_id": creds.client_id,
        "consumer_secret": creds.consumer_secret,
    }
    with open(path, "w") as f:
        json.dump(data, f)


def get_start_date() -> datetime.date:
    """Determine the date to start scraping from."""
    if os.path.exists(TOKEN_FILE.replace("tokens.json", "data.json")):
        json_file = TOKEN_FILE.replace("tokens.json", "data.json")
        with open(json_file, "r") as f:
            existing = json.load(f)
        existing = sorted(existing, key=lambda x: x["date"])
        valid = [e for e in existing if e.get("weight") is not None]
        if valid:
            last_date = valid[-1]["date"]
            return datetime.datetime.strptime(last_date, "%Y-%m-%d").date()
    return DEFAULT_START_DATE


def main() -> None:
    if WithingsApi is None:
        raise RuntimeError("withings_api package is required")

    creds = load_tokens(TOKEN_FILE)
    api = WithingsApi(creds)

    # Refresh token if needed
    refreshed = api.refresh_token()
    save_tokens(TOKEN_FILE, refreshed)

    start_date = get_start_date()
    end_date = datetime.date.today()

    meas = api.measure_get_meas(
        meastype=MeasuresType.WEIGHT,
        category=MeasureGetMeasGroupCategory.REAL,
        startdate=start_date,
        enddate=end_date,
    )

    for grp in meas.measuregrps:
        dt = datetime.date.fromtimestamp(grp.date)
        weight = None
        body_fat = None
        for m in grp.measures:
            if m.type == MeasuresType.WEIGHT:
                weight = m.value * (10 ** m.unit)
            if m.type == MeasuresType.FAT_RATIO:
                body_fat = m.value * (10 ** m.unit)

        date_str = dt.isoformat()
        doc_ref = (
            db.collection("users")
            .document("simon")
            .collection("weight_data")
            .document(date_str)
        )
        doc_ref.set({
            "date": date_str,
            "weight": weight,
            "bodyFat": body_fat,
        })

    print("✅ Simon's Withings data uploaded to Firebase.")


if __name__ == "__main__":
    main()

