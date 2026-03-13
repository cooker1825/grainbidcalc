/**
 * GrainBidCalc — Google Sheets Setup Script
 *
 * Paste into script.google.com → Run → approve permissions.
 * Creates "GrainBidCalc — Mapleview Grain" in your Drive with 4 formatted tabs.
 * After running, copy the SHEETS_ID from the popup into your .env file.
 */

function createGrainBidCalcSheet() {
  var ss = SpreadsheetApp.create("GrainBidCalc \u2014 Mapleview Grain");
  var ssId = ss.getId();

  // Rename default sheet and add the rest
  var futures  = ss.getSheets()[0];  futures.setName("Futures Prices");
  var ranked   = ss.insertSheet("Ranked Bids");
  var farmers  = ss.insertSheet("Farmer Contacts");
  var log      = ss.insertSheet("Ingestion Log");

  setupFuturesTab(futures);
  setupRankedTab(ranked);
  setupFarmersTab(farmers);
  setupLogTab(log);

  // Move to a sensible order
  ss.setActiveSheet(futures);
  ss.moveActiveSheet(1);

  var url = "https://docs.google.com/spreadsheets/d/" + ssId;
  console.log("=== DONE ===");
  console.log("SHEETS_ID=" + ssId);
  console.log("URL: " + url);
}

// ---------------------------------------------------------------------------
// Tab 1: Futures Prices
// ---------------------------------------------------------------------------
function setupFuturesTab(sheet) {
  var headers = ["Contract", "Price (USD/BU)", "Notes"];
  var contracts = [
    ["ZSH26", "", "Soybeans (CBOT) — Mar 2026"],
    ["ZSK26", "", "Soybeans (CBOT) — May 2026"],
    ["ZSN26", "", "Soybeans (CBOT) — Jul 2026"],
    ["ZSX26", "", "Soybeans (CBOT) — Nov 2026"],
    ["ZCH26", "", "Corn (CBOT) — Mar 2026"],
    ["ZCK26", "", "Corn (CBOT) — May 2026"],
    ["ZCN26", "", "Corn (CBOT) — Jul 2026"],
    ["ZCZ26", "", "Corn (CBOT) — Dec 2026"],
    ["ZWH26", "", "Wheat SRW (CBOT) — Mar 2026"],
    ["ZWN26", "", "Wheat SRW (CBOT) — Jul 2026"],
    ["ZWZ26", "", "Wheat SRW (CBOT) — Dec 2026"],
    ["RSK26", "", "Canola (ICE) — May 2026"],
    ["RSN26", "", "Canola (ICE) — Jul 2026"],
    ["RSX26", "", "Canola (ICE) — Nov 2026"],
  ];

  // Headers
  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground("#1e6432").setFontColor("#ffffff").setFontWeight("bold")
             .setHorizontalAlignment("center");
  sheet.setFrozenRows(1);

  // Data
  sheet.getRange(2, 1, contracts.length, 3).setValues(contracts);

  // Column B: number format for prices
  sheet.getRange(2, 2, contracts.length, 1).setNumberFormat("0.0000");

  // Highlight column B (user input) with light yellow
  sheet.getRange(2, 2, contracts.length, 1).setBackground("#fffde7");

  // Column widths
  sheet.setColumnWidth(1, 100);
  sheet.setColumnWidth(2, 140);
  sheet.setColumnWidth(3, 270);

  // Instruction note in D1
  sheet.getRange("D1").setValue("← Enter today's prices in column B");
  sheet.getRange("D1").setFontColor("#b71c1c").setFontWeight("bold");
}

// ---------------------------------------------------------------------------
// Tab 2: Ranked Bids
// ---------------------------------------------------------------------------
function setupRankedTab(sheet) {
  var headers = [
    "Commodity", "Delivery Month", "Rank", "Location", "Bid Type",
    "CAD Basis", "US Basis", "Live Cash (CAD/BU)", "Mapleview Price (CAD/BU)",
    "Calculated At"
  ];
  var widths = [110, 130, 60, 110, 90, 100, 100, 150, 175, 160];

  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground("#284f78").setFontColor("#ffffff").setFontWeight("bold")
             .setHorizontalAlignment("center");
  sheet.setFrozenRows(1);

  for (var i = 0; i < widths.length; i++) {
    sheet.setColumnWidth(i + 1, widths[i]);
  }

  sheet.getRange("A2").setValue("(System will populate this tab every 30 min during market hours)");
  sheet.getRange("A2").setFontColor("#888888").setFontStyle("italic");
}

// ---------------------------------------------------------------------------
// Tab 3: Farmer Contacts
// ---------------------------------------------------------------------------
function setupFarmersTab(sheet) {
  var headers = [
    "Name", "Farm Name", "Phone", "Email", "Region", "Location",
    "Preferred Channel", "Commodities", "Bid Types", "Active"
  ];
  var widths = [140, 160, 130, 200, 110, 130, 130, 160, 100, 70];
  var notes  = [
    "", "", "+15195551234", "", "SW Ontario", "Kerwood, ON",
    "sms or email", "soybeans,corn", "elevator,delivered", "TRUE"
  ];

  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground("#a64d1c").setFontColor("#ffffff").setFontWeight("bold")
             .setHorizontalAlignment("center");
  sheet.setFrozenRows(1);

  for (var i = 0; i < widths.length; i++) {
    sheet.setColumnWidth(i + 1, widths[i]);
  }

  // Example row (greyed out as a placeholder)
  sheet.getRange(2, 1, 1, notes.length).setValues([notes]);
  sheet.getRange(2, 1, 1, notes.length).setFontColor("#aaaaaa").setFontStyle("italic");

  // Data validation for Preferred Channel
  var channelRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["sms", "email", "both"], true).build();
  sheet.getRange(3, 7, 200, 1).setDataValidation(channelRule);

  // Data validation for Active
  var activeRule = SpreadsheetApp.newDataValidation()
    .requireValueInList(["TRUE", "FALSE"], true).build();
  sheet.getRange(3, 10, 200, 1).setDataValidation(activeRule);
}

// ---------------------------------------------------------------------------
// Tab 4: Ingestion Log
// ---------------------------------------------------------------------------
function setupLogTab(sheet) {
  var headers = ["Timestamp", "Source Type", "Buyer / Sender", "Status", "Bids Stored", "Notes"];
  var widths  = [175, 110, 210, 90, 100, 260];

  var headerRange = sheet.getRange(1, 1, 1, headers.length);
  headerRange.setValues([headers]);
  headerRange.setBackground("#444444").setFontColor("#ffffff").setFontWeight("bold")
             .setHorizontalAlignment("center");
  sheet.setFrozenRows(1);

  for (var i = 0; i < widths.length; i++) {
    sheet.setColumnWidth(i + 1, widths[i]);
  }

  sheet.getRange("A2").setValue("(System will append rows here after each ingestion)");
  sheet.getRange("A2").setFontColor("#888888").setFontStyle("italic");
}
