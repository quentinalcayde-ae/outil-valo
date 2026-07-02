-- Migration 004 — ajustement de croissance (pente β) + deltas + equity
-- Référence Supabase. En V1 SQLite : schéma géré par SQLAlchemy + scripts/sync_db.py.

ALTER TABLE targets ADD COLUMN growth_now FLOAT;                    -- croissance actuelle cible
ALTER TABLE target_anchors ADD COLUMN entry_growth FLOAT;          -- croissance cible au tour (saisie)
ALTER TABLE target_anchors ADD COLUMN entry_panel_growth FLOAT;    -- médiane croissance panel au tour (calc)
ALTER TABLE comp_snapshots ADD COLUMN revenue_growth FLOAT;        -- croissance YoY comp (trailing)
ALTER TABLE valuation_runs ADD COLUMN other_deltas FLOAT;          -- ajustements société additifs (tours)
