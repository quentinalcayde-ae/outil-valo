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


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o-mini") -> None:
        self.client = OpenAI(api_key=api_key)
        self.model = model

    def _complete_json(self, messages: list[dict]) -> dict:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        content = resp.choices[0].message.content or "{}"
        return json.loads(content)

    def suggest_comps(self, ctx: TargetContext, n: int = 8) -> list[CompSuggestion]:
        log = logger.bind(op="suggest_comps", model=self.model, target=ctx.name)
        try:
            data = self._complete_json(discovery.comps_messages(ctx, n))
        except Exception as exc:
            log.error("openai_suggest_comps_failed", error=str(exc))
            raise
        out: list[CompSuggestion] = []
        for c in data.get("comps", []):
            ticker = (c.get("ticker") or "").strip().upper()
            if not ticker:
                continue
            out.append(CompSuggestion(
                name=c.get("name") or ticker,
                ticker=ticker,
                rationale=c.get("rationale") or "",
                sector=c.get("sector") or ctx.sector,
                confidence=c.get("confidence") or "medium",
            ))
        # Garantit l'inclusion des tickers imposés par l'utilisateur
        known = {c.ticker for c in out}
        for t in ctx.extra_tickers:
            if t.upper() not in known:
                out.append(CompSuggestion(t.upper(), t.upper(), "Ajouté par l'utilisateur", ctx.sector, "high"))
        log.info("openai_suggest_comps_ok", n=len(out))
        return out

    def suggest_transactions(self, ctx: TargetContext, n: int = 5) -> list[TransactionSuggestion]:
        log = logger.bind(op="suggest_transactions", model=self.model, target=ctx.name)
        try:
            data = self._complete_json(discovery.transactions_messages(ctx, n))
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
