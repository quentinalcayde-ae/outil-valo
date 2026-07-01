"""CLI de test P2 — validation sur cas réel Syroco (SaaS maritime).

Usage :
    python scripts/test_p2.py
    python scripts/test_p2.py --mode B   (re-price médiane seulement)
    python scripts/test_p2.py --arr 8    (ARR cible en M€, défaut : 8)

Comps SaaS utilisés : ADBE, CRM, NOW, WDAY, HUBS, VEEV
Ancres fictives représentatives d'un tour série B mi-2023.
"""
import argparse
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from valo.config import settings
from valo.logging import configure_logging, logger
from valo.method.service import execute_run
from valo.providers.yahoo_provider import YahooProvider
from valo.storage.repositories import (
    add_run_comp,
    create_anchor,
    create_comp,
    create_run,
    create_target,
    get_comp_by_ticker,
    get_latest_snapshot,
    insert_snapshot,
)
from valo.storage.sqlite_store import SQLiteStore

configure_logging()

COMPS = [
    {"ticker": "ADBE", "name": "Adobe",        "sector": "SaaS / Digital Experience"},
    {"ticker": "CRM",  "name": "Salesforce",   "sector": "SaaS / CRM"},
    {"ticker": "NOW",  "name": "ServiceNow",   "sector": "SaaS / ITSM"},
    {"ticker": "WDAY", "name": "Workday",      "sector": "SaaS / HCM & Finance"},
    {"ticker": "HUBS", "name": "HubSpot",      "sector": "SaaS / Marketing & CRM"},
    {"ticker": "VEEV", "name": "Veeva",        "sector": "SaaS / Life Sciences"},
]

# Ancres représentatives d'un tour Série B mi-2023 (fictives mais cohérentes)
ANCHOR = {
    "entry_date": date(2023, 6, 30),
    "entry_round": "Série B",
    "m_entry_aggregate": 8.0,    # EV/ARR au tour
    "m_market_entry": 9.5,       # médiane panel SaaS au tour d'entrée
}


def run(mode: str, arr_m: float) -> None:
    store = SQLiteStore(settings.database_url)
    provider = YahooProvider()

    with store.get_session() as session:
        # 1. Cible
        target = create_target(
            session,
            name="Syroco",
            sector="SaaS / Maritime decarbonization",
            is_recurring=True,
            valuation_aggregate="arr",
            fund="FR FII",
            notes="Test P2 — validation méthode calibration delta",
        )
        create_anchor(session, target.id, **ANCHOR)
        logger.info("target_created", id=target.id, name=target.name)

        # 2. Comps + snapshots
        comp_snapshot_ids = []
        for c in COMPS:
            comp = get_comp_by_ticker(session, c["ticker"])
            if comp is None:
                comp = create_comp(session, name=c["name"], ticker=c["ticker"],
                                   sector=c["sector"], currency="USD", is_recurring=True)

            snap_existing = get_latest_snapshot(session, comp.id)
            if snap_existing is None:
                logger.info("fetching_snapshot", ticker=c["ticker"])
                try:
                    snap = provider.fetch_snapshot(c["ticker"])
                    stored = insert_snapshot(session, comp.id, snap)
                except Exception as exc:
                    logger.error("fetch_failed", ticker=c["ticker"], error=str(exc))
                    continue
            else:
                stored = snap_existing
                logger.info("snapshot_reused", ticker=c["ticker"], id=stored.id)

            comp_snapshot_ids.append((comp.id, stored.id, c))

        # 3. Créer le run
        # Agrégat "revenue" pour la validation P2 — recurring_value disponible en P4 seulement
        run_obj = create_run(
            session,
            target_id=target.id,
            mode=mode,
            aggregate="revenue",
            retention_factor=1.0,
        )

        # 4. Associer le panel — tous inclus sauf ADBE (outlier large cap pour démo)
        for _, snap_id, c in comp_snapshot_ids:
            excluded = c["ticker"] == "ADBE"
            add_run_comp(
                session,
                run_id=run_obj.id,
                snapshot_id=snap_id,
                included=not excluded,
                exclusion_reason="Large cap outlier — profil de croissance différent" if excluded else None,
                relevance_note=c["sector"] if not excluded else None,
            )

        session.flush()
        run_id = run_obj.id
        logger.info("run_created", run_id=run_id, mode=mode, n_comps=len(comp_snapshot_ids))

    # 5. Exécuter le run (hors transaction pour éviter les locks SQLite)
    with store.get_session() as session:
        ctx = execute_run(
            session,
            run_id=run_id,
            target_aggregate_value=arr_m * 1e6,  # en € (même unité que EV)
        )

    # 6. Affichage résultat
    import io, sys
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    print("\n=== SYROCO - Valorisation par comparables IPEV ===")
    print(f"  Mode             : {ctx.run.mode}")
    print(f"  Agrégat cible    : Revenue = {arr_m:.1f} M€  (ARR en P4 après extraction récurrent)")
    print(f"  Ancre tour       : {ANCHOR['m_entry_aggregate']:.2f}x ARR")
    print(f"  Médiane marché   : {ANCHOR['m_market_entry']:.2f}x (au tour)")
    print(f"  Médiane actuelle : {ctx.result.median_now:.2f}x")
    print(f"  Drift ratio      : {ctx.result.drift_ratio:.3f}")
    print(f"  Facteur rétention: {ctx.result.retention_factor:.2f}x")
    print(f"  M_final retenu   : {ctx.result.m_final:.2f}x ARR")
    print(f"  EV cible (100%)  : {ctx.run.result_ev/1e6:.1f} M€")
    print()
    print("  Comps inclus :")
    for c in ctx.included_comps:
        m = f"{c['multiple']:.2f}x" if c["multiple"] else "N/A"
        print(f"    {c['ticker']:6} EV/ARR={m}")
    print()
    print("  Exclus (hors médiane) :")
    for c in ctx.excluded_comps:
        print(f"    {c['ticker']:6} — {c.get('exclusion_reason','')}")
    print()
    print(f"  Excel : {ctx.excel_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["A", "B"], default="A")
    parser.add_argument("--arr", type=float, default=8.0, metavar="M€")
    args = parser.parse_args()
    run(args.mode, args.arr)
