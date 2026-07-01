"""Export Excel formula-driven auditable — voir PROJECT_V1.md §2."""
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from valo.method.valuation import ValuationResult
from valo.models import TargetAnchor, ValuationRun

# Palette
CLR_HEADER = "1F3864"   # bleu nuit
CLR_SECTION = "D6E4F7"  # bleu pâle
CLR_EXCL = "F2F2F2"     # gris exclu
CLR_RESULT = "E2EFDA"   # vert résultat


def _header(ws, row: int, col: int, value: str, bold: bool = True) -> None:
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(bold=bold, color="FFFFFF" if bold else "000000")
    if bold:
        cell.fill = PatternFill("solid", fgColor=CLR_HEADER)
    cell.alignment = Alignment(horizontal="center")


def _fmt_m(v: float | None) -> str:
    return f"{v:.2f}x" if v is not None else "N/A"


def _fmt_bn(v: float | None) -> str:
    if v is None:
        return "N/A"
    if abs(v) >= 1e9:
        return f"{v/1e9:.1f}B"
    if abs(v) >= 1e6:
        return f"{v/1e6:.0f}M"
    return str(round(v))


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

    _build_panel_sheet(wb, run, included_comps, excluded_comps)
    _build_valo_sheet(wb, run, anchor, result, target_aggregate_value, result_ev)

    # Supprimer la feuille vide par défaut
    if "Sheet" in wb.sheetnames:
        del wb["Sheet"]

    filename = f"valo_{run.target_id}_run{run.id}_{run.run_date.strftime('%Y%m%d')}.xlsx"
    path = str(Path(output_dir) / filename)
    wb.save(path)
    return path


def _build_panel_sheet(
    wb: Workbook,
    run: ValuationRun,
    included: list[dict],
    excluded: list[dict],
) -> None:
    ws = wb.create_sheet("Panel")
    ws.column_dimensions["A"].width = 12
    ws.column_dimensions["B"].width = 22
    ws.column_dimensions["C"].width = 16
    ws.column_dimensions["D"].width = 16
    ws.column_dimensions["E"].width = 14
    ws.column_dimensions["F"].width = 14
    ws.column_dimensions["G"].width = 35

    headers = ["Ticker", "Nom", "EV", f"Agrégat ({run.aggregate})", f"EV/{run.aggregate}", "Statut", "Note"]
    for col, h in enumerate(headers, 1):
        _header(ws, 1, col, h)

    row = 2
    # Comps inclus
    for c in included:
        ws.cell(row=row, column=1, value=c["ticker"])
        ws.cell(row=row, column=2, value=c["name"])
        ws.cell(row=row, column=3, value=c["ev"])
        ws.cell(row=row, column=3).number_format = '#,##0'
        ws.cell(row=row, column=4, value=c["aggregate_value"])
        ws.cell(row=row, column=4).number_format = '#,##0'
        # Formule : EV/agrégat — formula-driven
        ev_cell = f"C{row}"
        agg_cell = f"D{row}"
        ws.cell(row=row, column=5, value=f"=IF({agg_cell}>0,{ev_cell}/{agg_cell},\"N/A\")")
        ws.cell(row=row, column=5).number_format = '0.00"x"'
        ws.cell(row=row, column=6, value="Inclus")
        ws.cell(row=row, column=7, value=c.get("relevance_note") or "")
        row += 1

    # Ligne médiane (formule)
    if included:
        med_row = row
        first_m = 2
        last_m = row - 1
        ws.cell(row=med_row, column=5, value=f"=MEDIAN(E{first_m}:E{last_m})")
        ws.cell(row=med_row, column=5).number_format = '0.00"x"'
        ws.cell(row=med_row, column=5).font = Font(bold=True)
        ws.cell(row=med_row, column=6, value="MEDIANE")
        ws.cell(row=med_row, column=6).font = Font(bold=True)
        for col in range(1, 8):
            ws.cell(row=med_row, column=col).fill = PatternFill("solid", fgColor=CLR_SECTION)
        row = med_row + 2

    # Comps exclus
    if excluded:
        ws.cell(row=row, column=1, value="--- Exclus (hors médiane) ---")
        ws.cell(row=row, column=1).font = Font(italic=True, color="888888")
        row += 1
        for c in excluded:
            ws.cell(row=row, column=1, value=c["ticker"])
            ws.cell(row=row, column=2, value=c["name"])
            ws.cell(row=row, column=3, value=c["ev"])
            ws.cell(row=row, column=4, value=c["aggregate_value"])
            ws.cell(row=row, column=5, value=_fmt_m(c["multiple"]))
            ws.cell(row=row, column=6, value="Exclu")
            ws.cell(row=row, column=7, value=c.get("exclusion_reason") or "")
            for col in range(1, 8):
                ws.cell(row=row, column=col).fill = PatternFill("solid", fgColor=CLR_EXCL)
                ws.cell(row=row, column=col).font = Font(color="888888")
            row += 1


def _build_valo_sheet(
    wb: Workbook,
    run: ValuationRun,
    anchor: TargetAnchor,
    result: ValuationResult,
    target_aggregate_value: float,
    result_ev: float,
) -> None:
    ws = wb.create_sheet("Valo")
    ws.column_dimensions["A"].width = 38
    ws.column_dimensions["B"].width = 18
    ws.column_dimensions["C"].width = 30

    def row_label(r, label, value, formula=None, fmt=None, note=None):
        ws.cell(row=r, column=1, value=label)
        cell_b = ws.cell(row=r, column=2, value=formula if formula else value)
        if fmt:
            cell_b.number_format = fmt
        if note:
            ws.cell(row=r, column=3, value=note)

    r = 1
    _header(ws, r, 1, "Paramètre")
    _header(ws, r, 2, "Valeur")
    _header(ws, r, 3, "Note")
    r += 1

    # Section ancres
    ws.cell(row=r, column=1, value="── Ancres tour d'entrée ──").font = Font(bold=True)
    ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=CLR_SECTION)
    r += 1

    row_label(r, "Date du tour", str(anchor.entry_date))
    r += 1
    row_label(r, "Tour", anchor.entry_round or "")
    r += 1
    row_label(r, f"M_entry_aggregate (EV/{run.aggregate} au tour)", anchor.m_entry_aggregate,
              fmt='0.00"x"', note="Multiple ancré, agrégat cible")
    m_entry_agg_cell = f"B{r}"
    r += 1
    row_label(r, "M_market_entry (médiane marché au tour)", anchor.m_market_entry,
              fmt='0.00"x"', note="Médiane panel au tour d'entrée")
    m_market_entry_cell = f"B{r}"
    r += 1

    # Section marché actuel
    r += 1
    ws.cell(row=r, column=1, value="── Marché actuel ──").font = Font(bold=True)
    ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=CLR_SECTION)
    r += 1

    row_label(r, "Median_now (médiane panel actuel)", result.median_now,
              fmt='0.00"x"', note="=MEDIAN(Panel!E2:E...) — voir feuille Panel")
    median_now_cell = f"B{r}"
    r += 1
    row_label(r, "Drift ratio (median_now / m_market_entry)",
              formula=f"={median_now_cell}/{m_market_entry_cell}",
              value=None, fmt='0.000', note="Ratio sans unité — dérive relative du marché")
    drift_cell = f"B{r}"
    r += 1
    row_label(r, "Facteur de rétention", run.retention_factor or 1.0,
              fmt='0.000', note="1.0 si non récurrent ou neutre")
    retention_cell = f"B{r}"
    r += 1

    # Section résultat
    r += 1
    ws.cell(row=r, column=1, value="── Résultat ──").font = Font(bold=True)
    ws.cell(row=r, column=1).fill = PatternFill("solid", fgColor=CLR_SECTION)
    r += 1

    row_label(r, f"M_final (EV/{run.aggregate} retenu)",
              formula=f"={m_entry_agg_cell}*{drift_cell}*{retention_cell}",
              value=None, fmt='0.00"x"',
              note=f"= M_entry × drift × rétention  [MODE {run.mode}]")
    ws.cell(row=r, column=2).font = Font(bold=True)
    for col in range(1, 4):
        ws.cell(row=r, column=col).fill = PatternFill("solid", fgColor=CLR_RESULT)
    m_final_cell = f"B{r}"
    r += 1

    row_label(r, f"Agrégat cible ({run.aggregate})", target_aggregate_value,
              fmt='#,##0', note="Valeur issue du fichier compta AE")
    agg_cell = f"B{r}"
    r += 1

    row_label(r, "EV cible (100 %)",
              formula=f"={m_final_cell}*{agg_cell}",
              value=None, fmt='#,##0',
              note="EV = M_final × agrégat cible")
    ws.cell(row=r, column=2).font = Font(bold=True)
    for col in range(1, 4):
        ws.cell(row=r, column=col).fill = PatternFill("solid", fgColor=CLR_RESULT)
    r += 1

    r += 2
    ws.cell(row=r, column=1,
            value="Méthode : IPEV déc. 2022 — calibration par maintien du delta.").font = Font(italic=True, color="888888")
    r += 1
    ws.cell(row=r, column=1,
            value=f"Run #{run.id} | MODE {run.mode} | {run.run_date.strftime('%Y-%m-%d %H:%M')}").font = Font(italic=True, color="888888")
