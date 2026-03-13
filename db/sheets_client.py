"""
Google Sheets API client for GrainBidCalc.

The service account owns the spreadsheet (no domain-wide delegation needed).
Four operational functions:
  - read_futures_prices()     -> {contract: price} dict  (Futures Prices tab)
  - write_ranked_bids(rows)   -> overwrites Ranked Bids tab
  - append_ingestion_log(row) -> prepends to Ingestion Log tab
  - read_farmer_contacts()    -> list of farmer dicts    (Farmer Contacts tab)
"""

import logging
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config.settings import SHEETS_ID, SHEETS_OAUTH_CLIENT_JSON, SHEETS_TOKEN_JSON

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

TAB_FUTURES = "Futures Prices"
TAB_RANKED  = "Ranked Bids"
TAB_FARMERS = "Farmer Contacts"
TAB_LOG     = "Ingestion Log"

_service = None
_sheet_ids: dict[str, int] = {}


def _get_service():
    """
    Build the Sheets API service using stored OAuth2 user credentials.
    Requires credentials/sheets-token.json to exist (created by authorize_sheets.py).
    Auto-refreshes the access token when expired.
    """
    global _service
    if _service is not None:
        return _service

    import json, os
    if not os.path.exists(SHEETS_TOKEN_JSON):
        raise RuntimeError(
            f"Sheets token not found at {SHEETS_TOKEN_JSON}. "
            "Run: python scripts/authorize_sheets.py"
        )

    with open(SHEETS_TOKEN_JSON) as f:
        token_data = json.load(f)

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=SCOPES,
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Persist the refreshed token
        with open(SHEETS_TOKEN_JSON, "w") as f:
            json.dump({
                "token":         creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri":     creds.token_uri,
                "client_id":     creds.client_id,
                "client_secret": creds.client_secret,
            }, f)

    _service = build("sheets", "v4", credentials=creds)
    return _service


def _tab(tab: str, cells: str) -> str:
    return f"'{tab}'!{cells}"


def _get_sheet_id(tab_name: str) -> int:
    """Look up the numeric sheetId for a tab (needed for insertDimension)."""
    if tab_name in _sheet_ids:
        return _sheet_ids[tab_name]
    meta = (
        _get_service()
        .spreadsheets()
        .get(spreadsheetId=SHEETS_ID, fields="sheets.properties")
        .execute()
    )
    for sheet in meta.get("sheets", []):
        props = sheet["properties"]
        _sheet_ids[props["title"]] = props["sheetId"]
    if tab_name not in _sheet_ids:
        raise ValueError(f"Tab '{tab_name}' not found in spreadsheet")
    return _sheet_ids[tab_name]


# ---------------------------------------------------------------------------
# Futures Prices tab
# ---------------------------------------------------------------------------

def read_futures_prices() -> dict[str, float]:
    """
    Read Futures Prices tab. Returns {contract: price}.
    Layout (row 1 = headers): Col A = Contract, Col B = Price (USD/BU).
    Skips rows with no price entered.
    """
    if not SHEETS_ID:
        return {}
    try:
        result = (
            _get_service()
            .spreadsheets()
            .values()
            .get(spreadsheetId=SHEETS_ID, range=_tab(TAB_FUTURES, "A2:B50"))
            .execute()
        )
        prices = {}
        for row in result.get("values", []):
            if len(row) < 2 or not row[1].strip():
                continue
            contract = row[0].strip().upper()
            try:
                prices[contract] = float(row[1].strip())
            except ValueError:
                logger.warning("Sheets: non-numeric price for %s: %r", contract, row[1])
        return prices
    except HttpError as e:
        logger.error("Sheets: failed to read futures prices: %s", e)
        return {}


# ---------------------------------------------------------------------------
# Ranked Bids tab
# ---------------------------------------------------------------------------

RANKED_HEADERS = [
    "Commodity", "Delivery Month", "Rank", "Location", "Bid Type",
    "CAD Basis", "US Basis", "Live Cash (CAD/BU)", "Mapleview Price (CAD/BU)",
    "Calculated At",
]


def write_ranked_bids(rows: list[dict]) -> None:
    """
    Overwrite the Ranked Bids tab with current data.
    Expected dict keys: commodity, delivery_month, rank, location, bid_type,
                        cad_basis, us_basis, live_cash, mapleview_price
    """
    if not SHEETS_ID:
        return

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _fmt(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return round(v, 4)
        return str(v)

    sheet_rows = [RANKED_HEADERS]
    for r in rows:
        sheet_rows.append([
            _fmt(r.get("commodity")),
            _fmt(r.get("delivery_month")),
            _fmt(r.get("rank")),
            _fmt(r.get("location")),
            _fmt(r.get("bid_type")),
            _fmt(r.get("cad_basis")),
            _fmt(r.get("us_basis")),
            _fmt(r.get("live_cash")),
            _fmt(r.get("mapleview_price")),
            now,
        ])

    try:
        svc = _get_service().spreadsheets().values()
        svc.clear(
            spreadsheetId=SHEETS_ID,
            range=_tab(TAB_RANKED, "A1:Z500"),
            body={},
        ).execute()
        svc.update(
            spreadsheetId=SHEETS_ID,
            range=_tab(TAB_RANKED, "A1"),
            valueInputOption="USER_ENTERED",
            body={"values": sheet_rows},
        ).execute()
        logger.info("Sheets: wrote %d ranked bid rows", len(rows))
    except HttpError as e:
        logger.error("Sheets: failed to write ranked bids: %s", e)


# ---------------------------------------------------------------------------
# Ingestion Log tab
# ---------------------------------------------------------------------------

LOG_HEADERS = ["Timestamp", "Source Type", "Buyer / Sender", "Status", "Bids Stored", "Notes"]


def append_ingestion_log(row: dict) -> None:
    """
    Insert one row at position 2 (newest at top, below the header).
    row keys: source_type, source_identifier, status, stored, notes
    """
    if not SHEETS_ID:
        return
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    new_row = [
        now,
        row.get("source_type", ""),
        row.get("source_identifier", ""),
        row.get("status", ""),
        row.get("stored", ""),
        row.get("notes", ""),
    ]
    try:
        # Insert blank row at row 2 to push existing rows down
        _get_service().spreadsheets().batchUpdate(
            spreadsheetId=SHEETS_ID,
            body={
                "requests": [{
                    "insertDimension": {
                        "range": {
                            "sheetId": _get_sheet_id(TAB_LOG),
                            "dimension": "ROWS",
                            "startIndex": 1,
                            "endIndex": 2,
                        },
                        "inheritFromBefore": False,
                    }
                }]
            },
        ).execute()
        _get_service().spreadsheets().values().update(
            spreadsheetId=SHEETS_ID,
            range=_tab(TAB_LOG, "A2"),
            valueInputOption="USER_ENTERED",
            body={"values": [new_row]},
        ).execute()
    except HttpError as e:
        logger.error("Sheets: failed to append ingestion log: %s", e)


# ---------------------------------------------------------------------------
# Farmer Contacts tab
# ---------------------------------------------------------------------------

FARMER_HEADERS = [
    "Name", "Farm Name", "Phone", "Email", "Region", "Location",
    "Preferred Channel", "Commodities", "Bid Types", "Active",
]


def read_farmer_contacts() -> list[dict]:
    """
    Read Farmer Contacts tab. Returns list of dicts keyed by header.
    Skips rows where Name is blank.
    """
    if not SHEETS_ID:
        return []
    try:
        result = (
            _get_service()
            .spreadsheets()
            .values()
            .get(spreadsheetId=SHEETS_ID, range=_tab(TAB_FARMERS, "A2:J200"))
            .execute()
        )
        keys = [h.lower().replace(" ", "_") for h in FARMER_HEADERS]
        contacts = []
        for row in result.get("values", []):
            if not row or not row[0].strip():
                continue
            padded = row + [""] * (len(keys) - len(row))
            contacts.append(dict(zip(keys, padded)))
        return contacts
    except HttpError as e:
        logger.error("Sheets: failed to read farmer contacts: %s", e)
        return []
