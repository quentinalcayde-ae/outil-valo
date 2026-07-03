# Méthode de valorisation — snapshot réel

*Reflète `src/valo/method/`. Voir PROJECT_V1.md §5 pour la spec complète et le référentiel IPEV.*

## Formule centrale

```
M_final = M_entry_aggregate × (median_now / m_market_entry) × retention_factor
```

| Terme | Source | Remarque |
|---|---|---|
| `M_entry_aggregate` | `target_anchors.m_entry_aggregate` | Multiple ancré au dernier tour, agrégat cible |
| `m_market_entry` | `target_anchors.m_market_entry` | Médiane panel au tour d'entrée — figée |
| `median_now` | `MEDIAN(comp_multiples)` sur les comps inclus | Seul terme qui bouge en MODE B |
| `retention_factor` | Saisi au run | 1.0 si non récurrent ou neutre |
| `drift_ratio` | `median_now / m_market_entry` | Ratio sans unité — dérive relative du marché |

**Pas de discount stacking.** Un comp qui croît ne perd pas de valeur dans le mark.

## Modules

### `method/valuation.py` — noyau pur

- `compute_ev_multiple(market_cap, net_debt)` → EV
- `compute_multiple(ev, aggregate)` → EV/agrégat
- `run_valuation(ValuationInput)` → `ValuationResult`

Entrées via `ValuationInput` : `mode`, `m_entry_aggregate`, `m_market_entry`, `comp_multiples`, `retention_factor`.

### `method/service.py` — orchestration

`execute_run(session, run_id, target_aggregate_value, output_dir)` :
1. Charge le panel du run (`run_comps.included=True` uniquement pour la médiane)
2. Calcule `EV/agrégat` pour chaque comp inclus selon `run.aggregate`
3. Appelle `run_valuation()` et calcule `result_ev = M_final × target_aggregate_value`
4. Persiste le résultat dans `valuation_runs`
5. Génère l'Excel → retourne un `RunContext`

**Sélection de l'agrégat des comps** :
- `aggregate="arr"` ou `"recurring"` → `comp_snapshot.recurring_value` (disponible après P4)
- `aggregate="revenue"` → `comp_snapshot.revenue_ltm` (disponible via YahooProvider P1)

### `method/excel_export.py` — export formula-driven

Feuille **Panel** : comps inclus avec formule `=EV/agrégat` dans chaque cellule multiple, ligne `=MEDIAN(...)`.
Feuille **Valo** : toutes les cellules clés sont des formules Excel (pas de valeurs figées) — auditable et recalculable à l'ouverture.

### `method/anchor.py` — ancre marché (MODE A)

`compute_market_anchor(provider, tickers, entry_date)` → `AnchorProposal` :
- Pour chaque comp du panel inclus : `fetch_historical_snapshot` → EV/Revenue à `entry_date`.
- Médiane des multiples disponibles = `m_market_entry` proposé. `basis = "revenue"`.
- Comps sans donnée (IPO postérieure…) signalés (`available=False`), exclus du calcul.
- **Cas ARR** : pas d'ARR historique → override manuel du multiple (`source=manual`, `basis=arr`) ou ancre sur EV/Revenue. Le ratio de dérive étant sans unité, le mark reste valide.
- Valeur toujours **surchargeable** (ancre gelée à vie).

## Panel en tiers & ajustements (révision juillet 2026)

- **Tiers** : chaque comp a `tier` (1 pure-player / 2 software adjacent / 3 proxy value-chain) + `statut`. **Seuls les priced (Tier 1/2) entrent dans la médiane** ; les tier-3/proxies sont conservés pour la traçabilité mais exclus du calcul (garde-fou en dur `tier==3 → proxy`). Cf. `service._is_priced`.
- **β OLS supprimé (Option A)** : une régression EV/Rev~croissance sur un panel de dérive hétérogène à faible N est du bruit (β négatif observé). L'ajustement de croissance est désormais un **delta additif manuel** (`run.growth_delta`), justifié, avec `other_deltas` (marge/NRR/taille). Pas de cap dur : un **flag** alerte si `|Σ deltas| > 40 %` de la base.
- **Robustesse dérive** : médiane **+ moyenne winsorisée** du set priced ; flags `panel_priced_faible (<8)`, `derive_portee_par_nom_unique`, `proxy_dans_calcul`.
- `M_final = max(0 ; base + growth_delta + other_deltas)`. Croissance des comps = yfinance LTM (affichée, contexte).

## Deux régimes : calibration delta vs comparables directs

- **Calibration par delta** (ancre présente) : `M_final = M_entry × (median_now / m_market_entry) × rétention`.
- **Comparables directs** (aucune ancre) : `M_final = median_now × rétention`. Pour une opportunité sans historique / sans tour de référence — on applique directement la médiane des pairs. `median_now` est alors calculé sur l'**agrégat cible** lui-même (pas de drift sans unité).

Le régime est choisi automatiquement dans `execute_run` selon la présence d'une ancre complète (`ValuationResult.calibrated`). L'ancre est **optionnelle** et **persistée par cible** (une seule ligne `target_anchors`, mise à jour, pas recréée à chaque run).

## MODE A vs MODE B

| MODE | Usage | Comportement |
|---|---|---|
| A | Amorçage / premier run | Gèle `m_entry_aggregate` et `m_market_entry` depuis les ancres |
| B | Run trimestriel | Identique — seul `median_now` change (reflète le marché actuel) |

La distinction A/B est portée par le champ `valuation_runs.mode`. En pratique, le service exécute la même formule dans les deux cas — c'est la mise à jour du snapshot des comps qui fait évoluer `median_now`.
