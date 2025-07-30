
import datetime
import json
import logging
import os
from getpass import getpass
from pathlib import Path

import requests
from garth.exc import GarthHTTPError

import firebase_admin
from firebase_admin import credentials, firestore

from google.cloud import firestore as gcf  # Needed for ordering Firestore docs

# Path to your service account key (downloaded from Firebase Console)

# Load credential path from environment variable
cred_path = Path(__file__).parent / "firebase_key.json"
cred = credentials.Certificate(cred_path)
firebase_admin.initialize_app(cred)

db = firestore.client()
collection_name = "kevin_data"

# LOGGING
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)

# Configure debug logging
# logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables if defined
email = os.getenv("EMAIL")
password = os.getenv("PASSWORD")
tokenstore = os.getenv("GARMINTOKENS") or "~/.garminconnect"
tokenstore_base64 = os.getenv("GARMINTOKENS_BASE64") or "~/.garminconnect_base64"
api = None

# Example selections and settings

# Let's say we want to scrape all activities using switch menu_option "p". We change the values of the below variables, IE startdate days, limit,...

end_date = datetime.date.today()

json_file = "Kevin_Data.json"
existing_data = []

if os.path.exists(json_file):
    with open(json_file, "r") as f:
        existing_data = json.load(f)

    # Find last entry with real data (weight not None)
    existing_data = sorted(existing_data, key=lambda x: x["date"])
    valid_entries = [entry for entry in existing_data if entry.get("weight") is not None]

    if valid_entries:
        last_valid_date_str = valid_entries[-1]["date"]
        start_date = datetime.datetime.strptime(last_valid_date_str, "%Y-%m-%d").date()
    else:
        start_date = datetime.date(2025, 1, 1)  # fallback start
else:
    start_date = datetime.date(2025, 1, 1)

all_data = []


def display_json(api_call, output):
    """Format API output for better readability."""

    dashed = "-" * 20
    header = f"{dashed} {api_call} {dashed}"
    footer = "-" * len(header)

    # print(header)

    # if isinstance(output, (int, str, dict, list)):
    #     print(json.dumps(output, indent=4))
    # else:
    #     print(output)

    # print(footer)
    # Format the output
    if isinstance(output, (int, str, dict, list)):
        formatted_output = json.dumps(output, indent=4)
    else:
        formatted_output = str(output)

    # Combine the header, output, and footer
    full_output = f"{header}\n{formatted_output}\n{footer}"

    # Print to console
    print(full_output)

    # Save to a file
    output_filename = "response.json"
    with open(output_filename, "w") as file:
        file.write(full_output)

    print(f"Output saved to {output_filename}")

def display_text(output):
    """Format API output for better readability."""

    dashed = "-" * 60
    header = f"{dashed}"
    footer = "-" * len(header)

    print(header)
    print(json.dumps(output, indent=4))
    print(footer)

def get_credentials():
    """Get user credentials."""

    email = input("Login e-mail: ")
    password = getpass("Enter password: ")

    return email, password

def init_api(email, password):
    """Initialize Garmin API with your credentials."""

    try:
        # Using Oauth1 and OAuth2 token files from directory
        print(
            f"Trying to login to Garmin Connect using token data from directory '{tokenstore}'...\n"
        )

        # Using Oauth1 and Oauth2 tokens from base64 encoded string
        # print(
        #     f"Trying to login to Garmin Connect using token data from file '{tokenstore_base64}'...\n"
        # )
        # dir_path = os.path.expanduser(tokenstore_base64)
        # with open(dir_path, "r") as token_file:
        #     tokenstore = token_file.read()

        garmin = Garmin()
        garmin.login(tokenstore)

    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        # Session is expired. You'll need to log in again
        print(
            "Login tokens not present, login with your Garmin Connect credentials to generate them.\n"
            f"They will be stored in '{tokenstore}' for future use.\n"
        )
        try:
            # Ask for credentials if not set as environment variables
            if not email or not password:
                email, password = get_credentials()

            garmin = Garmin(
                email=email, password=password, is_cn=False, return_on_mfa=True
            )
            result1, result2 = garmin.login()
            if result1 == "needs_mfa":  # MFA is required
                mfa_code = get_mfa()
                garmin.resume_login(result2, mfa_code)

            # Save Oauth1 and Oauth2 token files to directory for next login
            garmin.garth.dump(tokenstore)
            print(
                f"Oauth tokens stored in '{tokenstore}' directory for future use. (first method)\n"
            )

            # Encode Oauth1 and Oauth2 tokens to base64 string and safe to file for next login (alternative way)
            token_base64 = garmin.garth.dumps()
            dir_path = os.path.expanduser(tokenstore_base64)
            with open(dir_path, "w") as token_file:
                token_file.write(token_base64)
            print(
                f"Oauth tokens encoded as base64 string and saved to '{dir_path}' file for future use. (second method)\n"
            )

            # Re-login Garmin API with tokens
            garmin.login(tokenstore)
        except (
            FileNotFoundError,
            GarthHTTPError,
            GarminConnectAuthenticationError,
            requests.exceptions.HTTPError,
        ) as err:
            logger.error(err)
            return None

    return garmin

def get_mfa():
    """Get MFA."""

    return input("MFA one-time code: ")


# Init API
if not api:
    api = init_api(email, password)

if api:
    # Display menu
        # Skip requests if login failed
    try:
        print("Fetching data from Garmin...")
        for day in range((end_date - start_date).days + 1):
            date = start_date + datetime.timedelta(days=day)
            weight = None
            body_fat = None

            try:
                body_data = api.get_body_composition(date.isoformat())
                total_avg = body_data.get("totalAverage", {})
                weight_raw = total_avg.get("weight")
                weight = round(weight_raw / 1000, 2) if weight_raw else None
                body_fat = total_avg.get("bodyFat")
            except Exception as e:
                if "No data" in str(e) or "404" in str(e):
                    print(f"{date}: No data available.")
                else:
                    print(f"{date}: Error – {e}")

            logger.info(f"{date}: weight = {weight} kg, body fat = {body_fat} %")

            # Save or update in Firebase
            if weight is not None:
                weight_collection = db.collection("users").document("kevin").collection("weight_data")

                date_str = date.isoformat() 

                # Get all existing docs for this date
                existing_docs = weight_collection.where("date", "==", date_str).stream()
                existing_weights = [doc.to_dict().get("weight") for doc in existing_docs]
                doc_count = len(existing_weights)

                if weight not in existing_weights:
                    doc_id = f"{date_str}_{doc_count + 1}"
                    weight_collection.document(doc_id).set({
                        "date": date_str,
                        "weight": weight,
                        "bodyFat": body_fat,
                        "scraped_at": datetime.datetime.now().isoformat(),
                        "source": "garmin"
                    })
                    print(f"📌 Saved new weight entry: {doc_id}")
                else:
                    print(f"➖ Weight for {date_str} already stored. Skipping.")

        print("✅ Data uploaded to Firebase.")

    except (
        GarminConnectConnectionError,
        GarminConnectAuthenticationError,
        GarminConnectTooManyRequestsError,
        requests.exceptions.HTTPError,
        GarthHTTPError,
    ) as err:
        logger.error(err)
    except KeyError:
        # Invalid menu option chosen
        pass
else:
    print("Could not login to Garmin Connect, try again later.")

test = 1

