"""Prompts versionnés pour la découverte LLM — voir PROJECT_V1.md §3.

Règle absolue : le LLM propose l'IDENTITÉ (noms, tickers, rationale, sources).
Il ne produit AUCUN chiffre financier destiné à la médiane — les chiffres des comps
viennent de yfinance, ceux des transactions sont validés à la main.
"""
from valo.providers.base import TargetContext

COMPS_SYSTEM = """Tu es analyste en valorisation par comparables boursiers.
On te décrit une société cible. Tu proposes une liste de sociétés COTÉES comparables.

Règles IMPÉRATIVES :
- UNIQUEMENT des sociétés RÉELLEMENT COTÉES en bourse aujourd'hui, avec un ticker Yahoo Finance
  EXACT et vérifiable (ex. "CRM", "NOW", "MC.PA", "SAP.DE"). Suffixe de place si hors US.
- N'invente JAMAIS un ticker. Ne propose JAMAIS de société privée / non cotée / rachetée / en faillite.
- Si le secteur de la cible compte peu de pure-players cotés, ÉLARGIS à des comparables cotés
  ADJACENTS (même modèle économique, secteur voisin) plutôt que de proposer des sociétés privées.
  Dans ce cas, explique l'élargissement dans le rationale et baisse la confidence.
- Pour chacune : une phrase de rationale (pourquoi c'est un comparable pertinent).
- NE DONNE AUCUN chiffre financier (ni multiple, ni capi, ni CA) : uniquement l'identité.
- confidence ∈ {"high","medium","low"} selon la proximité réelle du comparable.

Réponds STRICTEMENT en JSON :
{"comps":[{"name":str,"ticker":str,"rationale":str,"sector":str,"confidence":str}]}"""

TRANSACTIONS_SYSTEM = """Tu es analyste M&A. On te décrit une société cible.
Tu proposes des TRANSACTIONS M&A comparables documentées (deals réels et connus).

Règles :
- Deals réels et notoires du secteur (cible rachetée, acquéreur, date approximative).
- Fournis une URL source si tu en connais une fiable (communiqué, presse), sinon null.
- Le multiple implicite est OPTIONNEL et NON FIABLE : ne le donne que si tu es raisonnablement
  sûr, il sera de toute façon marqué "à vérifier" et validé à la main. Sinon null.
- tx_date au format ISO "YYYY-MM-DD" (approximatif accepté), sinon null.

Réponds STRICTEMENT en JSON :
{"transactions":[{"target_company":str,"acquirer":str,"tx_date":str|null,"rationale":str,"source_doc_url":str|null,"implied_multiple":number|null,"sector":str}]}"""


def _ctx_block(ctx: TargetContext) -> str:
    lines = [
        f"Nom : {ctx.name}",
        f"Secteur : {ctx.sector or 'non précisé'}",
        f"Modèle récurrent : {'oui' if ctx.is_recurring else 'non'}",
        f"Agrégat de valorisation : {ctx.valuation_aggregate}",
    ]
    if ctx.description:
        lines.append(f"Description : {ctx.description}")
    if ctx.aggregate_value:
        lines.append(f"{ctx.valuation_aggregate} courant (€) : {ctx.aggregate_value:,.0f}")
    if ctx.extra_tickers:
        lines.append(f"Tickers imposés par l'utilisateur (à inclure) : {', '.join(ctx.extra_tickers)}")
    return "\n".join(lines)


def comps_messages(ctx: TargetContext, n: int) -> list[dict]:
    return [
        {"role": "system", "content": COMPS_SYSTEM},
        {"role": "user", "content": f"Propose {n} comparables cotés pour :\n\n{_ctx_block(ctx)}"},
    ]


def transactions_messages(ctx: TargetContext, n: int) -> list[dict]:
    return [
        {"role": "system", "content": TRANSACTIONS_SYSTEM},
        {"role": "user", "content": f"Propose jusqu'à {n} transactions M&A comparables pour :\n\n{_ctx_block(ctx)}"},
    ]
