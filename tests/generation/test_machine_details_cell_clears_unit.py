# -*- coding: utf-8 -*-
"""Очистка ячейки в карточке агрегата сохраняется.

Раньше пустая ячейка мощности/названия, в которой до правки было значение,
тихо игнорировалась при сохранении: старое значение возвращалось, а пользователь
получал «Изменений не обнаружено».
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / "app" / "generation" / "services" / "machine_services" / "machine_services.py"
MACHINE_TEMPLATE = ROOT / "app" / "templates" / "generation" / "stations" / "machine_details.html"
PGU_TEMPLATE = ROOT / "app" / "templates" / "generation" / "stations" / "pgu_machine_details.html"


def _between(start_marker: str, end_marker: str) -> str:
    text = SERVICES.read_text(encoding="utf-8")
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _powers_block() -> str:
    return _between("def _power_field_changed", "    any_power_changed = False")


def _power_clear_block() -> str:
    return _between(
        "# Очистка ячейки сохраняется так же, как и правка",
        "power_fields_changed = any_power_changed",
    )


def test_cleared_power_cell_is_detected_in_all_three_fields() -> None:
    assert "def _power_field_cleared(raw_value, orig_value):" in _powers_block()
    block = _power_clear_block()
    for field in ("p_ust", "p_ogr", "p_rasp"):
        assert f"{field}_cleared = _power_field_cleared({field}_form_raw, {field}_orig_raw)" in block


def test_cleared_power_cell_is_saved_as_empty_instead_of_old_value() -> None:
    text = SERVICES.read_text(encoding="utf-8")
    assert "p_ust = None if p_ust_cleared else (" in text
    assert "elif p_ogr_cleared:" in text
    assert "elif p_rasp_cleared:" in text
    # очищенные ячейки автозаполнение не восстанавливает
    assert "if p_ust_cleared:\n                p_ust = None" in text
    assert "skip_ogr = user_modified_p_ogr or p_ogr_cleared" in text
    assert "skip_rasp = user_modified_p_rasp or p_rasp_cleared" in text


def test_name_cells_submit_the_displayed_value_for_clear_detection() -> None:
    machine_template = MACHINE_TEMPLATE.read_text(encoding="utf-8")
    pgu_template = PGU_TEMPLATE.read_text(encoding="utf-8")
    assert 'name="{{ nm.year_name.name }}_orig"' in machine_template
    assert 'name="{{ nm.year_name.name }}_orig"' in pgu_template


def test_cleared_name_cell_is_saved_as_empty() -> None:
    text = SERVICES.read_text(encoding="utf-8")
    assert '_orig") or "").strip() or None' in text
    assert "elif name_shown:" in text
