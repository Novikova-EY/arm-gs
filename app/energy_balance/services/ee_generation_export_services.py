# -*- coding: utf-8 -*-
"""Экспорт страницы «Выработка ЭЭ» в Excel."""

from __future__ import annotations

from io import BytesIO
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from app.energy_balance.services.station_ee_generation_page_services import (
    format_generation_cell,
    get_station_ee_generation_page_data,
    is_verification_nonzero,
)
from openpyxl.utils import get_column_letter

from app.fuel.services.fuel_exports.hierarchy_excel_layout import (
    FILL_EST,
    FILL_RES_HEADER,
    FILL_STATION_SUMMARY,
    FILL_UES,
    write_merged_section_row,
)

FILL_EU = PatternFill(start_color="D1E7DD", end_color="D1E7DD", fill_type="solid")
FILL_TOTAL_RU = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
FILL_VERIFY = PatternFill(start_color="E2ECF7", end_color="E2ECF7", fill_type="solid")

STATIC_COLUMNS = [
    "КТО",
    "Электростанция",
    "Тип электростанции",
    "Признак эл.ст.",
    "Тип ТЭС",
    "Тип агрегата ТЭС",
    "Основное топливо",
    "Топливо (по СО ЕЭС)",
]


def _format_period_value(value, rounding_digits: int, *, verification: bool = False) -> str:
    if verification:
        return format_generation_cell(value, rounding_digits, show_zero=True)
    return format_generation_cell(value, rounding_digits)


def _write_data_row(
    ws,
    row_idx: int,
    values: list,
    *,
    bold: bool = False,
    fill=None,
    red_period_cols: set[int] | None = None,
) -> None:
    for col_idx, value in enumerate(values, start=1):
        cell = ws.cell(row=row_idx, column=col_idx, value=value)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        if col_idx == 2:
            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
        if bold:
            cell.font = Font(bold=True)
        if fill is not None:
            cell.fill = fill
        if red_period_cols and col_idx in red_period_cols:
            cell.font = Font(bold=bold, color="FF0000")


def _write_total_row(
    ws,
    row_idx: int,
    label: str,
    period_columns: list[tuple[int, str]],
    period_totals: dict,
    rounding_digits: int,
    *,
    fill=None,
) -> int:
    values = ["", label, "", "", "", "", "", ""]
    values.extend(
        _format_period_value(period_totals.get(period_key), rounding_digits)
        for period_key, _label in period_columns
    )
    _write_data_row(ws, row_idx, values, bold=True, fill=fill)
    return row_idx + 1


def _write_verification_row(
    ws,
    row_idx: int,
    label: str,
    period_columns: list[tuple[int, str]],
    period_totals: dict,
    rounding_digits: int,
) -> int:
    values = ["", label, "", "", "", "", "", ""]
    red_cols: set[int] = set()
    for idx, (period_key, _label) in enumerate(period_columns, start=8):
        val = period_totals.get(period_key)
        values.append(_format_period_value(val, rounding_digits, verification=True))
        if is_verification_nonzero(val):
            red_cols.add(idx)
    _write_data_row(ws, row_idx, values, bold=True, fill=FILL_VERIFY, red_period_cols=red_cols)
    return row_idx + 1


def _write_sign_group_rows(
    ws,
    row_idx: int,
    sign_group: dict[str, Any],
    period_columns: list[tuple[int, str]],
    rounding_digits: int,
) -> int:
    stations = sign_group.get("stations") or []

    for station_row in stations:
        station_periods = station_row.get("periods") or {}
        values = [
            station_row.get("kto_display") or "—",
            station_row.get("station_name") or "—",
            station_row.get("station_type_name") or "—",
            station_row.get("station_sign_display") or "—",
            station_row.get("tes_types") or "—",
            station_row.get("tes_machine_type") or "—",
            station_row.get("primary_fuel") or "—",
            station_row.get("fuel_so") or "—",
        ]
        values.extend(
            _format_period_value(station_periods.get(period_key), rounding_digits)
            for period_key, _label in period_columns
        )
        _write_data_row(ws, row_idx, values)
        row_idx += 1
    return row_idx


def export_ee_generation_to_excel(
    *,
    filters: dict,
    period_mode: str,
    selected_year: int | None,
    start_year: int | None,
    end_year: int | None,
    rounding_digits: int,
    show_totals: bool,
    export_verification: bool,
    per_page: int | str = "all",
    page: int = 1,
) -> BytesIO | None:
    """Формирует Excel-файл с тем же содержимым, что отображается на странице."""
    page_data = get_station_ee_generation_page_data(
        filters=filters,
        page=page,
        per_page=per_page,
        period_mode=period_mode,
        selected_year=selected_year,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        show_totals=show_totals,
    )

    hierarchy = page_data.get("hierarchy") or []
    period_columns = page_data.get("period_columns") or []
    generation_aggregates = page_data.get("generation_aggregates") or {}
    should_show_totals = page_data.get("should_show_totals") or {}
    res_show_rd_level_map = page_data.get("res_show_rd_level_map") or {}
    res_verification_by_res = page_data.get("res_verification_by_res") or {}

    columns = STATIC_COLUMNS + [label for _key, label in period_columns]
    num_cols = len(columns)

    wb = Workbook()
    ws = wb.active
    ws.title = "Выработка ЭЭ"

    header_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    header_font = Font(bold=True, size=11)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_num, title in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_num, value=title)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment

    if not hierarchy:
        ws.cell(row=2, column=1, value="Электростанции не найдены")
        stream = BytesIO()
        wb.save(stream)
        stream.seek(0)
        return stream

    row_idx = 2
    for est_block in hierarchy:
        row_idx = write_merged_section_row(
            ws, row_idx, num_cols, est_block.get("est_name") or "—", FILL_EST
        )
        for ues_block in est_block.get("ues_list") or []:
            row_idx = write_merged_section_row(
                ws,
                row_idx,
                num_cols,
                ues_block.get("ues_name") or "—",
                FILL_UES,
            )
            for res_block in ues_block.get("res_list") or []:
                res_id = res_block.get("res_id")
                row_idx = write_merged_section_row(
                    ws,
                    row_idx,
                    num_cols,
                    res_block.get("res_name") or "—",
                    FILL_RES_HEADER,
                )
                show_rd_level = res_show_rd_level_map.get(res_id, False)
                for rd_block in res_block.get("rd_list") or []:
                    rd_id = rd_block.get("rd_id")
                    rd_name = rd_block.get("rd_name") or "—"
                    show_rd_totals = (
                        show_rd_level
                        and should_show_totals.get("regional_districts", {}).get(rd_id)
                    )
                    if show_rd_level and rd_name.lower() != "не указано" and show_rd_totals:
                        row_idx = write_merged_section_row(
                            ws, row_idx, num_cols, rd_name, FILL_STATION_SUMMARY
                        )
                    for eu_block in rd_block.get("eu_list") or []:
                        eu_id = eu_block.get("eu_id")
                        eu_name = eu_block.get("eu_name") or "—"
                        skip_eu = (not eu_id) or eu_name.lower() in ("не указано", "без энергоузла")
                        if not skip_eu and eu_name.lower() != "не указано":
                            row_idx = write_merged_section_row(
                                ws, row_idx, num_cols, eu_name, FILL_EU
                            )
                        for sign_group in eu_block.get("sign_groups") or []:
                            row_idx = _write_sign_group_rows(
                                ws, row_idx, sign_group, period_columns, rounding_digits
                            )
                        if not skip_eu and should_show_totals.get("energy_units", {}).get(eu_id):
                            eu_total_name = eu_name
                            row_idx = _write_total_row(
                                ws,
                                row_idx,
                                f"{eu_total_name}, всего",
                                period_columns,
                                generation_aggregates.get("energy_units", {}).get(eu_id, {}),
                                rounding_digits,
                                fill=FILL_EU,
                            )
                    if show_rd_totals and rd_name.lower() != "не указано":
                        row_idx = _write_total_row(
                            ws,
                            row_idx,
                            f"{rd_name}, всего",
                            period_columns,
                            generation_aggregates.get("regional_districts", {}).get(rd_id, {}),
                            rounding_digits,
                            fill=FILL_STATION_SUMMARY,
                        )
                if should_show_totals.get("regional_energy_systems", {}).get(res_id):
                    res_name = res_block.get("res_name") or "—"
                    row_idx = _write_total_row(
                        ws,
                        row_idx,
                        f"{res_name}, всего",
                        period_columns,
                        generation_aggregates.get("regional_energy_systems", {}).get(res_id, {}),
                        rounding_digits,
                        fill=FILL_RES_HEADER,
                    )
                    if export_verification:
                        row_idx = _write_verification_row(
                            ws,
                            row_idx,
                            f"Проверка для {res_name}",
                            period_columns,
                            res_verification_by_res.get(res_id, {}),
                            rounding_digits,
                        )
            ues_id = ues_block.get("ues_id")
            if should_show_totals.get("union_energy_systems", {}).get(ues_id):
                ues_label = ues_block.get("ues_name") or "—"
                row_idx = _write_total_row(
                    ws,
                    row_idx,
                    f"{ues_label}, всего",
                    period_columns,
                    generation_aggregates.get("union_energy_systems", {}).get(ues_id, {}),
                    rounding_digits,
                    fill=FILL_UES,
                )
    if should_show_totals.get("total"):
        row_idx = _write_total_row(
            ws,
            row_idx,
            "Россия, всего",
            period_columns,
            generation_aggregates.get("total", {}),
            rounding_digits,
            fill=FILL_TOTAL_RU,
        )

    max_lengths = [len(c) for c in columns]
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=True):
        for i, val in enumerate(row):
            if val is not None and i < len(max_lengths):
                max_lengths[i] = max(max_lengths[i], len(str(val)))
    for col_idx, width in enumerate(max_lengths, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = max(10, min(48, width + 2))

    stream = BytesIO()
    wb.save(stream)
    stream.seek(0)
    return stream
