from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from valo.dependencies import get_session, get_yahoo
from valo.providers.yahoo_provider import YahooProvider
from valo.schemas import CompCreate, CompOut, SnapshotOut
from valo.storage.repositories import (
    create_comp,
    get_comp_by_ticker,
    get_latest_snapshot,
    insert_snapshot,
    list_comps,
    list_snapshots,
    update_snapshot_recurring,
)

router = APIRouter(prefix="/comps", tags=["comps"])


@router.post("", response_model=CompOut, status_code=status.HTTP_201_CREATED)
def create(body: CompCreate, session: Session = Depends(get_session)):
    existing = get_comp_by_ticker(session, body.ticker)
    if existing:
        raise HTTPException(status_code=409, detail=f"Ticker {body.ticker.upper()} déjà enregistré.")
    return create_comp(session, **body.model_dump())


@router.get("", response_model=list[CompOut])
def list_all(session: Session = Depends(get_session)):
    return list_comps(session)


@router.get("/{ticker}", response_model=CompOut)
def get_one(ticker: str, session: Session = Depends(get_session)):
    comp = get_comp_by_ticker(session, ticker)
    if comp is None:
        raise HTTPException(status_code=404, detail="Comparable introuvable.")
    return comp


@router.post("/{ticker}/refresh", response_model=SnapshotOut)
def refresh_snapshot(
    ticker: str,
    session: Session = Depends(get_session),
    provider: YahooProvider = Depends(get_yahoo),
):
    """Déclenche l'acquisition d'un nouveau snapshot horodaté."""
    comp = get_comp_by_ticker(session, ticker)
    if comp is None:
        raise HTTPException(status_code=404, detail="Comparable introuvable.")
    try:
        snap = provider.fetch_snapshot(ticker)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Erreur acquisition Yahoo : {exc}")
    return insert_snapshot(session, comp.id, snap)


@router.get("/{ticker}/snapshots", response_model=list[SnapshotOut])
def get_snapshots(ticker: str, session: Session = Depends(get_session)):
    comp = get_comp_by_ticker(session, ticker)
    if comp is None:
        raise HTTPException(status_code=404, detail="Comparable introuvable.")
    return list_snapshots(session, comp.id)


@router.get("/{ticker}/snapshot/latest", response_model=SnapshotOut)
def get_latest(ticker: str, session: Session = Depends(get_session)):
    comp = get_comp_by_ticker(session, ticker)
    if comp is None:
        raise HTTPException(status_code=404, detail="Comparable introuvable.")
    snap = get_latest_snapshot(session, comp.id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Aucun snapshot disponible.")
    return snap


class RecurringIn(BaseModel):
    recurring_value: float
    recurring_basis_tag: str | None = None


@router.post("/{ticker}/recurring", response_model=SnapshotOut)
def validate_recurring(
    ticker: str,
    body: RecurringIn,
    session: Session = Depends(get_session),
):
    """Validation humaine du récurrent — écrit sur le snapshot le plus récent."""
    comp = get_comp_by_ticker(session, ticker)
    if comp is None:
        raise HTTPException(status_code=404, detail="Comparable introuvable.")
    snap = get_latest_snapshot(session, comp.id)
    if snap is None:
        raise HTTPException(status_code=404, detail="Aucun snapshot disponible.")
    return update_snapshot_recurring(
        session, snap.id, body.recurring_value, body.recurring_basis_tag
    )
