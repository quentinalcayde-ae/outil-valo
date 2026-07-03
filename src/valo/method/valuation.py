"""Méthode de valorisation agrégat-agnostique — voir PROJECT_V1.md §5.

Base marché :
- calibration par delta (ancre) : base = M_entry × (median_now / m_market_entry)
- comparables directs (sans ancre) : base = median_now

Delta croissance AUTOMATIQUE (méthode robuste, PAS de régression OLS) :
  prix d'un point de croissance = MÉDIANE du panel priced de (EV/Rev ÷ croissance)
  delta_croissance = prix × (croissance_cible − médiane_croissance_panel), écart clampé à la
  fourchette observée du panel. Calculé seulement si ≥3 comps priced ont une croissance exploitable.

Autres deltas (marge/NRR/taille) = additifs MANUELS (pas de donnée panel fiable pour les automatiser).

    M_final = max(0 ; base + delta_croissance + autres_deltas)
"""
from dataclasses import dataclass, field
from statistics import median

import numpy as np

DELTAS_FLAG_RATIO = 0.40   # flag si |Σ deltas| dépasse 40 % de la base
MIN_PRICED = 8             # flag dur sous ce seuil
MIN_COMPS_GROWTH = 3       # nb mini de comps avec croissance pour calculer le prix/point
GROWTH_FLOOR = 0.03        # croissance mini pour entrer dans le ratio (évite dénominateur ~0)


@dataclass
class ValuationInput:
    mode: str
    comp_multiples: list[float]              # EV/agrégat des comps PRICED
    comp_growths: list[float | None]         # croissance des mêmes comps (aligné ; None si inconnue)
    m_entry_aggregate: float | None = None
    m_market_entry: float | None = None
    target_growth_now: float | None = None   # croissance actuelle de la cible (décimal)
    other_deltas: float = 0.0                # marge/NRR/taille, additif manuel (tours)


@dataclass
class ValuationResult:
    median_now: float
    winsor_mean: float
    m_final: float
    calibrated: bool
    drift_ratio: float | None
    base: float
    growth_delta: float                      # calculé automatiquement
    other_deltas: float
    deltas_total: float
    n_priced: int
    price_per_pt_growth: float | None        # prix d'un point de croissance (médiane du ratio)
    median_growth: float | None
    growth_gap: float | None                 # écart de croissance retenu (clampé)
    flags: list[str] = field(default_factory=list)


def compute_ev_multiple(market_cap, net_debt):
    if market_cap is None or net_debt is None:
        return None
    return market_cap + net_debt


def compute_multiple(ev, aggregate):
    if ev is None or aggregate is None or aggregate == 0:
        return None
    return ev / aggregate


def _winsorized_mean(values: list[float]) -> float:
    if len(values) < 3:
        return float(np.mean(values))
    lo, hi = np.percentile(values, [10, 90])
    return float(np.mean([min(max(v, lo), hi) for v in values]))


def _growth_delta(multiples, growths, target_growth):
    """Prix d'un point de croissance (médiane du ratio EV/Rev÷croissance) × écart clampé.

    Retourne (delta, price_per_pt, median_growth, gap, reason_flag|None).
    """
    if target_growth is None:
        return 0.0, None, None, None, "delta_croissance_omis — croissance cible non saisie"
    pairs = [(m, g) for m, g in zip(multiples, growths, strict=False)
             if g is not None and g > GROWTH_FLOOR]
    if len(pairs) < MIN_COMPS_GROWTH:
        return 0.0, None, None, None, (
            f"delta_croissance_omis — <{MIN_COMPS_GROWTH} comps priced avec croissance exploitable"
        )
    ratios = [m / g for m, g in pairs]
    growths_ok = [g for _, g in pairs]
    price_per_pt = float(median(ratios))       # tours d'EV/Rev par unité (1.0 = +100 pts) de croissance
    med_g = float(median(growths_ok))
    lo, hi = min(growths_ok) - med_g, max(growths_ok) - med_g  # convexité : borne au nuage observé
    gap = min(max(target_growth - med_g, lo), hi)
    return price_per_pt * gap, price_per_pt, med_g, gap, None


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

    growth_delta, price_per_pt, med_g, gap, growth_flag = _growth_delta(
        inp.comp_multiples, inp.comp_growths, inp.target_growth_now
    )
    deltas_total = growth_delta + inp.other_deltas
    m_final = max(0.0, base + deltas_total)

    flags: list[str] = []
    if growth_flag:
        flags.append(growth_flag)
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
        growth_delta=growth_delta,
        other_deltas=inp.other_deltas,
        deltas_total=deltas_total,
        n_priced=n_priced,
        price_per_pt_growth=price_per_pt,
        median_growth=med_g,
        growth_gap=gap,
        flags=flags,
    )
