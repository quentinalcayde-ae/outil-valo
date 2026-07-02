import os

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from valo.dependencies import get_session, get_yahoo
from valo.method.anchor import compute_market_anchor
from valo.method.service import execute_run
from valo.providers.yahoo_provider import YahooProvider
from valo.schemas import (
    AnchorComputeIn,
    AnchorProposalOut,
    PanelCreate,
    RunCompsPatch,
    RunExecuteIn,
    RunOut,
)
from valo.storage.repositories import (
    add_run_comp,
    create_anchor,
    create_comp,
    create_run,
    get_anchors,
    get_comp_by_ticker,
    get_run,
    get_target,
    set_anchor_market,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("/panel", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_panel(target_id: int, body: PanelCreate, session: Session = Depends(get_session)):
    """
    Crée l'ancre d'entrée (m_market_entry restera à calculer), le run, et associe
    le panel de comps VALIDÉS (identité seulement — aucune recherche financière ici).
    """
    target = get_target(session, target_id)
    if target is None:
        raise HTTPException(status_code=404, detail="Cible introuvable.")

    # Ancre optionnelle et persistée par cible : on met à jour l'ancre existante si fournie,
    # on en crée une seule si besoin, on ne touche à rien si aucune ancre n'est fournie
    # (→ valorisation directe par comparables).
    if body.anchor is not None:
        existing = get_anchors(session, target_id)
        if existing:
            a = existing[-1]
            a.entry_date = body.anchor.entry_date
            a.entry_round = body.anchor.entry_round
            a.m_entry_aggregate = body.anchor.m_entry_aggregate
            a.entry_growth = body.anchor.entry_growth
            # entrée modifiée → l'ancre marché devra être recalculée
            a.m_market_entry = None
            a.market_anchor_basis = None
            a.entry_panel_growth = None
        else:
            create_anchor(
                session, target_id,
                entry_date=body.anchor.entry_date,
                entry_round=body.anchor.entry_round,
                m_entry_aggregate=body.anchor.m_entry_aggregate,
                entry_growth=body.anchor.entry_growth,
            )

    run = create_run(
        session,
        target_id=target_id,
        mode=body.mode,
        aggregate=body.aggregate,
        other_deltas=body.other_deltas,
    )

    for pc in body.comps:
        ticker = pc.ticker.upper()
        comp = get_comp_by_ticker(session, ticker)
        if comp is None:
            comp = create_comp(
                session, name=pc.name or ticker, ticker=ticker,
                currency="USD", is_recurring=target.is_recurring,
            )
        add_run_comp(session, run_id=run.id, comp_id=comp.id,
                     included=True, relevance_note=pc.relevance_note)

    session.flush()
    return _enrich_run(get_run(session, run.id))


@router.get("/{run_id}/excel")
def download_excel(run_id: int, session: Session = Depends(get_session)):
    """Télécharge le classeur Excel formula-driven du run."""
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run introuvable.")
    if not run.excel_path or not os.path.exists(run.excel_path):
        raise HTTPException(status_code=404, detail="Excel non généré — lancez d'abord le calcul de la valo.")
    return FileResponse(
        run.excel_path,
        filename=os.path.basename(run.excel_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


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

    by_id = {rc.id: rc for rc in run.run_comps}
    for patch in body.comps:
        rc = by_id.get(patch.run_comp_id)
        if rc is None:
            raise HTTPException(status_code=404, detail=f"run_comp_id {patch.run_comp_id} absent de ce run.")
        rc.included = patch.included
        rc.exclusion_reason = patch.exclusion_reason
        if patch.relevance_note is not None:
            rc.relevance_note = patch.relevance_note

    session.flush()
    return _enrich_run(get_run(session, run_id))


@router.post("/{run_id}/anchor", response_model=AnchorProposalOut)
def compute_anchor(
    run_id: int,
    body: AnchorComputeIn,
    session: Session = Depends(get_session),
    provider: YahooProvider = Depends(get_yahoo),
):
    """
    Fixe m_market_entry (MODE A). manual_value → override (cas ARR / correction).
    Sinon calcul auto EV/Revenue historique sur le panel inclus (best-effort).
    L'ancre n'est gelée que si une valeur est obtenue (auto ou manuelle).
    """
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run introuvable.")
    anchors = get_anchors(session, run.target_id)
    if not anchors:
        raise HTTPException(status_code=422, detail="Aucune ancre d'entrée — créer le panel d'abord.")
    anchor = anchors[-1]

    # Override manuel (cas ARR ou correction humaine)
    if body.manual_value is not None:
        basis = body.basis or "arr"
        set_anchor_market(session, anchor.id, body.manual_value, basis, "manual")
        return AnchorProposalOut(
            basis=basis, entry_date=anchor.entry_date, m_market_entry=body.manual_value,
            n_available=0, details=[], source="manual",
        )

    # Calcul auto sur le panel inclus
    tickers = [rc.comp.ticker for rc in run.run_comps if rc.included and rc.comp]
    proposal = compute_market_anchor(provider, tickers, anchor.entry_date)

    if proposal.m_market_entry is not None:
        set_anchor_market(session, anchor.id, proposal.m_market_entry, proposal.basis, "computed",
                          entry_panel_growth=proposal.entry_panel_growth)

    return AnchorProposalOut(
        basis=proposal.basis,
        entry_date=proposal.entry_date,
        m_market_entry=proposal.m_market_entry,
        n_available=proposal.n_available,
        details=[d.__dict__ for d in proposal.details],
        source="computed" if proposal.m_market_entry is not None else "pending",
    )


@router.post("/{run_id}/execute", response_model=RunOut)
def execute(
    run_id: int,
    body: RunExecuteIn,
    session: Session = Depends(get_session),
    provider: YahooProvider = Depends(get_yahoo),
):
    """Recherche financière (snapshots live des comps validés) + calcul de valo + Excel."""
    run = get_run(session, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run introuvable.")
    try:
        ctx = execute_run(
            session, run_id,
            target_aggregate_value=body.target_aggregate_value,
            target_growth_now=body.target_growth_now,
            provider=provider,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _enrich_run(ctx.run)


def _enrich_run(run) -> dict:
    run_comps_out = []
    for rc in run.run_comps:
        run_comps_out.append({
            "id": rc.id,
            "comp_id": rc.comp_id,
            "comp_snapshot_id": rc.comp_snapshot_id,
            "included": rc.included,
            "exclusion_reason": rc.exclusion_reason,
            "relevance_note": rc.relevance_note,
            "comp": rc.comp,
            "snapshot": rc.comp_snapshot,
        })
    return {
        "id": run.id,
        "target_id": run.target_id,
        "run_date": run.run_date,
        "mode": run.mode,
        "aggregate": run.aggregate,
        "median_now": run.median_now,
        "retention_factor": run.retention_factor,
        "other_deltas": run.other_deltas,
        "beta": run.beta,
        "growth_r2": run.growth_r2,
        "growth_delta": run.growth_delta,
        "growth_gap": run.growth_gap,
        "m_final": run.m_final,
        "result_ev": run.result_ev,
        "result_equity": run.result_equity,
        "excel_path": run.excel_path,
        "run_comps": run_comps_out,
    }
