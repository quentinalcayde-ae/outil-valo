"""Tests P1 — SQLiteStore + repositories CRUD."""
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from valo.models import Base
from valo.providers.base import MarketSnapshot
from valo.storage.repositories import (
    create_anchor,
    create_comp,
    create_target,
    create_transaction,
    delete_transaction,
    get_anchors,
    get_comp_by_ticker,
    get_latest_snapshot,
    insert_snapshot,
    list_comps,
    list_targets,
    list_transactions,
    update_snapshot_recurring,
    update_transaction,
)


@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _snap(ticker="ADBE", market_cap=50e9, net_debt=1e9, revenue_ltm=5e9) -> MarketSnapshot:
    return MarketSnapshot(
        ticker=ticker,
        fetched_at=datetime(2026, 6, 30, 12, 0),
        market_cap=market_cap,
        net_debt=net_debt,
        cash=500e6,
        revenue_ltm=revenue_ltm,
        source_by_field={"market_cap": "yfinance:marketCap"},
    )


# ── Targets ──────────────────────────────────────────────────────────────────

def test_create_and_list_target(session):
    create_target(session, name="Syroco", is_recurring=True, valuation_aggregate="arr")
    targets = list_targets(session)
    assert len(targets) == 1
    assert targets[0].name == "Syroco"


def test_create_anchor(session):
    t = create_target(session, name="T", is_recurring=True, valuation_aggregate="arr")
    anchor = create_anchor(
        session, t.id,
        entry_date=date(2024, 1, 1),
        m_entry_aggregate=8.0,
        m_market_entry=10.0,
    )
    anchors = get_anchors(session, t.id)
    assert len(anchors) == 1
    assert anchors[0].m_entry_aggregate == 8.0


# ── Comps & Snapshots ─────────────────────────────────────────────────────────

def test_create_comp(session):
    comp = create_comp(session, name="Adobe", ticker="ADBE", currency="USD", is_recurring=True)
    found = get_comp_by_ticker(session, "adbe")
    assert found is not None
    assert found.id == comp.id


def test_insert_snapshot_computes_ev(session):
    comp = create_comp(session, name="Adobe", ticker="ADBE", currency="USD", is_recurring=True)
    snap = _snap()
    stored = insert_snapshot(session, comp.id, snap)
    assert stored.ev == pytest.approx(51e9)
    assert stored.ev_rev == pytest.approx(51e9 / 5e9)


def test_snapshot_immutable_on_new_insert(session):
    comp = create_comp(session, name="Adobe", ticker="ADBE", currency="USD", is_recurring=True)
    insert_snapshot(session, comp.id, _snap(market_cap=50e9))
    insert_snapshot(session, comp.id, _snap(market_cap=55e9))
    snaps = list_comps(session)
    # latest snapshot doit être le second
    latest = get_latest_snapshot(session, comp.id)
    assert latest.market_cap == 55e9


def test_update_snapshot_recurring(session):
    comp = create_comp(session, name="Adobe", ticker="ADBE", currency="USD", is_recurring=True)
    stored = insert_snapshot(session, comp.id, _snap())
    updated = update_snapshot_recurring(session, stored.id, recurring_value=4e9, recurring_basis_tag="arr")
    assert updated.recurring_value == 4e9
    assert updated.ev_recurring == pytest.approx(51e9 / 4e9)


def test_snapshot_no_ev_when_missing_data(session):
    comp = create_comp(session, name="X", ticker="XXXX", currency="USD", is_recurring=False)
    snap = MarketSnapshot(
        ticker="XXXX",
        fetched_at=datetime.now(UTC),
        market_cap=None,
        net_debt=None,
        cash=None,
        revenue_ltm=None,
        source_by_field={},
    )
    stored = insert_snapshot(session, comp.id, snap)
    assert stored.ev is None
    assert stored.ev_rev is None


# ── Transactions M&A ─────────────────────────────────────────────────────────

def test_transaction_crud(session):
    tx = create_transaction(
        session,
        target_company="Acme SaaS",
        acquirer="BigCorp",
        tx_date=date(2023, 6, 1),
        price_disclosed=True,
        price=100e6,
        implied_multiple=8.5,
    )
    txs = list_transactions(session)
    assert len(txs) == 1
    assert txs[0].implied_multiple == 8.5

    updated = update_transaction(session, tx.id, implied_multiple=9.0)
    assert updated.implied_multiple == 9.0

    delete_transaction(session, tx.id)
    assert list_transactions(session) == []
