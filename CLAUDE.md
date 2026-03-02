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

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Runtime | Python 3.11+ |
| Web Framework | FastAPI |
| Database | Supabase (PostgreSQL) |
| Task Queue | Celery + Redis |
| LLM Parsing | Claude API (claude-sonnet-4-20250514) |
| OCR | Tesseract + pdf2image |
| SMS | Twilio |
| Email | Google Workspace API |
| Futures Data | CQG API |
| Exchange Rate | Bank of Canada API |
| Frontend | Jinja templates (admin dashboard) |

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run FastAPI dev server
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker
celery -A workers.celery_app worker --loglevel=info

# Run Celery beat scheduler
celery -A workers.celery_app beat --loglevel=info

# Seed initial data
python scripts/seed_commodities.py
python scripts/seed_buyers.py

# Test parser against sample bid sheets
python scripts/test_parse.py

# Run tests
pytest tests/
```

## Architecture

```
[Bid Arrives: email / SMS / web scrape / manual upload]
  → ingestion/router.py (identify buyer, preprocess)
  → parsing/llm_parser.py (Claude API → structured JSON)
  → parsing/normalizer.py (units, contracts, delivery months)
  → parsing/validator.py (flag anomalies, confidence check)
  → BACK-CALCULATE BASIS if cash-price-only source (see critical rule below)
  → db: store basis_bids record
  → calculation/ranking.py (re-rank on new bid arrival)

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

### Back-calculation (cash-price-only sources e.g. Sarnia email)
When a source provides ONLY a cash price (no basis), the router MUST immediately
back-calculate the basis using the LIVE futures and FX at that exact moment:
```
CAD Basis = Cash Price (CAD) − Futures Price (USD)
US Basis  = (Cash Price (CAD) ÷ FX Rate) − Futures Price (USD)
```
Store the basis, `was_back_calculated=True`, and the futures/FX snapshot used.
The cash price itself is NOT stored as a durable value.

### US Basis is the analytical truth
A "positive" CAD basis can be an illusion caused by a weak Canadian dollar.
US Basis strips out FX and shows true local demand vs the US market.
Strong US Basis (+0.50+) = buyer urgently needs grain.
Weak US Basis (−0.50 or worse) = buyer has supply, not competing hard.

### Three bid types (farmer-facing)
1. **Elevator** — farmer delivers to Mapleview's facility
2. **Delivered** — farmer delivers to a Mapleview-specified location (e.g., Windsor)
3. **FOB** — Mapleview arranges pickup from the farmer's farm

### Farmer privacy rule
Delivery locations are town/city names only (Windsor, Hamilton, London).
NEVER expose end-buyer names (ADM, Ingredion, etc.) to farmers.

## Module Overview

| Module | Responsibility |
|--------|---------------|
| `config/` | App settings, commodity defs, futures contract normalization rules |
| `db/` | Supabase connection, SQL queries, migrations |
| `ingestion/` | Email (Gmail), SMS (Twilio webhook), web scraping, manual upload, routing |
| `parsing/` | Claude API bid extraction, prompt templates, normalizer, validator, buyer profiles |
| `calculation/` | US basis, cash price, ranking, aggression, futures feed, exchange rate |
| `distribution/` | SMS/email outbound, message formatting, scheduler, threshold triggers |
| `api/` | FastAPI app, all REST endpoints, Twilio/email webhooks |
| `dashboard/` | Jinja admin UI: ranked bids, US basis heatmap, aggression matrix, farmer prefs |
| `workers/` | Celery app, async tasks, beat schedule |
| `scripts/` | Seed data, test parse |
| `tests/` | pytest suite + sample bid sheets |

## Key Files

- `parsing/prompt_templates.py` — LLM prompts (SYSTEM_PROMPT + EXTRACTION_PROMPT). Most critical file.
- `parsing/buyer_profiles.py` — Per-buyer format hints for the LLM parser
- `parsing/normalizer.py` — Unit conversion (CAD/MT↔CAD/BU), contract code normalization
- `calculation/price_calculator.py` — All pricing math: US basis, cash price, back-calculation
- `db/migrations/001_initial_schema.sql` — Full PostgreSQL schema
- `workers/beat_schedule.py` — Scheduled task definitions

## Known Buyer Sources

| Buyer | Source Type | Format |
|-------|------------|--------|
| ADM Windsor | email + web scrape | HTML table, CAD/BU |
| G3 Canada | email | Spreadsheet/image, H26/K26 contract codes |
| Farm Market News (OMAFRA) | email (PDF) | Multi-page PDF, CBOT fractional prices |
| Great Lakes Grain (Dutton) | web scrape | HTML, @C6H/@S6H contract codes |
| Sarnia Buyer | email | Plain text, FLAT CASH PRICE ONLY — must back-calculate basis |
| Hamilton | email | Spreadsheet image, USD/BU basis — needs FX conversion |

## Futures Contract Normalization

All contracts normalized to standard: `ZS`/`ZC`/`ZW`/`KE`/`RS` + month code + 2-digit year
```
Month codes: F=Jan G=Feb H=Mar J=Apr K=May M=Jun N=Jul Q=Aug U=Sep V=Oct X=Nov Z=Dec
Great Lakes: @C6H → ZCH26 (@=prefix, C=corn/S=soy/W=wheat, 6=2026, H=month)
G3 format:   H26  → ZSH26 (needs commodity context)
Fractional:  426'2s → (426 + 2/8) / 100 = $4.2625 (CBOT eighths-of-a-cent)
```

## Configuration

All secrets in `.env` (gitignored). See `.env.example` for required variables.
Config loaded via `config/settings.py` using python-dotenv.

## Deployment

Runs on DigitalOcean droplet `159.89.127.66` alongside GrainBot and n8n.

```bash
# Deploy from local machine
bash deploy/deploy.sh 159.89.127.66

# Server management
ssh root@159.89.127.66
systemctl status grainbidcalc
journalctl -u grainbidcalc -f
```

**GitHub repo:** (to be created — private)
