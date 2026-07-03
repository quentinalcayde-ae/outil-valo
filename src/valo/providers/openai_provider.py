"""OpenAIProvider — découverte comps & transactions via OpenAI (interface LLMProvider).

Même contrat que MockLLMProvider. Le LLM ne fournit que l'identité (jamais de chiffre
entrant dans la médiane). Modèle configurable via OPENAI_MODEL (petit modèle par défaut).
"""
import json
from datetime import date

from openai import OpenAI

from valo.logging import logger
from valo.prompts import discovery
from valo.providers.base import (
    CompSuggestion,
    LLMProvider,
    RecurringExtraction,
    TargetContext,
    TransactionSuggestion,
)


def _parse_date(v) -> date | None:
    if not v or not isinstance(v, str):
        return None
    try:
        return date.fromisoformat(v[:10])
    except ValueError:
        return None


# Prompts de MISE EN FORME (petit modèle) — normalisent le texte de découverte en JSON strict.
COMPS_FORMAT_SYSTEM = """Tu reçois l'analyse d'un autre expert listant des sociétés cotées comparables.
Extrais-la en JSON STRICT, sans rien inventer ni ajouter de société absente du texte.
Conserve les tickers EXACTEMENT tels quels. Fusionne toute nuance/limite dans "rationale".
Conserve tier (1/2/3), statut (priced/proxy/outlier/distressed) et pct_ca_activite_comparable (%).
Format : {"comps":[{"name":str,"ticker":str,"rationale":str,"sector":str,"confidence":"high"|"medium"|"low",
"tier":1|2|3,"statut":"priced"|"proxy"|"outlier"|"distressed","pct_ca_activite_comparable":number}]}
Si le texte ne contient aucune société exploitable : {"comps":[]}."""

TRANSACTIONS_FORMAT_SYSTEM = """Tu reçois l'analyse d'un expert listant des transactions M&A comparables.
Extrais-la en JSON STRICT, sans rien inventer. Ne fabrique aucun chiffre : implied_multiple=null sauf s'il
figure explicitement dans le texte. tx_date au format ISO "YYYY-MM-DD" ou null.
Format : {"transactions":[{"target_company":str,"acquirer":str|null,"tx_date":str|null,"rationale":str,"source_doc_url":str|null,"implied_multiple":number|null,"sector":str|null}]}
Si aucune transaction exploitable : {"transactions":[]}."""


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, discovery_model: str = "gpt-4o-mini",
                 formatting_model: str = "gpt-4o-mini") -> None:
        self.client = OpenAI(api_key=api_key)
        self.discovery_model = discovery_model
        self.formatting_model = formatting_model

    def _discover(self, messages: list[dict]) -> str:
        """Étape 1 — raisonnement (modèle fort), texte libre, sans contrainte JSON."""
        resp = self.client.chat.completions.create(model=self.discovery_model, messages=messages)
        return resp.choices[0].message.content or ""

    def _format_json(self, system: str, raw_text: str) -> dict:
        """Étape 2 — mise en forme JSON stricte (petit modèle rapide)."""
        resp = self.client.chat.completions.create(
            model=self.formatting_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": raw_text}],
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content or "{}")

    def suggest_comps(self, ctx: TargetContext, n: int = 8) -> list[CompSuggestion]:
        log = logger.bind(op="suggest_comps", model=self.discovery_model, target=ctx.name)
        try:
            raw = self._discover(discovery.comps_messages(ctx, n))
            data = self._format_json(COMPS_FORMAT_SYSTEM, raw)
        except Exception as exc:
            log.error("openai_suggest_comps_failed", error=str(exc))
            raise
        out: list[CompSuggestion] = []
        for c in data.get("comps", []):
            ticker = (c.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            tier = c.get("tier")
            statut = (c.get("statut") or "priced").strip().lower()
            # Garde-fou EN DUR : tier 3 → toujours proxy, jamais priced (indépendant du LLM)
            if tier == 3 and statut == "priced":
                statut = "proxy"
            out.append(CompSuggestion(
                name=c.get("name") or ticker,
                ticker=ticker,
                rationale=c.get("rationale") or "",
                sector=c.get("sector") or ctx.sector,
                confidence=c.get("confidence") or "medium",
                tier=tier if tier in (1, 2, 3) else None,
                statut=statut if statut in ("priced", "proxy", "outlier", "distressed") else "priced",
                pct_ca_comparable=c.get("pct_ca_activite_comparable"),
            ))
        # Garantit l'inclusion des tickers imposés par l'utilisateur
        known = {c.ticker for c in out}
        for t in ctx.extra_tickers:
            if t.upper() not in known:
                out.append(CompSuggestion(t.upper(), t.upper(), "Ajouté par l'utilisateur", ctx.sector, "high"))
        log.info("openai_suggest_comps_ok", n=len(out))
        return out

    def suggest_transactions(self, ctx: TargetContext, n: int = 5) -> list[TransactionSuggestion]:
        log = logger.bind(op="suggest_transactions", model=self.discovery_model, target=ctx.name)
        try:
            raw = self._discover(discovery.transactions_messages(ctx, n))
            data = self._format_json(TRANSACTIONS_FORMAT_SYSTEM, raw)
        except Exception as exc:
            log.error("openai_suggest_transactions_failed", error=str(exc))
            raise
        out: list[TransactionSuggestion] = []
        for t in data.get("transactions", []):
            company = (t.get("target_company") or "").strip()
            if not company:
                continue
            out.append(TransactionSuggestion(
                target_company=company,
                acquirer=t.get("acquirer"),
                tx_date=_parse_date(t.get("tx_date")),
                rationale=t.get("rationale") or "",
                source_doc_url=t.get("source_doc_url"),
                implied_multiple=t.get("implied_multiple"),
                sector=t.get("sector") or ctx.sector,
            ))
        log.info("openai_suggest_transactions_ok", n=len(out))
        return out

    def extract_recurring(self, ticker: str, filing_text: str) -> RecurringExtraction:
        # P4 — extraction du récurrent des filings
        raise NotImplementedError("extract_recurring sera implémenté en P4")
