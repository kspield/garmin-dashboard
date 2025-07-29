import json
import os

try:
    from withings_api import WithingsAuth
    from withings_api.common import AuthScope
except ImportError:
    raise RuntimeError("withings-api package is required")

TOKEN_FILE = os.getenv("WITHINGS_TOKEN_FILE", "withings_tokens.json")


def main() -> None:
    client_id = os.getenv("WITHINGS_CLIENT_ID") or input("Withings client ID: ")
    consumer_secret = os.getenv("WITHINGS_CONSUMER_SECRET") or input("Withings consumer secret: ")
    callback_uri = os.getenv("WITHINGS_CALLBACK_URI", "https://oauth.pstmn.io/v1/browser-callback")

    auth = WithingsAuth(
        client_id=client_id,
        consumer_secret=consumer_secret,
        callback_uri=callback_uri,
        scope=(AuthScope.USER_METRICS,),
    )

    authorize_url = auth.get_authorize_url()
    print("Open the following URL in a browser and authorize access:")
    print(authorize_url)

    code = input("Enter the code parameter from the callback URL: ").strip()
    creds = auth.get_credentials(code)

    data = {
        "access_token": creds.access_token,
        "token_expiry": int(creds.token_expiry.timestamp()),
        "token_type": creds.token_type,
        "refresh_token": creds.refresh_token,
        "userid": creds.userid,
        "client_id": client_id,
        "consumer_secret": consumer_secret,
    }

    with open(TOKEN_FILE, "w") as f:
        json.dump(data, f)

    print(f"✅ Credentials saved to {TOKEN_FILE}")


if __name__ == "__main__":
    main()
