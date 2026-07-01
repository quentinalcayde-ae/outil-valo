# Data model — snapshot réel

*Reflète `src/valo/models.py`. Voir PROJECT_V1.md §4 pour la spec complète.*

## Tables

| Table | Rôle |
|---|---|
| `targets` | Cible à valoriser — `name`, `is_recurring`, `valuation_aggregate` (arr/revenue/ebitda/…) |
| `target_anchors` | Ancres historiques figées pour le MODE A — `m_entry_aggregate`, `m_market_entry` |
| `comps` | Comparables cotés — `ticker` (unique), `is_recurring`, `recurring_basis_tag` |
| `comp_snapshots` | Snapshot financier **immuable et horodaté** — voir règle ci-dessous |
| `valuation_runs` | Exercice de valo daté — `mode` (A/B), résultat final, chemin Excel |
| `run_comps` | Panel d'un run — `included` (bool), `exclusion_reason` ; exclus conservés hors médiane |
| `transactions` | Transactions M&A — cross-check qualitatif, jamais dans la médiane |

## Recadrage P3a (1er juillet 2026)

- `targets` : + `aggregate_value`, `net_debt`, `description` (chiffres clés saisis + contexte découverte LLM).
- `target_anchors` : `m_market_entry` devient **nullable** (calculé à l'étape `/anchor`) ; + `market_anchor_basis` (revenue/arr…), `m_market_entry_source` (computed/manual).
- `transactions` : + `target_id`, `origin` (llm/manual), `status` (proposed/validated).
- `run_comps` : + `comp_id` (identité fixée au panel) ; `comp_snapshot_id` devient **nullable**, rempli à l'`execute` (recherche financière). Le snapshot gelé utilisé dans la médiane reste tracé pour l'audit.
- Nouvelles fonctions repo : `link_run_comp_snapshot`, `set_anchor_market`. Migration : `migrations/002_recadrage_decouverte.sql`.

## Règles invariantes

- **`comp_snapshots` est append-only.** `insert_snapshot()` crée toujours un nouveau row. Ne jamais appeler `update()` sur un snapshot existant (sauf `recurring_value` après validation humaine).
- **`get_latest_snapshot()` trie par `(snapshot_date DESC, id DESC)`** — tiebreaker sur `id` pour les snapshots du même horodatage.
- **EV et multiples calculés à l'insert** : `ev = market_cap + net_debt` ; `ev_rev = ev / revenue_ltm` ; `ev_recurring = ev / recurring_value` (ce dernier uniquement après validation humaine).
- **La médiane ne porte que sur `run_comps.included = true`.**

## CRUD — `src/valo/storage/repositories.py`

Toutes les opérations DB passent par les fonctions de ce module. Ne jamais requêter la session directement depuis un router ou un service.

| Fonction | Description |
|---|---|
| `create_target` / `list_targets` / `get_target` | CRUD cibles |
| `create_anchor` / `get_anchors` | Ancres MODE A |
| `create_comp` / `get_comp_by_ticker` / `list_comps` | CRUD comparables |
| `insert_snapshot` | Insert immuable — calcule EV/multiples |
| `get_latest_snapshot` / `list_snapshots` | Lecture snapshots |
| `update_snapshot_recurring` | Seul update autorisé sur snapshot (validation humaine) |
| `create_run` / `get_run` / `add_run_comp` / `update_run_result` | Runs de valo |
| `create_transaction` / `list_transactions` / `update_transaction` / `delete_transaction` | Transactions M&A |
