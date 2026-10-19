# -*- coding: utf-8 -*-
"""Юнит-тесты разбора Excel ГИС ТЭК."""

from __future__ import annotations

import io
from decimal import Decimal

from openpyxl import Workbook

from app.ecology.services.gis_tek_constants import REPORT_PG, REPORT_ZV, SHEET_NAMES
from app.ecology.services.gis_tek_import_services import (
    apply_column_aliases,
    find_sheet_name,
    normalize_header,
    read_gis_tek_sheet,
    safe_decimal,
    safe_int,
    station_type_str,
)


def test_normalize_header_station_number():
    assert normalize_header("№_станции") == "n_станции"
    assert normalize_header("Электростанция (ГИС ТЭК)") == "электростанция_гис_тэк"
    assert normalize_header("Электростанция (БАЗА)") == "электростанция_база"
    assert normalize_header("Год") == "год"


def test_find_sheet_name_pg_and_zv():
    names = ["СБОРКА ПГ", "СБОРКА ЗВ"]
    assert find_sheet_name(names, REPORT_PG) == "СБОРКА ПГ"
    assert find_sheet_name(names, REPORT_ZV) == "СБОРКА ЗВ"


def test_station_type_zero_is_empty():
    assert station_type_str(0) is None
    assert station_type_str("0") is None
    assert station_type_str("ТЭЦ") == "ТЭЦ"


def test_safe_int_and_decimal():
    assert safe_int(1706.0) == 1706
    assert safe_int("612") == 612
    assert safe_decimal("1 429,669") == safe_decimal("1429.669")


def test_safe_decimal_drops_float_noise_from_excel_cells():
    # Числовая ячейка Excel — double: 3.1300000000000003 — это 3.13 плюс шум double.
    assert safe_decimal(3.1300000000000003) == Decimal("3.13")
    assert safe_decimal(105.10000000000001) == Decimal("105.1")
    assert safe_decimal(9370.800000000001) == Decimal("9370.8")
    # Точные значения и текст со всеми знаками не трогаем.
    assert safe_decimal(1.522) == Decimal("1.522")
    assert safe_decimal(863585.0) == Decimal("863585")
    assert safe_decimal("1,02963561999219") == Decimal("1.02963561999219")
    # Для текста ограничение по знакам после запятой остаётся прежним (max_digits).
    assert safe_decimal("0.12345678901234567890") == Decimal("0.1234567890123457")


def test_read_gis_tek_sheet_pg_headers():
    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAMES[REPORT_PG]
    ws.append([None] * 5)
    ws.append([None, "СБОРКА ПГ ( ГИС ТЭК)"])
    ws.append(
        [
            "№_станции",
            "Электростанция (ГИС ТЭК)",
            "Электростанция (БАЗА)",
            "Тип станции",
            "Год",
            "Расход газа, т у.т.",
            "Выбросы СО2 от сжигания газа, т",
        ]
    )
    ws.append([1706, "Станция ГИС", "Станция БАЗА", "ТЭЦ", 2021, 10.5, 20])
    buf = io.BytesIO()
    wb.save(buf)
    df = read_gis_tek_sheet(buf.getvalue(), REPORT_PG)
    df = apply_column_aliases(df, REPORT_PG)
    assert "station_numb" in df.columns
    assert "gis_tek_station_name" in df.columns
    assert "year_number" in df.columns
    assert "gas_consumption_tce" in df.columns
    row = df.iloc[0]
    assert int(row["station_numb"]) == 1706
    assert int(row["year_number"]) == 2021


def test_zv_gaseous_and_liquid_header_is_not_imported():
    import pandas as pd

    df = pd.DataFrame(
        {
            "№_станции": [1],
            "Год": [2021],
            "Газообразные и жидкие вещества": [999],
            "диоксид серы": [10],
        }
    )
    df = apply_column_aliases(df, REPORT_ZV)
    assert "gaseous_and_liquid" not in df.columns
    assert "sulfur_dioxide" in df.columns
    assert normalize_header("Газообразные и жидкие вещества") == "газообразные_и_жидкие_вещества"

