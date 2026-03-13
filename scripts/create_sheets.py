"""
One-time script to create the GrainBidCalc Google Spreadsheet.

Creates 4 tabs with headers, formatting, and pre-populated futures contracts,
then shares the sheet with the owner email.

Usage:
    python scripts/create_sheets.py mapleviewgrain@gmail.com

After running:
    1. Copy the SHEETS_ID printed at the end into your .env file
    2. Open the URL to verify all tabs look correct
    3. Enter current futures prices in the Futures Prices tab
"""

import json
import os
import sys
from dotenv import load_dotenv
load_dotenv()

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

TOKEN_JSON  = os.environ.get("SHEETS_TOKEN_JSON",        "credentials/sheets-token.json")
CLIENT_JSON = os.environ.get("SHEETS_OAUTH_CLIENT_JSON", "credentials/oauth-client.json")


def _get_creds():
    if not os.path.exists(TOKEN_JSON):
        print(f"Error: token not found at {TOKEN_JSON}")
        print("Run first: python scripts/authorize_sheets.py")
        sys.exit(1)
    with open(TOKEN_JSON) as f:
        data = json.load(f)
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=["https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive.file"],
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    return creds

# Inline constants so this script runs without a full .env
ACTIVE_CONTRACTS = [
    "ZSH26", "ZSK26", "ZSN26", "ZSX26",
    "ZCH26", "ZCK26", "ZCN26", "ZCZ26",
    "ZWH26", "ZWN26", "ZWZ26",
    "RSK26", "RSN26", "RSX26",
]
TAB_FUTURES = "Futures Prices"
TAB_RANKED  = "Ranked Bids"
TAB_FARMERS = "Farmer Contacts"
TAB_LOG     = "Ingestion Log"
RANKED_HEADERS = [
    "Commodity", "Delivery Month", "Rank", "Location", "Bid Type",
    "CAD Basis", "US Basis", "Live Cash (CAD/BU)", "Mapleview Price (CAD/BU)",
    "Calculated At",
]
LOG_HEADERS    = ["Timestamp", "Source Type", "Buyer / Sender", "Status", "Bids Stored", "Notes"]
FARMER_HEADERS = [
    "Name", "Farm Name", "Phone", "Email", "Region", "Location",
    "Preferred Channel", "Commodities", "Bid Types", "Active",
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

WHITE        = {"red": 1.0,   "green": 1.0,   "blue": 1.0}
DARK_GREEN   = {"red": 0.118, "green": 0.392, "blue": 0.196}
DARK_BLUE    = {"red": 0.157, "green": 0.306, "blue": 0.475}
DARK_ORANGE  = {"red": 0.647, "green": 0.302, "blue": 0.086}
DARK_GREY    = {"red": 0.3,   "green": 0.3,   "blue": 0.3}


def _header_requests(sheet_id: int, headers: list[str], bg: dict) -> list[dict]:
    """Bold header row with background colour + freeze row 1."""
    return [
        {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 0, "endRowIndex": 1,
                    "startColumnIndex": 0, "endColumnIndex": len(headers),
                },
                "rows": [{"values": [
                    {
                        "userEnteredValue": {"stringValue": h},
                        "userEnteredFormat": {
                            "textFormat": {"bold": True, "foregroundColor": WHITE},
                            "backgroundColor": bg,
                            "horizontalAlignment": "CENTER",
                        },
                    }
                    for h in headers
                ]}],
                "fields": "userEnteredValue,userEnteredFormat",
            }
        },
        {
            "updateSheetProperties": {
                "properties": {
                    "sheetId": sheet_id,
                    "gridProperties": {"frozenRowCount": 1},
                },
                "fields": "gridProperties.frozenRowCount",
            }
        },
    ]


def _col_width(sheet_id: int, col: int, px: int) -> dict:
    return {
        "updateDimensionProperties": {
            "range": {
                "sheetId": sheet_id,
                "dimension": "COLUMNS",
                "startIndex": col,
                "endIndex": col + 1,
            },
            "properties": {"pixelSize": px},
            "fields": "pixelSize",
        }
    }


def _contract_note(contract: str) -> str:
    notes = {
        "ZS": "Soybeans (CBOT)",
        "ZC": "Corn (CBOT)",
        "ZW": "Wheat SRW (CBOT)",
        "KE": "Wheat HRW (CBOT)",
        "RS": "Canola (ICE)",
    }
    return notes.get(contract[:2], "")


def main(owner_email: str):
    creds = _get_creds()
    sheets_svc = build("sheets", "v4", credentials=creds)
    drive_svc  = build("drive",  "v3", credentials=creds)

    # ------------------------------------------------------------------
    # 1. Create spreadsheet with 4 named tabs
    # ------------------------------------------------------------------
    print("Creating spreadsheet...")
    spreadsheet = sheets_svc.spreadsheets().create(body={
        "properties": {"title": "GrainBidCalc — Mapleview Grain"},
        "sheets": [
            {"properties": {"title": TAB_FUTURES, "index": 0}},
            {"properties": {"title": TAB_RANKED,  "index": 1}},
            {"properties": {"title": TAB_FARMERS, "index": 2}},
            {"properties": {"title": TAB_LOG,     "index": 3}},
        ],
    }).execute()

    ss_id = spreadsheet["spreadsheetId"]
    sheet_map = {
        s["properties"]["title"]: s["properties"]["sheetId"]
        for s in spreadsheet["sheets"]
    }
    fid = sheet_map[TAB_FUTURES]
    rid = sheet_map[TAB_RANKED]
    mid = sheet_map[TAB_FARMERS]
    lid = sheet_map[TAB_LOG]

    # ------------------------------------------------------------------
    # 2. Format all tabs
    # ------------------------------------------------------------------
    print("Formatting tabs...")
    requests = []

    # Futures Prices tab
    requests += _header_requests(fid, ["Contract", "Price (USD/BU)", "Notes"], DARK_GREEN)
    for i, px in enumerate([100, 140, 260]):
        requests.append(_col_width(fid, i, px))

    # Ranked Bids tab
    requests += _header_requests(rid, RANKED_HEADERS, DARK_BLUE)
    for i, px in enumerate([110, 130, 60, 110, 90, 100, 100, 150, 175, 160]):
        requests.append(_col_width(rid, i, px))

    # Farmer Contacts tab
    requests += _header_requests(mid, FARMER_HEADERS, DARK_ORANGE)
    for i, px in enumerate([140, 160, 130, 200, 110, 130, 130, 160, 100, 70]):
        requests.append(_col_width(mid, i, px))

    # Ingestion Log tab
    requests += _header_requests(lid, LOG_HEADERS, DARK_GREY)
    for i, px in enumerate([175, 110, 210, 90, 100, 260]):
        requests.append(_col_width(lid, i, px))

    sheets_svc.spreadsheets().batchUpdate(
        spreadsheetId=ss_id,
        body={"requests": requests},
    ).execute()

    # ------------------------------------------------------------------
    # 3. Pre-populate Futures Prices with active contracts
    # ------------------------------------------------------------------
    print("Populating Futures Prices tab...")
    futures_rows = [[c, "", _contract_note(c)] for c in ACTIVE_CONTRACTS]
    sheets_svc.spreadsheets().values().update(
        spreadsheetId=ss_id,
        range=f"'{TAB_FUTURES}'!A2",
        valueInputOption="USER_ENTERED",
        body={"values": futures_rows},
    ).execute()

    # Placeholder rows in other tabs
    sheets_svc.spreadsheets().values().batchUpdate(
        spreadsheetId=ss_id,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [
                {
                    "range": f"'{TAB_RANKED}'!A2",
                    "values": [["(System will populate this tab after each ranking run)"]],
                },
                {
                    "range": f"'{TAB_LOG}'!A2",
                    "values": [["(System will append rows here after each ingestion)"]],
                },
            ],
        },
    ).execute()

    url = f"https://docs.google.com/spreadsheets/d/{ss_id}"
    print("\n--- Done! ---")
    print(f"URL:  {url}")
    print(f"\nAdd this to your .env file:")
    print(f"SHEETS_ID={ss_id}")
    print(f"\nNext: open the sheet, go to '{TAB_FUTURES}', and enter today's prices in column B.")


if __name__ == "__main__":
    main(None)
