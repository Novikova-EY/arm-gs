# -*- coding: utf-8 -*-
"""Excel «ТЭП основных площадок» ГЭС: как на экране — режим текущего года (_tep_machines_table_main) или исходные данные (_tep_machines_table_main_v2)."""
from __future__ import annotations

from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Как в шаблоне: №, наименование, …, стоимость (3 столбца без «года»), экономика (2), примечание
TEP_MAIN_COLS = 33
# Режим «исходные данные» (_tep_machines_table_main_v2.html): +3 столбца «год» у капзатрат и +2 у удельных
TEP_MAIN_SOURCE_COLS = 38


def _thin_border():
    return Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )


def _style_cell(cell, *, font=None, fill=None, align=None, border=None):
    if font is not None:
        cell.font = font
    if fill is not None:
        cell.fill = fill
    if align is not None:
        cell.alignment = align
    if border is not None:
        cell.border = border


def _apply_border_to_range(ws, min_row, max_row, min_col, max_col, border):
    for r in range(min_row, max_row + 1):
        for c in range(min_col, max_col + 1):
            ws.cell(row=r, column=c).border = border


def write_tep_main_screen_sheet(
    ws, tep_groups: list[dict], *, source_prices: bool = False
) -> None:
    """ТЭП основных площадок: как на экране — «текущий год» или «исходные данные» (годы у капзатрат)."""
    if source_prices:
        _write_ges_tep_main_sheet_source_prices(ws, tep_groups)
    else:
        _write_ges_tep_main_sheet_current_year_prices(ws, tep_groups)


def _write_ges_tep_main_sheet_current_year_prices(ws, tep_groups: list[dict]) -> None:
    """
    Лист как на экране «в ценах текущего года»: без столбцов «год» у капзатрат.
    Суммы капзатрат — из tep_full_current_year (пересчёт), если переданы в tep_groups.
    Шапка — 4 строки: 2-я — «Установленная мощность» + агрегаты…срок (на 3 строки) + «Выработка…»;
    3–4-я — детализация мощности (всего…2 очередь на две строки), выработка, очередь, стоимость.
    """
    thin = _thin_border()
    header_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    group_fill = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")
    header_font = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)

    # --- Шапка: 4 строки (вторая — «Выработка электроэнергии…» под «Основными параметрами»), колонки 1–33 ---
    ws.merge_cells(start_row=1, start_column=1, end_row=4, end_column=1)
    c = ws.cell(row=1, column=1, value="№ п/п")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 4, 1, 1, thin)

    ws.merge_cells(start_row=1, start_column=2, end_row=4, end_column=2)
    c = ws.cell(row=1, column=2, value="Наименование площадки")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 4, 2, 2, thin)

    ws.merge_cells(start_row=1, start_column=3, end_row=1, end_column=15)
    c = ws.cell(row=1, column=3, value="Основные параметры")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 1, 3, 15, thin)

    ws.merge_cells(start_row=1, start_column=16, end_row=1, end_column=27)
    c = ws.cell(
        row=1,
        column=16,
        value="Очередность строительства\n(прирост вводимой мощности), МВт",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 1, 16, 27, thin)

    ws.merge_cells(start_row=1, start_column=28, end_row=1, end_column=30)
    c = ws.cell(row=1, column=28, value="Капитальные затраты, млн руб.")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 1, 28, 30, thin)

    ws.merge_cells(start_row=1, start_column=31, end_row=4, end_column=31)
    c = ws.cell(
        row=1,
        column=31,
        value="Удельные условно-постоянные эксплуатационные затраты (без амортизационных отчислений), млн руб./МВт",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 4, 31, 31, thin)

    ws.merge_cells(start_row=1, start_column=32, end_row=4, end_column=32)
    c = ws.cell(
        row=1,
        column=32,
        value="Удельные капиталовложения в строительство (без НДС, за вычетом затрат на сооружение водохранилища для ГЭС), млн руб./МВт",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 4, 32, 32, thin)

    ws.merge_cells(start_row=1, start_column=33, end_row=4, end_column=33)
    c = ws.cell(row=1, column=33, value="Примечание")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 4, 33, 33, thin)

    # Строка 2: «Установленная мощность» (3–6); столбцы 7–10 — три строки шапки; выработка (11–15)
    ws.merge_cells(start_row=2, start_column=3, end_row=2, end_column=6)
    c = ws.cell(row=2, column=3, value="Установленная мощность, МВт")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 2, 2, 3, 6, thin)

    for col, text in (
        (7, "Количество агрегатов, шт."),
        (8, "Единичная мощность агрегата, МВт"),
        (9, "Тип гидротурбины"),
        (10, "Срок строительства ГЭС, лет"),
    ):
        ws.merge_cells(start_row=2, start_column=col, end_row=4, end_column=col)
        c = ws.cell(row=2, column=col, value=text)
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 2, 4, col, col, thin)

    ws.merge_cells(start_row=2, start_column=11, end_row=2, end_column=15)
    c = ws.cell(row=2, column=11, value="Выработка электроэнергии,\nмлн кВт·ч")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 2, 2, 11, 15, thin)

    for y in range(1, 13):
        col = 15 + y
        ws.merge_cells(start_row=2, start_column=col, end_row=4, end_column=col)
        c = ws.cell(row=2, column=col, value=f"{y} год")
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 2, 4, col, col, thin)

    ws.merge_cells(start_row=2, start_column=28, end_row=4, end_column=28)
    c = ws.cell(row=2, column=28, value="Капитальные затраты (без ПИР)")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 2, 4, 28, 28, thin)

    ws.merge_cells(start_row=2, start_column=29, end_row=2, end_column=30)
    c = ws.cell(row=2, column=29, value="в том числе")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 2, 2, 29, 30, thin)

    ws.merge_cells(start_row=3, start_column=29, end_row=4, end_column=29)
    c = ws.cell(
        row=3,
        column=29,
        value="здания, сооружения,\nоборудование и водохранилище ГЭС",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 4, 29, 29, thin)

    ws.merge_cells(start_row=3, start_column=30, end_row=4, end_column=30)
    c = ws.cell(row=3, column=30, value="СВМ")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 4, 30, 30, thin)

    # Блок «Выработка» (K–O), строки 3–4
    ws.merge_cells(start_row=3, start_column=11, end_row=4, end_column=11)
    c = ws.cell(
        row=3,
        column=11,
        value="Средне-\nмноголетняя выработка электро-\nэнергии",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 4, 11, 11, thin)

    ws.merge_cells(start_row=3, start_column=12, end_row=3, end_column=13)
    c = ws.cell(
        row=3,
        column=12,
        value="Средневодные условия\n(50% обеспеченности по каскаду)",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 3, 12, 13, thin)

    ws.merge_cells(start_row=3, start_column=14, end_row=3, end_column=15)
    c = ws.cell(
        row=3,
        column=14,
        value="Маловодные условия (95% обеспеченности по каскаду)",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 3, 14, 15, thin)

    for col, text in (
        (3, "всего"),
        (4, "в т.ч. пусковой комплекс"),
        (5, "1 очередь"),
        (6, "2 очередь"),
    ):
        ws.merge_cells(start_row=3, start_column=col, end_row=4, end_column=col)
        c = ws.cell(row=3, column=col, value=text)
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 3, 4, col, col, thin)

    for col, text in (
        (12, "Выработка электро-\nэнергии"),
        (13, "Водо-\nхозяй-\nственный год"),
        (14, "Выработка электро-\nэнергии"),
        (15, "Водо-\nхозяй-\nственный год"),
    ):
        c = ws.cell(row=4, column=col, value=text)
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 4, 4, col, col, thin)

    row_num = 5

    def _write_tf_row(rn: int, tf: dict) -> None:
        vals = [
            tf["installed_capacity_mw"],
            tf["startup_complex_capacity_mw"],
            tf["stage_1_capacity_mw"],
            tf["stage_2_capacity_mw"],
            tf["units_count"],
            tf["unit_capacity_mw"],
            tf["hydro_turbine_type"],
            tf["construction_period_years"],
            tf["generation_average_multiyear_billion_kwh"],
            tf["generation_medium_water_50pct_billion_kwh"],
            tf["generation_medium_water_management_year"],
            tf["generation_low_water_95pct_billion_kwh"],
            tf["generation_low_water_management_year"],
        ]
        for i in range(1, 13):
            vals.append(tf[f"construction_increment_year_{i:02d}_mw"])
        vals.extend(
            [
                tf["capital_cost_wo_pir_total_million_rub"],
                tf["capital_cost_wo_pir_ges_with_reservoir_million_rub"],
                tf["capital_cost_wo_pir_svm_million_rub"],
                tf["specific_semifixed_operating_costs_thous_rub_per_kw"],
                tf["specific_capital_investment_thous_rub_per_kw"],
                tf["note"],
            ]
        )
        note_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        for col, val in enumerate(vals, start=3):
            cell = ws.cell(row=rn, column=col, value=val)
            cell.border = thin
            cell.alignment = note_align if col == 33 else center

    for g in tep_groups:
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=TEP_MAIN_COLS)
        c = ws.cell(row=row_num, column=1, value=g.get("type_label", ""))
        c.font = Font(bold=True, size=14)
        c.alignment = center
        c.fill = group_fill
        c.border = thin
        _apply_border_to_range(ws, row_num, row_num, 1, TEP_MAIN_COLS, thin)
        row_num += 1

        tep_rows = g.get("tep_rows") or []
        if not tep_rows:
            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=TEP_MAIN_COLS)
            c = ws.cell(row=row_num, column=1, value="Нет данных")
            c.alignment = center
            c.border = thin
            _apply_border_to_range(ws, row_num, row_num, 1, TEP_MAIN_COLS, thin)
            row_num += 1
            continue

        for tep_row in tep_rows:
            tf = dict(tep_row["tep_full"])
            ty = tep_row.get("tep_full_current_year")
            if ty:
                tf["capital_cost_wo_pir_total_million_rub"] = ty[
                    "capital_cost_wo_pir_total_million_rub"
                ]
                tf["capital_cost_wo_pir_ges_with_reservoir_million_rub"] = ty[
                    "capital_cost_wo_pir_ges_with_reservoir_million_rub"
                ]
                tf["capital_cost_wo_pir_svm_million_rub"] = ty["capital_cost_wo_pir_svm_million_rub"]

            ws.cell(row=row_num, column=1, value=tep_row["idx"])
            ws.cell(row=row_num, column=1).border = thin
            ws.cell(row=row_num, column=1).alignment = center

            if tep_row["show_station_cell"]:
                rs = int(tep_row["station_rowspan"] or 1)
                ws.cell(row=row_num, column=2, value=tep_row["site_name"])
                if rs > 1:
                    ws.merge_cells(
                        start_row=row_num,
                        start_column=2,
                        end_row=row_num + rs - 1,
                        end_column=2,
                    )
                c2 = ws.cell(row=row_num, column=2)
                c2.border = thin
                c2.alignment = left
            _write_tf_row(row_num, tf)
            row_num += 1

    if not tep_groups:
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=TEP_MAIN_COLS)
        c = ws.cell(row=row_num, column=1, value="Нет данных")
        c.alignment = center
        c.border = thin
        _apply_border_to_range(ws, row_num, row_num, 1, TEP_MAIN_COLS, thin)

    widths = [6, 28] + [12] * 8 + [12] * 5 + [8] * 12 + [11] * 3 + [14, 14] + [32]
    for i, w in enumerate(widths, start=1):
        if i <= TEP_MAIN_COLS:
            ws.column_dimensions[get_column_letter(i)].width = min(w, 45)


def _write_ges_tep_main_sheet_source_prices(ws, tep_groups: list[dict]) -> None:
    """Как _tep_machines_table_main_v2.html: исходные капзатраты, столбцы «год» в блоке стоимости."""
    thin = _thin_border()
    header_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
    group_fill = PatternFill(start_color="E2E3E5", end_color="E2E3E5", fill_type="solid")
    header_font = Font(bold=True)
    center = Alignment(horizontal="center", vertical="center", wrap_text=True)
    left = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ncols = TEP_MAIN_SOURCE_COLS

    ws.merge_cells(start_row=1, start_column=1, end_row=4, end_column=1)
    c = ws.cell(row=1, column=1, value="№ п/п")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 4, 1, 1, thin)

    ws.merge_cells(start_row=1, start_column=2, end_row=4, end_column=2)
    c = ws.cell(row=1, column=2, value="Наименование площадки")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 4, 2, 2, thin)

    ws.merge_cells(start_row=1, start_column=3, end_row=1, end_column=15)
    c = ws.cell(row=1, column=3, value="Основные параметры")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 1, 3, 15, thin)

    ws.merge_cells(start_row=1, start_column=16, end_row=1, end_column=27)
    c = ws.cell(
        row=1,
        column=16,
        value="Очередность строительства\n(прирост вводимой мощности), МВт",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 1, 16, 27, thin)

    ws.merge_cells(start_row=1, start_column=28, end_row=1, end_column=33)
    c = ws.cell(row=1, column=28, value="Капитальные затраты, млн руб.")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 1, 28, 33, thin)

    ws.merge_cells(start_row=1, start_column=34, end_row=3, end_column=35)
    c = ws.cell(
        row=1,
        column=34,
        value="Удельные условно-постоянные эксплуатационные затраты (без амортизационных отчислений),",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 3, 34, 35, thin)

    ws.merge_cells(start_row=1, start_column=36, end_row=3, end_column=37)
    c = ws.cell(
        row=1,
        column=36,
        value="Удельные капиталовложения в строительство (без НДС, за вычетом затрат на сооружение водохранилища для ГЭС),",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 3, 36, 37, thin)

    for col, text in (
        (34, "млн руб./МВт"),
        (35, "год"),
        (36, "млн руб./МВт"),
        (37, "год"),
    ):
        c = ws.cell(row=4, column=col, value=text)
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 4, 4, col, col, thin)

    ws.merge_cells(start_row=1, start_column=38, end_row=4, end_column=38)
    c = ws.cell(row=1, column=38, value="Примечание")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 1, 4, 38, 38, thin)

    ws.merge_cells(start_row=2, start_column=3, end_row=2, end_column=6)
    c = ws.cell(row=2, column=3, value="Установленная мощность, МВт")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 2, 2, 3, 6, thin)

    for col, text in (
        (7, "Количество агрегатов, шт."),
        (8, "Единичная мощность агрегата, МВт"),
        (9, "Тип гидротурбины"),
        (10, "Срок строительства ГЭС, лет"),
    ):
        ws.merge_cells(start_row=2, start_column=col, end_row=4, end_column=col)
        c = ws.cell(row=2, column=col, value=text)
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 2, 4, col, col, thin)

    ws.merge_cells(start_row=2, start_column=11, end_row=2, end_column=15)
    c = ws.cell(row=2, column=11, value="Выработка электроэнергии,\nмлн кВт·ч")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 2, 2, 11, 15, thin)

    for y in range(1, 13):
        col = 15 + y
        ws.merge_cells(start_row=2, start_column=col, end_row=4, end_column=col)
        c = ws.cell(row=2, column=col, value=f"{y} год")
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 2, 4, col, col, thin)

    ws.merge_cells(start_row=2, start_column=28, end_row=3, end_column=29)
    c = ws.cell(row=2, column=28, value="Капитальные затраты (без ПИР)")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 2, 3, 28, 29, thin)

    ws.merge_cells(start_row=2, start_column=30, end_row=2, end_column=33)
    c = ws.cell(row=2, column=30, value="в том числе")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 2, 2, 30, 33, thin)

    ws.merge_cells(start_row=3, start_column=30, end_row=3, end_column=31)
    c = ws.cell(
        row=3,
        column=30,
        value="здания, сооружения,\nоборудование и водохранилище ГЭС",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 3, 30, 31, thin)

    ws.merge_cells(start_row=3, start_column=32, end_row=3, end_column=33)
    c = ws.cell(row=3, column=32, value="СВМ")
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 3, 32, 33, thin)

    ws.merge_cells(start_row=3, start_column=11, end_row=4, end_column=11)
    c = ws.cell(
        row=3,
        column=11,
        value="Средне-\nмноголетняя выработка электро-\nэнергии",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 4, 11, 11, thin)

    ws.merge_cells(start_row=3, start_column=12, end_row=3, end_column=13)
    c = ws.cell(
        row=3,
        column=12,
        value="Средневодные условия\n(50% обеспеченности по каскаду)",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 3, 12, 13, thin)

    ws.merge_cells(start_row=3, start_column=14, end_row=3, end_column=15)
    c = ws.cell(
        row=3,
        column=14,
        value="Маловодные условия (95% обеспеченности по каскаду)",
    )
    _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
    _apply_border_to_range(ws, 3, 3, 14, 15, thin)

    for col, text in (
        (3, "всего"),
        (4, "в т.ч. пусковой комплекс"),
        (5, "1 очередь"),
        (6, "2 очередь"),
    ):
        ws.merge_cells(start_row=3, start_column=col, end_row=4, end_column=col)
        c = ws.cell(row=3, column=col, value=text)
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 3, 4, col, col, thin)

    for col, text in (
        (12, "Выработка электро-\nэнергии"),
        (13, "Водо-\nхозяй-\nственный год"),
        (14, "Выработка электро-\nэнергии"),
        (15, "Водо-\nхозяй-\nственный год"),
    ):
        c = ws.cell(row=4, column=col, value=text)
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 4, 4, col, col, thin)

    for col, text in (
        (28, "млн\nруб."),
        (29, "год"),
        (30, "млн\nруб."),
        (31, "год"),
        (32, "млн\nруб."),
        (33, "год"),
    ):
        c = ws.cell(row=4, column=col, value=text)
        _style_cell(c, font=header_font, fill=header_fill, align=center, border=thin)
        _apply_border_to_range(ws, 4, 4, col, col, thin)

    row_num = 5

    def _write_tf_row(rn: int, tf: dict) -> None:
        vals = [
            tf["installed_capacity_mw"],
            tf["startup_complex_capacity_mw"],
            tf["stage_1_capacity_mw"],
            tf["stage_2_capacity_mw"],
            tf["units_count"],
            tf["unit_capacity_mw"],
            tf["hydro_turbine_type"],
            tf["construction_period_years"],
            tf["generation_average_multiyear_billion_kwh"],
            tf["generation_medium_water_50pct_billion_kwh"],
            tf["generation_medium_water_management_year"],
            tf["generation_low_water_95pct_billion_kwh"],
            tf["generation_low_water_management_year"],
        ]
        for i in range(1, 13):
            vals.append(tf[f"construction_increment_year_{i:02d}_mw"])
        vals.extend(
            [
                tf["capital_cost_wo_pir_total_million_rub"],
                tf["year_capital_cost_wo_pir_total"],
                tf["capital_cost_wo_pir_ges_with_reservoir_million_rub"],
                tf["year_capital_cost_wo_pir_ges_with_reservoir"],
                tf["capital_cost_wo_pir_svm_million_rub"],
                tf["year_capital_cost_wo_pir_svm"],
                tf["specific_semifixed_operating_costs_thous_rub_per_kw"],
                tf["year_specific_semifixed_operating_costs"],
                tf["specific_capital_investment_thous_rub_per_kw"],
                tf["year_specific_capital_investment"],
                tf["note"],
            ]
        )
        note_align = Alignment(horizontal="left", vertical="center", wrap_text=True)
        for col, val in enumerate(vals, start=3):
            cell = ws.cell(row=rn, column=col, value=val)
            cell.border = thin
            cell.alignment = note_align if col == 38 else center

    for g in tep_groups:
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=ncols)
        c = ws.cell(row=row_num, column=1, value=g.get("type_label", ""))
        c.font = Font(bold=True, size=14)
        c.alignment = center
        c.fill = group_fill
        c.border = thin
        _apply_border_to_range(ws, row_num, row_num, 1, ncols, thin)
        row_num += 1

        tep_rows = g.get("tep_rows") or []
        if not tep_rows:
            ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=ncols)
            c = ws.cell(row=row_num, column=1, value="Нет данных")
            c.alignment = center
            c.border = thin
            _apply_border_to_range(ws, row_num, row_num, 1, ncols, thin)
            row_num += 1
            continue

        for tep_row in tep_rows:
            tf = dict(tep_row["tep_full"])
            ws.cell(row=row_num, column=1, value=tep_row["idx"])
            ws.cell(row=row_num, column=1).border = thin
            ws.cell(row=row_num, column=1).alignment = center

            if tep_row["show_station_cell"]:
                rs = int(tep_row["station_rowspan"] or 1)
                ws.cell(row=row_num, column=2, value=tep_row["site_name"])
                if rs > 1:
                    ws.merge_cells(
                        start_row=row_num,
                        start_column=2,
                        end_row=row_num + rs - 1,
                        end_column=2,
                    )
                c2 = ws.cell(row=row_num, column=2)
                c2.border = thin
                c2.alignment = left
            _write_tf_row(row_num, tf)
            row_num += 1

    if not tep_groups:
        ws.merge_cells(start_row=row_num, start_column=1, end_row=row_num, end_column=ncols)
        c = ws.cell(row=row_num, column=1, value="Нет данных")
        c.alignment = center
        c.border = thin
        _apply_border_to_range(ws, row_num, row_num, 1, ncols, thin)

    widths = [6, 28] + [12] * 8 + [12] * 5 + [8] * 12 + [11, 10, 11, 10, 11, 10] + [14, 8, 14, 8] + [32]
    for i, w in enumerate(widths, start=1):
        if i <= ncols:
            ws.column_dimensions[get_column_letter(i)].width = min(w, 45)
