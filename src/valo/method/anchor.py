"""Calcul de l'ancre marché m_market_entry sur historique — voir PROJECT_V1.md §5.

Best-effort : reconstitue EV/Revenue de chaque comp à la date du tour via yfinance
historique, prend la médiane. Les comps sans donnée (IPO postérieure...) sont signalés
et exclus du calcul. La valeur reste toujours surchargeable à la main (ancre gelée à vie).

Cas ARR : l'ARR historique des comps n'existe pas → on ancre sur EV/Revenue (basis=revenue)
ou l'utilisateur saisit son multiple manuellement (géré par l'appelant).
"""
from dataclasses import dataclass, field
from datetime import date
from statistics import median

from valo.logging import logger
from valo.providers.base import MarketDataProvider


@dataclass
class AnchorCompDetail:
    ticker: str
    ev: float | None
    revenue_ltm: float | None
    multiple: float | None
    available: bool
    note: str = ""


@dataclass
class AnchorProposal:
    basis: str                       # agrégat sur lequel l'ancre est calculée (revenue)
    entry_date: date
    m_market_entry: float | None     # médiane des multiples disponibles
    n_available: int
    details: list[AnchorCompDetail] = field(default_factory=list)


def compute_market_anchor(
    provider: MarketDataProvider,
    tickers: list[str],
    entry_date: date,
) -> AnchorProposal:
    """Calcule la médiane EV/Revenue du panel à `entry_date` (best-effort)."""
    log = logger.bind(op="compute_market_anchor", entry_date=str(entry_date), n=len(tickers))
    details: list[AnchorCompDetail] = []
    multiples: list[float] = []

    for ticker in tickers:
        try:
            snap = provider.fetch_historical_snapshot(ticker, entry_date)
        except Exception as exc:
            details.append(AnchorCompDetail(ticker, None, None, None, False, str(exc)))
            continue

        ev = None
        if snap.market_cap is not None and snap.net_debt is not None:
            ev = snap.market_cap + snap.net_debt

        multiple = None
        if ev is not None and snap.revenue_ltm and snap.revenue_ltm > 0:
            multiple = ev / snap.revenue_ltm
            multiples.append(multiple)

        details.append(AnchorCompDetail(
            ticker=ticker,
            ev=ev,
            revenue_ltm=snap.revenue_ltm,
            multiple=multiple,
            available=multiple is not None,
            note="" if multiple is not None else "Données historiques incomplètes",
        ))

    m_market_entry = median(multiples) if multiples else None
    log.info("anchor_computed", m_market_entry=m_market_entry, n_available=len(multiples))

    return AnchorProposal(
        basis="revenue",
        entry_date=entry_date,
        m_market_entry=m_market_entry,
        n_available=len(multiples),
        details=details,
    )
