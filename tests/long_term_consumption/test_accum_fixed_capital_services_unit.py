# -*- coding: utf-8 -*-
"""Юнит-тесты построения строк таблицы накопленных инвестиций в основной капитал."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.economics.services import accum_fixed_capital_services as afcs
from app.economics.services.accum_fixed_capital_constants import (
    AFCI_TOTAL_OTHER_VED_TARGETS,
    AFCI_VED_HIDDEN_NAMES,
    INDUSTRIAL_COMPONENT_VED_TARGETS,
    INDUSTRIAL_GROUP_LABEL,
    TOTAL_ACCUM_FIXED_CAPITAL_NAME,
)


class _Ved:
    def __init__(self, ved_id: int, name: str):
        self.id = ved_id
        self.name = name
        self.display_order = ved_id


def _ved_types() -> list[_Ved]:
    return [
        _Ved(1, TOTAL_ACCUM_FIXED_CAPITAL_NAME),
        _Ved(2, "Всего потребление"),
        _Ved(3, "Домашние хозяйства"),
        _Ved(4, INDUSTRIAL_GROUP_LABEL),
        _Ved(5, "Добыча полезных ископаемых"),
        _Ved(6, "Обрабатывающие производства"),
        _Ved(
            7,
            "Обеспечение электрической энергией, газом и паром; Кондиционирование воздуха. "
            "Водоснабжение; Водоотведение, организация сбора и утилизация отходов, "
            "деятельность по ликвидации загрязнений",
        ),
        _Ved(8, "Строительство"),
        _Ved(9, "Транспорт"),
        _Ved(10, "Прочие ВЭД"),
        _Ved(11, "Сельскохозяйственное производство"),
        _Ved(12, "Потери в сетях"),
    ]


@pytest.mark.parametrize("hidden_name", AFCI_VED_HIDDEN_NAMES)
def test_ved_hidden_on_afci_page(hidden_name: str):
    assert afcs._is_ved_hidden_on_afci_page(hidden_name) is True


def test_ved_types_for_afci_page_excludes_hidden():
    all_types = _ved_types()
    hidden_count = sum(1 for v in all_types if afcs._is_ved_hidden_on_afci_page(v.name))
    visible = [
        v
        for v in all_types
        if v.name and not afcs._is_ved_hidden_on_afci_page(v.name)
    ]
    assert len(visible) == len(all_types) - hidden_count
    assert hidden_count >= 1


def test_fd_total_row_computed_from_sum():
    ved_types = [v for v in _ved_types() if not afcs._is_ved_hidden_on_afci_page(v.name)]
    values = {
        (5, 2020): Decimal("1"),
        (6, 2020): Decimal("2"),
        (7, 2020): Decimal("3"),
        (8, 2020): Decimal("10"),
        (9, 2020): Decimal("20"),
        (10, 2020): Decimal("30"),
        (11, 2020): Decimal("40"),
    }
    rows = afcs._build_territory_rows(
        territory_kind="fd",
        ved_types=ved_types,
        values_by_ved_year=values,
        display_years=[2020],
        rounding_digits=1,
    )
    assert rows[0]["ved_name"] == INDUSTRIAL_GROUP_LABEL
    assert rows[0]["cells_display"][2020] == "6"
    hidden_in_rows = {h for h in AFCI_VED_HIDDEN_NAMES if h in [r["ved_name"] for r in rows]}
    assert not hidden_in_rows
    assert rows[-1]["ved_name"] == TOTAL_ACCUM_FIXED_CAPITAL_NAME
    assert rows[-1]["is_computed"] is True
    # 6 + 10 + 20 + 30 + 40
    assert rows[-1]["cells_display"][2020] == "106"
    assert rows[-1]["cells"][2020] == Decimal("106")
    other_names = [r["ved_name"] for r in rows[4:-1]]
    for target in AFCI_TOTAL_OTHER_VED_TARGETS:
        assert any(n.startswith(target) or target in n for n in other_names)


def test_fd_total_excludes_consumption_ved_from_display():
    ved_types = _ved_types()
    values = {(5, 2020): Decimal("1")}
    rows = afcs._build_territory_rows(
        territory_kind="fd",
        ved_types=ved_types,
        values_by_ved_year=values,
        display_years=[2020],
        rounding_digits=0,
    )
    names = [r["ved_name"] for r in rows]
    assert "Всего потребление" not in names
    assert "Домашние хозяйства" not in names


def test_find_ved_matches_utilities_long_name():
    long_name = INDUSTRIAL_COMPONENT_VED_TARGETS[2]
    ved = _Ved(7, long_name)
    found = afcs._find_ved_by_target([ved], INDUSTRIAL_COMPONENT_VED_TARGETS[2])
    assert found is ved
