# outil-valo-comparables

Outil de **valorisation par multiples de comparables** selon la méthode IPEV (calibration par maintien du delta).

Décrit une cible → propose un panel de comparables cotés → valide la sélection → gèle la donnée de marché → applique la méthode → export Excel auditable.

## Stack

- **Backend** : Python 3.12 · FastAPI · SQLAlchemy · SQLite (V1) · yfinance · OpenAI · openpyxl
- **Frontend** : React 18 · TypeScript · Vite · shadcn-ui · Tailwind · TanStack Query

## Quickstart (V1 local)

```bash
# Backend
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
cp .env.example .env            # remplir OPENAI_API_KEY
uvicorn src.valo.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

L'API tourne sur `http://localhost:8000`, le front sur `http://localhost:5173`.

## Structure

```
src/valo/          — backend (FastAPI + logique métier)
  providers/       — MarketDataProvider, LLMProvider (interfaces pluggables)
  method/          — recomposition EV, médiane, calibration delta, export Excel
  storage/         — Storage interface + SQLiteStore
tests/             — pytest, miroir de src/
frontend/          — React + Vite
migrations/        — SQL numérotés (prêts pour Supabase V2)
scripts/           — one-shots idempotents
docs/              — snapshot de l'architecture réelle
```

## Docs

- [`PROJECT_V1.md`](PROJECT_V1.md) — source de vérité (spec complète, méthode verrouillée)
- [`docs/index.md`](docs/index.md) — navigation dans les docs techniques
- [`CLAUDE.md`](CLAUDE.md) — instructions IA / conventions
