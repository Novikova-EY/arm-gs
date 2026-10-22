# -*- coding: utf-8 -*-
"""Карточка агрегата: продление значений по строке на весь отображаемый период.

Протягивается только непустое значение: очистка ячейки не должна обнулять
остальные годы строки (Руст/Рогр/Ррасп, «Название агрегата», «Тип ТЭС», «Топливо»).
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEMPLATES = ROOT / "app" / "templates" / "generation" / "stations"
TEMPLATE = TEMPLATES / "machine_details.html"
PGU_TEMPLATE = TEMPLATES / "pgu_machine_details.html"


def _extend_power_value_body() -> str:
    text = TEMPLATE.read_text(encoding="utf-8")
    start = text.index("function extendPowerValue(")
    end = text.index("if (typeof syncZeroYearPowerDashes", start)
    return text[start:end]


def _function_body(path: Path, name: str) -> str:
    """Тело JS-функции по имени (с учётом вложенных фигурных скобок)."""
    text = path.read_text(encoding="utf-8")
    start = text.index("function {}(".format(name))
    depth = 0
    for pos in range(text.index("{", start), len(text)):
        char = text[pos]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : pos + 1]
    raise AssertionError("не закрыта функция {}".format(name))


def _clear_guard_before(text: str, loop_marker: str) -> None:
    clear_guard = text.index('trimmed === ""')
    first_loop = text.index(loop_marker)
    assert clear_guard < first_loop
    assert "return;" in text[clear_guard:first_loop]


def test_power_row_extension_does_not_stop_at_db_version_year() -> None:
    body = _extend_power_value_body()
    assert "maxVersionYear" not in body


def test_power_row_extension_fills_every_later_column() -> None:
    body = _extend_power_value_body()
    # Руст/Рогр/Ррасп протягиваются до последнего столбца таблицы
    assert "for (let i = idx + 1; i < inputs.length; i++)" in body
    # при вводе Руст заполняется и строка Ррасп
    assert "for (let i = idx; i < raspRowInputs.length; i++)" in body


def test_cleared_cell_is_not_propagated_to_the_rest_of_the_row() -> None:
    _clear_guard_before(
        _extend_power_value_body(), "for (let i = idx + 1; i < inputs.length; i++)"
    )


def test_name_row_extension_fills_every_later_column() -> None:
    body = _function_body(TEMPLATE, "extendNameValue")
    assert "maxVersionYear" not in body
    assert "for (let i = idx + 1; i < inputs.length; i++)" in body


def test_cleared_name_is_not_propagated_to_the_rest_of_the_row() -> None:
    _clear_guard_before(
        _function_body(TEMPLATE, "extendNameValue"),
        "for (let i = idx + 1; i < inputs.length; i++)",
    )


def test_tes_and_fuel_rows_skip_cleared_selects() -> None:
    body = _function_body(TEMPLATE, "attachTesAndFuelAutoFill")
    # очистка ("не указано", пустое значение) не протягивается
    assert body.count("if (isClearedSelectValue(this)) return;") == 2
    # значение протягивается до конца строки, без ограничения по году версии
    assert body.count("extendSelectValue(") == 3
    assert "maxVersionYear" not in body


def test_cleared_select_is_recognised_by_option_label() -> None:
    body = _function_body(TEMPLATE, "isClearedSelectValue")
    # «не указано» приходит со своим id, поэтому смотрим на текст варианта
    assert 'label === "не указано"' in body
    assert "selectedIndex" in body


def test_pgu_card_has_the_same_row_extension_rules() -> None:
    power = _function_body(PGU_TEMPLATE, "extendPowerValue")
    assert "maxVersionYear" not in power
    _clear_guard_before(power, "for (let i = idx + 1; i < inputs.length; i++)")

    name = _function_body(PGU_TEMPLATE, "extendNameValue")
    assert "maxVersionYear" not in name
    _clear_guard_before(name, "for (let i = idx + 1; i < inputs.length; i++)")
