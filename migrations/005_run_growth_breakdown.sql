-- Migration 005 — détail de l'ajustement de croissance persisté sur le run (traçabilité/affichage)
ALTER TABLE valuation_runs ADD COLUMN beta FLOAT;          -- pente panel (prix d'un point de croissance)
ALTER TABLE valuation_runs ADD COLUMN growth_delta FLOAT;  -- Δ croissance appliqué (tours)
ALTER TABLE valuation_runs ADD COLUMN growth_gap FLOAT;    -- écart de croissance retenu (clampé)
