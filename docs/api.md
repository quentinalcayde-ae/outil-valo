# API REST — contrats

*Reflète `src/valo/routers/`. Voir PROJECT_V1.md §7. Flux : saisir → découvrir → valider → ancrer → chercher → Excel.*

## Cibles & découverte

| Endpoint | Rôle |
|---|---|
| `POST /targets` | Crée une cible (nom + chiffres clés : `aggregate_value`, `net_debt`, `description`…) |
| `GET /targets` · `GET /targets/{id}` | Liste / détail |
| `GET /targets/{id}/anchors` | Ancres de la cible |
| `POST /targets/{id}/suggest` | **Découverte LLM** → `{comps[], transactions[]}` (identité + rationale, aucune acquisition) |

`POST /suggest` body : `{extra_tickers?, n_comps=8, n_transactions=5}`.

## Run : panel → ancre → execute

| Endpoint | Rôle |
|---|---|
| `POST /runs/panel?target_id=` | Crée l'ancre d'entrée + le run + associe les comps **validés** (identité seule, pas de fetch) |
| `PATCH /runs/{id}/comps` | Inclure/exclure des comps (`run_comp_id`, `included`, `exclusion_reason`) |
| `POST /runs/{id}/anchor` | Calcule `m_market_entry` (EV/Revenue historique) **ou** override manuel (`manual_value`, cas ARR) → gèle l'ancre |
| `POST /runs/{id}/execute` | **Recherche financière** (snapshots live des inclus) + calcul valo + Excel |
| `GET /runs/{id}` | Résultat auditable (run_comps avec comp + snapshot) |

`POST /panel` body : `{comps:[{ticker,name?,relevance_note?}], mode, aggregate, retention_factor, anchor:{entry_date, entry_round?, m_entry_aggregate}}`.

`POST /anchor` réponse : `{basis, entry_date, m_market_entry, n_available, details[], source}` — `source ∈ {computed, manual, pending}` (`pending` = aucune donnée historique, saisie manuelle requise).

## Comps & transactions

| Endpoint | Rôle |
|---|---|
| `POST /comps` · `GET /comps` · `POST /comps/{ticker}/refresh` | CRUD + snapshot manuel |
| `POST /comps/{ticker}/recurring` | Validation humaine du récurrent (P4) |
| `CRUD /transactions` | Transactions M&A (création manuelle + validation des propositions LLM `status=proposed→validated`) |

## Garde-fous

- `execute` refuse si l'ancre marché n'est pas calculée (`m_market_entry is None`).
- Un comp sans multiple calculable est auto-exclu (hors médiane) avec motif.
- Aucun chiffre LLM n'entre en médiane : comps chiffrés par yfinance, transactions validées à la main.
