"""Выгрузка сводных таблиц потребления в Excel (в духе экранной таблицы: шапка, подписи к годам, заливки)."""
from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter


def build_demand_summary_excel_stream(
    *,
    summary_rows: list[dict[str, Any]],
    years: list[int],
    sheet_title: str,
    year_features: dict[int, Any] | dict[Any, Any] | None = None,
) -> BytesIO:
    yf = year_features or {}
    wb = Workbook()
    ws = wb.active
    safe_title = (sheet_title or "Сводка").replace("/", "-").replace("\\", "-")[:31]
    ws.title = safe_title or "Сводка"

    header_fill = PatternFill(start_color="D1E7DD", end_color="D1E7DD", fill_type="solid")
    header_font = Font(bold=True, size=11)
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    entity_fill = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")
    entity_font = Font(bold=True, size=11)
    entity_align = Alignment(horizontal="left", vertical="center", wrap_text=True)

    fill_group_param = PatternFill(start_color="EEF5FF", end_color="EEF5FF", fill_type="solid")
    fill_child_param = PatternFill(start_color="FBFCFF", end_color="FBFCFF", fill_type="solid")
    fill_cell_white = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")
    fill_cell_stripe = PatternFill(start_color="F8F9FA", end_color="F8F9FA", fill_type="solid")

    thin = Side(style="thin", color="CCCCCC")
    cell_border = Border(left=thin, right=thin, top=thin, bottom=thin)
    base_font = Font(size=11)
    center_wrap = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left_wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)

    def year_header_cell(y: int) -> str:
        cap = yf.get(y)
        s = str(cap).strip() if cap is not None else ""
        if s:
            return f"{y}\n{s}"
        return str(y)

    ncols = 2 + len(years)
    ws.append([None] * ncols)
    ws.row_dimensions[1].height = 36

    ws.cell(row=1, column=1, value="Энергосистема")
    ws.cell(row=1, column=2, value="Наименование параметров")
    for j, y in enumerate(years, start=3):
        ws.cell(row=1, column=j, value=year_header_cell(y))

    for c in range(1, ncols + 1):
        cell = ws.cell(row=1, column=c)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = cell_border

    ws.freeze_panes = "A2"

    def body_fills(entity_kind: str, stripe: bool) -> tuple[PatternFill, PatternFill]:
        if entity_kind in ("group", "group-root"):
            return fill_group_param, fill_group_param
        if entity_kind == "child":
            return fill_child_param, fill_child_param
        param_fill = fill_cell_stripe if stripe else fill_cell_white
        return param_fill, param_fill

    for bi, row in enumerate(summary_rows):
        excel_row = bi + 2
        entity_kind = str(row.get("entity_kind") or "default")
        stripe = bool(bi % 2)
        param_fill, year_fill = body_fills(entity_kind, stripe)

        entity_cell = ""
        if row.get("show_entity_cell"):
            depth = int(row.get("entity_depth") or 0)
            label = row.get("entity_label") or ""
            entity_cell = ("  " * depth) + str(label)

        ws.cell(row=excel_row, column=1, value=entity_cell or None)
        ws.cell(row=excel_row, column=2, value=row.get("parameter_label") or "")

        c1 = ws.cell(row=excel_row, column=1)
        c1.font = entity_font
        c1.fill = entity_fill
        c1.alignment = entity_align
        c1.border = cell_border

        c2 = ws.cell(row=excel_row, column=2)
        c2.font = base_font
        c2.fill = param_fill
        c2.alignment = left_wrap
        c2.border = cell_border

        yvals = row.get("year_values") or []
        for i, _y in enumerate(years):
            v = yvals[i] if i < len(yvals) else "—"
            disp = v if v is not None and v != "" else "—"
            c = ws.cell(row=excel_row, column=3 + i, value=disp)
            c.font = base_font
            c.fill = year_fill
            c.alignment = center_wrap
            c.border = cell_border

    for col in range(1, ncols + 1):
        letter = get_column_letter(col)
        if col == 1:
            ws.column_dimensions[letter].width = 44
        elif col == 2:
            ws.column_dimensions[letter].width = 52
        else:
            ws.column_dimensions[letter].width = 14

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)
    return bio
