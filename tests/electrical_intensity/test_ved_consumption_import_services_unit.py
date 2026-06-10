# -*- coding: utf-8 -*-
"""Юнит-тесты разбора Excel для импорта потребления по ВЭД."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app.economics.services import ved_consumption_import_services as vis


@pytest.fixture
def structure_fo_xlsx_bytes() -> bytes:
    path = Path(__file__).resolve().parents[2] / "app" / "Структура потребление 2010-2025 по ФО.xlsx"
    if not path.is_file():
        pytest.skip("sample xlsx not in workspace")
    return path.read_bytes()


def test_detect_import_columns_structure_file(structure_fo_xlsx_bytes):
    wb = load_workbook(BytesIO(structure_fo_xlsx_bytes), read_only=True, data_only=True)
    sheet = wb.active
    header_row, _ = vis._detect_year_columns(sheet)
    assert header_row == 2
    territory_col, ved_col = vis._detect_import_columns(sheet, header_row, {})
    assert (territory_col, ved_col) == (2, 3)
    wb.close()


def test_territory_and_ved_label_helpers():
    assert vis._is_russia_marker("РФ — Российская Федерация")
    assert vis._is_russia_marker("РОССИЯ")
    fd_lookup = {vis._normalize_label("ЦФО"): 1}
    assert vis._is_fd_marker("ЦФО", fd_lookup)
    assert vis._resolve_fd_id("ЦФО — Центральный", fd_lookup) == 1
    ved_lookup = {vis._normalize_label("Промышленное производство"): 10}
    assert vis._resolve_ved_id("Промышленное производство, в том числе:", ved_lookup) == 10


def test_ved_lookup_maps_fd_total_label_to_total_consumption():
    ved_lookup = {
        vis._normalize_label("Всего потребление"): 1,
    }
    ved_lookup[vis._normalize_label("Всего")] = 1
    assert vis._resolve_ved_id("Всего потребление", ved_lookup) == 1
    assert vis._resolve_ved_id("Всего", ved_lookup) == 1


def test_resolve_ved_prefix_match():
    ved_lookup = {
        vis._normalize_label(
            "Обеспечение электрической энергией, газом и паром"
        ): 5,
    }
    long_label = (
        "Обеспечение электрической энергией, газом и паром; "
        "Кондиционирование воздуха."
    )
    assert vis._resolve_ved_id(long_label, ved_lookup) == 5
