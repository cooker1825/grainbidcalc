/**
 * GrainBidCalc — Sheets Web App
 *
 * Deploy as a web app (Execute as: Me, Who has access: Anyone).
 * Gives the Python server read/write access to the sheet with no credentials.
 *
 * Deploy: Apps Script → Deploy → New deployment → Web app
 *   Execute as: Me
 *   Who has access: Anyone
 * Copy the web app URL → add to .env as SHEETS_WEBAPP_URL
 */

var SS_ID = "1Aq6yPZynXzX_UN-erORaT3ycZo_JQe-P_mmKyolb-5w";

// ---------------------------------------------------------------------------
// GET — read futures prices
// ?action=futures  →  {"ZSH26": 11.375, "ZCK26": 4.431, ...}
// ---------------------------------------------------------------------------
function doGet(e) {
  var action = e.parameter.action || "futures";

  if (action === "futures") {
    var ss    = SpreadsheetApp.openById(SS_ID);
    var sheet = ss.getSheetByName("Futures Prices");
    var data  = sheet.getRange(2, 1, sheet.getLastRow() - 1, 2).getValues();
    var prices = {};
    data.forEach(function(row) {
      var contract = String(row[0]).trim().toUpperCase();
      var price    = parseFloat(row[1]);
      if (contract && !isNaN(price) && price > 0) {
        prices[contract] = price;
      }
    });
    return ContentService
      .createTextOutput(JSON.stringify(prices))
      .setMimeType(ContentService.MimeType.JSON);
  }

  return ContentService
    .createTextOutput(JSON.stringify({error: "unknown action"}))
    .setMimeType(ContentService.MimeType.JSON);
}

// ---------------------------------------------------------------------------
// POST — write ranked bids or append ingestion log
// body: {"action": "write_ranked", "rows": [...]}
// body: {"action": "append_log",   "row":  {...}}
// ---------------------------------------------------------------------------
function doPost(e) {
  try {
    var payload = JSON.parse(e.postData.contents);
    var action  = payload.action;
    var ss      = SpreadsheetApp.openById(SS_ID);

    if (action === "write_ranked") {
      var sheet = ss.getSheetByName("Ranked Bids");
      var rows  = payload.rows || [];
      // Clear data rows, keep header
      var lastRow = sheet.getLastRow();
      if (lastRow > 1) sheet.getRange(2, 1, lastRow - 1, 10).clearContent();
      if (rows.length > 0) {
        sheet.getRange(2, 1, rows.length, rows[0].length).setValues(rows);
      }
      return _ok("wrote " + rows.length + " rows");
    }

    if (action === "append_log") {
      var sheet = ss.getSheetByName("Ingestion Log");
      var row   = payload.row || [];
      sheet.insertRowBefore(2);
      sheet.getRange(2, 1, 1, row.length).setValues([row]);
      return _ok("appended");
    }

    return _error("unknown action: " + action);

  } catch(err) {
    return _error(err.toString());
  }
}

function _ok(msg)    { return ContentService.createTextOutput(JSON.stringify({ok: true,  msg: msg})).setMimeType(ContentService.MimeType.JSON); }
function _error(msg) { return ContentService.createTextOutput(JSON.stringify({ok: false, msg: msg})).setMimeType(ContentService.MimeType.JSON); }
