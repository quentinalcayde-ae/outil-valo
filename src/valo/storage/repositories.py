"""CRUD repositories — toutes les opérations DB passent par ici, jamais par session directe."""

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


def delete_target(session: Session, target_id: int) -> None:
    """Supprime une cible et tout ce qui en dépend (runs, run_comps, ancres, transactions liées).
    Les comps/snapshots sont partagés entre cibles → conservés."""
    target = session.get(Target, target_id)
    if target is None:
        raise ValueError(f"Cible {target_id} introuvable.")
    run_ids = [r.id for r in session.query(ValuationRun).filter_by(target_id=target_id).all()]
    if run_ids:
        session.query(RunComp).filter(RunComp.run_id.in_(run_ids)).delete(synchronize_session=False)
        session.query(ValuationRun).filter(ValuationRun.id.in_(run_ids)).delete(synchronize_session=False)
    session.query(TargetAnchor).filter_by(target_id=target_id).delete(synchronize_session=False)
    session.query(Transaction).filter_by(target_id=target_id).delete(synchronize_session=False)
    session.delete(target)
    session.flush()


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
        revenue_growth=snap.revenue_growth,
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


def add_run_comp(
    session: Session,
    run_id: int,
    comp_id: int,
    snapshot_id: int | None = None,
    **kwargs,
) -> RunComp:
    """Associe un comp (identité) au panel d'un run. Le snapshot est lié plus tard (execute)."""
    rc = RunComp(run_id=run_id, comp_id=comp_id, comp_snapshot_id=snapshot_id, **kwargs)
    session.add(rc)
    session.flush()
    return rc


def link_run_comp_snapshot(session: Session, run_comp_id: int, snapshot_id: int) -> RunComp:
    """Attache le snapshot gelé effectivement utilisé (recherche financière à l'execute)."""
    rc = session.get(RunComp, run_comp_id)
    if rc is None:
        raise ValueError(f"RunComp {run_comp_id} introuvable.")
    rc.comp_snapshot_id = snapshot_id
    session.flush()
    return rc


def set_anchor_market(
    session: Session,
    anchor_id: int,
    m_market_entry: float,
    basis: str,
    source: str,
    entry_panel_growth: float | None = None,
) -> "TargetAnchor":
    """Gèle l'ancre marché (calculée ou saisie) — MODE A."""
    anchor = session.get(TargetAnchor, anchor_id)
    if anchor is None:
        raise ValueError(f"Ancre {anchor_id} introuvable.")
    anchor.m_market_entry = m_market_entry
    anchor.market_anchor_basis = basis
    anchor.m_market_entry_source = source
    if entry_panel_growth is not None:
        anchor.entry_panel_growth = entry_panel_growth
    session.flush()
    return anchor


def update_run_result(
    session: Session,
    run_id: int,
    median_now: float,
    m_final: float,
    result_ev: float | None,
    result_equity: float | None,
    excel_path: str | None = None,
    winsor_mean: float | None = None,
    flags: list[str] | None = None,
) -> ValuationRun:
    run = session.get(ValuationRun, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} introuvable.")
    run.median_now = median_now
    run.m_final = m_final
    run.result_ev = result_ev
    run.result_equity = result_equity
    run.excel_path = excel_path
    run.winsor_mean = winsor_mean
    run.flags = flags or []
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
