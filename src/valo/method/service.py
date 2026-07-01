"""Service d'orchestration d'un run de valo — voir PROJECT_V1.md §5."""
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from valo.method.excel_export import export_excel
from valo.method.valuation import ValuationInput, ValuationResult, run_valuation
from valo.models import CompSnapshot, RunComp, TargetAnchor, ValuationRun
from valo.storage.repositories import get_anchors, get_run, update_run_result


@dataclass
class RunContext:
    """Données résolues pour affichage / audit après le run."""
    run: ValuationRun
    result: ValuationResult
    included_comps: list[dict]   # [{ticker, ev, aggregate, multiple}, ...]
    excluded_comps: list[dict]
    target_aggregate_value: float
    excel_path: str | None


def _pick_aggregate(snap: CompSnapshot, aggregate_key: str) -> float | None:
    """Sélectionne la valeur d'agrégat du comp selon le type de run."""
    if aggregate_key in ("arr", "recurring"):
        return snap.recurring_value
    if aggregate_key == "revenue":
        return snap.revenue_ltm
    # Pour les autres (ebitda, …) : non encore supporté en P1 data — retourne None
    return None


def execute_run(
    session: Session,
    run_id: int,
    target_aggregate_value: float,
    output_dir: str = "exports",
) -> RunContext:
    """
    Orchestre un run complet :
    1. Charge le panel (run_comps.included=True uniquement pour la médiane)
    2. Calcule EV/agrégat homogène pour chaque comp inclus
    3. Lance run_valuation() — formule calibration delta
    4. Persiste le résultat dans valuation_runs
    5. Génère le fichier Excel formula-driven
    """
    run = get_run(session, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} introuvable.")

    anchors = get_anchors(session, run.target_id)
    if not anchors:
        raise ValueError(f"Aucune ancre trouvée pour la cible {run.target_id}. Créer un TargetAnchor d'abord.")
    anchor: TargetAnchor = anchors[-1]

    run_comps: list[RunComp] = run.run_comps
    included_multiples = []
    included_comps = []
    excluded_comps = []

    for rc in run_comps:
        snap: CompSnapshot = rc.comp_snapshot
        comp_name = snap.comp.name if snap.comp else f"comp_{snap.comp_id}"
        agg_value = _pick_aggregate(snap, run.aggregate)

        if snap.ev is None or agg_value is None or agg_value <= 0:
            multiple = None
        else:
            multiple = snap.ev / agg_value

        entry = {
            "ticker": snap.comp.ticker if snap.comp else "?",
            "name": comp_name,
            "ev": snap.ev,
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
        raise ValueError("Panel vide après filtrage — aucun comp avec multiple calculable.")

    inp = ValuationInput(
        mode=run.mode,
        m_entry_aggregate=anchor.m_entry_aggregate,
        m_market_entry=anchor.m_market_entry,
        comp_multiples=included_multiples,
        retention_factor=run.retention_factor or 1.0,
    )
    result = run_valuation(inp)

    # EV cible = M_final × agrégat cible
    result_ev = result.m_final * target_aggregate_value
    # Equity = EV (la dette nette de la cible est traitée en dehors du mark)
    result_equity = result_ev

    Path(output_dir).mkdir(exist_ok=True)
    excel_path = export_excel(
        run=run,
        anchor=anchor,
        result=result,
        included_comps=included_comps,
        excluded_comps=excluded_comps,
        target_aggregate_value=target_aggregate_value,
        result_ev=result_ev,
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
