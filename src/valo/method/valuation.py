"""Méthode de valorisation agrégat-agnostique — voir PROJECT_V1.md §5.

Deux régimes :
- calibration par delta (ancre présente) : base = M_entry × (median_now / m_market_entry)
- comparables directs (pas d'ancre)     : base = median_now

Ajustement de croissance (si données dispo) : on lit dans le panel le prix d'un point de
croissance (pente β d'une régression EV/Rev = a + β·croissance), puis on l'applique au SEUL
écart de croissance (delta depuis le tour en mode ancré ; écart de niveau en mode direct),
plafonné à la fourchette observée du panel (convexité). Base V1 = trailing (yfinance).

    M_final = base + β·écart_croissance_clampé + autres_deltas
    EV = M_final × agrégat_cible ;  Equity = EV − dette_nette (calculé côté service)
"""
from dataclasses import dataclass
from statistics import median

import numpy as np

MIN_COMPS_FOR_BETA = 3  # en-deçà, pente non fiable → terme de croissance omis


@dataclass
class ValuationInput:
    mode: str                          # "A" ou "B"
    comp_multiples: list[float]        # EV/agrégat des comps inclus (base médiane)
    comp_growths: list[float | None]   # croissance des mêmes comps (aligné ; None si inconnue)
    m_entry_aggregate: float | None = None
    m_market_entry: float | None = None
    target_growth_now: float | None = None
    target_growth_entry: float | None = None      # croissance cible au tour (mode ancré)
    entry_panel_growth: float | None = None        # médiane croissance panel au tour (mode ancré)
    other_deltas: float = 0.0          # ajustements société additifs (marge/NRR/taille), en tours


@dataclass
class ValuationResult:
    median_now: float
    m_final: float
    calibrated: bool
    drift_ratio: float | None      # median_now / m_market_entry (None en direct)
    beta: float | None             # pente panel brute (x par unité de croissance), None si non calculable
    growth_r2: float | None        # R² de la régression = confiance dans β (shrinkage)
    median_growth_now: float | None
    growth_gap: float | None       # écart de croissance retenu (après clamp)
    growth_delta: float            # R² × β × growth_gap (0 si terme omis)
    other_deltas: float


def compute_ev_multiple(market_cap: float | None, net_debt: float | None) -> float | None:
    if market_cap is None or net_debt is None:
        return None
    return market_cap + net_debt


def compute_multiple(ev: float | None, aggregate: float | None) -> float | None:
    if ev is None or aggregate is None or aggregate == 0:
        return None
    return ev / aggregate


def _winsorize(values: list[float]) -> list[float]:
    """Clippe aux 10e/90e percentiles pour amortir les outliers avant régression."""
    if len(values) < 3:
        return values
    lo, hi = np.percentile(values, [10, 90])
    return [min(max(v, lo), hi) for v in values]


def _panel_beta(growths: list[float], multiples: list[float]) -> tuple[float | None, float | None]:
    """Pente β de EV/Rev = a + β·croissance + R² (confiance). (None, None) si non calculable."""
    if len(growths) < MIN_COMPS_FOR_BETA:
        return None, None
    g = np.array(_winsorize(growths), dtype=float)
    m = np.array(_winsorize(multiples), dtype=float)
    if np.ptp(g) == 0:  # aucune variance de croissance → pente indéfinie
        return None, None
    beta, intercept = np.polyfit(g, m, 1)
    # R² = fraction de variance des multiples expliquée par la croissance
    pred = beta * g + intercept
    ss_res = float(np.sum((m - pred) ** 2))
    ss_tot = float(np.sum((m - m.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0
    r2 = max(0.0, min(1.0, r2))
    return float(beta), r2


def run_valuation(inp: ValuationInput) -> ValuationResult:
    if not inp.comp_multiples:
        raise ValueError("Panel vide — aucun comp inclus dans la médiane.")

    median_now = median(inp.comp_multiples)
    calibrated = inp.m_entry_aggregate is not None and inp.m_market_entry not in (None, 0)

    # Paires (croissance, multiple) des comps ayant les deux → pente β + médiane croissance
    pairs = [(g, m) for g, m in zip(inp.comp_growths, inp.comp_multiples, strict=False) if g is not None]
    beta = None
    growth_r2 = None
    median_growth_now = None
    growth_range = None
    if pairs:
        pg = [g for g, _ in pairs]
        pm = [m for _, m in pairs]
        median_growth_now = median(pg)
        growth_range = (min(pg), max(pg))
        beta, growth_r2 = _panel_beta(pg, pm)

    # Base marché
    if calibrated:
        drift_ratio = median_now / inp.m_market_entry
        base = inp.m_entry_aggregate * drift_ratio
    else:
        drift_ratio = None
        base = median_now

    # Terme de croissance (seulement si β calculable et données de croissance présentes)
    growth_gap = None
    growth_delta = 0.0
    if beta is not None and median_growth_now is not None and inp.target_growth_now is not None:
        if calibrated and inp.target_growth_entry is not None and inp.entry_panel_growth is not None:
            # Écart de SUR-performance depuis le tour (deltas, pas niveaux → pas de double comptage)
            d_target = inp.target_growth_now - inp.target_growth_entry
            d_panel = median_growth_now - inp.entry_panel_growth
            gap = d_target - d_panel
        elif not calibrated:
            # Mode direct : écart de niveau cible vs médiane panel
            gap = inp.target_growth_now - median_growth_now
        else:
            gap = None

        if gap is not None:
            # Convexité : ne pas extrapoler hors du nuage observé du panel
            lo = growth_range[0] - median_growth_now
            hi = growth_range[1] - median_growth_now
            growth_gap = min(max(gap, lo), hi)
            # Shrinkage par R² : on ne fait confiance à β qu'à hauteur de ce que le panel
            # explique réellement (amortit fortement les panels bruités/hétérogènes).
            growth_delta = (growth_r2 or 0.0) * beta * growth_gap

    # Garde-fou de validité : un multiple d'EV ne peut pas être négatif (β raide × sous-perf
    # sur petit panel peut sinon faire passer M_final sous zéro — cas dénué de sens).
    m_final = max(0.0, base + growth_delta + inp.other_deltas)

    return ValuationResult(
        median_now=median_now,
        m_final=m_final,
        calibrated=calibrated,
        drift_ratio=drift_ratio,
        beta=beta,
        growth_r2=growth_r2,
        median_growth_now=median_growth_now,
        growth_gap=growth_gap,
        growth_delta=growth_delta,
        other_deltas=inp.other_deltas,
    )
