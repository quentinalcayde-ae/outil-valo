# PROJECT — outil-valo-comparables — V1
*Source de vérité du projet. Ne pas modifier sans accord de Quentin. Date : 30 juin 2026.*

---

## 1. Vision & objectif

Outil autonome (pas un skill) de **valorisation par multiples de comparables** selon une calibration IPEV par maintien du delta. On décrit une cible, l'outil propose un panel de comparables (cotés + transactions M&A documentées), l'utilisateur valide la sélection, l'outil récupère et gèle la donnée financière de marché, applique la méthode à la demande, et livre un résultat auditable (écran + export Excel formula-driven).

Né du besoin trimestriel sur 4 boîtes SaaS, le projet s'élargit à **toute cible** : le caractère récurrent du business model et l'agrégat de valo (ARR, CA, EBITDA…) sont des **paramètres du dossier**, pas un présupposé. L'IPEV n'est qu'un cas de la calibration par delta.

**Trajectoire :** proto **local mono-utilisateur** (Quentin) qui tourne d'abord → puis passage à l'échelle sur **Axya** (Supabase + RLS + accès équipe) en V2. La règle d'or de l'archi est que ce passage soit un swap d'adaptateurs, jamais une réécriture.

## 2. Périmètre V1 / hors-scope

**Dans V1 :**
- Saisie d'une cible avec ses attributs : `is_recurring` (bool) + `valuation_aggregate` libre (ARR / revenue / EBITDA / …).
- Proposition d'un panel de comparables **cotés** + récap du *pourquoi* chaque comp est pertinent.
- Volet **transactions M&A documentées** (saisie manuelle), en cross-check qualitatif, **hors médiane**.
- Porte de validation humaine : sélection/exclusion des comps (avec motif).
- Couche acquisition `YahooProvider` (yfinance pinné + fallback), réseau ouvert local.
- Couche méthode **agrégat-agnostique** (calibration par delta, MODE A/B).
- Extraction assistée du récurrent des comps via **OpenAI**, avec validation humaine dans le front.
- Stockage **SQLite local** (snapshots horodatés, immuables).
- Front web local (saisie, validation panel, validation extraction, résultats).
- Export **Excel formula-driven** auditable.

**Hors-scope V1 (→ V2) :**
- Supabase / Postgres / RLS / auth multi-utilisateurs.
- Déploiement Axya (Docker + GitHub Action, cible VPS/Render à trancher avec Axel).
- Providers data payants (Dealroom & co.) et providers Python alternatifs.
- LLM Claude API.
- Exposition MCP (nice-to-have ultérieur).

## 3. Architecture

Principe directeur : **séparer la donnée de la méthode**, et **tout brancher derrière des interfaces** (data provider, LLM provider, storage) pour que la montée en puissance (provider payant, Claude API, Postgres, Axya) soit un swap d'implémentation.

```
┌──────────────────────────── FRONT WEB (local V1) ────────────────────────────┐
│  React + Vite : saisie cible · validation panel · validation extraction       │
│                 récurrent · résultats · bouton export Excel                    │
└───────────────────────────────────┬───────────────────────────────────────────┘
                                     │ HTTP (REST)
┌───────────────────────────────────▼───────────────────────────────────────────┐
│                              API — FastAPI (local V1)                           │
│                                                                                 │
│   ┌─ Couche ACQUISITION ────────────┐   ┌─ Couche MÉTHODE ─────────────────┐   │
│   │ interface MarketDataProvider     │   │ agrégat-agnostique               │   │
│   │  └ YahooProvider (yfinance pin)  │   │ recomposition EV/agrégat         │   │
│   │ interface LLMProvider            │   │ médiane (inclus seulement)       │   │
│   │  └ OpenAIProvider                │   │ calibration delta + rétention    │   │
│   │ → JSON normalisé horodaté        │   │ MODE A (gèle ancres) / MODE B    │   │
│   │   + source par champ             │   │ → export Excel formula-driven    │   │
│   └─────────────┬────────────────────┘   └───────────────┬──────────────────┘   │
│                 │                                          │                      │
│          ┌──────▼──────────────────────────────────────────▼──────┐             │
│          │  interface Storage → SQLiteStore (V1)  [V2: SupabaseStore]│            │
│          └───────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────────┘
```

**Nature de la donnée (assumée dans le design) :**
- **Rapide** (prix de marché / capi) : seul vrai live, via couche acquisition.
- **Lente** (dette nette, CA, récurrent des comps) : dernier reporting, **mise en cache** dans les snapshots, re-fetchée seulement à nouveau trimestre.
- **Récurrent des comps** : extrait des filings/decks IR (document figé) → extraction LLM assistée + validation humaine, jamais un pull live.

## 4. Data model

SQLite en V1 via **SQLAlchemy** (le switch Postgres/Supabase en V2 = changement de connexion + adaptateur, pas de réécriture du modèle).

| Table | Rôle | Colonnes clés |
|---|---|---|
| `targets` | Cible à valoriser | `id`, `name`, `sector`, `is_recurring` (bool), `valuation_aggregate` (enum: arr/revenue/ebitda/…), `fund` (FR FII / EN FIII pour le template compta), `notes` |
| `target_anchors` | Ancres historiques figées (MODE A) | `id`, `target_id`, `entry_date`, `entry_round`, `m_entry_aggregate` (EV/agrégat au tour), `m_market_entry` (médiane marché au tour) |
| `comps` | Comparables cotés | `id`, `name`, `ticker`, `sector`, `currency`, `is_recurring`, `recurring_basis_tag` (subscription/recurring/arr/acv/null) |
| `comp_snapshots` | Snapshot financier horodaté immuable | `id`, `comp_id`, `snapshot_date`, `market_cap`, `net_debt`, `cash`, `revenue_ltm`, `recurring_value` (validé), `source_by_field` (JSON), **computed** `ev`, `ev_rev`, `ev_recurring` |
| `valuation_runs` | Exercice de valo daté | `id`, `target_id`, `run_date`, `mode` (A/B), `aggregate`, `median_now`, `retention_factor`, `m_final`, `result_ev`, `result_equity`, `excel_path` |
| `run_comps` | Panel d'un run (traçabilité) | `id`, `run_id`, `comp_snapshot_id`, `included` (bool), `exclusion_reason`, `relevance_note` |
| `transactions` | Transactions M&A comparables | `id`, `target_company`, `acquirer`, `tx_date`, `sector`, `price_disclosed` (bool), `price`, `implied_multiple`, `source_doc_url`, `notes` |

**Règles :**
- Les `comp_snapshots` sont **immuables et horodatés** (audit). Un nouveau trimestre = nouveaux snapshots, jamais d'écrasement.
- La médiane se calcule sur `run_comps.included = true` uniquement. Les exclus restent stockés, hors médiane.
- `transactions` = cross-check, **jamais** dans la médiane.

## 5. Algorithmes / logique clé (méthode verrouillée)

**Référentiel :** IPEV déc. 2022, **calibration par maintien du delta**.

- **Recomposition** : `EV = market_cap + net_debt` ; `M = EV / agrégat_LTM`. On ne prend jamais un multiple affiché tel quel.
- **Médiane panel** : 5–10 noms *priced* après exclusion outliers/distressed (exclus conservés, hors médiane).
- **Formule** : `M_final = M_entry_aggregate × (median_now / m_market_entry) × facteur_rétention`.
  - Multiple **ancré sur le dernier tour** (dans l'agrégat du dossier), ne bouge que de la **dérive relative du marché** (`median_now / m_market_entry`, ratio sans unité).
  - **Facteur de rétention** = performance relative vs pairs depuis le tour. Si `is_recurring = false` ou non pertinent → **neutre (= 1)**.
  - Ajustements société en **delta depuis le tour**. **Pas de discount stacking** (une boîte qui croît ne perd pas de valeur dans le mark).
- **Bridge récurrent** : nécessaire seulement pour comparer des *niveaux* (cross-check, facteur de rétention). Le ratio de dérive étant sans unité, le mark reste valide sans rebridge même en cas de mismatch ARR/CA.
- **Deux agrégats distincts** : celui de la cible (fichier compta AE) ≠ celui des comps (leurs filings).
- **MODE A (amorçage)** : gèle `m_entry_aggregate` et `m_market_entry`. **MODE B (trimestriel)** : ne re-price que `median_now`.
- **EV → equity 100 %** en sortie. **Provisions ACC** = sans rapport avec la valo equity, ne jamais écraser le calcul par multiples.
- **Extraction compta** pilotée par labels (templates FR Fonds II / EN Fonds III diffèrent).

## 6. Stack & dépendances

**Backend (Python 3.12) :**
- `fastapi` + `uvicorn` — API.
- `sqlalchemy` — ORM (SQLite V1 → Postgres V2 sans réécriture).
- `yfinance` (**version pinnée** + fallback) — données marché.
- `openai` — extraction récurrent (interface `LLMProvider`, Claude slottable en V2).
- `openpyxl` — export Excel formula-driven.
- `pydantic` — schémas / validation.
- `structlog` — logs structurés ; `sentry-sdk` (optionnel via `SENTRY_DSN`).
- Tooling : `ruff` (lint), `pytest` (tests).

**Front (local V1) :** React 18 + TypeScript + Vite + shadcn-ui + Tailwind + TanStack Query.

**V2 :** Supabase (Postgres + RLS + auth), Docker (slim, non-root), GitHub Action `deploy.yml`, cible Axya.

## 7. API / interfaces

Contrats REST (FastAPI), à figer en P3 :
- `POST /targets` — crée une cible (attributs + agrégat).
- `POST /targets/{id}/panel` — propose un panel de comps (cotés) + relevance notes.
- `PATCH /runs/{id}/comps` — valide la sélection (include/exclude + motif).
- `POST /comps/{id}/refresh` — déclenche l'acquisition (snapshot horodaté).
- `POST /comps/{id}/recurring` — extraction LLM du récurrent → renvoie pour validation humaine.
- `POST /runs` — lance un run de valo (mode A/B) → résultat + chemin Excel.
- `GET /runs/{id}` — résultat auditable.
- `CRUD /transactions` — transactions M&A documentées.

**Interfaces internes (pluggables) :** `MarketDataProvider`, `LLMProvider`, `Storage`. Ce sont les trois points de bascule V1→V2.

## 8. Sécurité & garde-fous

- **V1 local mono-utilisateur** : pas d'auth, SQLite local. Secrets (`OPENAI_API_KEY`, `SENTRY_DSN`) en `.env` uniquement, jamais commités ; toute variable → `.env.example`.
- **Portes de validation humaine obligatoires** : (a) sélection des comps, (b) extraction du récurrent. Rien ne part en médiane ou en mark sans validation.
- **Immuabilité** des snapshots (audit / reproductibilité).
- **V2** : RLS systématique, rôles lecture/écriture séparés, auth Supabase.

## 9. Phases d'implémentation

- **P1 — Socle données** : data model SQLAlchemy + `SQLiteStore` + couche acquisition `YahooProvider` + CLI de test. Doc de migration Supabase prête (sans l'implémenter).
- **P2 — Méthode** : couche méthode agrégat-agnostique (recomposition, médiane, calibration delta, MODE A/B) + export Excel. **Validée sur un cas réel (Syroco).**
- **P3 — API + Front** : FastAPI + front web local (saisie cible, sélection/validation panel, résultats, export). Transactions M&A.
- **P4 — Extraction assistée** : `OpenAIProvider` pour le récurrent des comps + validation dans le front.
- **P5 — Mise à l'échelle (V2)** : swap Supabase + RLS + auth, Docker + GitHub Action, déploiement Axya (avec Axel).

Chaque phase est testable indépendamment (pytest), miroir de `src/`.

## 10. Points ouverts

- **Cible de déploiement Axya** (VPS / Render / autre) — à trancher avec **Axel** en P5.
- **Provider data V2** (Dealroom via Axya ? autre lib Python ?) — dépend des accès ; l'interface `MarketDataProvider` est déjà prête à l'accueillir.
- **Sourcing systématique des transactions M&A** — V1 = manuel ; automatisation à explorer.
- **Standardisation de la définition du récurrent** entre comps — V1 = tag de base par comp, pas de normalisation auto.
- **Exposition MCP** — nice-to-have post-V2.
