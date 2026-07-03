"""Méthode de valorisation agrégat-agnostique — voir PROJECT_V1.md §5.

Deux régimes :
- calibration par delta (ancre présente) : base = M_entry × (median_now / m_market_entry)
- comparables directs (pas d'ancre)     : base = median_now

Ajustements société (croissance, marge, NRR, taille) = deltas ADDITIFS MANUELS, justifiés,
sommés à la base (pas de β OLS : une régression sur un panel de dérive hétérogène N faible est
du bruit — voir décision Option A). Un flag alerte si la somme des deltas est importante.

    M_final = max(0 ; base + delta_croissance + autres_deltas)
    EV = M_final × agrégat_cible ;  Equity = EV − dette_nette (côté service)
"""
from dataclasses import dataclass, field
from statistics import median

import numpy as np

# Seuil d'alerte : deltas société importants vs la base (pas de cap dur, juste un flag)
DELTAS_FLAG_RATIO = 0.40
MIN_PRICED = 8  # en-dessous, panel jugé fragile (flag dur)


@dataclass
class ValuationInput:
    mode: str                          # "A" ou "B"
    comp_multiples: list[float]        # EV/agrégat des comps PRICED inclus
    m_entry_aggregate: float | None = None
    m_market_entry: float | None = None
    growth_delta: float = 0.0          # ajustement de croissance manuel (tours)
    other_deltas: float = 0.0          # autres ajustements société (marge/NRR/taille, tours)


@dataclass
class ValuationResult:
    median_now: float
    winsor_mean: float                 # moyenne winsorisée du set priced (robustesse petit N)
    m_final: float
    calibrated: bool
    drift_ratio: float | None          # median_now / m_market_entry (None en direct)
    base: float                        # multiple de base avant deltas société
    deltas_total: float                # delta_croissance + autres_deltas
    n_priced: int
    flags: list[str] = field(default_factory=list)


def compute_ev_multiple(market_cap: float | None, net_debt: float | None) -> float | None:
    if market_cap is None or net_debt is None:
        return None
    return market_cap + net_debt


def compute_multiple(ev: float | None, aggregate: float | None) -> float | None:
    if ev is None or aggregate is None or aggregate == 0:
        return None
    return ev / aggregate


def _winsorized_mean(values: list[float]) -> float:
    """Moyenne après clip aux 10e/90e percentiles (amortit les outliers)."""
    if len(values) < 3:
        return float(np.mean(values))
    lo, hi = np.percentile(values, [10, 90])
    clipped = [min(max(v, lo), hi) for v in values]
    return float(np.mean(clipped))


def run_valuation(inp: ValuationInput) -> ValuationResult:
    if not inp.comp_multiples:
        raise ValueError("Panel vide — aucun comp priced dans la médiane.")

    median_now = median(inp.comp_multiples)
    winsor_mean = _winsorized_mean(inp.comp_multiples)
    n_priced = len(inp.comp_multiples)
    calibrated = inp.m_entry_aggregate is not None and inp.m_market_entry not in (None, 0)

    if calibrated:
        drift_ratio = median_now / inp.m_market_entry
        base = inp.m_entry_aggregate * drift_ratio
    else:
        drift_ratio = None
        base = median_now

    deltas_total = inp.growth_delta + inp.other_deltas
    m_final = max(0.0, base + deltas_total)

    flags: list[str] = []
    if n_priced < MIN_PRICED:
        flags.append(f"panel_priced_faible ({n_priced} < {MIN_PRICED}) — dérive fragile")
    if n_priced <= 3:
        flags.append("derive_portee_par_nom_unique — médiane sur très peu de noms")
    if base > 0 and abs(deltas_total) > DELTAS_FLAG_RATIO * base:
        flags.append(
            f"deltas_societe_eleves — Σ deltas = {deltas_total:+.2f}x soit "
            f">{int(DELTAS_FLAG_RATIO * 100)}% de la base ({base:.2f}x)"
        )
    if m_final == 0.0 and base + deltas_total < 0:
        flags.append("m_final_planché_a_0 — deltas négatifs sous la base")

    return ValuationResult(
        median_now=median_now,
        winsor_mean=winsor_mean,
        m_final=m_final,
        calibrated=calibrated,
        drift_ratio=drift_ratio,
        base=base,
        deltas_total=deltas_total,
        n_priced=n_priced,
        flags=flags,
    )
