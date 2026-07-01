from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from valo.dependencies import get_session, get_yahoo
from valo.method.service import execute_run
from valo.providers.yahoo_provider import YahooProvider
from valo.schemas import PanelCreate, RunCompsPatch, RunExecuteIn, RunOut
from valo.storage.repositories import (
    add_run_comp,
    create_anchor,
    create_comp,
    create_run,
    get_anchors,
    get_comp_by_ticker,
    get_latest_snapshot,
    get_run,
    insert_snapshot,
)
from valo.storage.repositories import get_target

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/panel", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_panel(
    target_id: int,
    body: PanelCreate,
    session: Session = Depends(get_session),
    provider: YahooProvider = Depends(get_yahoo),
):
    """
    Crée un run + associe le panel soumis par l'utilisateur.
    Pour chaque ticker :
      - crée le comp s'il n'existe pas
      - rafraîchit le snapshot si aucun n'existe
      - ajoute au panel du run (tous inclus par défaut)
    """
    target = get_target(session, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Cible introuvable.")

    # Crée l'ancre si fournie et qu'il n'en existe pas encore
    anchors = get_anchors(session, target_id)
    if not anchors and body.anchor is None:
        raise HTTPException(
            status_code=422,
            detail="Aucune ancre sur cette cible. Fournir `anchor` dans le body.",
        )
    if body.anchor is not None:
        create_anchor(session, target_id, **body.anchor.model_dump())

    run = create_run(
        session,
        target_id=target_id,
        mode=body.mode,
        aggregate=body.aggregate,
        retention_factor=body.retention_factor,
    )

    errors = []
    for pc in body.comps:
        ticker = pc.ticker.upper()
        comp = get_comp_by_ticker(session, ticker)
        if comp is None:
            try:
                info = provider.fetch_snapshot(ticker)
                comp = create_comp(
                    session, name=ticker, ticker=ticker,
                    currency="USD", is_recurring=True,
                )
                snap = insert_snapshot(session, comp.id, info)
            except Exception as exc:
                errors.append(f"{ticker}: {exc}")
                continue
        else:
            snap = get_latest_snapshot(session, comp.id)
            if snap is None:
                try:
                    info = provider.fetch_snapshot(ticker)
                    snap = insert_snapshot(session, comp.id, info)
                except Exception as exc:
                    errors.append(f"{ticker}: {exc}")
                    continue

        add_run_comp(session, run_id=run.id, snapshot_id=snap.id,
                     included=True, relevance_note=pc.relevance_note)

    session.flush()

    run = get_run(session, run.id)
    if errors:
        # On retourne quand même le run avec un warning dans le header — non bloquant
        pass

    return _enrich_run(run)


@router.get("/{run_id}", response_model=RunOut)
def get_one(run_id: int, session: Session = Depends(get_session)):
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run introuvable.")
    return _enrich_run(run)


@router.patch("/{run_id}/comps", response_model=RunOut)
def patch_comps(run_id: int, body: RunCompsPatch, session: Session = Depends(get_session)):
    """Validation panel : inclure / exclure des comps avec motif."""
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run introuvable.")

    snap_map = {rc.comp_snapshot_id: rc for rc in run.run_comps}
    for patch in body.comps:
        rc = snap_map.get(patch.comp_snapshot_id)
        if rc is None:
            raise HTTPException(
                status_code=404,
                detail=f"comp_snapshot_id {patch.comp_snapshot_id} absent de ce run.",
            )
        rc.included = patch.included
        rc.exclusion_reason = patch.exclusion_reason
        if patch.relevance_note is not None:
            rc.relevance_note = patch.relevance_note

    session.flush()
    return _enrich_run(get_run(session, run_id))


@router.post("/{run_id}/execute", response_model=RunOut)
def execute(
    run_id: int,
    body: RunExecuteIn,
    session: Session = Depends(get_session),
):
    """Lance le calcul de valo et génère l'Excel."""
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run introuvable.")
    try:
        ctx = execute_run(session, run_id, target_aggregate_value=body.target_aggregate_value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return _enrich_run(ctx.run)


def _enrich_run(run) -> dict:
    """Construit le RunOut avec snapshots et comps imbriqués."""
    run_comps_out = []
    for rc in run.run_comps:
        snap = rc.comp_snapshot
        comp = snap.comp
        run_comps_out.append({
            "id": rc.id,
            "comp_snapshot_id": rc.comp_snapshot_id,
            "included": rc.included,
            "exclusion_reason": rc.exclusion_reason,
            "relevance_note": rc.relevance_note,
            "snapshot": snap,
            "comp": comp,
        })
    return {
        "id": run.id,
        "target_id": run.target_id,
        "run_date": run.run_date,
        "mode": run.mode,
        "aggregate": run.aggregate,
        "median_now": run.median_now,
        "retention_factor": run.retention_factor,
        "m_final": run.m_final,
        "result_ev": run.result_ev,
        "result_equity": run.result_equity,
        "excel_path": run.excel_path,
        "run_comps": run_comps_out,
    }
