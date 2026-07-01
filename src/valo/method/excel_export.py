"""Export Excel formula-driven — 2 onglets : Synthèse + Comparables. Voir PROJECT_V1.md §2."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from valo.method.valuation import ValuationResult
from valo.models import TargetAnchor, ValuationRun

CLR_HEADER = "1F3864"
CLR_SECTION = "D6E4F7"
CLR_EXCL = "F2F2F2"
CLR_RESULT = "E2EFDA"


def _header(ws, row, col, value, bold=True):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(bold=bold, color="FFFFFF" if bold else "000000")
    if bold:
        cell.fill = PatternFill("solid", fgColor=CLR_HEADER)
    cell.alignment = Alignment(horizontal="center")


def _fmt_m(v):
    return f"{v:.2f}x" if v is not None else "N/A"


def export_excel(
    run: ValuationRun,
    anchor: TargetAnchor,
    result: ValuationResult,
    included_comps: list[dict],
    excluded_comps: list[dict],
    target_aggregate_value: float,
    result_ev: float,
    output_dir: str = "exports",
) -> str:
    wb = Workbook()
    median_ref = _build_comps_sheet(wb, run, included_comps, excluded_comps)
    _build_synthese_sheet(wb, run, anchor, result, target_aggregate_value, median_ref)

    # Ordonne : Synthèse en premier
    wb.move_sheet("Synthèse", -(len(wb.sheetnames) - 1))
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    filename = f"valo_{run.target_id}_run{run.id}_{run.run_date.strftime('%Y%m%d')}.xlsx"
    path = str(Path(output_dir) / filename)
    wb.save(path)
    return path


def _build_comps_sheet(wb, run, included, excluded) -> str:
    """Tableau de comps classique. Retourne la réf cellule de la médiane (ex. 'Comparables!G7')."""
    ws = wb.create_sheet("Comparables")
    widths = {"A": 10, "B": 22, "C": 14, "D": 13, "E": 14, "F": 14, "G": 11, "H": 10, "I": 32}
    for col, w in widths.items():
        ws.column_dimensions[col].width = w

    agg = run.aggregate
    headers = ["Ticker", "Nom", "Market Cap", "Net Debt", "EV", f"Agrégat ({agg})", f"EV/{agg}", "Statut", "Note"]
    for c, h in enumerate(headers, 1):
        _header(ws, 1, c, h)

    row = 2
    for c in included:
        ws.cell(row=row, column=1, value=c["ticker"])
        ws.cell(row=row, column=2, value=c["name"])
        ws.cell(row=row, column=3, value=c["market_cap"]).number_format = "#,##0"
        ws.cell(row=row, column=4, value=c["net_debt"]).number_format = "#,##0"
        # EV = market_cap + net_debt (formule)
        ws.cell(row=row, column=5, value=f"=C{row}+D{row}").number_format = "#,##0"
        ws.cell(row=row, column=6, value=c["aggregate_value"]).number_format = "#,##0"
        # EV/agrégat (formule)
        ws.cell(row=row, column=7, value=f'=IF(F{row}>0,E{row}/F{row},"N/A")').number_format = '0.00"x"'
        ws.cell(row=row, column=8, value="Inclus")
        ws.cell(row=row, column=9, value=c.get("relevance_note") or "")
        row += 1

    first, last = 2, row - 1
    median_row = row
    ws.cell(row=median_row, column=6, value="MÉDIANE").font = Font(bold=True)
    med_cell = ws.cell(row=median_row, column=7, value=f"=MEDIAN(G{first}:G{last})")
    med_cell.number_format = '0.00"x"'
    med_cell.font = Font(bold=True)
    for c in range(1, 10):
        ws.cell(row=median_row, column=c).fill = PatternFill("solid", fgColor=CLR_SECTION)
    row = median_row + 2

    if excluded:
        ws.cell(row=row, column=1, value="— Exclus (hors médiane) —").font = Font(italic=True, color="888888")
        row += 1
        for c in excluded:
            ws.cell(row=row, column=1, value=c["ticker"])
            ws.cell(row=row, column=2, value=c["name"])
            ws.cell(row=row, column=3, value=c["market_cap"]).number_format = "#,##0"
            ws.cell(row=row, column=4, value=c["net_debt"]).number_format = "#,##0"
            ws.cell(row=row, column=5, value=c["ev"]).number_format = "#,##0"
            ws.cell(row=row, column=6, value=c["aggregate_value"]).number_format = "#,##0"
            ws.cell(row=row, column=7, value=_fmt_m(c["multiple"]))
            ws.cell(row=row, column=8, value="Exclu")
            ws.cell(row=row, column=9, value=c.get("exclusion_reason") or "")
            for cc in range(1, 10):
                ws.cell(row=row, column=cc).fill = PatternFill("solid", fgColor=CLR_EXCL)
                ws.cell(row=row, column=cc).font = Font(color="888888")
            row += 1

    return f"Comparables!G{median_row}"


def _build_synthese_sheet(wb, run, anchor, result, target_aggregate_value, median_ref: str):
    ws = wb.create_sheet("Synthèse")
    ws.column_dimensions["A"].width = 40
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 34

    def line(r, label, value=None, formula=None, fmt=None, note=None, bold=False, fill=None):
        ws.cell(row=r, column=1, value=label)
        cell = ws.cell(row=r, column=2, value=formula if formula else value)
        if fmt:
            cell.number_format = fmt
        if bold:
            cell.font = Font(bold=True)
        if note:
            ws.cell(row=r, column=3, value=note)
        if fill:
            for c in range(1, 4):
                ws.cell(row=r, column=c).fill = PatternFill("solid", fgColor=fill)

    _header(ws, 1, 1, "Paramètre")
    _header(ws, 1, 2, "Valeur")
    _header(ws, 1, 3, "Note")

    line(2, "── Ancres tour d'entrée ──", fill=CLR_SECTION, bold=True)
    line(3, "Date du tour", str(anchor.entry_date))
    line(4, "Tour", anchor.entry_round or "")
    line(5, f"M_entry (EV/{run.aggregate} au tour)", anchor.m_entry_aggregate, fmt='0.00"x"',
         note="Multiple ancré, agrégat cible")
    line(6, "M_market_entry (médiane marché au tour)", anchor.m_market_entry, fmt='0.00"x"',
         note=f"basis={anchor.market_anchor_basis or '?'} · source={anchor.m_market_entry_source}")

    line(8, "── Marché actuel ──", fill=CLR_SECTION, bold=True)
    # median_now référence l'onglet Comparables (auditable / recalculable)
    line(9, "Median_now (médiane panel actuel)", formula=f"={median_ref}", fmt='0.00"x"',
         note="Référence l'onglet Comparables")
    line(10, "Drift ratio (median_now / m_market_entry)", formula="=B9/B6", fmt="0.000",
         note="Ratio sans unité — dérive relative du marché")
    line(11, "Facteur de rétention", run.retention_factor or 1.0, fmt="0.000",
         note="1.0 si non récurrent ou neutre")

    line(13, "── Résultat ──", fill=CLR_SECTION, bold=True)
    line(14, f"M_final (EV/{run.aggregate} retenu)", formula="=B5*B10*B11", fmt='0.00"x"',
         note=f"M_entry × drift × rétention [MODE {run.mode}]", bold=True, fill=CLR_RESULT)
    line(15, f"Agrégat cible ({run.aggregate})", target_aggregate_value, fmt="#,##0",
         note="Chiffre clé saisi sur la cible")
    line(16, "EV cible (100 %)", formula="=B14*B15", fmt="#,##0",
         note="EV = M_final × agrégat cible", bold=True, fill=CLR_RESULT)

    ws.cell(row=18, column=1, value="Méthode : IPEV déc. 2022 — calibration par maintien du delta.").font = Font(italic=True, color="888888")
    ws.cell(row=19, column=1, value=f"Run #{run.id} · MODE {run.mode} · {run.run_date.strftime('%Y-%m-%d %H:%M')}").font = Font(italic=True, color="888888")
