def _ctx_block(ctx: TargetContext) -> str:
    lines = [
        f"Nom de la cible : {ctx.name}",
        f"Secteur indiqué : {ctx.sector or 'non précisé'}",
        f"Modèle récurrent : {'oui' if ctx.is_recurring else 'non'}",
        f"Agrégat de valorisation utilisé ensuite : {ctx.valuation_aggregate}",
    ]

    if ctx.description:
        lines.extend([
            "",
            "Description qualitative de la cible :",
            ctx.description,
        ])

    if getattr(ctx, "website", None):
        lines.append(f"Site web : {ctx.website}")

    if getattr(ctx, "customer_type", None):
        lines.append(f"Type de clients : {ctx.customer_type}")

    if getattr(ctx, "business_model", None):
        lines.append(f"Business model : {ctx.business_model}")

    if getattr(ctx, "value_chain_position", None):
        lines.append(f"Position dans la chaîne de valeur : {ctx.value_chain_position}")

    if getattr(ctx, "geography", None):
        lines.append(f"Géographie principale : {ctx.geography}")

    if getattr(ctx, "keywords", None):
        lines.append(f"Mots-clés métier : {', '.join(ctx.keywords)}")

    if ctx.aggregate_value:
        lines.append(
            f"{ctx.valuation_aggregate} courant (€), fourni uniquement comme contexte de taille "
            f"et à ne jamais réutiliser dans la réponse : {ctx.aggregate_value:,.0f}"
        )

    if ctx.extra_tickers:
        lines.extend([
            "",
            "Tickers suggérés ou imposés par l'utilisateur :",
            ", ".join(ctx.extra_tickers),
            "Instruction : ne pas les inclure automatiquement. Les inclure uniquement s'ils passent les tests "
            "de statut coté, ticker Yahoo Finance exact et pertinence économique.",
        ])

    return "\n".join(lines)


def comps_messages(ctx: TargetContext, n: int) -> list[dict]:
    return [
        {"role": "system", "content": COMPS_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Propose jusqu'à {n} comparables cotés pour la société cible ci-dessous.\n\n"
                "Important : ne cherche pas à atteindre absolument ce nombre. "
                "Retourne uniquement les comparables réellement pertinents, cotés et vérifiables. "
                "Ne donne aucun chiffre financier.\n\n"
                f"{_ctx_block(ctx)}"
            ),
        },
    ]


def transactions_messages(ctx: TargetContext, n: int) -> list[dict]:
    return [
        {"role": "system", "content": TRANSACTIONS_SYSTEM},
        {
            "role": "user",
            "content": (
                f"Propose jusqu'à {n} transactions M&A comparables pour la société cible ci-dessous.\n\n"
                "Important : chaque transaction doit être réelle, sourcée, et la source doit confirmer exactement "
                "la relation cible ← acquéreur. Exclure toute transaction sans source fiable. "
                "Ne donne aucun prix, aucun multiple, aucun chiffre financier.\n\n"
                f"{_ctx_block(ctx)}"
            ),
        },
    ]