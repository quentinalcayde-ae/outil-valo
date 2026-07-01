"""MockLLMProvider — suggestions déterministes, zéro appel réseau.

Sert à développer et tester tout le flux de découverte sans consommer la clé OpenAI.
Le vrai OpenAIProvider (P3b) implémente la même interface.
"""
from datetime import date

from valo.providers.base import (
    CompSuggestion,
    LLMProvider,
    RecurringExtraction,
    TargetContext,
    TransactionSuggestion,
)

# Petit annuaire sectoriel factice mais plausible (tickers réels → testables via yfinance)
_SECTOR_COMPS: dict[str, list[tuple[str, str, str]]] = {
    "saas": [
        ("Salesforce", "CRM", "Leader CRM SaaS, ARR élevé, marge récurrente forte"),
        ("ServiceNow", "NOW", "Plateforme workflow SaaS, croissance ARR soutenue"),
        ("Workday", "WDAY", "SaaS HCM & Finance, base d'abonnement récurrente"),
        ("HubSpot", "HUBS", "SaaS marketing/CRM mid-market, modèle subscription"),
        ("Veeva", "VEEV", "SaaS vertical life sciences, revenus récurrents"),
        ("Datadog", "DDOG", "Observabilité SaaS, usage-based recurring"),
        ("Snowflake", "SNOW", "Data cloud, consommation récurrente"),
        ("Adobe", "ADBE", "Suite créative SaaS, ARR massif"),
    ],
    "default": [
        ("Salesforce", "CRM", "Comparable SaaS large cap"),
        ("Workday", "WDAY", "Comparable SaaS mid/large cap"),
        ("HubSpot", "HUBS", "Comparable SaaS mid-market"),
        ("Veeva", "VEEV", "Comparable SaaS vertical"),
    ],
}

_SECTOR_TX: dict[str, list[tuple[str, str, str, str]]] = {
    "saas": [
        ("Slack", "Salesforce", "2021-07-21", "M&A SaaS collaboration, multiple EV/Rev élevé"),
        ("Figma", "Adobe", "2022-09-15", "Deal design SaaS (finalement abandonné) — repère de multiple"),
        ("Anaplan", "Thoma Bravo", "2022-03-20", "LBO SaaS planning, multiple documenté"),
    ],
    "default": [
        ("Anaplan", "Thoma Bravo", "2022-03-20", "LBO SaaS, repère de multiple"),
    ],
}


def _key(ctx: TargetContext) -> str:
    hay = f"{ctx.sector or ''} {ctx.description or ''}".lower()
    return "saas" if ("saas" in hay or "logiciel" in hay or "software" in hay) else "default"


class MockLLMProvider(LLMProvider):
    def suggest_comps(self, ctx: TargetContext, n: int = 8) -> list[CompSuggestion]:
        rows = _SECTOR_COMPS[_key(ctx)]
        out = [
            CompSuggestion(name=name, ticker=ticker, rationale=rationale,
                           sector=ctx.sector, confidence="medium")
            for name, ticker, rationale in rows[:n]
        ]
        # Intègre d'éventuels tickers imposés par l'utilisateur
        known = {c.ticker for c in out}
        for t in ctx.extra_tickers:
            if t.upper() not in known:
                out.append(CompSuggestion(name=t.upper(), ticker=t.upper(),
                                          rationale="Ajouté par l'utilisateur", confidence="high"))
        return out

    def suggest_transactions(self, ctx: TargetContext, n: int = 5) -> list[TransactionSuggestion]:
        rows = _SECTOR_TX[_key(ctx)]
        return [
            TransactionSuggestion(
                target_company=tgt, acquirer=acq,
                tx_date=date.fromisoformat(d), rationale=rationale,
                source_doc_url=None, implied_multiple=None, sector=ctx.sector,
            )
            for tgt, acq, d, rationale in rows[:n]
        ]

    def extract_recurring(self, ticker: str, filing_text: str) -> RecurringExtraction:
        return RecurringExtraction(
            ticker=ticker, recurring_value=None, recurring_basis_tag=None,
            source_excerpt="[mock] extraction non implémentée", confidence="low",
        )
