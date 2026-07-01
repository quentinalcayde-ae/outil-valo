"""Interfaces pluggables — voir PROJECT_V1.md §7."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime

# ── MarketDataProvider ────────────────────────────────────────────────────────

@dataclass
class MarketSnapshot:
    ticker: str
    fetched_at: datetime
    market_cap: float | None
    net_debt: float | None
    cash: float | None
    revenue_ltm: float | None
    source_by_field: dict
    # Rempli pour un snapshot historique (ancre marché) ; None si live
    as_of_date: date | None = None


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        """Données marché courantes (live)."""
        ...

    @abstractmethod
    def fetch_historical_snapshot(self, ticker: str, as_of: date) -> MarketSnapshot:
        """Données marché reconstituées à une date passée (ancre marché, MODE A)."""
        ...


# ── LLMProvider ───────────────────────────────────────────────────────────────

@dataclass
class CompSuggestion:
    """Comparable coté proposé par le LLM — IDENTITÉ seulement, jamais de chiffre."""
    name: str
    ticker: str
    rationale: str          # pourquoi ce comp est pertinent
    sector: str | None = None
    confidence: str = "medium"


@dataclass
class TransactionSuggestion:
    """Transaction M&A proposée par le LLM — chiffres 'à vérifier' par l'humain."""
    target_company: str
    acquirer: str | None
    tx_date: date | None
    rationale: str
    source_doc_url: str | None = None
    implied_multiple: float | None = None  # best-effort, à valider
    sector: str | None = None


@dataclass
class RecurringExtraction:
    ticker: str
    recurring_value: float | None
    recurring_basis_tag: str | None
    source_excerpt: str
    confidence: str


@dataclass
class TargetContext:
    """Contexte passé au LLM pour la découverte."""
    name: str
    sector: str | None
    description: str | None
    is_recurring: bool
    valuation_aggregate: str
    aggregate_value: float | None = None
    extra_tickers: list[str] = field(default_factory=list)


class LLMProvider(ABC):
    @abstractmethod
    def suggest_comps(self, ctx: TargetContext, n: int = 8) -> list[CompSuggestion]:
        """Propose des comparables cotés (identité + rationale). Aucun chiffre financier."""
        ...

    @abstractmethod
    def suggest_transactions(self, ctx: TargetContext, n: int = 5) -> list[TransactionSuggestion]:
        """Propose des transactions M&A comparables (identité + source + multiple best-effort)."""
        ...

    @abstractmethod
    def extract_recurring(self, ticker: str, filing_text: str) -> RecurringExtraction:
        """Extrait le récurrent d'un filing/deck IR (P4)."""
        ...
