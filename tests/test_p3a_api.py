"""Tests P3a — flux complet via l'API : target → suggest → panel → anchor → execute.

Providers fakes injectés (mock LLM par défaut, fake marché live + historique).
"""
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from valo.dependencies import get_llm, get_session, get_yahoo
from valo.main import app
from valo.models import Base
from valo.providers.base import MarketDataProvider, MarketSnapshot
from valo.providers.mock_llm import MockLLMProvider


class FakeMarketProvider(MarketDataProvider):
    """Live + historique cannés (mêmes chiffres) pour un flux déterministe."""
    LIVE = {
        "CRM": (200e9, 10e9, 30e9),   # market_cap, net_debt, revenue → EV=210, 7x
        "NOW": (100e9, 0, 10e9),      # 10x
        "WDAY": (60e9, 0, 6e9),       # 10x
        "HUBS": (30e9, 0, 3e9),       # 10x
        "VEEV": (28e9, -2e9, 2e9),    # EV=26 → 13x
    }

    def fetch_snapshot(self, ticker: str) -> MarketSnapshot:
        mc, nd, rev = self.LIVE[ticker]
        return MarketSnapshot(ticker, datetime(2026, 7, 1), mc, nd, 0, rev, {})

    def fetch_historical_snapshot(self, ticker: str, as_of: date) -> MarketSnapshot:
        mc, nd, rev = self.LIVE[ticker]
        # Marché "au tour" : 20% plus bas en valo → multiples plus faibles
        return MarketSnapshot(ticker, datetime(2026, 7, 1), mc * 0.8, nd, 0, rev, {}, as_of_date=as_of)


@pytest.fixture
def client(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    def override_session():
        s = Session()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_yahoo] = lambda: FakeMarketProvider()
    app.dependency_overrides[get_llm] = lambda: MockLLMProvider()  # déterministe, zéro appel réseau
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_full_flow(client, tmp_path, monkeypatch):
    # export Excel dans tmp
    import valo.method.service as svc
    monkeypatch.setattr(svc, "export_excel", lambda **kw: str(tmp_path / "out.xlsx"))

    # 1. Cible avec chiffres clés
    t = client.post("/targets", json={
        "name": "Syroco", "sector": "SaaS maritime", "description": "logiciel SaaS",
        "is_recurring": True, "valuation_aggregate": "revenue",
        "aggregate_value": 8e6,
    }).json()
    tid = t["id"]

    # 2. Découverte LLM (mock)
    sug = client.post(f"/targets/{tid}/suggest", json={"n_comps": 5, "n_transactions": 2}).json()
    assert len(sug["comps"]) == 5
    assert len(sug["transactions"]) == 2
    tickers = [c["ticker"] for c in sug["comps"]]

    # 3. Panel validé (identité seulement)
    run = client.post(f"/runs/panel?target_id={tid}", json={
        "comps": [{"ticker": tk, "name": tk} for tk in tickers],
        "mode": "A", "aggregate": "revenue", "other_deltas": 0.0,
        "anchor": {"entry_date": "2023-06-30", "entry_round": "Série B", "m_entry_aggregate": 8.0},
    }).json()
    run_id = run["id"]
    assert len(run["run_comps"]) == 5
    # Pas encore de snapshot (recherche financière non faite)
    assert all(rc["snapshot"] is None for rc in run["run_comps"])

    # 4. Ancre auto (historique)
    anchor = client.post(f"/runs/{run_id}/anchor", json={}).json()
    assert anchor["source"] == "computed"
    assert anchor["m_market_entry"] is not None
    assert anchor["n_available"] == 5

    # 5. Execute (recherche financière live + valo + Excel)
    result = client.post(f"/runs/{run_id}/execute", json={}).json()
    assert result["m_final"] is not None
    assert result["result_ev"] is not None
    # Snapshots gelés à l'execute
    assert any(rc["snapshot"] is not None for rc in result["run_comps"])


def test_anchor_manual_override(client):
    t = client.post("/targets", json={
        "name": "T", "is_recurring": True, "valuation_aggregate": "arr", "aggregate_value": 5e6,
    }).json()
    tid = t["id"]
    run = client.post(f"/runs/panel?target_id={tid}", json={
        "comps": [{"ticker": "CRM"}],
        "mode": "A", "aggregate": "arr", "other_deltas": 0.0,
        "anchor": {"entry_date": "2023-06-30", "m_entry_aggregate": 12.0},
    }).json()
    # Cas ARR : override manuel du multiple d'ancre
    anchor = client.post(f"/runs/{run['id']}/anchor", json={"manual_value": 15.0, "basis": "arr"}).json()
    assert anchor["source"] == "manual"
    assert anchor["m_market_entry"] == 15.0
    assert anchor["basis"] == "arr"
