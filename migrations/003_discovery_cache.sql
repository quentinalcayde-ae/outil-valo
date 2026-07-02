-- Migration 003 — cache de découverte LLM sur la cible
-- Référence Supabase. En V1 SQLite, le schéma est géré par SQLAlchemy (create_all).

-- Mémorise la dernière découverte LLM (comps + transactions) pour ne pas relancer
-- l'appel LLM à chaque nouveau run tant que le panel convient.
ALTER TABLE targets ADD COLUMN discovery_json JSONB;
