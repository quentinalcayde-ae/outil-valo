from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from valo.dependencies import get_llm, get_session
from valo.providers.base import LLMProvider, TargetContext
from valo.schemas import (
    AnchorOut,
    SuggestRequest,
    SuggestResponse,
    TargetCreate,
    TargetOut,
)
from valo.storage.repositories import (
    create_target,
    delete_target,
    get_anchors,
    get_target,
    list_targets,
)

router = APIRouter(prefix="/targets", tags=["targets"])


@router.post("", response_model=TargetOut, status_code=status.HTTP_201_CREATED)
def create(body: TargetCreate, session: Session = Depends(get_session)):
    return create_target(session, **body.model_dump())


@router.get("", response_model=list[TargetOut])
def list_all(session: Session = Depends(get_session)):
    return list_targets(session)


@router.get("/{target_id}", response_model=TargetOut)
def get_one(target_id: int, session: Session = Depends(get_session)):
    target = get_target(session, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Cible introuvable.")
    return target


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(target_id: int, session: Session = Depends(get_session)):
    try:
        delete_target(session, target_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{target_id}/anchors", response_model=list[AnchorOut])
def list_anchors(target_id: int, session: Session = Depends(get_session)):
    return get_anchors(session, target_id)


@router.post("/{target_id}/suggest", response_model=SuggestResponse)
def suggest(
    target_id: int,
    body: SuggestRequest,
    session: Session = Depends(get_session),
    llm: LLMProvider = Depends(get_llm),
):
    """Découverte LLM : propose comps cotés + transactions M&A (identité + rationale)."""
    target = get_target(session, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Cible introuvable.")

    ctx = TargetContext(
        name=target.name,
        sector=target.sector,
        description=target.description,
        is_recurring=target.is_recurring,
        valuation_aggregate=target.valuation_aggregate,
        aggregate_value=target.aggregate_value,
        extra_tickers=[t.upper() for t in body.extra_tickers],
    )
    comps = llm.suggest_comps(ctx, n=body.n_comps)
    txs = llm.suggest_transactions(ctx, n=body.n_transactions)
    return SuggestResponse(
        comps=[c.__dict__ for c in comps],
        transactions=[t.__dict__ for t in txs],
    )
