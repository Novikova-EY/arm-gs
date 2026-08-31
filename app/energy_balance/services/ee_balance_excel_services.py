# -*- coding: utf-8 -*-
"""Выгрузка расчета балансов электрической энергии в Excel (все листы макета)."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook

from app.energy_balance.services.ee_balance_page_services import (
    EE_BALANCE_UNIT,
    build_ee_balance_tables,
    get_ee_balance_sheets,
    get_ee_balance_year_columns,
    get_ee_balance_year_features,
    resolve_ee_balance_rounding_digits,
)
from app.energy_balance.services.power_balance_excel_services import (
    _safe_sheet_title,
    _write_sheet,
)


def ee_balance_excel_table_title(sheet: dict[str, Any]) -> str:
    """Первая строка листа: «Таблица N - Баланс электрической энергии …, млн.кВт·ч»."""
    number = sheet.get("table_number") or 0
    title = str(
        sheet.get("title") or f"Баланс электрической энергии {sheet.get('sheet_name') or ''}"
    ).strip()
    unit = str(sheet.get("unit") or EE_BALANCE_UNIT).strip() or EE_BALANCE_UNIT
    if title.lower().endswith(f", {unit.lower()}"):
        named = title
    else:
        named = f"{title}, {unit}"
    if number:
        return f"Таблица {int(number)} - {named}"
    return named


def export_ee_balance_to_excel(
    *,
    start_year: Any = None,
    end_year: Any = None,
    rounding_digits: Any = None,
    include_type_breakdown: bool = False,
    show_empty_rows: bool = True,
    show_flow_rows: bool = True,
    tables: dict[str, dict[str, Any]] | None = None,
    sheets: list[dict[str, Any]] | None = None,
    years: list[int] | None = None,
    year_features: dict[int, str] | None = None,
    hydro_year: Any = None,
) -> BytesIO:
    """Файл со вкладкой на каждый лист баланса электрической энергии."""
    digits = resolve_ee_balance_rounding_digits(rounding_digits)
    if years is None:
        years = get_ee_balance_year_columns(start_year, end_year)
    if sheets is None:
        sheets = get_ee_balance_sheets()
    if tables is None:
        tables = build_ee_balance_tables(
            years, rounding_digits=digits, hydro_year=hydro_year
        )
    if year_features is None:
        year_features = get_ee_balance_year_features()

    wb = Workbook()
    used_titles: set[str] = set()
    first = True
    for sheet in sheets:
        if sheet.get("skip_table"):
            continue
        slug = sheet.get("slug")
        payload = (tables or {}).get(slug) or {}
        rows = payload.get("rows") or []
        if first:
            ws = wb.active
            first = False
        else:
            ws = wb.create_sheet()
        ws.title = _safe_sheet_title(str(sheet.get("sheet_name") or slug or "Лист"), used_titles)
        sheet_for_title = dict(payload.get("sheet") or sheet)
        sheet_for_title["title"] = ee_balance_excel_table_title(sheet_for_title).split(" - ", 1)[-1]
        # _write_sheet prepends «Таблица N - » again via power_balance_excel_table_title.
        # Pass a sheet whose title already includes unit; table_number keeps «Таблица N».
        _write_sheet(
            ws,
            sheet=sheet_for_title,
            rows=rows,
            years=years,
            year_features=year_features or {},
            rounding_digits=digits,
            include_type_breakdown=include_type_breakdown,
            show_empty_rows=show_empty_rows,
            show_flow_rows=show_flow_rows,
        )
        # Replace title cell with energy wording (helper writes power-balance title).
        ws.cell(row=1, column=1).value = ee_balance_excel_table_title(sheet_for_title)

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
