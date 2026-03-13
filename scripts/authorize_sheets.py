"""
One-time OAuth2 authorization for Google Sheets access.

Run this once on the server to generate credentials/sheets-token.json.
After that, the system uses the stored token automatically (auto-refreshes).

Usage:
    python scripts/authorize_sheets.py

It will print a URL. Open it in your browser, approve access as
mapleviewgrain@gmail.com, then paste the code back here.
"""

import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

# Paths relative to project root
CLIENT_JSON = os.environ.get("SHEETS_OAUTH_CLIENT_JSON", "credentials/oauth-client.json")
TOKEN_JSON  = os.environ.get("SHEETS_TOKEN_JSON",        "credentials/sheets-token.json")


def main():
    if not os.path.exists(CLIENT_JSON):
        print(f"Error: OAuth client file not found at {CLIENT_JSON}")
        print("Download it from Google Cloud Console → APIs & Services → Credentials")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_JSON, SCOPES)

    # Generate auth URL manually — paste code back (no local server needed)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    auth_url, _ = flow.authorization_url(prompt="consent")
    print(f"\nOpen this URL in your browser:\n\n{auth_url}\n")
    code = input("Paste the authorization code here: ").strip()
    flow.fetch_token(code=code)
    creds = flow.credentials

    os.makedirs(os.path.dirname(TOKEN_JSON), exist_ok=True)
    with open(TOKEN_JSON, "w") as f:
        json.dump({
            "token":         creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri":     creds.token_uri,
            "client_id":     creds.client_id,
            "client_secret": creds.client_secret,
        }, f)

    print(f"\nAuthorization complete. Token saved to {TOKEN_JSON}")
    print("You can now run: python scripts/create_sheets.py mapleviewgrain@gmail.com")


if __name__ == "__main__":
    main()
