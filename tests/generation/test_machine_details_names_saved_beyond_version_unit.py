# -*- coding: utf-8 -*-
"""Сохранение названий агрегата по всем годам отображаемого периода.

Раньше названия для годов позже последнего года версии БД принудительно
обнулялись при сохранении (в то время как мощности, тип ТЭС и топливо
сохранялись по всему периоду) – из-за этого введённое название терялось
после перезагрузки карточки.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / "app" / "generation" / "services" / "machine_services" / "machine_services.py"


def _between(start_marker: str, end_marker: str) -> str:
    text = SERVICES.read_text(encoding="utf-8")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _machine_names_persist_block() -> str:
    return _between(
        "# Название по году (machine_names)",
        "# Для ТЭС/ГЭС/ГАЭС: поле",
    )


def _pgu_machine_names_persist_block() -> str:
    return _between(
        "# Сохранение названий по годам (pgu_machine_names)",
        "if year_num not in names_map:",
    )


def test_machine_names_are_saved_for_years_beyond_db_version() -> None:
    block = _machine_names_persist_block()
    assert "year_num > current_year_for_version" not in block
    # обнуление названия бывает только при ручной очистке ячейки
    assert block.index("elif name_shown:") < block.index("effective_name = None")


def test_machine_names_are_still_propagated_across_the_row() -> None:
    block = _machine_names_persist_block()
    # последнее введённое название протягивается на все последующие годы
    assert "last_effective_name = raw_name" in block
    assert "effective_name = last_effective_name" in block
    # но не заполняет год, ячейку которого очистили вручную
    assert "elif name_shown:" in block
    assert "effective_name = None" in block


def test_pgu_machine_names_are_saved_for_years_beyond_db_version() -> None:
    block = _pgu_machine_names_persist_block()
    assert "year_num > version_year_end" not in block
    assert "last_effective_name = raw_name" in block
    assert "effective_name = last_effective_name" in block
    assert "elif name_shown:" in block
