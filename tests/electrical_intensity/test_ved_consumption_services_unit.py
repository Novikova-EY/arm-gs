# -*- coding: utf-8 -*-
"""Юнит-тесты построения строк таблицы потребления по ВЭД."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.economics.services import ved_consumption_services as vcs
from app.economics.services.ved_consumption_constants import (
    INDUSTRIAL_COMPONENT_VED_TARGETS,
    INDUSTRIAL_GROUP_LABEL,
    TOTAL_VED_NAME,
)


class _Ved:
    def __init__(self, ved_id: int, name: str):
        self.id = ved_id
        self.name = name
        self.display_order = ved_id


class _Fd:
    def __init__(self, fd_id: int, name: str, *, name_abr: str | None = None, name_full: str | None = None):
        self.id = fd_id
        self.name = name
        self.name_abr = name_abr
        self.name_full = name_full


@pytest.mark.parametrize(
    "fd",
    [
        _Fd(1, "Новые территории"),
        _Fd(2, "не указано"),
        _Fd(3, "ФО — Новые территории"),
        _Fd(4, "не указано2"),
    ],
)
def test_federal_district_excluded_from_ved(fd):
    assert vcs._is_federal_district_excluded_from_ved(fd) is True


@pytest.mark.parametrize(
    "fd",
    [
        _Fd(10, "Центральный"),
        _Fd(11, "Южный", name_abr="ЮФО"),
    ],
)
def test_federal_district_not_excluded_from_ved(fd):
    assert vcs._is_federal_district_excluded_from_ved(fd) is False


def _ved_types() -> list[_Ved]:
    return [
        _Ved(1, "Всего потребление"),
        _Ved(2, "Промышленное производство, в том числе:"),
        _Ved(3, "Добыча полезных ископаемых"),
        _Ved(4, "Обрабатывающие производства"),
        _Ved(
            5,
            "Обеспечение электрической энергией, газом и паром; Кондиционирование воздуха. "
            "Водоснабжение; Водоотведение, организация сбора и утилизация отходов, "
            "деятельность по ликвидации загрязнений",
        ),
        _Ved(6, "Строительство"),
    ]


def test_ved_row_cell_tooltips_full_precision():
    ved = _Ved(10, "Строительство")
    row = vcs._ved_row(
        ved,
        {(10, 2020): Decimal("1.234567")},
        [2020],
        rounding_digits=0,
    )
    assert row["cell_tooltips"][2020] == "1,234567"
    assert row["cells_display"][2020] == "1,234567"


def test_fd_rows_industrial_group_first_with_sum():
    ved_types = _ved_types()
    values = {
        (3, 2020): Decimal("1"),
        (4, 2020): Decimal("2"),
        (5, 2020): Decimal("3"),
    }
    rows = vcs._build_territory_rows(
        territory_kind="fd",
        ved_types=ved_types,
        values_by_ved_year=values,
        display_years=[2020],
        rounding_digits=1,
    )
    assert rows[0]["ved_name"] == INDUSTRIAL_GROUP_LABEL
    assert rows[0]["cells_display"][2020] == "6"
    assert rows[0]["is_computed"] is True
    assert rows[0]["cells"][2020] == Decimal("6")
    assert rows[0]["cell_tooltips"][2020] == "6"
    assert rows[1]["is_industrial_component"] is True
    assert rows[1]["ved_name"].startswith("Добыча")
    assert rows[2]["is_industrial_component"] is True
    assert rows[3]["is_industrial_component"] is True
    other_names = [r["ved_name"] for r in rows[4:-1]]
    assert "Строительство" in other_names
    assert "Промышленное производство, в том числе:" not in other_names
    assert "Всего потребление" not in other_names
    assert rows[-1]["ved_name"] == TOTAL_VED_NAME
    assert rows[-1]["is_total"] is True
    assert rows[-1]["is_computed"] is True
    assert rows[-1]["cells_display"][2020] == "6"
    assert rows[-1]["ved_id"] == 1


def test_rf_rows_industrial_group_with_total_at_end():
    ved_types = _ved_types()
    values = {
        (3, 2020): Decimal("10"),
        (4, 2020): Decimal("20"),
        (5, 2020): Decimal("30"),
    }
    rows = vcs._build_territory_rows(
        territory_kind="rf",
        ved_types=ved_types,
        values_by_ved_year=values,
        display_years=[2020],
        rounding_digits=0,
    )
    assert rows[0]["ved_name"] == INDUSTRIAL_GROUP_LABEL
    assert rows[0]["cells_display"][2020] == "60"
    assert rows[0]["is_computed"] is True
    assert rows[0]["cells"][2020] == Decimal("60")
    assert rows[1]["is_industrial_component"] is True
    assert rows[-1]["ved_name"] == "Всего потребление"
    assert rows[-1]["is_total"] is True
    assert rows[-1]["is_computed"] is True
    assert rows[-1]["cells_display"][2020] == "60"


def test_fd_fallback_when_component_missing():
    ved_types = [_Ved(1, "Добыча полезных ископаемых")]
    rows = vcs._build_territory_rows(
        territory_kind="fd",
        ved_types=ved_types,
        values_by_ved_year={},
        display_years=[2020],
        rounding_digits=1,
    )
    assert len(rows) == 1
    assert not rows[0].get("is_industrial_group")


@pytest.mark.parametrize(
    "long_name",
    [
        "Обеспечение электрической энергией, газом и паром; Кондиционирование воздуха. "
        "Водоснабжение; Водоотведение, организация сбора и утилизация отходов, "
        "деятельность по ликивдации загрязнений",
    ],
)
def test_find_ved_matches_utilities_with_typo(long_name: str):
    ved = _Ved(5, long_name)
    found = vcs._find_ved_by_target([ved], INDUSTRIAL_COMPONENT_VED_TARGETS[2])
    assert found is ved
