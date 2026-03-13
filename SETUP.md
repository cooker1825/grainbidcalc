# GrainBidCalc — Setup Guide

Complete step-by-step instructions to go from a fresh scaffold to a fully running system.
Work through each section in order. Don't skip ahead — later steps depend on earlier ones.

---

## Table of Contents

1. [Accounts & Services to Create](#1-accounts--services-to-create)
2. [Supabase (Database)](#2-supabase-database)
3. [Anthropic API Key (LLM Parsing)](#3-anthropic-api-key-llm-parsing)
4. [Twilio (SMS)](#4-twilio-sms)
5. [Email Inbox (IMAP)](#5-email-inbox-imap)
6. [SharePoint XLSX via Microsoft Graph API](#6-sharepoint-xlsx-via-microsoft-graph-api-futures-prices--bid-writes)
7. [Bank of Canada API (Exchange Rate)](#7-bank-of-canada-api-exchange-rate)
8. [Local Development Setup](#8-local-development-setup)
9. [Configure .env](#9-configure-env)
10. [Run Database Migrations & Seed Data](#10-run-database-migrations--seed-data)
11. [Test the Parser](#11-test-the-parser)
12. [Server Deployment (DigitalOcean)](#12-server-deployment-digitalocean)
13. [Configure Systemd Services](#13-configure-systemd-services)
14. [Set Up Nightly GitHub Backup](#14-set-up-nightly-github-backup)
15. [Add Your First Farmer](#15-add-your-first-farmer)
16. [End-to-End Test](#16-end-to-end-test)
17. [Go-Live Checklist](#17-go-live-checklist)

---

## 1. Accounts & Services to Create

Before writing a single line of config, make sure you have accounts for everything below.

| Service | URL | What it's used for | Cost |
|---------|-----|--------------------|------|
| Supabase | supabase.com | PostgreSQL database | Free tier OK to start |
| Anthropic | console.anthropic.com | Claude API for LLM parsing | Pay-as-you-go |
| Twilio | twilio.com | Inbound bid SMS + outbound farmer SMS | ~$20-40/mo |
| HostPapa (IMAP) | mapleviewgrain.ca:993 | markets@ email inbox polling | Already have |
| Microsoft Azure | portal.azure.com | Graph API for SharePoint XLSX (futures + bid writes) | Free |
| GitHub | github.com | Already done | Free |
| DigitalOcean | digitalocean.com | Already have | Already running |

---

## 2. Supabase (Database)

### 2.1 Create a new Supabase project

1. Go to [supabase.com](https://supabase.com) and sign in
2. Click **New Project**
3. Name it `grainbidcalc`
4. Choose a strong database password — save it somewhere safe
5. Region: **Canada (Central)** if available, otherwise US East
6. Click **Create new project** — wait ~2 minutes for it to spin up

### 2.2 Get your credentials

Once the project is ready:

1. In the left sidebar, click **Settings** → **API**
2. Copy the following — you'll need them in Step 9:
   - **Project URL** → this is your `SUPABASE_URL`
   - **anon / public key** → this is your `SUPABASE_ANON_KEY`
   - **service_role key** (click to reveal) → this is your `SUPABASE_KEY`
   > Keep the service_role key secret. It bypasses row-level security.

### 2.3 Run the database migrations

1. In the Supabase sidebar, click **SQL Editor**
2. Click **New query**
3. Open the file `db/migrations/001_initial_schema.sql` from this repo
4. Copy the entire contents and paste into the SQL editor
5. Click **Run** (or press Cmd/Ctrl + Enter)
6. You should see: `Success. No rows returned`
7. Verify by clicking **Table Editor** in the sidebar — you should see all tables listed:
   `buyers`, `commodities`, `basis_bids`, `aggression_params`, `futures_prices`,
   `exchange_rates`, `farmer_contacts`, `farmer_bid_preferences`, `bid_destinations`,
   `us_basis_history`, `distribution_log`, `ingestion_log`

---

## 3. Anthropic API Key (LLM Parsing)

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign in (or create account)
3. Click **API Keys** in the left sidebar
4. Click **Create Key**
5. Name it `grainbidcalc-production`
6. Copy the key immediately — it's only shown once
7. Save it as `ANTHROPIC_API_KEY` for Step 9

> The parser uses `claude-sonnet-4-20250514`. Budget ~$5-15/month for 100 parses/day.

---

## 4. Twilio (SMS)

### 4.1 Create account and buy a phone number

1. Go to [twilio.com](https://twilio.com) and sign in
2. From the Console dashboard, note your:
   - **Account SID** → `TWILIO_ACCOUNT_SID`
   - **Auth Token** (click to reveal) → `TWILIO_AUTH_TOKEN`
3. In the left sidebar: **Phone Numbers** → **Manage** → **Buy a number**
4. Search for a Canadian number (+1) in your area code
5. Make sure it has **SMS** capability checked
6. Buy it (~$1.50/month)
7. Copy the phone number → `TWILIO_PHONE_NUMBER`

### 4.2 Configure the SMS webhook (do this after Step 12 — server is running)

Once your server is live at your DigitalOcean IP:

1. Go to **Phone Numbers** → **Manage** → **Active numbers**
2. Click your number
3. Under **Messaging** → **A message comes in**:
   - Set to **Webhook**
   - URL: `http://159.89.127.66:8000/api/webhooks/sms`
   - Method: **HTTP POST**
4. Click **Save**

> From now on, any SMS sent to this number is automatically processed as a bid.
> Tell buyers (or yourself) to forward bid sheets to this number.

---

## 5. Email Inbox (IMAP)

The system polls `markets@mapleviewgrain.ca` via IMAP for inbound bid emails.
Hosted on HostPapa (not Google Workspace — no Gmail API needed).

### 5.1 Get IMAP credentials

1. Log in to your HostPapa email admin panel
2. Note the IMAP settings:
   - **Host**: `mapleviewgrain.ca` (port 993, SSL)
   - **User**: `markets@mapleviewgrain.ca`
   - **Password**: your email account password

### 5.2 Update .env

```bash
IMAP_HOST=mapleviewgrain.ca
IMAP_PORT=993
IMAP_USER=markets@mapleviewgrain.ca
IMAP_PASSWORD=your-email-password
```

### 5.3 Test the connection

```bash
PYTHONPATH=/opt/grainbidcalc venv/bin/python -c "
import asyncio; from ingestion.email_listener import test_connection
print(asyncio.run(test_connection()))"
```

> The Celery beat scheduler polls every 5 minutes. Processed emails are marked as read.

---

## 6. SharePoint XLSX via Microsoft Graph API (Futures Prices + Bid Writes)

The XLSX workbook is hosted on SharePoint. Jeff keeps it open on his desktop with CQG toolkit
providing live futures in Col C. The server reads futures from it and writes basis bids (Col D)
+ timestamps (Col M) back to it via the Microsoft Graph API.

### 6.1 Register an Azure app

1. Go to [portal.azure.com](https://portal.azure.com) → **Azure Active Directory** → **App registrations**
2. Click **New registration**
3. Name: `GrainBidCalc`
4. Supported account types: **Single tenant**
5. Click **Register**
6. Note the **Application (client) ID** and **Directory (tenant) ID**

### 6.2 Create a client secret

1. In your app → **Certificates & secrets** → **New client secret**
2. Description: `grainbidcalc-prod`, Expiry: 24 months
3. Copy the secret **Value** immediately (shown only once)

### 6.3 Grant API permissions

1. In your app → **API permissions** → **Add a permission** → **Microsoft Graph**
2. Choose **Application permissions** and add:
   - `Files.ReadWrite.All`
   - `Sites.ReadWrite.All`
   - `User.Read.All`
3. Click **Grant admin consent** (requires admin)

### 6.4 Update .env

```bash
MS_TENANT_ID=your-tenant-id
MS_CLIENT_ID=your-client-id
MS_CLIENT_SECRET=your-client-secret
```

### 6.5 Find the Drive ID and File Item ID

The server needs the SharePoint drive ID and file item ID. These are already configured in
`data/onedrive_writer.py` and `data/onedrive_reader.py`. If you need to find them for a
different file, use the Graph API explorer or the scripts in `data/`.

### 6.6 How it works

- `data/onedrive_reader.py` reads futures prices from the XLSX via Graph API
- `data/onedrive_writer.py` writes CAD basis (Col D) + timestamp (Col M) to buyer tabs
- `calculation/futures_feed.py` tries OneDrive first → local XLSX fallback → DB cache
- Tab names with special characters (P&H) are URL-encoded (`P%26H`) for the Graph API
- Celery beat fetches futures every 5 min during market hours (Mon–Fri 8:30 AM–3 PM ET)

---

## 7. Bank of Canada API (Exchange Rate)

No setup required — this is a free public API with no authentication.

The system fetches USD/CAD from:
```
https://www.bankofcanada.ca/valet/observations/FXUSDCAD/json?recent=1
```

To manually seed the exchange rate until the Celery task is running:
```sql
INSERT INTO exchange_rates (pair, rate) VALUES ('USD/CAD', 1.369);
```
Update this value to the current rate each morning until Celery is running.

---

## 8. Local Development Setup

Do this on your **local machine** (Windows/Mac) for development and testing.

### 8.1 Clone the repo

```bash
git clone git@github.com:cooker1825/grainbidcalc.git
cd grainbidcalc
```

### 8.2 Create a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # Mac/Linux
# or on Windows:
venv\Scripts\activate
```

### 8.3 Install dependencies

```bash
pip install -r requirements.txt
```

For PDF processing, you also need system packages:
```bash
# Mac
brew install tesseract poppler

# Ubuntu/Debian (already handled by setup-server.sh on the droplet)
apt-get install tesseract-ocr poppler-utils
```

---

## 9. Configure .env

### 9.1 Copy the example file

```bash
cp .env.example .env
```

### 9.2 Fill in every value

Open `.env` and fill in the credentials gathered from the steps above:

```bash
# Supabase — from Step 2
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your-service-role-key
SUPABASE_ANON_KEY=your-anon-key

# Anthropic — from Step 3
ANTHROPIC_API_KEY=sk-ant-...

# Twilio — from Step 4
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1...

# IMAP Email — from Step 5
IMAP_HOST=mapleviewgrain.ca
IMAP_PORT=993
IMAP_USER=markets@mapleviewgrain.ca
IMAP_PASSWORD=your-email-password

# Microsoft Graph API (SharePoint XLSX) — from Step 6
MS_TENANT_ID=your-azure-tenant-id
MS_CLIENT_ID=your-azure-app-client-id
MS_CLIENT_SECRET=your-azure-client-secret

# Redis
REDIS_URL=redis://localhost:6379/0

# App
APP_HOST=0.0.0.0
APP_PORT=8000
APP_ENV=production
SECRET_KEY=generate-a-random-string-here
```

> To generate a SECRET_KEY: `python3 -c "import secrets; print(secrets.token_hex(32))"`

### 9.3 Verify the connection

```bash
python3 -c "from db.connection import get_client; c = get_client(); print('Supabase connected')"
```

---

## 10. Run Database Migrations & Seed Data

(Already ran the SQL in Step 2.3. This step seeds the initial data via Python.)

### 10.1 Seed commodities

```bash
python scripts/seed_commodities.py
```

Expected output:
```
Seeded commodity: Soybeans
Seeded commodity: Corn
Seeded commodity: SRW Wheat
Seeded commodity: HRW Wheat
Seeded commodity: SWR Wheat
Seeded commodity: Canola
```

### 10.2 Seed buyers

```bash
python scripts/seed_buyers.py
```

Expected output:
```
Seeded buyer: ADM Windsor
Seeded buyer: G3 Canada Limited
Seeded buyer: Farm Market News (OMAFRA)
Seeded buyer: Great Lakes Grain
Seeded buyer: Sarnia Grain Buyer
Seeded buyer: Hamilton Buyer
```

### 10.3 Verify in Supabase

Open Supabase → Table Editor → `commodities` and `buyers` tables.
You should see all rows populated.

### 10.4 Seed aggression parameters (your margin)

In the Supabase SQL editor, insert your starting aggression values.
These are the CAD/BU adjustments Mapleview adds on top of the best buyer bid:

```sql
-- Example: -0.05 CAD/BU on brokered soybeans (Mapleview takes 5 cents)
-- Adjust these to your actual margins

INSERT INTO aggression_params (commodity_id, handling_type, adjustment_value, notes)
SELECT id, 'brokered', -0.05, 'Default brokered margin'
FROM commodities WHERE name = 'soybeans';

INSERT INTO aggression_params (commodity_id, handling_type, adjustment_value, notes)
SELECT id, 'brokered', -0.03, 'Default brokered margin'
FROM commodities WHERE name = 'corn';

-- Add more as needed. You can update these anytime from the dashboard.
```

### 10.5 Seed bid destinations

In Supabase SQL editor, add the known delivery destinations:

```sql
-- Get buyer IDs first
-- SELECT id, short_name FROM buyers;

-- Then insert destinations (update buyer_id UUIDs from the query above)
INSERT INTO bid_destinations (location_name, bid_type, region, commodities_accepted, internal_name, end_buyer_name)
VALUES
  ('Mapleview', 'elevator', 'SW Ontario', '{"soybeans","corn","srw_wheat"}', 'mapleview_elevator', NULL),
  ('Windsor',   'delivered', 'SW Ontario', '{"soybeans","corn","canola"}',   'adm_windsor',        'ADM'),
  ('London',    'delivered', 'SW Ontario', '{"corn"}',                        'ingredion_london',   'Ingredion'),
  ('Hamilton',  'delivered', 'SW Ontario', '{"soybeans"}',                    'hamilton_terminal',  'Terminal Buyer'),
  ('Sarnia',    'delivered', 'SW Ontario', '{"soybeans","corn","srw_wheat"}', 'sarnia_buyer',       'Sarnia Buyer');
```

---

## 11. Test the Parser

Before going live, test the LLM parser against real bid sheets.

### 11.1 Add sample bid sheets

Copy real bid files into `tests/sample_data/`:
```
tests/sample_data/adm_windsor.txt      ← paste body of a real ADM email
tests/sample_data/sarnia_email.txt     ← paste body of a real Sarnia email
tests/sample_data/farm_market_news.pdf ← a real Farm Market News PDF
tests/sample_data/g3_canada.png        ← screenshot of a G3 bid sheet
```

### 11.2 Run the test parser

```bash
# Test ADM Windsor email
python scripts/test_parse.py tests/sample_data/adm_windsor.txt email "ADM Windsor"

# Test Sarnia (cash-price-only — basis_value should be null in raw parse)
python scripts/test_parse.py tests/sample_data/sarnia_email.txt email "Sarnia"

# Test Farm Market News PDF
python scripts/test_parse.py tests/sample_data/farm_market_news.pdf email "Farm Market News"

# Test G3 screenshot
python scripts/test_parse.py tests/sample_data/g3_canada.png email "G3 Canada"
```

### 11.3 What to look for in the output

**Good output for ADM Windsor:**
```json
[{
  "buyer_name": "ADM Windsor",
  "commodity": "soybeans",
  "delivery_month": "2026-02",
  "basis_value": 4.33,
  "basis_unit": "CAD/BU",
  "futures_contract_normalized": "ZSH26",
  "confidence": 0.97
}]
```

**Good output for Sarnia (cash-price only — basis will be null):**
```json
[{
  "buyer_name": "Sarnia Buyer",
  "commodity": "soybeans",
  "basis_value": null,          ← correct — will be back-calculated
  "cash_price": 14.90,
  "confidence": 0.95
}]
```

### 11.4 If parsing looks wrong

- Check `parsing/buyer_profiles.py` — update the `format_hints` for that buyer
- Check `parsing/prompt_templates.py` — adjust the rules section if needed
- Re-run until output is clean

### 11.5 Run unit tests

```bash
pytest tests/test_calculator.py tests/test_normalizer.py -v
```

All tests should pass before deploying.

---

## 12. Server Deployment (DigitalOcean)

The server at `159.89.127.66` already runs GrainBot and n8n. GrainBidCalc runs alongside them.

### 12.1 Copy project files to the server

From your local machine in the project root:

```bash
bash deploy/deploy.sh 159.89.127.66
```

### 12.2 SSH into the server and run setup

```bash
ssh root@159.89.127.66
cd /opt/grainbidcalc
bash deploy/setup-server.sh
```

This installs: Python, Redis, Tesseract, poppler, creates the venv, installs all Python packages, and registers the systemd services.

### 12.3 Copy credentials to the server

From your local machine:

```bash
# Copy .env (contains IMAP, Supabase, Anthropic, MS Graph, Twilio credentials)
scp .env root@159.89.127.66:/opt/grainbidcalc/.env
```

### 12.4 Re-run seed scripts on the server

```bash
ssh root@159.89.127.66
cd /opt/grainbidcalc
venv/bin/python scripts/seed_commodities.py
venv/bin/python scripts/seed_buyers.py
```

---

## 13. Configure Systemd Services

Three services run GrainBidCalc:

| Service | What it runs |
|---------|-------------|
| `grainbidcalc` | FastAPI web server (API + dashboard) |
| `grainbidcalc-worker` | Celery worker (processes async tasks) |
| `grainbidcalc-beat` | Celery beat (scheduler — triggers email polls, scrapes, distributions) |

### 13.1 Install the service files

```bash
ssh root@159.89.127.66
cp /opt/grainbidcalc/deploy/grainbidcalc.service /etc/systemd/system/
cp /opt/grainbidcalc/deploy/grainbidcalc-worker.service /etc/systemd/system/
cp /opt/grainbidcalc/deploy/grainbidcalc-beat.service /etc/systemd/system/
systemctl daemon-reload
```

### 13.2 Start all services

```bash
systemctl enable grainbidcalc grainbidcalc-worker grainbidcalc-beat
systemctl start redis-server
systemctl start grainbidcalc
systemctl start grainbidcalc-worker
systemctl start grainbidcalc-beat
```

### 13.3 Verify everything is running

```bash
systemctl status grainbidcalc
systemctl status grainbidcalc-worker
systemctl status grainbidcalc-beat
systemctl status redis-server
```

All four should show `active (running)`.

### 13.4 Check the logs

```bash
journalctl -u grainbidcalc -f          # FastAPI server
journalctl -u grainbidcalc-worker -f   # Celery worker
journalctl -u grainbidcalc-beat -f     # Scheduler
```

### 13.5 Verify the API is responding

```bash
curl http://159.89.127.66:8000/health
# Expected: {"status":"ok"}
```

---

## 14. Set Up Nightly GitHub Backup

### 14.1 Initialize git on the server

```bash
ssh root@159.89.127.66
cd /opt/grainbidcalc
git init
git remote add origin git@github.com:cooker1825/grainbidcalc.git
git pull origin master
```

### 14.2 Add the backup cron job

```bash
crontab -e
```

Add this line:
```
0 2 * * * /bin/bash /opt/grainbidcalc/deploy/github-backup.sh >> /opt/grainbidcalc/data/backup.log 2>&1
```

Save and exit. Every night at 2 AM, any code changes are automatically committed and pushed to GitHub.

---

## 15. Add Your First Farmer

Add a farmer contact and their bid preferences so the first distribution has someone to send to.

### 15.1 Insert farmer contact

In Supabase SQL editor:

```sql
INSERT INTO farmer_contacts (name, farm_name, phone, email, region, location, preferred_channel)
VALUES ('Jeff Test', 'Mapleview Farms', '+15195551234', 'jeff@mapleviewgrain.ca', 'SW Ontario', 'Kerwood, ON', 'sms');
```

### 15.2 Set up their bid preferences

```sql
-- Get the farmer ID and commodity IDs first
SELECT id FROM farmer_contacts WHERE name = 'Jeff Test';
SELECT id, name FROM commodities;

-- Then insert preferences (replace UUIDs with real ones from above queries)
INSERT INTO farmer_bid_preferences (farmer_id, commodity_id, bid_type)
SELECT
  (SELECT id FROM farmer_contacts WHERE name = 'Jeff Test'),
  id,
  'elevator'
FROM commodities WHERE name IN ('soybeans', 'corn');
```

---

## 16. End-to-End Test

Run through the full pipeline manually before opening to real farmers.

### 16.1 Test bid ingestion

Send a test bid SMS to your Twilio number:
```
ADM Windsor Soybeans Feb'26 basis 4.33 CAD/BU ZSH26
```

Check the ingestion log in Supabase:
```sql
SELECT * FROM ingestion_log ORDER BY created_at DESC LIMIT 5;
```

Check the basis_bids table:
```sql
SELECT * FROM basis_bids ORDER BY ingested_at DESC LIMIT 5;
```

### 16.2 Manually seed a test futures price

Until CQG is connected, insert a test futures price:
```sql
INSERT INTO futures_prices (contract, price) VALUES ('ZSH26', 11.375);
INSERT INTO exchange_rates (pair, rate) VALUES ('USD/CAD', 1.369);
```

### 16.3 Test the ranking endpoint

```bash
# Get commodity_id for soybeans first
# Then call the API:
curl "http://159.89.127.66:8000/api/bids/ranked?commodity_id=<uuid>&delivery_month=2026-02"
```

You should see ranked bids with calculated cash prices and US basis values.

### 16.4 Test on-demand distribution

```bash
curl -X POST "http://159.89.127.66:8000/api/distribution/trigger"
```

Check your phone — you should receive the bid SMS.

Check the distribution log:
```sql
SELECT * FROM distribution_log ORDER BY sent_at DESC LIMIT 5;
```

---

## 17. Go-Live Checklist

Work through this before sending prices to real farmers.

### Infrastructure
- [x] Supabase project created and migrated
- [x] All tables verified in Supabase Table Editor
- [x] Commodities and buyers seeded (48+ buyers)
- [x] RLS enabled on all 12 tables
- [ ] Aggression parameters set to real margins
- [ ] Bid destinations seeded
- [x] `.env` filled in with all real credentials (IMAP, MS Graph, Supabase, Anthropic, Twilio)
- [x] All three systemd services running (`active`)
- [x] Redis running
- [x] API health check returns `{"status":"ok"}`

### Parsing
- [ ] Parser tested against real ADM Windsor email → clean output
- [ ] Parser tested against real Sarnia email → `basis_value: null`, `cash_price` populated
- [ ] Parser tested against Farm Market News PDF → multiple locations extracted
- [ ] All unit tests passing (`pytest tests/test_calculator.py tests/test_normalizer.py`)

### Data
- [x] Futures prices from SharePoint XLSX (CQG add-in, read via Graph API)
- [x] Exchange rate fetcher running (Bank of Canada API, every 30 min)
- [x] ~210+ bids in `basis_bids` table (email + web scrapers)
- [ ] US basis calculating correctly (check against manual calculation)

### Web Scrapers
- [x] DG Global scraper: ~35 bids per run (CAD/BU)
- [x] HDC/Hensall scraper: ~16 bids per run (USD/BU, normalizer converts)
- [x] Running every 30 min during market hours via Celery beat
- [x] Idempotent re-scrapes via `upsert_bid()`

### Distribution
- [ ] At least one farmer contact added
- [ ] Farmer bid preferences set
- [ ] Test SMS delivered successfully to your own phone
- [ ] Distribution log shows successful send

### Twilio
- [ ] Webhook URL configured on Twilio phone number
- [ ] Test inbound SMS processed correctly

### Scheduled Tasks (Celery Beat)
- [x] `grainbidcalc-beat` service running
- [x] Email polling task firing every 5 minutes
- [x] Futures fetch task firing every 5 min during market hours
- [x] Exchange rate fetch task firing every 30 min
- [x] Web scraper task firing every 30 min during market hours

### Backup
- [ ] Nightly cron job added
- [ ] Test by running `bash deploy/github-backup.sh` manually and verifying push

---

## 18. Supabase Row Level Security (RLS)

RLS is enabled on all 12 tables with permissive policies for `anon` and `service_role` roles.
This was configured in 2026-03-11 via the Supabase SQL Editor.

If you ever need to re-apply (e.g., after creating new tables):

```sql
-- For each table:
ALTER TABLE <table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow anon full access" ON <table_name>
  FOR ALL TO anon USING (true) WITH CHECK (true);

CREATE POLICY "Allow service_role full access" ON <table_name>
  FOR ALL TO service_role USING (true) WITH CHECK (true);
```

Tables with RLS: `buyers`, `commodities`, `basis_bids`, `aggression_params`,
`futures_prices`, `exchange_rates`, `farmer_contacts`, `farmer_bid_preferences`,
`bid_destinations`, `us_basis_history`, `distribution_log`, `ingestion_log`.

---

## Common Issues

**Parser returns empty array**
→ Check your `ANTHROPIC_API_KEY` is valid
→ Make sure the sample file has actual text content
→ Try a simpler test: `python3 -c "import anthropic; c = anthropic.Anthropic(); print('OK')"`

**Supabase connection fails**
→ Double-check `SUPABASE_URL` includes `https://` and ends with `.supabase.co`
→ Make sure you're using the `service_role` key, not the `anon` key

**Celery tasks not running**
→ Check Redis is running: `systemctl status redis-server`
→ Check `REDIS_URL=redis://localhost:6379/0` in `.env`
→ Restart worker: `systemctl restart grainbidcalc-worker`

**SMS not arriving from Twilio**
→ Verify webhook URL is set correctly in Twilio console
→ Check FastAPI logs: `journalctl -u grainbidcalc -f`
→ Make sure port 8000 is open on the droplet firewall:
  `ufw allow 8000`

**Back-calculation fails with "No futures price available"**
→ Check that the SharePoint XLSX has CQG prices in Col C on the relevant buyer tab
→ Verify MS Graph credentials are correct in `.env`
→ Fallback: manually insert a futures price into `futures_prices` table in Supabase

**Graph API 404 on worksheet update**
→ Tab names with special characters must be URL-encoded (P&H → `P%26H`)
→ Do NOT single-quote tab names in Graph API URLs — just URL-encode them

**Web scraper returns 0 bids**
→ DG Global: check if `:desktop_bids` attribute still exists in page HTML (Vue component)
→ HDC: check if DTN API key is still valid (key: `XTyJHKfc0BlMM4zBa0bvUOL6GGYKDq22`)
→ Check `journalctl -u grainbidcalc-worker -f` for scraper error logs

**Duplicate key error on bid insert**
→ Web scrapers use `upsert_bid()` for same-day re-scrapes — this is normal
→ If email pipeline hits this, the same email may have been processed twice

---

*Save sample bid sheets from each buyer as you receive them. These become your test fixtures for validating future parser changes.*
