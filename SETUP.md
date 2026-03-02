# GrainBidCalc — Setup Guide

Complete step-by-step instructions to go from a fresh scaffold to a fully running system.
Work through each section in order. Don't skip ahead — later steps depend on earlier ones.

---

## Table of Contents

1. [Accounts & Services to Create](#1-accounts--services-to-create)
2. [Supabase (Database)](#2-supabase-database)
3. [Anthropic API Key (LLM Parsing)](#3-anthropic-api-key-llm-parsing)
4. [Twilio (SMS)](#4-twilio-sms)
5. [Google Workspace API (Email)](#5-google-workspace-api-email)
6. [CQG API (Futures Prices)](#6-cqg-api-futures-prices)
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
| Google Workspace | admin.google.com | markets@mapleviewgrain.ca email | Already have |
| CQG | cqg.com | Live futures prices | Contact for API pricing |
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

## 5. Google Workspace API (Email)

This lets the system read `markets@mapleviewgrain.ca` for inbound bid emails.

### 5.1 Create a Google Cloud project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top → **New Project**
3. Name: `grainbidcalc`
4. Click **Create**

### 5.2 Enable the Gmail API

1. In the search bar at the top, search: `Gmail API`
2. Click it → click **Enable**

### 5.3 Create a service account

1. In the left sidebar: **IAM & Admin** → **Service Accounts**
2. Click **Create Service Account**
3. Name: `grainbidcalc-email`
4. Click **Create and Continue** → **Done**
5. Click on the service account you just created
6. Go to the **Keys** tab → **Add Key** → **Create new key** → **JSON**
7. A JSON file downloads automatically — this is your service account key
8. Rename it to `service-account.json`
9. Move it to `/opt/grainbidcalc/credentials/service-account.json` on the server

### 5.4 Grant the service account access to the inbox

1. Copy the service account's email address (looks like `grainbidcalc-email@grainbidcalc-xxxxx.iam.gserviceaccount.com`)
2. Log in to Google Workspace Admin at [admin.google.com](https://admin.google.com)
3. Go to **Security** → **API Controls** → **Domain-wide Delegation**
4. Click **Add new** and enter:
   - Client ID: (find this in the JSON file, field `client_id`)
   - OAuth Scopes:
     ```
     https://www.googleapis.com/auth/gmail.readonly,https://www.googleapis.com/auth/gmail.modify
     ```
5. Click **Authorize**

> This allows the service account to read and label emails in `markets@mapleviewgrain.ca`.

### 5.5 Update .env

Set `GOOGLE_SERVICE_ACCOUNT_JSON=credentials/service-account.json`

---

## 6. CQG API (Futures Prices)

CQG provides real-time CBOT/ICE futures data.

### 6.1 Get API access

1. Contact CQG at [cqg.com](https://www.cqg.com) or through your existing broker relationship
2. Request **CQG API** access for data feed
3. They will provide `CQG_API_KEY` and `CQG_API_SECRET`
4. Add these to your `.env` in Step 9

### 6.2 If CQG is not yet available

The system is designed to work without live CQG data initially:
- `calculation/futures_feed.py` has a manual fallback
- You can manually insert futures prices into the `futures_prices` table via Supabase SQL editor:
  ```sql
  INSERT INTO futures_prices (contract, price) VALUES ('ZSH26', 11.375);
  INSERT INTO futures_prices (contract, price) VALUES ('ZCK26', 4.431);
  ```
- Update these manually each morning until the API integration is built
- The `task_fetch_futures` Celery task will handle it automatically once CQG is connected

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

# Google — from Step 5
GOOGLE_SERVICE_ACCOUNT_JSON=credentials/service-account.json
GMAIL_TARGET_EMAIL=markets@mapleviewgrain.ca

# CQG — from Step 6 (leave blank until you have it)
CQG_API_KEY=
CQG_API_SECRET=

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
# Copy .env
scp .env root@159.89.127.66:/opt/grainbidcalc/.env

# Copy Google service account key
scp credentials/service-account.json root@159.89.127.66:/opt/grainbidcalc/credentials/
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
- [ ] Supabase project created and migrated
- [ ] All tables verified in Supabase Table Editor
- [ ] Commodities and buyers seeded
- [ ] Aggression parameters set to real margins
- [ ] Bid destinations seeded
- [ ] `.env` filled in with all real credentials (no blanks except CQG if deferred)
- [ ] All three systemd services running (`active`)
- [ ] Redis running
- [ ] API health check returns `{"status":"ok"}`

### Parsing
- [ ] Parser tested against real ADM Windsor email → clean output
- [ ] Parser tested against real Sarnia email → `basis_value: null`, `cash_price` populated
- [ ] Parser tested against Farm Market News PDF → multiple locations extracted
- [ ] All unit tests passing (`pytest tests/test_calculator.py tests/test_normalizer.py`)

### Data
- [ ] Futures prices seeded or CQG connected
- [ ] Exchange rate seeded or Bank of Canada fetcher running
- [ ] At least one bid in `basis_bids` table
- [ ] US basis calculating correctly (check against manual calculation)

### Distribution
- [ ] At least one farmer contact added
- [ ] Farmer bid preferences set
- [ ] Test SMS delivered successfully to your own phone
- [ ] Distribution log shows successful send

### Twilio
- [ ] Webhook URL configured on Twilio phone number
- [ ] Test inbound SMS processed correctly

### Scheduled Tasks (Celery Beat)
- [ ] `grainbidcalc-beat` service running
- [ ] Email polling task firing every 5 minutes (check `journalctl -u grainbidcalc-beat -f`)
- [ ] Futures fetch task firing (or manually updated daily until CQG)
- [ ] Exchange rate fetch task firing

### Backup
- [ ] Nightly cron job added
- [ ] Test by running `bash deploy/github-backup.sh` manually and verifying push

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
→ Manually insert a futures price row into `futures_prices` in Supabase
→ This happens when CQG is not yet connected and no price is cached

---

*Save sample bid sheets from each buyer as you receive them. These become your test fixtures for validating future parser changes.*
