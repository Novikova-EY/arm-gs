# -*- coding: utf-8 -*-
"""Юнит-тесты сводных строк ФО на странице электроёмкости."""

from __future__ import annotations

from decimal import Decimal

from app.energy_consumption.long_term_consumption.services import (
    electrical_intensity_services as eis,
)
from app.energy_consumption.long_term_consumption.services.electrical_intensity_constants import (
    FD_TOTAL_SECTION_LABEL,
    INDUSTRIAL_GROUP_SECTION_LABEL,
    REF_ROW_FD_TOTAL_CONSUMPTION,
    REF_ROW_FD_VED_CONSUMPTION,
    REF_ROW_FD_VRP,
    ROW_KIND_INTENSITY,
)


class _Ved:
    def __init__(self, ved_id: int, name: str, *, name_2: str | None = None):
        self.id = ved_id
        self.name = name
        self.name_2 = name_2
        self.display_order = ved_id


def _ved_types() -> list[_Ved]:
    return [
        _Ved(1, "Всего потребление", name_2="Всего"),
        _Ved(2, "Промышленное производство, в том числе:"),
        _Ved(3, "Добыча полезных ископаемых", name_2="Добывающие производства"),
        _Ved(4, "Обрабатывающие производства", name_2="Обрабатывающие производства"),
        _Ved(
            6,
            "Обеспечение электрической энергией, газом и паром; Кондиционирование воздуха. "
            "Водоснабжение; Водоотведение, организация сбора и утилизация отходов, "
            "деятельность по ликвидации загрязнений",
            name_2="Производство и распределение электроэнергии, газа и воды",
        ),
        _Ved(5, "Строительство", name_2="Строительство"),
        _Ved(10, "Потери в сетях", name_2="Потери в сетях"),
        _Ved(11, "С.н. электростанций", name_2="С.н. электростанций"),
    ]


def test_build_ved_sections_omits_fd_total_block(app):
    ved_types = _ved_types()
    with app.app_context():
        sections = eis._build_ved_sections_for_fd(
            ved_types=ved_types,
            refdata_ved_ids=frozenset({3, 4, 5, 6}),
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
    names = [s["ved_name"] for s in sections]
    assert FD_TOTAL_SECTION_LABEL not in names
    assert not any(s.get("is_fd_total_group") for s in sections)
    assert INDUSTRIAL_GROUP_SECTION_LABEL in names


def test_build_fd_territory_summary_rows(app):
    ved_types = _ved_types()
    product_by_ved = {
        (3, 2020): Decimal("100"),
        (4, 2020): Decimal("200"),
        (5, 2020): Decimal("50"),
        (6, 2020): Decimal("30"),
    }
    consumption_by_ved = {
        (3, 2020): Decimal("1000"),
        (4, 2020): Decimal("2000"),
        (5, 2020): Decimal("500"),
        (6, 2020): Decimal("300"),
        (10, 2020): Decimal("300"),
        (11, 2020): Decimal("200"),
    }
    accum_by_ved = {
        (3, 2020): Decimal("10"),
        (4, 2020): Decimal("20"),
        (5, 2020): Decimal("5"),
        (6, 2020): Decimal("3"),
    }
    with app.app_context():
        summary = eis._build_fd_territory_summary(
            ved_types=ved_types,
            product_output_by_ved_year=product_by_ved,
            consumption_by_ved_year=consumption_by_ved,
            accum_by_ved_year=accum_by_ved,
            display_years=[2020],
            rounding_digits=1,
            price_year=2020,
            current_year=2020,
        )
    assert summary is not None
    assert "ved_name" not in summary
    assert summary["has_ei_intensity_block"] is True

    ref_by_kind = {r["row_kind"]: r for r in summary["reference_rows"]}
    assert ref_by_kind[REF_ROW_FD_VRP]["cells"][2020] == Decimal("380")
    assert ref_by_kind[REF_ROW_FD_VRP]["formula_hint"]
    assert ref_by_kind[REF_ROW_FD_VED_CONSUMPTION]["cells"][2020] == Decimal("3.8")
    assert ref_by_kind[REF_ROW_FD_VED_CONSUMPTION]["unit_label"] == "млрд кВт.ч."
    assert ref_by_kind[REF_ROW_FD_TOTAL_CONSUMPTION]["cells"][2020] == Decimal("4.3")
    assert ref_by_kind[REF_ROW_FD_TOTAL_CONSUMPTION]["formula_hint"]

    intensity_row = next(
        r for r in summary["rows"] if r["row_kind"] == ROW_KIND_INTENSITY
    )
    assert intensity_row["cells"][2020] == eis._quantize_ei_value(
        Decimal("4300") / Decimal("380") * Decimal("1000"),
        1,
        row_kind=ROW_KIND_INTENSITY,
    )
    assert intensity_row["formula_hint"]
