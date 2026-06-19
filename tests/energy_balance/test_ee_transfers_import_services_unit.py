# -*- coding: utf-8 -*-
"""Юнит-тесты импорта перетоков ЭЭ."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.energy_balance.services.ee_generation_import_services import _normalize_name
from app.energy_balance.services.ee_transfers_import_services import (
    _is_transfer_row,
    parse_ee_transfers_workbook,
)


def test_is_transfer_row_skips_border_trade_labels_in_to_column():
    assert _is_transfer_row("ЭС Псковской области", "Эстония") is True
    assert _is_transfer_row("ЭС Мурманской области", "приграничная торговля") is False
    assert _is_transfer_row(
        "ЭС г. Санкт-Петербурга и Ленинградской области",
        "в т.ч. приграничная торговля",
    ) is False
    assert _is_transfer_row("ЭС Псковской области", "САЛЬДО") is False


def test_parse_northwest_workbook_includes_estonia_rows():
    path = Path("app/СВОД 2024 год/ОЭС Северо-Запада свод_выработка и перетоки_2024.xlsx")
    if not path.is_file():
        pytest.skip("sample workbook is not available")

    parsed = parse_ee_transfers_workbook(path.read_bytes(), filename=path.name)
    estonia_rows = [
        row
        for row in parsed.transfers
        if _normalize_name(row.to_name) == _normalize_name("Эстония")
    ]
    assert parsed.source_oes_name == "ОЭС Северо-Запада"
    assert len(estonia_rows) == 2
    assert not any("пригранич" in _normalize_name(row.to_name) for row in parsed.transfers)


def test_parse_siberia_workbook_includes_subject_rows():
    path = Path("app/СВОД 2024 год/ОЭС Сибири свод_выработка и перетоки_2024.xlsx")
    if not path.is_file():
        pytest.skip("sample workbook is not available")

    parsed = parse_ee_transfers_workbook(path.read_bytes(), filename=path.name)
    altai_rows = [
        row
        for row in parsed.transfers
        if _normalize_name(row.from_name) == _normalize_name("Алтайский край")
    ]
    assert parsed.source_oes_name == "ОЭС СИБИРИ"
    assert len(altai_rows) >= 4


def test_parse_svod_2023_workbook_from_xls_template():
    path = Path(
        r"z:\НИО-10\АРМ ГС\Шаблоны для АРМ ГС\2. Балансы электроэнергии и мощности"
        r"\Баланс ЭЭ\Для загрузки\Свод 2023\Перетоки_свод_2023_ для загрузки.xls"
    )
    if not path.is_file():
        pytest.skip("svod 2023 template is not available")

    parsed = parse_ee_transfers_workbook(path.read_bytes(), filename=path.name)
    assert parsed.year_number == 2023
    assert parsed.is_svod_format is True
    assert parsed.source_oes_name is None
    assert len(parsed.transfers) == 374
    belgorod_voronezh = [
        row
        for row in parsed.transfers
        if _normalize_name(row.from_name) == _normalize_name("ЭС Белгородской области")
        and _normalize_name(row.to_name) == _normalize_name("ЭС Воронежской области")
    ]
    assert len(belgorod_voronezh) == 1
    assert belgorod_voronezh[0].values.annual is not None
    assert belgorod_voronezh[0].values.months.get(1) is not None


def test_parse_siberia_workbook_includes_energy_unit_targets():
    path = Path("app/СВОД 2024 год/ОЭС Сибири свод_выработка и перетоки_2024.xlsx")
    if not path.is_file():
        pytest.skip("sample workbook is not available")

    parsed = parse_ee_transfers_workbook(path.read_bytes(), filename=path.name)
    eu_targets = {
        _normalize_name(row.to_name)
        for row in parsed.transfers
        if _normalize_name(row.to_name)
        in {
            _normalize_name("Западный энергорайон"),
            _normalize_name("Южно-Якутский энергорайон"),
        }
    }
    assert len(eu_targets) == 2
