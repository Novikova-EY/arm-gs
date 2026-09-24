# -*- coding: utf-8 -*-
"""Экспорт отчетных данных ГИС ТЭК в Excel."""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from werkzeug.datastructures import MultiDict
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from app.ecology.services.gis_tek_constants import PAGE_TITLES, SHEET_NAMES
from app.ecology.services.gis_tek_page_services import (
    IDENTITY_COLUMNS,
    build_gis_tek_page_context,
)


def _style_header_cell(cell, fill, font, alignment):
    cell.fill = fill
    cell.font = font
    cell.alignment = alignment


def build_gis_tek_excel_stream(kind: str, args) -> BytesIO:
    export_args = MultiDict(args)
    export_args["per_page"] = "all"
    context = build_gis_tek_page_context(kind, export_args)
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAMES[kind][:31]

    header_fill = PatternFill("solid", fgColor="C6EFCE")
    header_font = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.cell(1, 2, PAGE_TITLES[kind])

    identity_headers = [label for _key, label, _num in IDENTITY_COLUMNS]
    groups = list(context.get("value_column_groups") or [])
    value_columns = list(context.get("value_columns") or [])

    if groups:
        banner = str(context.get("value_column_banner") or "").strip()
        header_top = 3
        group_row = header_top + 1 if banner else header_top
        header_bottom = group_row + 1
        for col, title in enumerate(identity_headers, start=1):
            cell = ws.cell(header_top, col, title)
            _style_header_cell(cell, header_fill, header_font, center)
            ws.merge_cells(
                start_row=header_top,
                start_column=col,
                end_row=header_bottom,
                end_column=col,
            )
        value_start = len(identity_headers) + 1
        if banner:
            cell = ws.cell(header_top, value_start, banner)
            _style_header_cell(cell, header_fill, header_font, center)
            ws.merge_cells(
                start_row=header_top,
                start_column=value_start,
                end_row=header_top,
                end_column=value_start + len(value_columns) - 1,
            )
        col = value_start
        for group_label, group_cols in groups:
            n = len(group_cols)
            cell = ws.cell(group_row, col, group_label)
            _style_header_cell(cell, header_fill, header_font, center)
            if n == 1 and not group_cols[0][1]:
                ws.merge_cells(
                    start_row=group_row,
                    start_column=col,
                    end_row=header_bottom,
                    end_column=col,
                )
                col += 1
                continue
            if n > 1:
                ws.merge_cells(
                    start_row=group_row,
                    start_column=col,
                    end_row=group_row,
                    end_column=col + n - 1,
                )
            for offset, (_attr, label) in enumerate(group_cols):
                sub = ws.cell(header_bottom, col + offset, label)
                _style_header_cell(sub, header_fill, header_font, center)
            col += n
        data_row = header_bottom + 1
        total_cols = col - 1
    else:
        headers = identity_headers + [label for _attr, label in value_columns]
        for col, title in enumerate(headers, start=1):
            cell = ws.cell(3, col, title)
            _style_header_cell(cell, header_fill, header_font, center)
        data_row = 4
        total_cols = len(headers)

    row_idx = data_row
    show_empty_rows = bool(context.get("show_empty_rows"))
    identity_count = len(IDENTITY_COLUMNS)

    def _write_summary(summary: dict | None) -> None:
        nonlocal row_idx
        if not summary:
            return
        if not show_empty_rows and summary.get("is_empty"):
            return
        ws.cell(row_idx, 1, summary.get("label"))
        metrics = summary.get("metrics") or {}
        for offset, (attr, _label) in enumerate(value_columns):
            ws.cell(row_idx, identity_count + 1 + offset, metrics.get(attr))
        row_idx += 1

    for ues in context["hierarchy"]:
        for res in ues["res_list"]:
            for row in res["rows"]:
                if not show_empty_rows and row.get("is_empty"):
                    continue
                values = []
                for key, _label, _num in IDENTITY_COLUMNS:
                    val = row.get(key)
                    if key == "station_type" and val == "—":
                        val = None
                    values.append(val)
                values += [row["metrics"].get(attr) for attr, _label in value_columns]
                for col, value in enumerate(values, start=1):
                    ws.cell(row_idx, col, value)
                row_idx += 1
            _write_summary(res.get("summary"))
        _write_summary(ues.get("summary"))

    for col in range(1, total_cols + 1):
        ws.column_dimensions[get_column_letter(col)].width = 18

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
