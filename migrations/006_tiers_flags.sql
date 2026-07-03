-- Migration 006 — tiers de comps, statut, %CA, flags de run, moyenne winsorisée
-- Réf Supabase. En V1 SQLite : réconcilié automatiquement au démarrage (reconcile_schema).

ALTER TABLE run_comps ADD COLUMN tier INTEGER;
ALTER TABLE run_comps ADD COLUMN statut VARCHAR(20) DEFAULT 'priced';
ALTER TABLE run_comps ADD COLUMN pct_ca_comparable FLOAT;

ALTER TABLE valuation_runs ADD COLUMN winsor_mean FLOAT;
ALTER TABLE valuation_runs ADD COLUMN flags JSONB;
