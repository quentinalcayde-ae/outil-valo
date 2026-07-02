"""Tests P3b — parsing/mapping de l'OpenAIProvider (sans appel réseau)."""
from datetime import date

from valo.providers.base import TargetContext
from valo.providers.openai_provider import OpenAIProvider, _parse_date


def _provider(monkeypatch, payload):
    """Instancie un OpenAIProvider dont la découverte/mise en forme renvoie payload (aucun réseau)."""
    p = OpenAIProvider.__new__(OpenAIProvider)  # évite __init__ (pas de client réel)
    p.discovery_model = "test"
    p.formatting_model = "test"
    monkeypatch.setattr(p, "_discover", lambda messages: "raw text")
    monkeypatch.setattr(p, "_format_json", lambda system, raw: payload)
    return p


def test_parse_date():
    assert _parse_date("2021-07-21") == date(2021, 7, 21)
    assert _parse_date("2021-07-21T00:00:00") == date(2021, 7, 21)
    assert _parse_date(None) is None
    assert _parse_date("n/a") is None


def test_suggest_comps_mapping(monkeypatch):
    payload = {"comps": [
        {"name": "Salesforce", "ticker": "crm", "rationale": "CRM SaaS", "sector": "SaaS", "confidence": "high"},
        {"name": "NoTicker", "ticker": "", "rationale": "ignoré"},
    ]}
    ctx = TargetContext(name="X", sector="SaaS", description=None, is_recurring=True, valuation_aggregate="arr")
    comps = _provider(monkeypatch, payload).suggest_comps(ctx, n=5)
    assert len(comps) == 1  # l'entrée sans ticker est ignorée
    assert comps[0].ticker == "CRM"  # normalisé en majuscules
    assert comps[0].confidence == "high"


def test_suggest_comps_includes_extra_tickers(monkeypatch):
    payload = {"comps": [{"name": "Salesforce", "ticker": "CRM", "rationale": "r"}]}
    ctx = TargetContext(name="X", sector="SaaS", description=None, is_recurring=True,
                        valuation_aggregate="arr", extra_tickers=["WDAY"])
    comps = _provider(monkeypatch, payload).suggest_comps(ctx, n=5)
    assert {"CRM", "WDAY"} <= {c.ticker for c in comps}


def test_suggest_transactions_mapping(monkeypatch):
    payload = {"transactions": [
        {"target_company": "Slack", "acquirer": "Salesforce", "tx_date": "2021-07-21",
         "rationale": "SaaS collab", "source_doc_url": "http://x", "implied_multiple": None, "sector": "SaaS"},
        {"target_company": "", "rationale": "ignoré"},
    ]}
    ctx = TargetContext(name="X", sector="SaaS", description=None, is_recurring=True, valuation_aggregate="arr")
    txs = _provider(monkeypatch, payload).suggest_transactions(ctx, n=5)
    assert len(txs) == 1
    assert txs[0].target_company == "Slack"
    assert txs[0].tx_date == date(2021, 7, 21)
    assert txs[0].implied_multiple is None
