# CLAUDE.md

This file provides guidance to Claude Code when working in this repository.
Full architecture and design is in `architecture.md`.

## What This Is

GrainBidCalc — automated grain bid aggregation, calculation, and farmer distribution
platform for Mapleview Grain. Ingests basis bids from 20-30 end-user buyers via email,
SMS, and web scraping. Normalizes, ranks, applies Mapleview's margin (aggression),
calculates live cash prices from futures + FX, and distributes Mapleview-branded prices
to farmers via SMS, email, and Grain Discovery.

**Business model:** Mapleview is the sole counterparty to the farmer. Farmers sell to
Mapleview; Mapleview fulfills contracts with end-user buyers. End-buyer names are NEVER
shown to farmers — they only see Mapleview's price and a delivery location (town/city).

## Current Status (2026-03-11)

### Working
- ✅ End-to-end email pipeline: IMAP → LLM parse → normalize → resolve IDs → Supabase → SharePoint XLSX
- ✅ IMAP email polling (HostPapa, `mapleviewgrain.ca:993`) every 5 min via Celery beat
- ✅ LLM parser (claude-sonnet-4-20250514, extended output beta `output-128k-2025-02-19`)
- ✅ Web scrapers: DG Global (HTML/JSON) + HDC (DTN API) — structured, no LLM cost
- ✅ SharePoint XLSX via Microsoft Graph API (read futures + write bids remotely)
- ✅ Staleness filtering: buyer tab Col H = NA() if bid >3 days old → excluded from Master ranking
- ✅ Bid timestamps: Col M written alongside Col D basis on every bid write
- ✅ 48+ buyers seeded (Ontario Farm Market News locations + 10 major buyers added for scrapers)
- ✅ 7 commodities: soybeans, corn, srw_wheat, hrw_wheat, swr_wheat, canola, wheat_general
- ✅ All 14 buyer tabs scaffolded with formulas/CQG codes (via `data/scaffold_tabs.py`)
- ✅ Supabase RLS enabled on all 12 tables with permissive policies
- ✅ Idempotent re-scraping via `upsert_bid()` (same buyer/commodity/month/dest/date = update)
- ✅ systemd services: grainbidcalc-api (port 8000), grainbidcalc-worker, grainbidcalc-beat

### In Progress / Next Session
- ⏳ Buyer profiles: need sample bids from each buyer to build parsing profiles
- ⏳ Farm Market News: extract Middlesex avg for old/new crop corn, soybeans, SRW wheat
- ⏳ SMS distribution to farmers (Twilio configured, not yet tested end-to-end)
- ⏳ Per-destination aggression margins (flat -0.05 CAD/BU for now)
- ⏳ Farmer contacts seed + SMS distribution test
- ⏳ Review freight rates (currently estimates: $8/mt DG Global dests, $10/mt Hensall dests)

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.12 |
| Web Framework | FastAPI + uvicorn |
| Database | Supabase (PostgreSQL) |
| Task Queue | Celery + Redis (redis://localhost:6379/0) |
| LLM Parsing | Claude API (claude-sonnet-4-20250514) |
| SMS | Twilio (+12394229925) |
| Email | IMAP (mapleviewgrain.ca:993, markets@mapleviewgrain.ca) |
| Futures Data | SharePoint XLSX with CQG add-in via Microsoft Graph API |
| SharePoint | Microsoft Graph API (Azure app `GrainBidCalc`, client credentials flow) |
| Web Scraping | httpx — DG Global (HTML), HDC (DTN API) |
| Exchange Rate | Bank of Canada API |
| Frontend | Jinja templates (admin dashboard) |

## Commands

```bash
# Always prefix with PYTHONPATH
PYTHONPATH=/opt/grainbidcalc venv/bin/python <script>

# Services
systemctl status grainbidcalc-api grainbidcalc-worker grainbidcalc-beat
journalctl -u grainbidcalc-worker -f

# Manual email poll
PYTHONPATH=/opt/grainbidcalc venv/bin/python -c "
import asyncio; from ingestion.email_listener import poll_email_inbox
print(asyncio.run(poll_email_inbox()))"

# Check IMAP connection
PYTHONPATH=/opt/grainbidcalc venv/bin/python -c "
import asyncio; from ingestion.email_listener import test_connection
print(asyncio.run(test_connection()))"
```

## Architecture

```
[Bid Arrives: email / SMS / manual upload]
  → ingestion/router.py (identify buyer, preprocess)
  → parsing/llm_parser.py (Claude API → structured JSON)
  → parsing/normalizer.py (units, contracts, delivery months)
  → db/queries.py: resolve_buyer_id() + resolve_commodity_id()
  → parsing/validator.py (flag anomalies, confidence check)
  → BACK-CALCULATE BASIS if cash-price-only source
  → db: insert_bid() → basis_bids
  → data/onedrive_writer.py: write CAD basis (col D) + timestamp (col M) to SharePoint XLSX

[Bid Arrives: web scraper (DG Global, HDC)]
  → ingestion/scrapers/<buyer>.py: fetch + extract structured bids (no LLM)
  → parsing/normalizer.py → resolve IDs → validator
  → db: upsert_bid() (idempotent same-day re-scrapes)
  → data/onedrive_writer.py: write to SharePoint XLSX

[Distribution trigger: scheduled / on-demand / threshold]
  → calculation/price_calculator.py (live cash = stored basis + live futures + FX)
  → calculation/aggression.py (apply Mapleview margin)
  → distribution/formatter.py (personalized per farmer preferences)
  → distribution/sms_sender.py + email_sender.py
  → db: log to distribution_log
```

## Critical Business Rules

### BASIS is the durable data point — NEVER store cash prices as durable values
```
CAD Basis        = CAD Cash Price − USD Futures Price      (simple subtraction, no FX)
US Basis         = (CAD Cash Price ÷ FX Rate) − USD Futures (strips out currency)
Live Cash Price  = Stored CAD Basis + Live USD Futures      (calculated on the fly)
Mapleview Price  = Live Cash Price + Aggression Adjustment
```

### Futures price units (CRITICAL)
XLSX prices from CQG add-in are **already in USD/BU** (e.g., corn ~4.60, soy ~12.00).
NO ÷100 conversion needed — `data/onedrive_reader.py` / `data/xlsx_reader.py` return prices as-is.
CQG uses 3-char prefixes (ZCE/ZSE/ZWA) → mapped to 2-char (ZC/ZS/ZW) by the reader.
ICE canola (RS) is not in the XLSX — falls back to DB cache.

### Back-calculation (cash-price-only sources e.g. Sarnia email)
When a source provides ONLY a cash price (no basis), the router MUST immediately
back-calculate the basis using the LIVE futures and FX at that exact moment.
Store the basis, `was_back_calculated=True`, and the futures/FX snapshot used.

### US Basis is the analytical truth
A "positive" CAD basis can be an illusion caused by a weak Canadian dollar.
US Basis strips out FX and shows true local demand vs the US market.

### Farmer privacy rule
Delivery locations are town/city names only (Windsor, Hamilton, London).
NEVER expose end-buyer names (ADM, Ingredion, etc.) to farmers.

## Key Files

- `ingestion/router.py` — main pipeline, step 8 writes bids to DB + SharePoint XLSX
- `ingestion/email_listener.py` — IMAP poller (HostPapa, not Gmail API)
- `ingestion/web_scraper.py` — orchestrates both LLM-based and structured web scrapers
- `ingestion/scrapers/dg_global.py` — DG Global scraper (HTML/JSON, CAD/BU)
- `ingestion/scrapers/hdc.py` — HDC/Hensall scraper (DTN API, USD/BU)
- `parsing/llm_parser.py` — Claude API call, extended output beta, truncation recovery
- `parsing/prompt_templates.py` — SYSTEM_PROMPT + EXTRACTION_PROMPT (most critical)
- `parsing/buyer_profiles.py` — per-buyer LLM hints; farm_market_news has multi_location=True
- `parsing/normalizer.py` — unit conversion, contract normalization
- `db/queries.py` — resolve IDs, insert_bid(), upsert_bid() (idempotent)
- `data/onedrive_writer.py` — writes basis (col D) + timestamp (col M) to SharePoint XLSX via Graph API
- `data/onedrive_reader.py` — reads futures prices from SharePoint XLSX via Graph API
- `data/xlsx_reader.py` — reads futures from local XLSX (fallback/dev)
- `data/xlsx_writer.py` — writes to local XLSX (fallback/dev), buyer→tab mapping
- `data/setup_staleness_formulas.py` — one-time: set Col H staleness formula on all buyer tabs
- `data/scaffold_tabs.py` — one-time: set up empty buyer tabs from Ingredion template
- `calculation/futures_feed.py` — OneDrive first → local XLSX → DB cache fallback
- `calculation/ranking.py` — rank_bids() + get_ranked_bids() for all months
- `workers/beat_schedule.py` — all Celery periodic task schedules
- `config/settings.py` — all env vars (IMAP, MS Graph, Supabase, etc.)

## Known Fixes (don't repeat these mistakes)

- LLM parser: use `client.beta.messages.create` with `betas=["output-128k-2025-02-19"]`
- JSON extraction: if no `]` found, find last `}` and append `]` (handles truncation)
- `resolve_buyer_id`: normalized matching strips non-alphanumeric via `_norm()`
- `maybe_single()` returns `None` (not object) when no row found — check `if result and result.data`
- Farm Market News: all bids attributed to individual locations, not to "Farm Market News"
- XLSX futures are already USD/BU — do NOT divide by 100 (old Google Sheets used cents)
- `get_ranked_bids` in ranking.py (not `rank_bids`) is what tasks.py imports

## XLSX Workbook (SharePoint: `grainbidcalculator.xlsx`)

Hosted on SharePoint (`mapleviewfarms1825.sharepoint.com`), accessed via Microsoft Graph API.
Jeff keeps it open on desktop with CQG toolkit for live futures in Col C.

- **Master tab**: all formulas — auto-ranks bids across buyer tabs (NEVER overwrite)
  - Col I = best net US basis (MAX across buyers, net of freight via VLOOKUP to Freight tab)
  - Cols D, E, H, J, K = formulas pulling from winning buyer tab
  - VLOOKUP range: `Freight!$A$4:$G$20` (expanded for new scraper destinations)
- **Buyer tabs** (Ingredion, Cargill, HDC, VDB, P&H, ADM, DG Global, Scoular, GLG, Andersons, G3, Richardsons, Broadgrain, HG):
  - Col A = delivery month name, Col B = CQG futures code (static)
  - Col C = CQG live futures formula (add-in), Col D = **CAD Basis (bid data — write here)**
  - Col E = premium/aggression (static), Cols F-G, L = calculation formulas
  - Col H = US Basis: `=IF(OR(D="",D=0,M="",NOW()-M>3),NA(),G-C)` — stale bids (>3 days) → NA() → excluded from Master
  - Col M = **Last Updated** timestamp (Excel serial date, written by server alongside basis)
  - 3 commodity sections per tab: Corn (rows 7-28), Soybeans (rows 36-57), Wheat (rows 65-86)
- **Freight tab**: freight rates per destination per commodity ($/mt and $/bu)
  - Original: London, Sarnia, Aylmer. Added: Becher, Princeton, Shetland, Staples, Talbotville ($8/mt), Hensall, HC Locations ($10/mt)
- **Futures Month Codes tab**: CQG ticker reference
- **Buyer→Tab mapping** (in `data/xlsx_writer.py`): ADM Windsor→ADM, Great Lakes Grain→GLG,
  Hensall District→HDC, VDB Grain→VDB, Hoffsuemmer→HG, G3 Canada→G3, etc.
- **Month→Row**: base year 2026. March=offset 0, Dec=offset 9, Jan(+1)=offset 10, Dec(+1)=offset 21
- **Graph API notes**: URL-encode tab names (P&H → `P%26H`), use `quote(tab_name, safe="")` in Python

## Deployment

Runs on DigitalOcean droplet alongside GrainBot and n8n.
Server: `159.89.127.66`
Services auto-start on reboot (systemd enabled).

## Known Buyer Sources

| Buyer | Source | Notes |
|-------|--------|-------|
| ADM Windsor | email | HTML table, CAD/BU |
| G3 Canada | email | Spreadsheet/image |
| Farm Market News (OMAFRA) | email | Multi-location digest, extract each location separately |
| Great Lakes Grain (Dutton) | email (jeff@mapleviewfarms.ca forwards) | FOB bids |
| Sarnia Buyer | email | Flat cash price only — back-calculate basis |
| Hamilton Buyer | email | Spreadsheet image, USD/BU basis |
| DG Global | web scraper | `ingestion/scrapers/dg_global.py` — HTML/JSON, CAD/BU, 5 destinations |
| HDC (Hensall) | web scraper | `ingestion/scrapers/hdc.py` — DTN API, USD/BU (normalizer converts) |
| Ingredion | not scraped | Bushel platform requires OAuth account — skip |
| HG (Hoffsuemmer) | not scraped | Grain Discovery requires login — skip for now |

## Aggression (Mapleview Margin)

Currently flat `-0.05 CAD/BU` across all destinations.
Per-destination margins deferred — user to revisit later.
`calculation/aggression.py` + `aggression_params` table in DB.
