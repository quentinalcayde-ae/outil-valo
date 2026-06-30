"""Interfaces pluggables — voir PROJECT_V1.md §7."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class MarketSnapshot:
    ticker: str
    fetched_at: datetime
    market_cap: float | None
    net_debt: float | None
    cash: float | None
    revenue_ltm: float | None
    source_by_field: dict


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        """Fetch current market data for a ticker."""
        ...

    @abstractmethod
    def suggest_comps(self, target_description: str) -> list[dict]:
        """Suggest a panel of comparable listed companies."""
        ...


@dataclass
class RecurringExtraction:
    ticker: str
    recurring_value: float | None
    recurring_basis_tag: str | None
    source_excerpt: str
    confidence: str


class LLMProvider(ABC):
    @abstractmethod
    def extract_recurring(self, ticker: str, filing_text: str) -> RecurringExtraction:
        """Extract recurring revenue from a filing/IR deck."""
        ...
