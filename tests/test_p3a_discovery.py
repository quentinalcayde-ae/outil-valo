"""Tests P3a — découverte (mock LLM) + calcul d'ancre marché (fake provider historique)."""
from datetime import date, datetime

import pytest

from valo.method.anchor import compute_market_anchor
from valo.providers.base import MarketDataProvider, MarketSnapshot, TargetContext
from valo.providers.mock_llm import MockLLMProvider

# ── Mock LLM ──────────────────────────────────────────────────────────────────

def test_suggest_comps_saas():
    llm = MockLLMProvider()
    ctx = TargetContext(name="Syroco", sector="SaaS maritime", description="logiciel SaaS",
                        is_recurring=True, valuation_aggregate="arr")
    comps = llm.suggest_comps(ctx, n=5)
    assert len(comps) == 5
    assert all(c.ticker and c.rationale for c in comps)
    assert "CRM" in {c.ticker for c in comps}


def test_suggest_comps_includes_user_tickers():
    llm = MockLLMProvider()
    ctx = TargetContext(name="X", sector="SaaS", description="software",
                        is_recurring=True, valuation_aggregate="revenue",
                        extra_tickers=["ZZZZ"])
    comps = llm.suggest_comps(ctx, n=3)
    assert "ZZZZ" in {c.ticker for c in comps}


def test_suggest_transactions():
    llm = MockLLMProvider()
    ctx = TargetContext(name="X", sector="SaaS", description="software SaaS",
                        is_recurring=True, valuation_aggregate="arr")
    txs = llm.suggest_transactions(ctx, n=2)
    assert len(txs) == 2
    # Chiffres non fournis par le LLM (à vérifier par l'humain)
    assert all(t.implied_multiple is None for t in txs)


# ── Ancre marché ──────────────────────────────────────────────────────────────

class FakeHistoricalProvider(MarketDataProvider):
    """Provider historique canné pour tester le calcul d'ancre sans yfinance."""
    def __init__(self, data: dict[str, dict | None]):
        self.data = data  # ticker -> {market_cap, net_debt, revenue_ltm} ou None (indispo)

    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        raise NotImplementedError

    def fetch_historical_snapshot(self, ticker: str, as_of: date) -> MarketSnapshot:
        d = self.data.get(ticker)
        if d is None:
            raise RuntimeError(f"{ticker}: pas de données à {as_of}")
        return MarketSnapshot(
            ticker=ticker, fetched_at=datetime(2023, 1, 1),
            market_cap=d["market_cap"], net_debt=d["net_debt"], cash=None,
            revenue_ltm=d["revenue_ltm"], source_by_field={}, as_of_date=as_of,
        )


def test_compute_anchor_median():
    provider = FakeHistoricalProvider({
        "AAA": {"market_cap": 100e6, "net_debt": 10e6, "revenue_ltm": 10e6},  # EV=110 → 11x
        "BBB": {"market_cap": 200e6, "net_debt": 20e6, "revenue_ltm": 20e6},  # 11x
        "CCC": {"market_cap": 90e6, "net_debt": 0, "revenue_ltm": 10e6},      # 9x
    })
    proposal = compute_market_anchor(provider, ["AAA", "BBB", "CCC"], date(2023, 6, 30))
    assert proposal.n_available == 3
    assert proposal.m_market_entry == pytest.approx(11.0)  # médiane de [11, 11, 9]
    assert proposal.basis == "revenue"


def test_compute_anchor_skips_unavailable():
    provider = FakeHistoricalProvider({
        "AAA": {"market_cap": 110e6, "net_debt": 0, "revenue_ltm": 10e6},  # 11x
        "IPO": None,  # IPO postérieure → indispo
    })
    proposal = compute_market_anchor(provider, ["AAA", "IPO"], date(2023, 6, 30))
    assert proposal.n_available == 1
    assert proposal.m_market_entry == pytest.approx(11.0)
    unavailable = [d for d in proposal.details if not d.available]
    assert len(unavailable) == 1
    assert unavailable[0].ticker == "IPO"


def test_compute_anchor_all_unavailable():
    provider = FakeHistoricalProvider({"IPO1": None, "IPO2": None})
    proposal = compute_market_anchor(provider, ["IPO1", "IPO2"], date(2023, 6, 30))
    assert proposal.n_available == 0
    assert proposal.m_market_entry is None
