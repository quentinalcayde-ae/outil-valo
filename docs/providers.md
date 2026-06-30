# Providers — interfaces et implémentations

*Reflète `src/valo/providers/`. Voir PROJECT_V1.md §3 pour la spec.*

## MarketDataProvider

Interface : `src/valo/providers/base.py`

```python
class MarketDataProvider(ABC):
    def fetch_snapshot(self, ticker: str) -> MarketSnapshot: ...
    def suggest_comps(self, target_description: str) -> list[dict]: ...
```

**`MarketSnapshot`** — champs retournés : `ticker`, `fetched_at`, `market_cap`, `net_debt`, `cash`, `revenue_ltm`, `source_by_field`.

### YahooProvider (V1)

`src/valo/providers/yahoo_provider.py` — yfinance, réseau ouvert local.

- `fetch_snapshot` : appelle `yf.Ticker(ticker).info`, mappe les champs yfinance.
  - `net_debt = totalDebt - totalCash` (peut être négatif = trésorerie nette).
  - `revenue_ltm = totalRevenue`.
- `suggest_comps` : non implémenté en P1 — sera branché sur LLM en P3.

**Point de bascule V2** : remplacer `YahooProvider` par un provider Dealroom ou autre lib — l'interface `MarketDataProvider` reste stable.

## LLMProvider

Interface : `src/valo/providers/base.py`

```python
class LLMProvider(ABC):
    def extract_recurring(self, ticker: str, filing_text: str) -> RecurringExtraction: ...
```

**`RecurringExtraction`** — champs : `ticker`, `recurring_value`, `recurring_basis_tag`, `source_excerpt`, `confidence`.

- V1 : `OpenAIProvider` (P4).
- V2 : `ClaudeProvider` slottable (même interface).

## Storage

Interface : `src/valo/storage/base.py` — voir [`data-model.md`](data-model.md).
