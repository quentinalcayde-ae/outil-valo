# CLAUDE.md — outil-valo-comparables

## Sources de vérité
- `PROJECT_V1.md` = source de vérité absolue (architecture cible). NE JAMAIS modifier sans accord explicite de Quentin.
- Le code = réalité du fonctionnement. En cas de divergence avec la spec → corriger le code.
- `docs/` = snapshot du code. Mettre à jour après chaque changement significatif. `docs/index.md` = carte de navigation.

## Workflow obligatoire
1. Avant d'implémenter : relire la section concernée de `PROJECT_V1.md`.
2. Avant d'écrire du code touchant la DB : vérifier le schéma réel (`src/valo/models.py` et `migrations/`) — jamais de colonne devinée.
3. Après implémentation : tests (`pytest`), puis mise à jour des docs concernées + `docs/index.md`.
4. Migrations : toujours un fichier SQL numéroté dans `migrations/`, jamais de modification directe non historisée.
5. Nouvelle dépendance : ajouter à `requirements.txt` (version pinnée), jamais de pip install non tracé.

## Conventions
- Code et identifiants en anglais ; messages utilisateur final et docs métier en français.
- Secrets : `.env` uniquement, jamais en dur, jamais commité. Toute nouvelle variable → `.env.example`.
- Scripts et pipelines idempotents (upsert, relançables sans effet de bord).
- Logs structurés (`structlog`) : timestamp, opération, durée, résultat.
- Erreurs : message clair en français côté front, sans détails internes.
- Snapshots `comp_snapshots` : **immuables et horodatés** — ne jamais écraser, toujours insérer un nouveau snapshot.
- La médiane se calcule sur `run_comps.included = true` uniquement.
- `transactions` M&A = cross-check qualitatif, **jamais** dans la médiane.

## Architecture (résumé — voir PROJECT_V1.md §3)
```
Front React (Vite) → HTTP REST → FastAPI → SQLiteStore (V1) / SupabaseStore (V2)
                                         → YahooProvider (marché)
                                         → OpenAIProvider (extraction récurrent)
```

## Stack (voir PROJECT_V1.md §6)
- **Backend** : Python 3.12, FastAPI + uvicorn, SQLAlchemy (SQLite V1), yfinance (pinné), openai, openpyxl, pydantic, structlog, sentry-sdk
- **Frontend** : React 18 + TypeScript + Vite + shadcn-ui + Tailwind + TanStack Query
- **Tooling** : ruff (lint), pytest (tests)
- **V2** : Supabase (Postgres + RLS + auth), Docker slim non-root, GitHub Action deploy

## Phases (voir PROJECT_V1.md §9)
- **P1** — Socle données : models SQLAlchemy + SQLiteStore + YahooProvider + CLI test
- **P2** — Méthode : recomposition EV, médiane, calibration delta, MODE A/B, export Excel
- **P3** — API + Front : FastAPI + React (saisie cible, panel, résultats, export) + transactions M&A
- **P4** — Extraction assistée : OpenAIProvider récurrent + validation front
- **P5** — V2 : swap Supabase + RLS + auth + Docker + GitHub Action (avec Axel)

## Interfaces pluggables (points de bascule V1→V2)
- `MarketDataProvider` → `YahooProvider` (V1) / provider payant (V2)
- `LLMProvider` → `OpenAIProvider` (V1) / `ClaudeProvider` (V2)
- `Storage` → `SQLiteStore` (V1) / `SupabaseStore` (V2)
