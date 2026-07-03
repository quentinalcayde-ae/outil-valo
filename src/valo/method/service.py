"""Service d'orchestration d'un run de valo — voir PROJECT_V1.md §5.

Flux : le panel (identité + tier/statut des comps) est fixé en amont. À l'execute, on fait la
recherche financière (snapshot live par comp), on gèle les snapshots, on calcule la médiane sur
le set PRICED (proxies tier 3 exclus en dur), on applique la base marché + les deltas société
manuels, on lève des flags de robustesse, on génère l'Excel.
"""
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from valo.method.excel_export import export_excel
from valo.method.valuation import ValuationInput, ValuationResult, run_valuation
from valo.models import CompSnapshot, RunComp, Target, TargetAnchor, ValuationRun
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


def _is_priced(rc: RunComp) -> bool:
    """Compte dans la médiane uniquement si inclus, statut priced, et pas un proxy tier 3."""
    return bool(rc.included) and (rc.statut or "priced") == "priced" and rc.tier != 3


def execute_run(
    session: Session,
    run_id: int,
    target_aggregate_value: float | None = None,
    target_growth_now: float | None = None,
    other_deltas: float | None = None,
    provider: MarketDataProvider | None = None,
    output_dir: str = "exports",
) -> RunContext:
    run = get_run(session, run_id)
    if run is None:
        raise ValueError(f"Run {run_id} introuvable.")

    target: Target | None = session.get(Target, run.target_id)
    anchors = get_anchors(session, run.target_id)
    anchor: TargetAnchor | None = anchors[-1] if anchors else None

    delta_mode = anchor is not None and anchor.m_market_entry is not None
    if anchor is not None and anchor.m_entry_aggregate is not None and anchor.m_market_entry is None:
        raise ValueError(
            "Ancre définie mais médiane marché non calculée — lancez l'ancrage, "
            "ou retirez l'ancre pour une valorisation directe."
        )

    if target_aggregate_value is None:
        target_aggregate_value = target.aggregate_value if target else None
    if not target_aggregate_value or target_aggregate_value <= 0:
        raise ValueError("Agrégat cible manquant — renseigner target.aggregate_value ou le passer au run.")

    # Croissance actuelle de la cible (pour le delta croissance auto) : override sinon valeur stockée.
    if target_growth_now is not None and target is not None:
        target.growth_now = target_growth_now
    effective_growth_now = target_growth_now if target_growth_now is not None else (target.growth_now if target else None)
    # Autres deltas (marge/NRR/taille) : manuels, override sinon valeur du run.
    if other_deltas is not None:
        run.other_deltas = other_deltas

    comp_basis = (anchor.market_anchor_basis or run.aggregate) if delta_mode else run.aggregate

    included_multiples: list[float] = []
    included_growths: list[float | None] = []
    included_comps: list[dict] = []
    excluded_comps: list[dict] = []

    for rc in run.run_comps:  # type: RunComp
        snap: CompSnapshot | None = rc.comp_snapshot
        if snap is None:
            if provider is None:
                raise ValueError(
                    f"Comp {rc.comp.ticker if rc.comp else rc.comp_id} sans snapshot et aucun provider fourni."
                )
            try:
                market = provider.fetch_snapshot(rc.comp.ticker)
            except Exception as exc:
                rc.included = False
                rc.exclusion_reason = f"[auto] acquisition impossible : {exc}"
                session.flush()
                excluded_comps.append(_entry(rc, None, None, comp_basis))
                continue
            snap = insert_snapshot(session, rc.comp_id, market)
            rc.comp_snapshot = snap
            session.flush()

        agg_value = _pick_aggregate(snap, comp_basis)
        multiple = snap.ev / agg_value if (snap.ev is not None and agg_value and agg_value > 0) else None
        entry = _entry(rc, snap, multiple, comp_basis, agg_value)

        # Set PRICED = inclus + statut priced + non-proxy + multiple calculable
        if _is_priced(rc) and multiple is not None:
            included_multiples.append(multiple)
            included_growths.append(snap.revenue_growth)
            included_comps.append(entry)
        else:
            if _is_priced(rc) and multiple is None:
                rc.exclusion_reason = (rc.exclusion_reason or "") + " [auto: multiple non calculable]"
            excluded_comps.append(entry)

    if not included_multiples:
        extra = ""
        if comp_basis in ("arr", "recurring"):
            extra = (" L'agrégat comp est l'ARR : les comparables cotés n'ont pas d'ARR renseigné "
                     "(extraction P4). Ancrez plutôt sur EV/Revenue (basis=revenue).")
        raise ValueError(
            f"Panel vide après filtrage — aucun comp priced avec multiple EV/{comp_basis} calculable.{extra}"
        )

    inp = ValuationInput(
        mode=run.mode,
        comp_multiples=included_multiples,
        comp_growths=included_growths,
        m_entry_aggregate=anchor.m_entry_aggregate if delta_mode else None,
        m_market_entry=anchor.m_market_entry if delta_mode else None,
        target_growth_now=effective_growth_now,
        other_deltas=run.other_deltas or 0.0,
    )
    result = run_valuation(inp)
    run.growth_delta = result.growth_delta  # delta croissance calculé automatiquement

    # Flags additionnels (proxy tenté dans le calcul = toujours faux ici, garde-fou)
    flags = list(result.flags)
    if any(rc.tier == 3 and rc.included and (rc.statut or "priced") == "priced" for rc in run.run_comps):
        flags.append("proxy_dans_calcul — anomalie (tier 3 forcé priced)")

    result_ev = result.m_final * target_aggregate_value
    net_debt = (target.net_debt if target else None) or 0.0
    result_equity = result_ev - net_debt

    Path(output_dir).mkdir(exist_ok=True)
    excel_path = export_excel(
        run=run,
        anchor=anchor,
        result=result,
        included_comps=included_comps,
        excluded_comps=excluded_comps,
        target_aggregate_value=target_aggregate_value,
        result_ev=result_ev,
        net_debt=net_debt,
        result_equity=result_equity,
        comp_basis=comp_basis,
        flags=flags,
        output_dir=output_dir,
    )

    update_run_result(
        session,
        run_id=run_id,
        median_now=result.median_now,
        m_final=result.m_final,
        result_ev=result_ev,
        result_equity=result_equity,
        excel_path=excel_path,
        winsor_mean=result.winsor_mean,
        flags=flags,
    )

    return RunContext(
        run=run,
        result=result,
        included_comps=included_comps,
        excluded_comps=excluded_comps,
        target_aggregate_value=target_aggregate_value,
        excel_path=excel_path,
    )


def _entry(rc: RunComp, snap: CompSnapshot | None, multiple, comp_basis, agg_value=None) -> dict:
    return {
        "ticker": rc.comp.ticker if rc.comp else "?",
        "name": rc.comp.name if rc.comp else f"comp_{rc.comp_id}",
        "tier": rc.tier,
        "statut": rc.statut,
        "pct_ca_comparable": rc.pct_ca_comparable,
        "ev": snap.ev if snap else None,
        "market_cap": snap.market_cap if snap else None,
        "net_debt": snap.net_debt if snap else None,
        "revenue_ltm": snap.revenue_ltm if snap else None,
        "recurring_value": snap.recurring_value if snap else None,
        "revenue_growth": snap.revenue_growth if snap else None,
        "aggregate_value": agg_value,
        "multiple": multiple,
        "included": bool(rc.included),
        "priced": _is_priced(rc) and multiple is not None,
        "exclusion_reason": rc.exclusion_reason,
        "relevance_note": rc.relevance_note,
    }
