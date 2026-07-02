# PROJECT — outil-valo-comparables — V1
*Source de vérité du projet. Ne pas modifier sans accord de Quentin. Date : 30 juin 2026 — révisé le 1er juillet 2026 (recadrage flux : découverte auto des comps & transactions, ancre marché calculée).*

---

## 1. Vision & objectif

Outil autonome (pas un skill) de **valorisation par multiples de comparables** selon une calibration IPEV par maintien du delta. L'utilisateur ne renseigne qu'un **nom de société + ses chiffres clés** ; l'outil **découvre automatiquement** (via LLM) un panel de comparables cotés + de transactions M&A pertinentes, avec le *pourquoi* de chacun. L'utilisateur **valide et corrige** cette sélection, **l'ancre**, puis l'outil récupère et gèle la donnée financière de marché, applique la méthode, et livre un résultat auditable (écran + export Excel formula-driven).

Né du besoin trimestriel sur 4 boîtes SaaS, le projet s'élargit à **toute cible** : le caractère récurrent du business model et l'agrégat de valo (ARR, CA, EBITDA…) sont des **paramètres du dossier**, pas un présupposé. L'IPEV n'est qu'un cas de la calibration par delta.

**Trajectoire :** proto **local mono-utilisateur** (Quentin) qui tourne d'abord → puis passage à l'échelle sur **Axya** (Supabase + RLS + accès équipe) en V2. La règle d'or de l'archi est que ce passage soit un swap d'adaptateurs, jamais une réécriture.

## 2. Périmètre V1 / hors-scope

**Dans V1 :**
- Saisie minimale d'une cible : `name` + chiffres clés (agrégat courant, dette nette, `is_recurring`, `valuation_aggregate` ARR/revenue/EBITDA/…, date du tour, multiple d'entrée).
- **Découverte automatique (LLM)** d'un panel de comparables **cotés** (nom + ticker + *pourquoi* chacun est pertinent). L'utilisateur **corrige/complète les tickers** avant acquisition.
- **Découverte automatique (LLM)** de **transactions M&A** comparables (cible, acquéreur, date, URL source, multiple **best-effort marqué « à vérifier »**). Cross-check qualitatif, **hors médiane**, validation humaine des chiffres.
- Porte de validation humaine : sélection/exclusion des comps & transactions (avec motif), puis **ancrage**.
- Couche acquisition `YahooProvider` (yfinance pinné + fallback), réseau ouvert local — **snapshots live ET historiques** (pour l'ancre marché).
- Couche méthode **agrégat-agnostique** (calibration par delta, MODE A/B).
- Extraction assistée du récurrent des comps via **OpenAI**, avec validation humaine dans le front.
- Stockage **SQLite local** (snapshots horodatés, immuables).
- Front web local (saisie, découverte, validation panel + transactions, ancrage, résultats).
- Export **Excel formula-driven** auditable : onglet **Synthèse** (multiple synthétique en formules) + onglet **Comparables** (tableau de comps classique, sources).

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

**Rôle du `LLMProvider` (OpenAI en V1) :** deux usages, tous deux en *proposition + validation humaine*, jamais en source de chiffre entrant dans la médiane :
1. **Découverte** — à partir du nom + description + chiffres clés de la cible, propose les comparables cotés (nom, ticker, rationale) et les transactions M&A (identité, source, multiple « à vérifier »).
2. **Extraction récurrent** — extrait l'ARR/récurrent des filings des comps (P4).

**Nature de la donnée (assumée dans le design) :**
- **Rapide** (prix de marché / capi) : seul vrai live, via couche acquisition.
- **Lente** (dette nette, CA, récurrent des comps) : dernier reporting, **mise en cache** dans les snapshots, re-fetchée seulement à nouveau trimestre.
- **Récurrent des comps** : extrait des filings/decks IR (document figé) → extraction LLM assistée + validation humaine, jamais un pull live.

## 4. Data model

SQLite en V1 via **SQLAlchemy** (le switch Postgres/Supabase en V2 = changement de connexion + adaptateur, pas de réécriture du modèle).

| Table | Rôle | Colonnes clés |
|---|---|---|
| `targets` | Cible à valoriser | `id`, `name`, `sector`, `is_recurring` (bool), `valuation_aggregate` (enum: arr/revenue/ebitda/…), `fund` (FR FII / EN FIII pour le template compta), `notes` |
| `target_anchors` | Ancres historiques figées (MODE A) | `id`, `target_id`, `entry_date`, `entry_round`, `m_entry_aggregate` (EV/agrégat au tour), `m_market_entry` (médiane marché au tour), `market_anchor_basis` (revenue/ebitda/arr — sur quel agrégat l'ancre marché est calculée), `m_market_entry_source` (computed/manual) |
| `comps` | Comparables cotés | `id`, `name`, `ticker`, `sector`, `currency`, `is_recurring`, `recurring_basis_tag` (subscription/recurring/arr/acv/null) |
| `comp_snapshots` | Snapshot financier horodaté immuable | `id`, `comp_id`, `snapshot_date`, `market_cap`, `net_debt`, `cash`, `revenue_ltm`, `recurring_value` (validé), `source_by_field` (JSON), **computed** `ev`, `ev_rev`, `ev_recurring` |
| `valuation_runs` | Exercice de valo daté | `id`, `target_id`, `run_date`, `mode` (A/B), `aggregate`, `median_now`, `retention_factor`, `m_final`, `result_ev`, `result_equity`, `excel_path` |
| `run_comps` | Panel d'un run (traçabilité) | `id`, `run_id`, `comp_snapshot_id`, `included` (bool), `exclusion_reason`, `relevance_note` |
| `transactions` | Transactions M&A comparables | `id`, `target_id`, `target_company`, `acquirer`, `tx_date`, `sector`, `price_disclosed` (bool), `price`, `implied_multiple`, `source_doc_url`, `origin` (llm/manual), `status` (proposed/validated), `notes` |

**Règles :**
- Les `comp_snapshots` sont **immuables et horodatés** (audit). Un nouveau trimestre = nouveaux snapshots, jamais d'écrasement.
- La médiane se calcule sur `run_comps.included = true` uniquement. Les exclus restent stockés, hors médiane.
- `transactions` = cross-check, **jamais** dans la médiane. Les transactions proposées par LLM ont `origin = llm` / `status = proposed` tant que l'humain n'a pas validé leurs chiffres depuis la source.
- Comps & transactions **proposés par LLM = identité + rationale + sources uniquement**. Aucun chiffre financier produit par le LLM n'entre dans la médiane : les chiffres des comps viennent de `YahooProvider`, ceux des transactions sont validés à la main.

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
- **Ancre marché `m_market_entry` — calcul automatique** : au run d'amorçage (MODE A), on reconstitue la médiane du panel à la `entry_date` via yfinance historique (prix historique + bilan trimestriel + revenue LTM à la date). Best-effort, avec **override manuel** toujours possible (l'ancre est gelée à vie → l'humain garde le dernier mot). Un comp sans donnée à la date (IPO postérieure, etc.) est exclu du calcul de l'ancre et signalé.
  - **Cas ARR** : l'ARR historique des comps n'existe pas. L'utilisateur choisit alors entre (a) **saisir manuellement** son multiple d'ARR d'entrée, ou (b) **ancrer sur EV/Revenue** (`market_anchor_basis = revenue`). Le ratio de dérive étant sans unité, un drift calculé sur EV/Revenue reste valide pour un multiple cible ancré sur l'ARR.
- **MODE A (amorçage)** : calcule puis gèle `m_entry_aggregate` et `m_market_entry`. **MODE B (trimestriel)** : ne re-price que `median_now`.
- **EV → equity 100 %** en sortie. **Provisions ACC** = sans rapport avec la valo equity, ne jamais écraser le calcul par multiples.
- **Extraction compta** pilotée par labels (templates FR Fonds II / EN Fonds III diffèrent).

## 6. Stack & dépendances

**Backend (Python 3.12) :**
- `fastapi` + `uvicorn` — API.
- `sqlalchemy` — ORM (SQLite V1 → Postgres V2 sans réécriture).
- `yfinance` (**version pinnée** + fallback) — données marché **live + historiques** (ancre marché).
- `openai` — **découverte comps & transactions** + extraction récurrent (interface `LLMProvider`, Claude slottable en V2).
- `openpyxl` — export Excel formula-driven.
- `pydantic` — schémas / validation.
- `structlog` — logs structurés ; `sentry-sdk` (optionnel via `SENTRY_DSN`).
- Tooling : `ruff` (lint), `pytest` (tests).

**Front (local V1) :** React 18 + TypeScript + Vite + shadcn-ui + Tailwind + TanStack Query.

**V2 :** Supabase (Postgres + RLS + auth), Docker (slim, non-root), GitHub Action `deploy.yml`, cible Axya.

## 7. API / interfaces

Contrats REST (FastAPI). L'ordre reflète le flux : **saisir → découvrir → valider → ancrer → chercher → Excel**.
- `POST /targets` — crée une cible (nom + chiffres clés + date/multiple d'entrée).
- `POST /targets/{id}/suggest` — **découverte LLM** : renvoie comps cotés (nom/ticker/rationale) + transactions M&A (identité/source/multiple « à vérifier »). Aucune acquisition financière à ce stade.
- `POST /targets/{id}/panel` — l'utilisateur soumet la sélection **validée/corrigée** (tickers + transactions retenues) → crée le run, associe le panel.
- `PATCH /runs/{id}/comps` — ajuste la sélection (include/exclude + motif).
- `POST /runs/{id}/anchor` — calcule `m_market_entry` (yfinance historique, ou saisie manuelle cas ARR) → renvoie pour **confirmation/override** → gèle l'ancre.
- `POST /runs/{id}/execute` — acquisition live des comps validés + calcul de valo (mode A/B) → résultat + Excel (onglets Synthèse + Comparables).
- `GET /runs/{id}` — résultat auditable.
- `POST /comps/{id}/recurring` — extraction LLM du récurrent → validation humaine (P4).
- `CRUD /transactions` — transactions M&A (création manuelle + validation des propositions LLM).

**Interfaces internes (pluggables) :** `MarketDataProvider` (`fetch_snapshot` live + `fetch_historical_snapshot`), `LLMProvider` (`suggest_comps`, `suggest_transactions`, `extract_recurring`), `Storage`. Ce sont les trois points de bascule V1→V2.

## 8. Sécurité & garde-fous

- **V1 local mono-utilisateur** : pas d'auth, SQLite local. Secrets (`OPENAI_API_KEY`, `SENTRY_DSN`) en `.env` uniquement, jamais commités ; toute variable → `.env.example`.
- **Portes de validation humaine obligatoires** : (a) sélection/correction des comps proposés par LLM, (b) validation des chiffres des transactions M&A proposées, (c) confirmation/override de l'ancre marché avant gel, (d) extraction du récurrent. Rien de produit par un LLM n'entre en médiane ou en mark sans validation.
- **Immuabilité** des snapshots (audit / reproductibilité).
- **V2** : RLS systématique, rôles lecture/écriture séparés, auth Supabase.

## 9. Phases d'implémentation

- **P1 — Socle données** : data model SQLAlchemy + `SQLiteStore` + couche acquisition `YahooProvider` + CLI de test. Doc de migration Supabase prête (sans l'implémenter).
- **P2 — Méthode** : couche méthode agrégat-agnostique (recomposition, médiane, calibration delta, MODE A/B) + export Excel. **Validée sur un cas réel (Syroco).**
- **P3 — API + Front** : FastAPI + front web local. Flux complet **saisir → découvrir (LLM) → valider → ancrer → chercher → Excel**. Inclut `OpenAIProvider.suggest_comps` / `suggest_transactions`, `fetch_historical_snapshot` pour l'ancre, et l'export Excel 2 onglets (Synthèse + Comparables). Transactions M&A auto-proposées + validation.
- **P4 — Extraction récurrent** : `OpenAIProvider.extract_recurring` pour l'ARR des comps + validation dans le front (débloque la valo ARR live).
- **P5 — Mise à l'échelle (V2)** : swap Supabase + RLS + auth, Docker + GitHub Action, déploiement Axya (avec Axel).

Chaque phase est testable indépendamment (pytest), miroir de `src/`.

## 10. Points ouverts

- **Cible de déploiement Axya** (VPS / Render / autre) — à trancher avec **Axel** en P5.
- **Provider data V2** (Dealroom via Axya ? autre lib Python ?) — dépend des accès ; l'interface `MarketDataProvider` est déjà prête à l'accueillir.
- **Fiabilité de la découverte LLM** — les tickers/transactions proposés sont validés à la main (garde-fou). Qualité à monitorer ; un provider data payant (V2) réduira la dépendance au LLM pour le sourcing.
- **Couverture yfinance historique** pour l'ancre marché — profondeur (~4 ans) et disponibilité variables selon les tickers ; fallback = override manuel de `m_market_entry`.
- **Standardisation de la définition du récurrent** entre comps — V1 = tag de base par comp, pas de normalisation auto.
- **Exposition MCP** — nice-to-have post-V2.
