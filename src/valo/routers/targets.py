from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from valo.dependencies import get_session
from valo.schemas import AnchorCreate, AnchorOut, TargetCreate, TargetOut
from valo.storage.repositories import (
    create_anchor,
    create_target,
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


@router.post("/{target_id}/anchors", response_model=AnchorOut, status_code=status.HTTP_201_CREATED)
def add_anchor(target_id: int, body: AnchorCreate, session: Session = Depends(get_session)):
    if get_target(session, target_id) is None:
        raise HTTPException(status_code=404, detail="Cible introuvable.")
    return create_anchor(session, target_id, **body.model_dump())


@router.get("/{target_id}/anchors", response_model=list[AnchorOut])
def list_anchors(target_id: int, session: Session = Depends(get_session)):
    return get_anchors(session, target_id)
