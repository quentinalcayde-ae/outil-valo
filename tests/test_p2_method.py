"""Tests P2 — service d'orchestration du run."""
from datetime import UTC, date, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from valo.method.service import execute_run
from valo.models import Base
from valo.providers.base import MarketSnapshot
from valo.storage.repositories import (
    add_run_comp,
    create_anchor,
    create_comp,
    create_run,
    create_target,
    insert_snapshot,
)


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path}/test.db")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()


def _make_snap(ticker, market_cap, net_debt, revenue_ltm):
    return MarketSnapshot(
        ticker=ticker,
        fetched_at=datetime.now(UTC),
        market_cap=market_cap,
        net_debt=net_debt,
        cash=0,
        revenue_ltm=revenue_ltm,
        source_by_field={},
    )


def _setup_run(session, mode="A", aggregate="revenue", retention_factor=1.0):
    target = create_target(session, name="Cible Test", is_recurring=True, valuation_aggregate=aggregate)
    create_anchor(
        session, target.id,
        entry_date=date(2023, 1, 1),
        entry_round="Série B",
        m_entry_aggregate=8.0,
        m_market_entry=10.0,
    )
    comps_data = [
        ("AAA", 100e6, 10e6, 10e6),
        ("BBB", 200e6, 20e6, 20e6),
        ("CCC", 150e6, 15e6, 15e6),
    ]
    run = create_run(session, target_id=target.id, mode=mode, aggregate=aggregate,
                     retention_factor=retention_factor)
    for ticker, mc, nd, rev in comps_data:
        comp = create_comp(session, name=ticker, ticker=ticker, currency="USD", is_recurring=True)
        snap = insert_snapshot(session, comp.id, _make_snap(ticker, mc, nd, rev))
        add_run_comp(session, run_id=run.id, comp_id=comp.id, snapshot_id=snap.id, included=True)
    session.flush()
    return run.id, target.id


def test_execute_run_basic(session, tmp_path):
    run_id, _ = _setup_run(session)
    ctx = execute_run(session, run_id, target_aggregate_value=5e6, output_dir=str(tmp_path))

    # AAA: EV=110M / Rev=10M = 11x ; BBB: 220M/20M = 11x ; CCC: 165M/15M = 11x → médiane = 11x
    assert ctx.result.median_now == pytest.approx(11.0)
    # drift = 11 / 10 = 1.1 ; m_final = 8 * 1.1 * 1.0 = 8.8
    assert ctx.result.m_final == pytest.approx(8.8)
    assert ctx.run.result_ev == pytest.approx(8.8 * 5e6)


def test_execute_run_mode_b(session, tmp_path):
    run_id, _ = _setup_run(session, mode="B")
    ctx = execute_run(session, run_id, target_aggregate_value=5e6, output_dir=str(tmp_path))
    assert ctx.run.mode == "B"
    assert ctx.result.m_final == pytest.approx(8.8)


def test_execute_run_with_retention(session, tmp_path):
    run_id, _ = _setup_run(session, retention_factor=1.2)
    ctx = execute_run(session, run_id, target_aggregate_value=5e6, output_dir=str(tmp_path))
    # m_final = 8 * 1.1 * 1.2 = 10.56
    assert ctx.result.m_final == pytest.approx(10.56)


def test_execute_run_excluded_comp(session, tmp_path):
    """Un comp exclu ne rentre pas dans la médiane."""
    target = create_target(session, name="T", is_recurring=True, valuation_aggregate="revenue")
    create_anchor(session, target.id, entry_date=date(2023, 1, 1),
                  m_entry_aggregate=8.0, m_market_entry=10.0)
    run = create_run(session, target_id=target.id, mode="A", aggregate="revenue", retention_factor=1.0)

    # Comp inclus : multiple 11x
    comp1 = create_comp(session, name="AAA", ticker="AAA1", currency="USD", is_recurring=True)
    snap1 = insert_snapshot(session, comp1.id, _make_snap("AAA1", 110e6, 0, 10e6))
    add_run_comp(session, run_id=run.id, comp_id=comp1.id, snapshot_id=snap1.id, included=True)

    # Comp exclu : multiple 5x (outlier distressed)
    comp2 = create_comp(session, name="EXCL", ticker="EXCL", currency="USD", is_recurring=True)
    snap2 = insert_snapshot(session, comp2.id, _make_snap("EXCL", 50e6, 0, 10e6))
    add_run_comp(session, run_id=run.id, comp_id=comp2.id, snapshot_id=snap2.id, included=False,
                 exclusion_reason="Distressed")
    session.flush()

    ctx = execute_run(session, run.id, target_aggregate_value=5e6, output_dir=str(tmp_path))
    assert len(ctx.included_comps) == 1
    assert len(ctx.excluded_comps) == 1
    assert ctx.result.median_now == pytest.approx(11.0)


def test_execute_run_no_anchor_direct_mode(session, tmp_path):
    """Sans ancre → valorisation directe : M_final = médiane des comparables × rétention."""
    target = create_target(session, name="T", is_recurring=True, valuation_aggregate="revenue")
    run = create_run(session, target_id=target.id, mode="A", aggregate="revenue", retention_factor=1.0)
    for ticker, mc, nd, rev in [("AAA", 110e6, 0, 10e6), ("BBB", 240e6, 0, 20e6)]:  # 11x, 12x
        comp = create_comp(session, name=ticker, ticker=ticker, currency="USD", is_recurring=True)
        snap = insert_snapshot(session, comp.id, _make_snap(ticker, mc, nd, rev))
        add_run_comp(session, run_id=run.id, comp_id=comp.id, snapshot_id=snap.id, included=True)
    session.flush()

    ctx = execute_run(session, run.id, target_aggregate_value=5e6, output_dir=str(tmp_path))
    assert ctx.result.calibrated is False
    assert ctx.result.median_now == pytest.approx(11.5)  # médiane [11, 12]
    assert ctx.result.m_final == pytest.approx(11.5)
    assert ctx.run.result_ev == pytest.approx(11.5 * 5e6)


def test_excel_file_created(session, tmp_path):
    run_id, _ = _setup_run(session)
    ctx = execute_run(session, run_id, target_aggregate_value=5e6, output_dir=str(tmp_path))
    import os
    assert ctx.excel_path is not None
    assert os.path.exists(ctx.excel_path)
    assert ctx.excel_path.endswith(".xlsx")
