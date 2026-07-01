# Providers — interfaces et implémentations

*Reflète `src/valo/providers/`. Voir PROJECT_V1.md §3/§7.*

## MarketDataProvider

`src/valo/providers/base.py` :

```python
class MarketDataProvider(ABC):
    def fetch_snapshot(self, ticker) -> MarketSnapshot: ...              # live
    def fetch_historical_snapshot(self, ticker, as_of) -> MarketSnapshot: ...  # ancre marché
```

`MarketSnapshot` : `ticker`, `fetched_at`, `market_cap`, `net_debt`, `cash`, `revenue_ltm`, `source_by_field`, `as_of_date` (rempli si historique).

### YahooProvider (V1) — `yahoo_provider.py`

- `fetch_snapshot` : `yf.Ticker(t).info` → `net_debt = totalDebt - totalCash`, `revenue_ltm = totalRevenue`.
- `fetch_historical_snapshot(ticker, as_of)` : **best-effort** pour l'ancre marché (MODE A).
  - `market_cap` ≈ close historique (fenêtre ±7j) × `sharesOutstanding` courant.
  - `net_debt` / `revenue_ltm` : états **trimestriels** (LTM = 4 trimestres) puis fallback **annuels** (profondeur ~4 ans) — les trimestriels ne remontent que ~5 trimestres.
  - Lève `HistoricalDataUnavailable` si le prix à la date est introuvable (IPO postérieure…).

**Point de bascule V2** : provider payant (Dealroom…) derrière la même interface.

## LLMProvider

`src/valo/providers/base.py` — **découverte + extraction**, jamais source de chiffre en médiane :

```python
class LLMProvider(ABC):
    def suggest_comps(self, ctx: TargetContext, n=8) -> list[CompSuggestion]: ...
    def suggest_transactions(self, ctx: TargetContext, n=5) -> list[TransactionSuggestion]: ...
    def extract_recurring(self, ticker, filing_text) -> RecurringExtraction: ...  # P4
```

- `CompSuggestion` : `name`, `ticker`, `rationale`, `sector`, `confidence` — **identité uniquement**.
- `TransactionSuggestion` : `target_company`, `acquirer`, `tx_date`, `rationale`, `source_doc_url`, `implied_multiple` (**best-effort, « à vérifier »**).
- `TargetContext` : contexte passé au LLM (`name`, `sector`, `description`, `is_recurring`, `valuation_aggregate`, `aggregate_value`, `extra_tickers`).

### Implémentations

- **`MockLLMProvider`** (`mock_llm.py`) — suggestions déterministes par secteur, **zéro réseau**. Utilisé en P3a et dans les tests (voir [feedback tests LLM]).
- **`OpenAIProvider`** (P3b) — même interface, modèle configurable (défaut petit modèle), prompts versionnés. Activé quand `OPENAI_API_KEY` est présent (`dependencies.get_llm`).

## Storage

`storage/base.py` + `SQLiteStore` — voir [`data-model.md`](data-model.md).
