"""
Lightweight client for the GrainBidCalc Google Sheets web app.
No credentials required — the Apps Script web app handles auth as the sheet owner.

Replaces sheets_client.py for environments where OAuth credentials aren't available.
"""

import logging
import urllib.request
import urllib.parse
import json
from datetime import datetime, timezone

from config.settings import SHEETS_WEBAPP_URL

logger = logging.getLogger(__name__)


def _get(params: dict) -> dict:
    if not SHEETS_WEBAPP_URL:
        return {}
    url = SHEETS_WEBAPP_URL + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error("Sheets webapp GET failed: %s", e)
        return {}


def _post(payload: dict) -> dict:
    if not SHEETS_WEBAPP_URL:
        return {}
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        SHEETS_WEBAPP_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        logger.error("Sheets webapp POST failed: %s", e)
        return {}


def read_futures_prices() -> dict[str, float]:
    """Returns {contract: price} from the Futures Prices tab."""
    result = _get({"action": "futures"})
    if isinstance(result, dict) and "error" not in result:
        return {k: float(v) for k, v in result.items()}
    return {}


def write_ranked_bids(rows: list[dict]) -> None:
    """Overwrite the Ranked Bids tab with current data."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    def _fmt(v):
        if v is None:
            return ""
        if isinstance(v, float):
            return round(v, 4)
        return str(v)

    sheet_rows = []
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

    result = _post({"action": "write_ranked", "rows": sheet_rows})
    if not result.get("ok"):
        logger.error("Sheets webapp write_ranked failed: %s", result.get("msg"))
    else:
        logger.info("Sheets: wrote %d ranked bid rows via webapp", len(rows))


def append_ingestion_log(row: dict) -> None:
    """Prepend one row to the Ingestion Log tab."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    sheet_row = [
        now,
        row.get("source_type", ""),
        row.get("source_identifier", ""),
        row.get("status", ""),
        row.get("stored", ""),
        row.get("notes", ""),
    ]
    result = _post({"action": "append_log", "row": sheet_row})
    if not result.get("ok"):
        logger.error("Sheets webapp append_log failed: %s", result.get("msg"))
