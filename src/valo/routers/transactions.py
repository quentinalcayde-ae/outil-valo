from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from valo.dependencies import get_session
from valo.schemas import TransactionCreate, TransactionOut, TransactionUpdate
from valo.storage.repositories import (
    create_transaction,
    delete_transaction,
    get_transaction,
    list_transactions,
    update_transaction,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create(body: TransactionCreate, session: Session = Depends(get_session)):
    return create_transaction(session, **body.model_dump())


@router.get("", response_model=list[TransactionOut])
def list_all(session: Session = Depends(get_session)):
    return list_transactions(session)


@router.get("/{tx_id}", response_model=TransactionOut)
def get_one(tx_id: int, session: Session = Depends(get_session)):
    tx = get_transaction(session, tx_id)
    if tx is None:
        raise HTTPException(status_code=404, detail="Transaction introuvable.")
    return tx


@router.patch("/{tx_id}", response_model=TransactionOut)
def update(tx_id: int, body: TransactionUpdate, session: Session = Depends(get_session)):
    try:
        return update_transaction(session, tx_id, **{k: v for k, v in body.model_dump().items() if v is not None})
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(tx_id: int, session: Session = Depends(get_session)):
    try:
        delete_transaction(session, tx_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
