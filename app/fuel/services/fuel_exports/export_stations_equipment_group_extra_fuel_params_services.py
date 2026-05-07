# -*- coding: utf-8 -*-
"""Экспорт дополнительных топливных параметров групп оборудования в Excel."""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter

from app.common.services.help_services import apply_nbsp_to_row, format_decimal_for_display
from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_services import (
    get_equipment_groups_with_extra_fuel_params_data,
    build_equipment_group_extra_fuel_params_hierarchy,
)
from app.fuel.services.fuel_exports.hierarchy_excel_layout import (
    EQUIPMENT_GROUP_ID_HEADER,
    FILL_EST,
    FILL_RES_HEADER,
    FILL_RES_SUMMARY,
    FILL_STATION_SUMMARY,
    FILL_UES,
    equipment_group_id_cell,
    next_data_row_index,
    style_data_row,
    write_merged_section_row,
)

# Как в stations_equipment_group_extra_fuel_params.html (extra_fuel_param_columns)
EXTRA_FUEL_STATIONS_COLUMNS = [
    ("numb1120", "Код электростанции", False),
    ("gaz_prir", "gaz_prir", True),
    ("gazpp", "gazpp", True),
    ("disel", "disel", True),
    ("maztop", "maztop", True),
    ("gtt", "gtt", True),
    ("nft_proch", "nft_proch", True),
    ("domen_g", "domen_g", True),
    ("koks_g", "koks_g", True),
    ("prochgaz", "prochgaz", True),
    ("tvproch", "tvproch", True),
    ("szh_gaz", "szh_gaz", True),
    ("inoe", "inoe", True),
    ("nazar", "nazar", True),
    ("ibor", "ibor", True),
    ("berez", "berez", True),
    ("per", "per", True),
    ("irbei", "irbei", True),
    ("kansk", "kansk", True),
    ("gusin", "gusin", True),
    ("tugn", "tugn", True),
    ("okino", "okino", True),
    ("azey", "azey", True),
    ("mug", "mug", True),
    ("cher", "cher", True),
    ("jer", "jer", True),
    ("karab", "karab", True),
    ("vork", "vork", True),
    ("intin", "intin", True),
    ("sver", "sver", True),
    ("chel", "chel", True),
    ("kizel", "kizel", True),
    ("har", "har", True),
    ("urt", "urt", True),
    ("tataur", "tataur", True),
    ("tarbag", "tarbag", True),
    ("zab_kam", "zab_kam", True),
    ("rai", "rai", True),
    ("erk", "erk", True),
    ("ogodj", "ogodj", True),
    ("svo", "svo", True),
    ("bikin", "bikin", True),
    ("razdol", "razdol", True),
    ("hankai", "hankai", True),
    ("neru", "neru", True),
    ("zyryan", "zyryan", True),
    ("pyak", "pyak", True),
    ("kuzngd", "kuzngd", True),
    ("kuznt", "kuznt", True),
    ("kuznss", "kuznss", True),
    ("kuznun", "kuznun", True),
    ("bering", "bering", True),
    ("anad", "anad", True),
    ("ekib", "ekib", True),
    ("maikub", "maikub", True),
    ("karag", "karag", True),
    ("karajyra", "karajyra", True),
    ("teniz", "teniz", True),
    ("numb1", "numb1", False),
]


def _format_cell_value(param, attr, is_numeric, rounding_digits):
    if param is None:
        return "—"
    val = getattr(param, attr, None)
    if val is None:
        return "—"
    if is_numeric:
        return format_decimal_for_display(val, digits=rounding_digits)
    return str(val) if val is not None else "—"


def _format_summary_value(summary, attr, is_numeric, rounding_digits):
    if summary is None or attr not in summary:
        return "—"
    val = summary.get(attr)
    if val is None:
        return "—"
    if is_numeric:
        return format_decimal_for_display(val, digits=rounding_digits)
    return str(val)


def export_stations_equipment_group_extra_fuel_params_to_excel(
    filters,
    start_year,
    end_year,
    *,
    per_page="all",
    page=1,
    show_all=True,
    rounding_digits=1,
):
    """
    Экспорт доп. топливных параметров с теми же фильтрами, что на странице.
    Всегда полный набор строк (per_page=all); иерархия и агрегации по полным данным.
    """
    extra_data = get_equipment_groups_with_extra_fuel_params_data(
        filters=filters,
        per_page=per_page,
        page=page,
        start_year=start_year,
        end_year=end_year,
        show_all=show_all,
    )
    rows = extra_data.get("rows") or []
    if not rows:
        return None

    hierarchy = build_equipment_group_extra_fuel_params_hierarchy(rows)
    if not hierarchy:
        return None

    wb = Workbook()
    ws = wb.active
    ws.title = "Доп. топливные параметры"

    columns = [EQUIPMENT_GROUP_ID_HEADER, "Группа оборудования"] + [
        label for _, label, _ in EXTRA_FUEL_STATIONS_COLUMNS
    ]
    num_cols = len(columns)

    header_fill = PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid")
    header_font = Font(bold=True, size=10)
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_num, column_title in enumerate(columns, 1):
        cell = ws.cell(row=1, column=col_num)
        cell.value = apply_nbsp_to_row([column_title])[0]
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment

    max_lengths = [len(str(c)) for c in columns]

    def _bump_lengths(row_vals):
        for i, v in enumerate(row_vals):
            if v is not None and len(str(v)) > max_lengths[i]:
                max_lengths[i] = len(str(v))

    for est_block in hierarchy:
        title = est_block.get("est_name") or "—"
        _bump_lengths([title] + [""] * (num_cols - 1))
        write_merged_section_row(
            ws, next_data_row_index(ws), num_cols, title, FILL_EST
        )

        for ues_block in est_block.get("ues_list") or []:
            ues_title = ues_block.get("ues_name") or "—"
            _bump_lengths([ues_title] + [""] * (num_cols - 1))
            write_merged_section_row(
                ws, next_data_row_index(ws), num_cols, ues_title, FILL_UES
            )

            for res_block in ues_block.get("res_list") or []:
                res_title = res_block.get("res_name") or "—"
                _bump_lengths([res_title] + [""] * (num_cols - 1))
                write_merged_section_row(
                    ws,
                    next_data_row_index(ws),
                    num_cols,
                    res_title,
                    FILL_RES_HEADER,
                )

                for station_block in res_block.get("station_blocks") or []:
                    for group_block in station_block.get("group_blocks") or []:
                        group_entity = group_block.get("equipment_group")
                        group_name = (
                            (group_entity.name if group_entity and group_entity.name else None)
                            or (
                                group_entity.name_ext
                                if group_entity and group_entity.name_ext
                                else None
                            )
                            or "—"
                        )
                        for _eg, param in group_block.get("rows") or []:
                            row_data = [
                                equipment_group_id_cell(group_entity),
                                group_name,
                            ]
                            for attr, _label, is_numeric in EXTRA_FUEL_STATIONS_COLUMNS:
                                row_data.append(
                                    _format_cell_value(param, attr, is_numeric, rounding_digits)
                                )
                            _bump_lengths(row_data)
                            ws.append(apply_nbsp_to_row(row_data))

                    gb_count = len(station_block.get("group_blocks") or [])
                    if gb_count > 1 and not station_block.get("is_virtual"):
                        st_name = station_block.get("station_name") or "—"
                        label = f"{st_name}, всего"
                        summary = station_block.get("station_summary") or {}
                        row_data = ["—", label]
                        for attr, _label, is_numeric in EXTRA_FUEL_STATIONS_COLUMNS:
                            row_data.append(
                                _format_summary_value(
                                    summary, attr, is_numeric, rounding_digits
                                )
                            )
                        _bump_lengths(row_data)
                        ws.append(apply_nbsp_to_row(row_data))
                        style_data_row(
                            ws, ws.max_row, bold=True, fill=FILL_STATION_SUMMARY
                        )

                if res_block.get("group_blocks"):
                    res_nm = res_block.get("res_name") or "—"
                    label = f"{res_nm}, всего"
                    summary = res_block.get("res_summary") or {}
                    row_data = ["—", label]
                    for attr, _label, is_numeric in EXTRA_FUEL_STATIONS_COLUMNS:
                        row_data.append(
                            _format_summary_value(summary, attr, is_numeric, rounding_digits)
                        )
                    _bump_lengths(row_data)
                    ws.append(apply_nbsp_to_row(row_data))
                    style_data_row(ws, ws.max_row, bold=True, fill=FILL_RES_SUMMARY)

    for col_idx, max_length in enumerate(max_lengths, start=1):
        adjusted_width = min(max_length + 2, 22)
        ws.column_dimensions[get_column_letter(col_idx)].width = adjusted_width

    output = BytesIO()
    wb.save(output)
    output.seek(0)
    return output
