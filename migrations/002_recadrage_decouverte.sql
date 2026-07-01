-- Migration 002 — recadrage flux découverte (1er juillet 2026)
-- Référence Supabase. En V1 SQLite, le schéma est géré par SQLAlchemy (create_all).
-- Voir PROJECT_V1.md §4 (révisé).

-- Chiffres clés de la cible (contexte découverte LLM + calcul valo)
ALTER TABLE targets ADD COLUMN aggregate_value FLOAT;
ALTER TABLE targets ADD COLUMN net_debt FLOAT;
ALTER TABLE targets ADD COLUMN description TEXT;

-- Ancre marché : calculée sur historique, avec basis + source
ALTER TABLE target_anchors ALTER COLUMN m_market_entry DROP NOT NULL;
ALTER TABLE target_anchors ADD COLUMN market_anchor_basis VARCHAR(50);
ALTER TABLE target_anchors ADD COLUMN m_market_entry_source VARCHAR(20) DEFAULT 'computed';

-- Transactions : proposition LLM + statut de validation
ALTER TABLE transactions ADD COLUMN target_id INTEGER REFERENCES targets(id);
ALTER TABLE transactions ADD COLUMN origin VARCHAR(20) DEFAULT 'manual';
ALTER TABLE transactions ADD COLUMN status VARCHAR(20) DEFAULT 'validated';

-- run_comps : identité du comp au panel, snapshot gelé rempli à l'execute
ALTER TABLE run_comps ADD COLUMN comp_id INTEGER REFERENCES comps(id);
ALTER TABLE run_comps ALTER COLUMN comp_snapshot_id DROP NOT NULL;
