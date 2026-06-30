"""Méthode de valorisation agrégat-agnostique — voir PROJECT_V1.md §5."""
from dataclasses import dataclass
from statistics import median


@dataclass
class ValuationInput:
    """Entrées pour un run de valo."""
    mode: str                    # "A" ou "B"
    m_entry_aggregate: float     # multiple ancré au dernier tour (agrégat cible)
    m_market_entry: float        # médiane marché au tour d'entrée
    comp_multiples: list[float]  # multiples des comps inclus (EV/agrégat homogène)
    retention_factor: float = 1.0  # performance relative vs pairs — 1.0 si non récurrent


@dataclass
class ValuationResult:
    median_now: float
    retention_factor: float
    m_final: float
    drift_ratio: float  # median_now / m_market_entry — ratio sans unité


def compute_ev_multiple(market_cap: float | None, net_debt: float | None) -> float | None:
    """EV = market_cap + net_debt (net_debt peut être négatif = cash net)."""
    if market_cap is None or net_debt is None:
        return None
    ev = market_cap + net_debt
    return ev


def compute_multiple(ev: float | None, aggregate: float | None) -> float | None:
    """M = EV / agrégat. Jamais de multiple affiché tel quel."""
    if ev is None or aggregate is None or aggregate == 0:
        return None
    return ev / aggregate


def run_valuation(inp: ValuationInput) -> ValuationResult:
    """
    M_final = M_entry_aggregate × (median_now / m_market_entry) × retention_factor

    Le multiple est ancré sur le dernier tour et ne dérive que du mouvement
    relatif du marché (ratio sans unité) × performance relative.
    Pas de discount stacking.
    """
    if not inp.comp_multiples:
        raise ValueError("Panel vide — aucun comp inclus dans la médiane.")

    median_now = median(inp.comp_multiples)
    drift_ratio = median_now / inp.m_market_entry
    m_final = inp.m_entry_aggregate * drift_ratio * inp.retention_factor

    return ValuationResult(
        median_now=median_now,
        retention_factor=inp.retention_factor,
        m_final=m_final,
        drift_ratio=drift_ratio,
    )
