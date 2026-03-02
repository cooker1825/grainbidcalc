-- GrainBidCalc Initial Schema
-- Run against your Supabase project SQL editor

-- ─────────────────────────────────────────────
-- buyers
-- ─────────────────────────────────────────────
CREATE TABLE buyers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    short_name TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL,             -- "email", "sms", "web_scrape", "manual"
    source_identifier TEXT,               -- email address, phone number, URL
    location TEXT,
    region TEXT,
    notes TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────
-- commodities
-- ─────────────────────────────────────────────
CREATE TABLE commodities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL UNIQUE,            -- "soybeans", "corn", "srw_wheat", "canola"
    display_name TEXT NOT NULL,
    default_unit TEXT NOT NULL DEFAULT 'CAD/BU',
    futures_exchange TEXT,                -- "CBOT", "ICE"
    notes TEXT
);

-- ─────────────────────────────────────────────
-- basis_bids  (core table)
-- ─────────────────────────────────────────────
CREATE TABLE basis_bids (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id UUID NOT NULL REFERENCES buyers(id),
    commodity_id UUID NOT NULL REFERENCES commodities(id),

    -- Delivery window
    delivery_month TEXT NOT NULL,         -- "2026-02" (ISO YYYY-MM)
    delivery_label TEXT,                  -- Original: "Feb'26", "Oct'26 (Harvest)"
    delivery_start DATE,
    delivery_end DATE,

    -- Core data: BASIS is the durable value
    basis_value DECIMAL(10,4) NOT NULL,
    basis_unit TEXT NOT NULL DEFAULT 'CAD/BU',
    basis_normalized_cad_bu DECIMAL(10,4),

    -- US Basis snapshot at ingestion (reference)
    us_basis_at_ingestion DECIMAL(10,4),

    -- Back-calculation metadata (when source only provided cash price)
    was_back_calculated BOOLEAN DEFAULT false,
    source_cash_price DECIMAL(10,4),
    back_calc_futures DECIMAL(10,4),
    back_calc_fx_rate DECIMAL(10,6),
    back_calc_timestamp TIMESTAMPTZ,

    -- Futures reference
    futures_contract TEXT,                -- Normalized: "ZSH26"
    futures_contract_raw TEXT,            -- Original: "@S6H", "H26"

    -- Delivery terms
    bid_type TEXT NOT NULL DEFAULT 'delivered', -- "elevator", "delivered", "fob"
    destination TEXT,
    fob_origin TEXT,

    -- Metadata
    source_type TEXT NOT NULL,
    raw_text TEXT,
    confidence DECIMAL(3,2),
    bid_date DATE NOT NULL,
    ingested_at TIMESTAMPTZ DEFAULT now(),
    expires_at TIMESTAMPTZ,
    is_current BOOLEAN DEFAULT true,

    UNIQUE(buyer_id, commodity_id, delivery_month, bid_type, destination, bid_date)
);

CREATE INDEX idx_basis_bids_ranking ON basis_bids(commodity_id, delivery_month, is_current, basis_normalized_cad_bu DESC);
CREATE INDEX idx_basis_bids_buyer ON basis_bids(buyer_id, bid_date DESC);
CREATE INDEX idx_basis_bids_current ON basis_bids(is_current) WHERE is_current = true;

-- ─────────────────────────────────────────────
-- aggression_params
-- ─────────────────────────────────────────────
CREATE TABLE aggression_params (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    commodity_id UUID NOT NULL REFERENCES commodities(id),
    delivery_month TEXT,                  -- NULL = default for commodity
    handling_type TEXT NOT NULL DEFAULT 'brokered', -- "physical", "brokered"
    adjustment_value DECIMAL(10,4) NOT NULL,
    adjustment_unit TEXT NOT NULL DEFAULT 'CAD/BU',
    notes TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(commodity_id, delivery_month, handling_type)
);

-- ─────────────────────────────────────────────
-- futures_prices  (CQG cache)
-- ─────────────────────────────────────────────
CREATE TABLE futures_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    contract TEXT NOT NULL,               -- "ZSH26", "ZCK26"
    price DECIMAL(10,4) NOT NULL,
    change DECIMAL(10,4),
    fetched_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(contract, fetched_at)
);

CREATE INDEX idx_futures_latest ON futures_prices(contract, fetched_at DESC);

-- ─────────────────────────────────────────────
-- exchange_rates
-- ─────────────────────────────────────────────
CREATE TABLE exchange_rates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pair TEXT NOT NULL DEFAULT 'USD/CAD',
    rate DECIMAL(10,6) NOT NULL,
    fetched_at TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────
-- farmer_contacts
-- ─────────────────────────────────────────────
CREATE TABLE farmer_contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    farm_name TEXT,
    phone TEXT,
    email TEXT,
    region TEXT,
    location TEXT,
    preferred_channel TEXT DEFAULT 'sms', -- "sms", "email", "both"
    active BOOLEAN DEFAULT true,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────
-- farmer_bid_preferences
-- ─────────────────────────────────────────────
-- One row = one (farmer × commodity × bid_type × destination) combo.
-- NULL destination = all destinations for that bid_type.
-- NULL delivery_months = all available months.
CREATE TABLE farmer_bid_preferences (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    farmer_id UUID NOT NULL REFERENCES farmer_contacts(id) ON DELETE CASCADE,
    commodity_id UUID NOT NULL REFERENCES commodities(id),
    bid_type TEXT NOT NULL,               -- "elevator", "delivered", "fob"
    destination TEXT,                     -- NULL = all
    fob_origin TEXT,
    delivery_months TEXT[],               -- NULL = all
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(farmer_id, commodity_id, bid_type, destination)
);

CREATE INDEX idx_farmer_prefs_lookup ON farmer_bid_preferences(farmer_id, active) WHERE active = true;
CREATE INDEX idx_farmer_prefs_distribution ON farmer_bid_preferences(commodity_id, bid_type, active) WHERE active = true;

-- ─────────────────────────────────────────────
-- bid_destinations
-- ─────────────────────────────────────────────
-- Farmer sees location_name. end_buyer_name is INTERNAL ONLY.
CREATE TABLE bid_destinations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_name TEXT NOT NULL,          -- "Windsor", "London", "Hamilton"
    bid_type TEXT NOT NULL,               -- "elevator", "delivered", "fob"
    region TEXT,
    commodities_accepted TEXT[],
    internal_name TEXT NOT NULL UNIQUE,   -- "adm_windsor", "ingredion_london"
    end_buyer_name TEXT,                  -- NEVER shown to farmers
    buyer_id UUID REFERENCES buyers(id),
    active BOOLEAN DEFAULT true,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────
-- us_basis_history  (daily snapshots for trend analysis)
-- ─────────────────────────────────────────────
CREATE TABLE us_basis_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    buyer_id UUID NOT NULL REFERENCES buyers(id),
    commodity_id UUID NOT NULL REFERENCES commodities(id),
    delivery_month TEXT NOT NULL,
    us_basis DECIMAL(10,4) NOT NULL,
    cad_basis DECIMAL(10,4),
    exchange_rate DECIMAL(10,6),
    futures_price DECIMAL(10,4),
    snapshot_date DATE NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(buyer_id, commodity_id, delivery_month, snapshot_date)
);

CREATE INDEX idx_us_basis_history_lookup ON us_basis_history(commodity_id, delivery_month, snapshot_date DESC);

-- ─────────────────────────────────────────────
-- distribution_log
-- ─────────────────────────────────────────────
CREATE TABLE distribution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    distribution_type TEXT NOT NULL,      -- "scheduled", "on_demand", "threshold_triggered"
    channel TEXT NOT NULL,                -- "sms", "email", "grain_discovery"
    bid_type TEXT,
    recipient_count INTEGER,
    message_content TEXT,
    commodities TEXT[],
    destinations TEXT[],
    triggered_by TEXT,
    sent_at TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────
-- ingestion_log
-- ─────────────────────────────────────────────
CREATE TABLE ingestion_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,
    source_identifier TEXT,
    buyer_id UUID REFERENCES buyers(id),
    raw_content TEXT,
    parsed_bids_count INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',        -- "pending", "parsed", "failed", "review"
    error_message TEXT,
    processing_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ─────────────────────────────────────────────
-- Seed: commodities
-- ─────────────────────────────────────────────
INSERT INTO commodities (name, display_name, default_unit, futures_exchange) VALUES
  ('soybeans',     'Soybeans',   'CAD/BU', 'CBOT'),
  ('corn',         'Corn',       'CAD/BU', 'CBOT'),
  ('srw_wheat',    'SRW Wheat',  'CAD/BU', 'CBOT'),
  ('hrw_wheat',    'HRW Wheat',  'CAD/BU', 'CBOT'),
  ('swr_wheat',    'SWR Wheat',  'CAD/BU', 'CBOT'),
  ('canola',       'Canola',     'CAD/MT', 'ICE');
