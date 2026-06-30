"""CLI de test P1 — cycle complet : cible → comp → snapshot Yahoo → stockage → affichage.

Usage :
    python scripts/test_p1.py
    python scripts/test_p1.py --ticker BILL --ticker VEEV
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from valo.config import settings
from valo.logging import configure_logging, logger
from valo.providers.yahoo_provider import YahooProvider
from valo.storage.repositories import (
    create_comp,
    create_target,
    get_comp_by_ticker,
    get_latest_snapshot,
    insert_snapshot,
)
from valo.storage.sqlite_store import SQLiteStore

configure_logging()

DEFAULT_TICKERS = ["ADBE", "CRM", "NOW", "WDAY", "HUBS"]


def run(tickers: list[str]) -> None:
    store = SQLiteStore(settings.database_url)
    provider = YahooProvider()

    with store.get_session() as session:
        target = create_target(
            session,
            name="Syroco [TEST P1]",
            sector="SaaS / Maritime",
            is_recurring=True,
            valuation_aggregate="arr",
            fund="FR FII",
            notes="Cible de test P1 — à supprimer",
        )
        logger.info("target_created", id=target.id, name=target.name)

        for ticker in tickers:
            ticker = ticker.upper()
            comp = get_comp_by_ticker(session, ticker)
            if comp is None:
                comp = create_comp(
                    session,
                    name=ticker,
                    ticker=ticker,
                    sector="SaaS",
                    currency="USD",
                    is_recurring=True,
                )
                logger.info("comp_created", ticker=ticker, id=comp.id)
            else:
                logger.info("comp_exists", ticker=ticker, id=comp.id)

            logger.info("fetching_snapshot", ticker=ticker)
            try:
                snap = provider.fetch_snapshot(ticker)
            except Exception as exc:
                logger.error("fetch_failed", ticker=ticker, error=str(exc))
                continue

            snapshot = insert_snapshot(session, comp.id, snap)
            logger.info(
                "snapshot_inserted",
                ticker=ticker,
                snapshot_id=snapshot.id,
                market_cap=snapshot.market_cap,
                ev=snapshot.ev,
                ev_rev=round(snapshot.ev_rev, 2) if snapshot.ev_rev else None,
            )

    print("\n--- Resultats stockes ---")
    with store.get_session() as session:
        for ticker in tickers:
            comp = get_comp_by_ticker(session, ticker.upper())
            if comp is None:
                continue
            snap = get_latest_snapshot(session, comp.id)
            if snap is None:
                print(f"  {ticker}: pas de snapshot")
                continue
            ev_rev = f"{snap.ev_rev:.1f}x" if snap.ev_rev else "N/A"
            print(
                f"  {ticker:6} | market_cap={_fmt(snap.market_cap)} "
                f"| EV={_fmt(snap.ev)} | EV/Rev={ev_rev} "
                f"| {snap.snapshot_date.strftime('%Y-%m-%d %H:%M')}"
            )


def _fmt(v: float | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e9:
        return f"{v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"{v/1e6:.0f}M"
    return str(round(v))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test P1 — cycle acquisition → stockage")
    parser.add_argument("--ticker", action="append", dest="tickers", metavar="TICKER")
    args = parser.parse_args()
    run(args.tickers or DEFAULT_TICKERS)
