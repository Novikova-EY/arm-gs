# -*- coding: utf-8 -*-
"""Юнит-тесты импорта выработки ЭЭ."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.energy_balance.services.ee_generation_import_services import (
    _detect_column_layout,
    _detect_multi_year_column_layout,
    _extract_external_code,
    _is_espp_row,
    _resolve_espp_res_name,
    parse_ee_generation_workbook,
)
from app.generation.models.station.station_constants import STATION_SIGN_ESPP

STATION_UUID = "aa68b842-dcbe-5aa3-b379-ca48c69112b1"


def _build_workbook_bytes(rows: list[list]) -> bytes:
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = "Выработка 2024 год"
    for row in rows:
        worksheet.append(row)
    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_detect_multi_year_column_layout():
    rows = [
        ("Выработка электроэнергии", None, None, None),
        ("Наименование", "external_code", "2019 г.", "2020 г.", "2021 г."),
        ("ГТЭС тест", STATION_UUID, 10.5, 11.2, 12.0),
    ]
    layout = _detect_multi_year_column_layout([tuple(row) for row in rows])
    assert layout is not None
    assert layout.external_code_col == 1
    assert layout.name_col == 0
    assert layout.year_cols == {2: 2019, 3: 2020, 4: 2021}


def test_parse_multi_year_workbook():
    file_bytes = _build_workbook_bytes(
        [
            ["Выработка электроэнергии электростанциями", None, None, None],
            ["Наименование", "external_code", "2023 г.", "2024 г."],
            ["ГТЭС тест", STATION_UUID, 100.5, 101.2],
            ['ИТОГО ПАО "Сургутнефтегаз"', None, 100.5, 101.2],
        ]
    )
    parsed = parse_ee_generation_workbook(
        file_bytes,
        filename="Выработка электроэнергии станциями ПАО Сургутнефтегаз.xlsx",
    )
    assert parsed.is_multi_year
    assert len(parsed.multi_year_stations) == 1
    assert parsed.multi_year_stations[0].external_code == STATION_UUID
    assert parsed.multi_year_stations[0].values_by_year[2023] == Decimal("100.5")
    assert parsed.multi_year_stations[0].values_by_year[2024] == Decimal("101.2")


def test_parse_surgutneftegaz_workbook_if_available():
    path = Path(
        r"z:\НИО-10\АРМ ГС\Шаблоны для АРМ ГС\2. Балансы электроэнергии и мощности"
        r"\Баланс ЭЭ\Выработка электроэнергии станциями ПАО Сургутнефтегаз.xlsx"
    )
    if not path.is_file():
        pytest.skip("sample workbook is not available")

    parsed = parse_ee_generation_workbook(path.read_bytes(), filename=path.name)
    assert parsed.is_multi_year
    assert len(parsed.multi_year_stations) > 0
    assert all(row.external_code for row in parsed.multi_year_stations)
    years = {year for row in parsed.multi_year_stations for year in row.values_by_year}
    assert 2019 in years
    assert 2025 in years


def test_parse_kpo_external_code_workbook_if_available():
    path = Path(
        r"z:\НИО-10\АРМ ГС\Шаблоны для АРМ ГС\2. Балансы электроэнергии и мощности"
        r"\Баланс ЭЭ\Информация по фактическому производству электрической энергии+КПО+external_code.xlsx"
    )
    if not path.is_file():
        pytest.skip("sample workbook is not available")

    parsed = parse_ee_generation_workbook(path.read_bytes(), filename=path.name)
    assert parsed.is_multi_year
    assert len(parsed.multi_year_stations) > 0

    row_with_prom = next(
        (row for row in parsed.multi_year_stations if row.station_sign == "true"),
        None,
    )
    assert row_with_prom is not None
    assert row_with_prom.kto

    row_without_prom = next(
        (row for row in parsed.multi_year_stations if row.station_sign == "false"),
        None,
    )
    assert row_without_prom is not None

    years = {year for row in parsed.multi_year_stations for year in row.values_by_year}
    assert 2019 in years
    assert 2025 in years


def test_detect_multi_year_kpo_columns():
    rows = [
        ("Заголовок", None, None, None, None, None, None, None, None, None, None),
        (
            "Код КПО",
            "external_code",
            "external_code",
            "Наименование",
            "ОЭС",
            "Энергосистемы",
            "Объекты",
            "Тип электростанции",
            "Станции пром предприятий",
            "Основное топливо",
            2019,
            2020,
        ),
        (310326, STATION_UUID, STATION_UUID, "Тест", "ОЭС", "РЭС", "Станция", "ГРЭС", "Да", "Газ", 100.5, 101.2),
    ]
    layout = _detect_multi_year_column_layout([tuple(row) for row in rows])
    assert layout is not None
    assert layout.kto_col == 0
    assert layout.prom_sign_col == 8
    assert layout.year_cols == {10: 2019, 11: 2020}

    parsed = parse_ee_generation_workbook(
        _build_workbook_bytes(
            [
                list(rows[0]),
                list(rows[1]),
                list(rows[2]),
            ]
        ),
        filename="kpo_test.xlsx",
    )
    assert len(parsed.multi_year_stations) == 1
    assert parsed.multi_year_stations[0].kto == "310326"
    assert parsed.multi_year_stations[0].station_sign == "true"
    assert parsed.multi_year_stations[0].values_by_year[2019] == Decimal("100.5")


def test_is_espp_row_accepts_sign_or_name_column():
    assert _is_espp_row(STATION_SIGN_ESPP, "ЭС Тверская область")
    assert _is_espp_row("", STATION_SIGN_ESPP)
    assert not _is_espp_row("", "Конаковская ГРЭС")


def test_resolve_espp_res_name_from_res_or_name_columns():
    assert (
        _resolve_espp_res_name(
            "ЭС Тверская область",
            "ЭС Тверская область",
            STATION_SIGN_ESPP,
            None,
        )
        == "ЭС Тверская область"
    )
    assert (
        _resolve_espp_res_name(
            "",
            STATION_SIGN_ESPP,
            "",
            "ЭС Тверская область",
        )
        == "ЭС Тверская область"
    )


def test_detect_columns_by_header_names():
    rows = [
        ("РЭС", "Признак", "external_code", "Станция", "Послед. месяц в накоплении", "1 квартал", "январь", "февраль"),
        (None, None, STATION_UUID, "Тест", 100, None, 10, 20),
    ]
    layout = _detect_column_layout([tuple(row) for row in rows])
    assert layout.external_code_cols == [2]
    assert layout.annual_col == 4
    assert layout.month_cols == {6: 1, 7: 2}
    assert layout.res_col == 0
    assert layout.sign_col == 1
    assert layout.name_col == 3


def test_detect_columns_when_external_code_is_first():
    rows = [
        ("external_code", "external_code", "Наименование в БД", "Выработка и распределение", "Послед. месяц в накоплении", "январь"),
        (STATION_UUID, STATION_UUID, "Конаковская ГРЭС", "Конаковская ГРЭС", 340.8, 108.9),
    ]
    layout = _detect_column_layout([tuple(row) for row in rows])
    assert layout.external_code_cols == [0, 1]
    assert layout.annual_col == 4
    assert layout.month_cols[5] == 1
    assert _extract_external_code(rows[1], layout) == STATION_UUID


def test_parse_workbook_with_reordered_columns():
    file_bytes = _build_workbook_bytes(
        [
            ["Станция", "январь", "external_code", "Послед. месяц в накоплении", "февраль"],
            ["Тест", 11, STATION_UUID, 100, 22],
        ]
    )
    parsed = parse_ee_generation_workbook(file_bytes, filename="выработка_2024.xlsx")
    assert parsed.year_number == 2024
    assert len(parsed.stations) == 1
    assert parsed.stations[0].external_code == STATION_UUID
    assert parsed.stations[0].values.annual == 100
    assert parsed.stations[0].values.months[1] == 11
    assert parsed.stations[0].values.months[2] == 22


def test_parse_consolidated_2022_xls_if_available():
    path = Path("СВОД_выработка_2022.xls")
    if not path.is_file():
        pytest.skip("sample workbook is not available")

    parsed = parse_ee_generation_workbook(path.read_bytes(), filename=path.name)
    assert parsed.year_number == 2022
    assert len(parsed.stations) > 0
    assert all(row.external_code for row in parsed.stations)
    with_annual = [row for row in parsed.stations if row.values.annual is not None]
    assert len(with_annual) == len(parsed.stations)
    assert len(parsed.stations[0].values.months) == 12
    assert len(parsed.espp_rows) > 0
    assert all(
        row.res_name or row.anchor_external_code for row in parsed.espp_rows
    )


def test_parse_prepared_2022_xls_espp_if_available():
    path = Path("1_СВОД_выработка_2022_для загрузки.xls")
    if not path.is_file():
        pytest.skip("sample workbook is not available")

    parsed = parse_ee_generation_workbook(path.read_bytes(), filename=path.name)
    assert parsed.year_number == 2022
    assert len(parsed.espp_rows) > 0
    assert all(row.res_name for row in parsed.espp_rows)


def test_detect_oes_standard_column_layout_a_to_u():
    """Классическая раскладка свода ОЭС: A–U с квартальными заголовками."""
    header = [""] * 21
    header[2] = "external_code"
    header[3] = "Выработка электроэнергии и распределение"
    header[4] = "Послед. месяц в накоплении"
    header[5] = "1 квартал"
    header[6:9] = ["январь", "февраль", "март"]
    header[9] = "2 квартал"
    header[10:13] = ["апрель", "май", "июнь"]
    header[13] = "3 квартал"
    header[14:17] = ["июль", "август", "сентябрь"]
    header[17] = "4 квартал"
    header[18:21] = ["октябрь", "ноябрь", "декабрь"]

    layout = _detect_column_layout([tuple(header)])
    assert layout.external_code_cols == [2]
    assert layout.annual_col == 4
    assert layout.res_col == 0
    assert layout.sign_col == 1
    assert layout.name_col == 3
    assert layout.month_cols == {
        6: 1,
        7: 2,
        8: 3,
        10: 4,
        11: 5,
        12: 6,
        14: 7,
        15: 8,
        16: 9,
        18: 10,
        19: 11,
        20: 12,
    }

    data_row = [""] * 21
    data_row[0] = "ЭС Московской области"
    data_row[1] = ""
    data_row[2] = STATION_UUID
    data_row[3] = "Тестовая ГРЭС"
    data_row[4] = 1000
    data_row[6] = 100
    data_row[7] = 90
    data_row[8] = 80
    data_row[10] = 70
    data_row[11] = 60
    data_row[12] = 50
    data_row[14] = 40
    data_row[15] = 30
    data_row[16] = 20
    data_row[18] = 10
    data_row[19] = 9
    data_row[20] = 8

    file_bytes = _build_workbook_bytes([header, data_row])
    parsed = parse_ee_generation_workbook(file_bytes, filename="ОЭС_выработка_2024.xlsx")
    assert len(parsed.stations) == 1
    assert parsed.stations[0].external_code == STATION_UUID
    assert parsed.stations[0].values.annual == 1000
    assert parsed.stations[0].values.months == {
        1: 100,
        2: 90,
        3: 80,
        4: 70,
        5: 60,
        6: 50,
        7: 40,
        8: 30,
        9: 20,
        10: 10,
        11: 9,
        12: 8,
    }


def test_parse_oes_workbook_if_available():
    candidates = list(Path("app").rglob("*свод*выработка*2024*.xlsx"))
    candidates = [path for path in candidates if not path.name.startswith("~")]
    if not candidates:
        pytest.skip("sample workbook is not available")

    parsed = parse_ee_generation_workbook(candidates[0].read_bytes(), filename=candidates[0].name)
    assert parsed.year_number == 2024
    assert len(parsed.stations) > 0
