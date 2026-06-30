"""CRUD repositories — toutes les opérations DB passent par ici, jamais par session directe."""
from datetime import datetime

from sqlalchemy.orm import Session

from valo.models import (
    Comp,
    CompSnapshot,
    RunComp,
    Target,
    TargetAnchor,
    Transaction,
    ValuationRun,
)
from valo.providers.base import MarketSnapshot


# ── Targets ─────────────────────────────────────────────────────────────────

def create_target(session: Session, **kwargs) -> Target:
    target = Target(**kwargs)
    session.add(target)
    session.flush()
    return target


def get_target(session: Session, target_id: int) -> Target | None:
    return session.get(Target, target_id)


def list_targets(session: Session) -> list[Target]:
    return session.query(Target).order_by(Target.created_at.desc()).all()


def create_anchor(session: Session, target_id: int, **kwargs) -> TargetAnchor:
    anchor = TargetAnchor(target_id=target_id, **kwargs)
    session.add(anchor)
    session.flush()
    return anchor


def get_anchors(session: Session, target_id: int) -> list[TargetAnchor]:
    return session.query(TargetAnchor).filter_by(target_id=target_id).all()


# ── Comps ────────────────────────────────────────────────────────────────────

def create_comp(session: Session, **kwargs) -> Comp:
    comp = Comp(**kwargs)
    session.add(comp)
    session.flush()
    return comp


def get_comp_by_ticker(session: Session, ticker: str) -> Comp | None:
    return session.query(Comp).filter_by(ticker=ticker.upper()).first()


def list_comps(session: Session) -> list[Comp]:
    return session.query(Comp).order_by(Comp.name).all()


# ── CompSnapshots (immuables — insert only) ──────────────────────────────────

def insert_snapshot(session: Session, comp_id: int, snap: MarketSnapshot) -> CompSnapshot:
    """Crée un nouveau snapshot horodaté. Ne jamais mettre à jour un snapshot existant."""
    ev = None
    ev_rev = None
    ev_recurring = None

    if snap.market_cap is not None and snap.net_debt is not None:
        ev = snap.market_cap + snap.net_debt
        if snap.revenue_ltm and snap.revenue_ltm > 0:
            ev_rev = ev / snap.revenue_ltm

    snapshot = CompSnapshot(
        comp_id=comp_id,
        snapshot_date=snap.fetched_at,
        market_cap=snap.market_cap,
        net_debt=snap.net_debt,
        cash=snap.cash,
        revenue_ltm=snap.revenue_ltm,
        recurring_value=None,
        source_by_field=snap.source_by_field,
        ev=ev,
        ev_rev=ev_rev,
        ev_recurring=ev_recurring,
    )
    session.add(snapshot)
    session.flush()
    return snapshot


def get_latest_snapshot(session: Session, comp_id: int) -> CompSnapshot | None:
    return (
        session.query(CompSnapshot)
        .filter_by(comp_id=comp_id)
        .order_by(CompSnapshot.snapshot_date.desc(), CompSnapshot.id.desc())
        .first()
    )


def list_snapshots(session: Session, comp_id: int) -> list[CompSnapshot]:
    return (
        session.query(CompSnapshot)
        .filter_by(comp_id=comp_id)
        .order_by(CompSnapshot.snapshot_date.desc())
        .all()
    )


def update_snapshot_recurring(
    session: Session,
    snapshot_id: int,
    recurring_value: float,
    recurring_basis_tag: str | None = None,
) -> CompSnapshot:
    """Validation humaine du récurrent — seul champ mutable après création."""
    snap = session.get(CompSnapshot, snapshot_id)
    if snap is None:
        raise ValueError(f"Snapshot {snapshot_id} introuvable.")
    snap.recurring_value = recurring_value
    if snap.ev and recurring_value > 0:
        snap.ev_recurring = snap.ev / recurring_value
    if recurring_basis_tag is not None:
        comp = session.get(Comp, snap.comp_id)
        if comp:
            comp.recurring_basis_tag = recurring_basis_tag
    session.flush()
    return snap


# ── Valuation runs ───────────────────────────────────────────────────────────

def create_run(session: Session, **kwargs) -> ValuationRun:
    run = ValuationRun(**kwargs)
    session.add(run)
    session.flush()
    return run


def get_run(session: Session, run_id: int) -> ValuationRun | None:
    return session.get(ValuationRun, run_id)


def add_run_comp(session: Session, run_id: int, snapshot_id: int, **kwargs) -> RunComp:
    rc = RunComp(run_id=run_id, comp_snapshot_id=snapshot_id, **kwargs)
    session.add(rc)
    session.flush()
    return rc


def update_run_result(
    session: Session,
    run_id: int,
    median_now: float,
    retention_factor: float,
    m_final: float,
    result_ev: float | None,
    result_equity: float | None,
    excel_path: str | None = None,
) -> ValuationRun:
    run = session.get(ValuationRun, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} introuvable.")
    run.median_now = median_now
    run.retention_factor = retention_factor
    run.m_final = m_final
    run.result_ev = result_ev
    run.result_equity = result_equity
    run.excel_path = excel_path
    session.flush()
    return run


# ── Transactions M&A ─────────────────────────────────────────────────────────

def create_transaction(session: Session, **kwargs) -> Transaction:
    tx = Transaction(**kwargs)
    session.add(tx)
    session.flush()
    return tx


def list_transactions(session: Session) -> list[Transaction]:
    return session.query(Transaction).order_by(Transaction.tx_date.desc()).all()


def get_transaction(session: Session, tx_id: int) -> Transaction | None:
    return session.get(Transaction, tx_id)


def update_transaction(session: Session, tx_id: int, **kwargs) -> Transaction:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise ValueError(f"Transaction {tx_id} introuvable.")
    for k, v in kwargs.items():
        setattr(tx, k, v)
    session.flush()
    return tx


def delete_transaction(session: Session, tx_id: int) -> None:
    tx = session.get(Transaction, tx_id)
    if tx is None:
        raise ValueError(f"Transaction {tx_id} introuvable.")
    session.delete(tx)
    session.flush()
