# -*- coding: utf-8 -*-
"""Юнит-тесты блока «Промышленное производство» на странице электроёмкости (ФО)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.electrical_intensity.services import (
    electrical_intensity_services as eis,
)
from app.electrical_intensity.services.electrical_intensity_constants import (
    INDUSTRIAL_GROUP_SECTION_LABEL,
    ROW_KIND_INTENSITY,
)
from app.economics.services.ved_consumption_constants import INDUSTRIAL_COMPONENT_VED_TARGETS


class _Ved:
    def __init__(self, ved_id: int, name: str, *, name_2: str | None = None):
        self.id = ved_id
        self.name = name
        self.name_2 = name_2
        self.display_order = ved_id


def _ved_types() -> list[_Ved]:
    return [
        _Ved(1, "Всего потребление"),
        _Ved(2, "Промышленное производство, в том числе:"),
        _Ved(3, "Добыча полезных ископаемых", name_2="Добывающие производства"),
        _Ved(4, "Обрабатывающие производства", name_2="Обрабатывающие производства"),
        _Ved(
            5,
            "Обеспечение электрической энергией, газом и паром; Кондиционирование воздуха. "
            "Водоснабжение; Водоотведение, организация сбора и утилизация отходов, "
            "деятельность по ликвидации загрязнений",
            name_2="Производство и распределение электроэнергии, газа и воды",
        ),
        _Ved(6, "Строительство", name_2="Строительство"),
    ]


def test_build_ved_sections_inserts_industrial_group_before_mining(app):
    ved_types = _ved_types()
    product_by_ved = {
        (3, 2020): Decimal("1"),
        (4, 2020): Decimal("2"),
        (5, 2020): Decimal("3"),
    }
    consumption_by_ved = {
        (3, 2020): Decimal("10"),
        (4, 2020): Decimal("20"),
        (5, 2020): Decimal("30"),
    }
    accum_by_ved = {
        (3, 2020): Decimal("100"),
        (4, 2020): Decimal("200"),
        (5, 2020): Decimal("300"),
    }
    with app.app_context():
        sections = eis._build_ved_sections_for_fd(
            ved_types=ved_types,
            refdata_ved_ids=frozenset({3, 4, 5, 6}),
            product_output_by_ved_year=product_by_ved,
            consumption_by_ved_year=consumption_by_ved,
            accum_by_ved_year=accum_by_ved,
            ei_year_by_ved_kind_year={},
            coef_by_ved={},
            display_years=[2020],
            rounding_digits=1,
            price_year=2020,
            current_year=2020,
        )
    names = [s["ved_name"] for s in sections]
    assert INDUSTRIAL_GROUP_SECTION_LABEL in names
    assert names.index(INDUSTRIAL_GROUP_SECTION_LABEL) < names.index("Добывающие производства")
    assert "Промышленное производство, в том числе:" not in names

    industrial = next(s for s in sections if s.get("is_industrial_group"))
    assert industrial["has_ei_intensity_block"] is True
    assert industrial["has_ei_model_block"] is False

    po_row = industrial["reference_rows"][0]
    assert po_row["cells"][2020] == Decimal("6")
    assert po_row["formula_hint"]
    assert po_row["is_computed"] is True

    intensity_row = next(
        r for r in industrial["rows"] if r["row_kind"] == ROW_KIND_INTENSITY
    )
    assert intensity_row["cells"][2020] == Decimal("10000")
    assert intensity_row["formula_hint"]


def test_build_ved_sections_without_industrial_components_skips_group(app):
    ved_types = [_Ved(3, "Добыча полезных ископаемых", name_2="Добывающие производства")]
    with app.app_context():
        sections = eis._build_ved_sections_for_fd(
            ved_types=ved_types,
            refdata_ved_ids=frozenset({3}),
            product_output_by_ved_year={},
            consumption_by_ved_year={},
            accum_by_ved_year={},
            ei_year_by_ved_kind_year={},
            coef_by_ved={},
            display_years=[2020],
            rounding_digits=1,
            price_year=2020,
            current_year=2020,
        )
    assert not any(s.get("is_industrial_group") for s in sections)


@pytest.mark.parametrize("target", INDUSTRIAL_COMPONENT_VED_TARGETS)
def test_find_industrial_component_veds_requires_all_targets(target: str):
    ved_types = _ved_types()
    found = eis._find_industrial_component_veds(ved_types)
    assert len(found) == 3
    assert any(v.name.startswith(target.split()[0]) or target in v.name for v in found)
