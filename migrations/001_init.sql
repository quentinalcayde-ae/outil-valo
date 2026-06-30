-- Migration 001 — schéma initial
-- Utilisé en V2 (Supabase). En V1 SQLite, le schéma est géré par SQLAlchemy (Base.metadata.create_all).
-- Ce fichier est la référence SQL pour le swap Supabase.

CREATE TABLE IF NOT EXISTS targets (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sector VARCHAR(255),
    is_recurring BOOLEAN NOT NULL,
    valuation_aggregate VARCHAR(50) NOT NULL,
    fund VARCHAR(100),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS target_anchors (
    id SERIAL PRIMARY KEY,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    entry_date DATE NOT NULL,
    entry_round VARCHAR(100),
    m_entry_aggregate FLOAT NOT NULL,
    m_market_entry FLOAT NOT NULL
);

CREATE TABLE IF NOT EXISTS comps (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    ticker VARCHAR(20) NOT NULL UNIQUE,
    sector VARCHAR(255),
    currency VARCHAR(10) DEFAULT 'USD',
    is_recurring BOOLEAN DEFAULT TRUE,
    recurring_basis_tag VARCHAR(50)
);

CREATE TABLE IF NOT EXISTS comp_snapshots (
    id SERIAL PRIMARY KEY,
    comp_id INTEGER NOT NULL REFERENCES comps(id),
    snapshot_date TIMESTAMPTZ NOT NULL,
    market_cap FLOAT,
    net_debt FLOAT,
    cash FLOAT,
    revenue_ltm FLOAT,
    recurring_value FLOAT,
    source_by_field JSONB,
    ev FLOAT,
    ev_rev FLOAT,
    ev_recurring FLOAT
);

CREATE TABLE IF NOT EXISTS valuation_runs (
    id SERIAL PRIMARY KEY,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    run_date TIMESTAMPTZ DEFAULT NOW(),
    mode VARCHAR(1) NOT NULL,
    aggregate VARCHAR(50) NOT NULL,
    median_now FLOAT,
    retention_factor FLOAT,
    m_final FLOAT,
    result_ev FLOAT,
    result_equity FLOAT,
    excel_path VARCHAR(500)
);

CREATE TABLE IF NOT EXISTS run_comps (
    id SERIAL PRIMARY KEY,
    run_id INTEGER NOT NULL REFERENCES valuation_runs(id),
    comp_snapshot_id INTEGER NOT NULL REFERENCES comp_snapshots(id),
    included BOOLEAN DEFAULT TRUE,
    exclusion_reason TEXT,
    relevance_note TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    target_company VARCHAR(255) NOT NULL,
    acquirer VARCHAR(255),
    tx_date DATE,
    sector VARCHAR(255),
    price_disclosed BOOLEAN DEFAULT FALSE,
    price FLOAT,
    implied_multiple FLOAT,
    source_doc_url VARCHAR(1000),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
