"""Service d'orchestration d'un run de valo — voir PROJECT_V1.md §5.

Flux : le panel (identité des comps) est fixé en amont. À l'execute, on fait la
recherche financière (snapshot live par comp), on gèle les snapshots, on calcule
la médiane sur les inclus, on applique la calibration delta, on génère l'Excel.
L'ancre marché (m_market_entry) doit avoir été calculée/confirmée au préalable.
"""
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from valo.method.excel_export import export_excel
from valo.method.valuation import ValuationInput, ValuationResult, run_valuation
from valo.models import CompSnapshot, Target, TargetAnchor, ValuationRun
from valo.providers.base import MarketDataProvider
from valo.storage.repositories import (
    get_anchors,
    get_run,
    insert_snapshot,
    update_run_result,
)


@dataclass
class RunContext:
    run: ValuationRun
    result: ValuationResult
    included_comps: list[dict]
    excluded_comps: list[dict]
    target_aggregate_value: float
    excel_path: str | None


def _pick_aggregate(snap: CompSnapshot, aggregate_key: str) -> float | None:
    if aggregate_key in ("arr", "recurring"):
        return snap.recurring_value
    if aggregate_key == "revenue":
        return snap.revenue_ltm
    return None


def execute_run(
    session: Session,
    run_id: int,
    target_aggregate_value: float | None = None,
    provider: MarketDataProvider | None = None,
    output_dir: str = "exports",
) -> RunContext:
    run = get_run(session, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} introuvable.")

    target: Target | None = session.get(Target, run.target_id)
    anchors = get_anchors(session, run.target_id)
    if not anchors:
        raise ValueError("Aucune ancre pour cette cible — créer/ancrer d'abord.")
    anchor: TargetAnchor = anchors[-1]
    if anchor.m_market_entry is None:
        raise ValueError("Ancre marché non calculée — appeler /runs/{id}/anchor avant execute.")

    if target_aggregate_value is None:
        target_aggregate_value = target.aggregate_value if target else None
    if not target_aggregate_value or target_aggregate_value <= 0:
        raise ValueError("Agrégat cible manquant — renseigner target.aggregate_value ou le passer au run.")

    # Le drift (median_now / m_market_entry) est SANS UNITÉ : median_now se calcule sur le
    # MÊME agrégat que l'ancre marché (basis), pas sur l'agrégat cible. Cas ARR : basis=revenue
    # (l'ARR des comps nécessiterait l'extraction P4). Le M_final reste ancré sur l'agrégat cible.
    comp_basis = anchor.market_anchor_basis or run.aggregate

    included_multiples: list[float] = []
    included_comps: list[dict] = []
    excluded_comps: list[dict] = []

    for rc in run.run_comps:  # type: RunComp
        # Recherche financière : snapshot gelé s'il existe, sinon fetch live
        snap: CompSnapshot | None = rc.comp_snapshot
        if snap is None:
            if provider is None:
                raise ValueError(
                    f"Comp {rc.comp.ticker if rc.comp else rc.comp_id} sans snapshot et aucun provider fourni."
                )
            try:
                market = provider.fetch_snapshot(rc.comp.ticker)
            except Exception as exc:
                # Ticker introuvable/invalide (ex. proposition LLM douteuse) → exclu, run préservé
                rc.included = False
                rc.exclusion_reason = f"[auto] acquisition impossible : {exc}"
                session.flush()
                excluded_comps.append({
                    "ticker": rc.comp.ticker if rc.comp else "?",
                    "name": rc.comp.name if rc.comp else f"comp_{rc.comp_id}",
                    "ev": None, "market_cap": None, "net_debt": None, "revenue_ltm": None,
                    "recurring_value": None, "aggregate_value": None, "multiple": None,
                    "included": False, "exclusion_reason": rc.exclusion_reason,
                    "relevance_note": rc.relevance_note,
                })
                continue
            snap = insert_snapshot(session, rc.comp_id, market)
            rc.comp_snapshot = snap  # met à jour la relation (pas seulement le FK)
            session.flush()

        agg_value = _pick_aggregate(snap, comp_basis)
        multiple = None
        if snap.ev is not None and agg_value and agg_value > 0:
            multiple = snap.ev / agg_value

        entry = {
            "ticker": rc.comp.ticker if rc.comp else "?",
            "name": rc.comp.name if rc.comp else f"comp_{rc.comp_id}",
            "ev": snap.ev,
            "market_cap": snap.market_cap,
            "net_debt": snap.net_debt,
            "revenue_ltm": snap.revenue_ltm,
            "recurring_value": snap.recurring_value,
            "aggregate_value": agg_value,
            "multiple": multiple,
            "included": rc.included,
            "exclusion_reason": rc.exclusion_reason,
            "relevance_note": rc.relevance_note,
        }

        if rc.included and multiple is not None:
            included_multiples.append(multiple)
            included_comps.append(entry)
        else:
            if rc.included and multiple is None:
                rc.included = False
                rc.exclusion_reason = (rc.exclusion_reason or "") + " [auto: multiple non calculable]"
            excluded_comps.append(entry)

    if not included_multiples:
        extra = ""
        if comp_basis in ("arr", "recurring"):
            extra = (" L'agrégat comp est l'ARR : les comparables cotés n'ont pas d'ARR renseigné "
                     "(extraction P4). Ancrez plutôt sur EV/Revenue (basis=revenue).")
        raise ValueError(
            f"Panel vide après filtrage — aucun comp avec multiple EV/{comp_basis} calculable.{extra}"
        )

    inp = ValuationInput(
        mode=run.mode,
        m_entry_aggregate=anchor.m_entry_aggregate,
        m_market_entry=anchor.m_market_entry,
        comp_multiples=included_multiples,
        retention_factor=run.retention_factor or 1.0,
    )
    result = run_valuation(inp)

    result_ev = result.m_final * target_aggregate_value
    result_equity = result_ev  # bridge dette nette traité hors mark (voir PROJECT_V1 §5)

    Path(output_dir).mkdir(exist_ok=True)
    excel_path = export_excel(
        run=run,
        anchor=anchor,
        result=result,
        included_comps=included_comps,
        excluded_comps=excluded_comps,
        target_aggregate_value=target_aggregate_value,
        result_ev=result_ev,
        comp_basis=comp_basis,
        output_dir=output_dir,
    )

    update_run_result(
        session,
        run_id=run_id,
        median_now=result.median_now,
        retention_factor=result.retention_factor,
        m_final=result.m_final,
        result_ev=result_ev,
        result_equity=result_equity,
        excel_path=excel_path,
    )

    return RunContext(
        run=run,
        result=result,
        included_comps=included_comps,
        excluded_comps=excluded_comps,
        target_aggregate_value=target_aggregate_value,
        excel_path=excel_path,
    )
