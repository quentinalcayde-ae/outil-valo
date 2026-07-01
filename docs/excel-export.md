# Export Excel formula-driven

*Reflète `src/valo/method/excel_export.py`.*

## Structure du classeur

### Feuille `Panel`

| Colonne | Contenu |
|---|---|
| A | Ticker |
| B | Nom |
| C | EV (valeur brute) |
| D | Agrégat (revenue_ltm ou recurring_value) |
| E | `=IF(D>0,C/D,"N/A")` — multiple formula-driven |
| F | Statut (Inclus / Exclu) |
| G | Note de pertinence / motif d'exclusion |

Ligne médiane : `=MEDIAN(E2:En)` — recalculable si on modifie le panel.

Les comps exclus apparaissent en grisé sous les inclus, **hors plage de la MEDIAN**.

### Feuille `Valo`

Toutes les valeurs clés sont des formules qui font référence aux cellules de la même feuille :

```
M_final  =  B_m_entry  ×  (B_median_now / B_m_market_entry)  ×  B_retention
EV       =  B_m_final  ×  B_aggregate_cible
```

Aucune valeur n'est figée dans les cellules résultat — le classeur se recalcule si on modifie manuellement une hypothèse.

## Nommage des fichiers

```
valo_<target_id>_run<run_id>_<YYYYMMDD>.xlsx
```

Stocké dans `exports/` (hors git). Le chemin est persisté dans `valuation_runs.excel_path`.
