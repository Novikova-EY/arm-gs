# -*- coding: utf-8 -*-
"""Юнит-тесты блока «Население» РФ на странице электроёмкости."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from app.electrical_intensity.services import (
    electrical_intensity_services as eis,
)
from app.electrical_intensity.services.electrical_intensity_constants import (
    POPULATION_SECTION_LABEL,
    POPULATION_SECTION_MARKER,
    REF_ROW_ACCUM_MONETARY_INCOME,
    REF_ROW_HOUSEHOLD_CONSUMPTION,
    REF_ROW_POPULATION,
    REF_ROW_RF_VED_CONSUMPTION,
    ROW_KIND_INTENSITY,
)


class _Ved:
    def __init__(self, ved_id: int, name: str, *, name_2: str | None = None):
        self.id = ved_id
        self.id_economic_activity_type = ved_id
        self.name = name
        self.name_2 = name_2
        self.display_order = ved_id


def _ved_types_with_household() -> list[_Ved]:
    return [
        _Ved(1, "Всего потребление", name_2="Всего"),
        _Ved(2, "Промышленное производство, в том числе:"),
        _Ved(3, "Добыча полезных ископаемых", name_2="Добывающие производства"),
        _Ved(4, "Обрабатывающие производства", name_2="Обрабатывающие производства"),
        _Ved(5, "Строительство", name_2="Строительство"),
        _Ved(
            6,
            "Обеспечение электрической энергией, газом и паром; Кондиционирование воздуха. "
            "Водоснабжение; Водоотведение, организация сбора и утилизация отходов, "
            "деятельность по ликвидации загрязнений",
            name_2="Производство и распределение электроэнергии, газа и воды",
        ),
        _Ved(7, "Домашние хозяйства", name_2="Домашние хозяйства"),
        _Ved(10, "Потери в сетях", name_2="Потери в сетях"),
        _Ved(11, "С.н. электростанций", name_2="С.н. электростанций"),
    ]


def test_build_population_section_for_rf(app):
    ved_types = _ved_types_with_household()
    household_by_year = {2020: Decimal("400"), 2021: Decimal("440")}
    population_by_year = {2020: Decimal("1000"), 2021: Decimal("1010")}

    with app.app_context(), patch.object(
        eis,
        "_aggregate_rf_household_and_population_by_year",
        return_value=(household_by_year, population_by_year),
    ), patch.object(
        eis,
        "_federal_districts_for_page",
        return_value=[],
    ):
        section = eis._build_population_section_for_rf(
            version_id=1,
            ved_types=ved_types,
            display_years=[2020, 2021],
            rounding_digits=1,
            fd_filter_ids=frozenset(),
            current_year=2020,
        )

    assert section["ved_id"] == POPULATION_SECTION_MARKER
    assert section["ved_name"] == POPULATION_SECTION_LABEL
    assert section["has_ei_model_block"] is False
    assert len(section["reference_rows"]) == 3
    assert section["reference_rows"][0]["row_kind"] == REF_ROW_HOUSEHOLD_CONSUMPTION
    assert section["reference_rows"][1]["row_kind"] == REF_ROW_POPULATION
    assert section["reference_rows"][2]["row_kind"] == REF_ROW_ACCUM_MONETARY_INCOME
    assert section["reference_rows"][0]["cells"][2020] == Decimal("400")
    assert section["reference_rows"][1]["cells"][2020] == Decimal("1000")

    per_capita = section["rows"][0]
    assert per_capita["row_kind"] == ROW_KIND_INTENSITY
    expected = eis._quantize_ei_value(
        Decimal("400") / Decimal("1000"),
        1,
        row_kind=ROW_KIND_INTENSITY,
    )
    assert per_capita["cells"][2020] == expected


def test_rf_summary_includes_household_from_fd_aggregate(app):
    ved_types = _ved_types_with_household()
    consumption_by_ved = {
        (3, 2020): Decimal("1000"),
        (4, 2020): Decimal("2000"),
        (5, 2020): Decimal("500"),
        (6, 2020): Decimal("300"),
        (7, 2020): Decimal("9999"),
        (10, 2020): Decimal("300"),
        (11, 2020): Decimal("200"),
    }
    product_by_ved = {
        (3, 2020): Decimal("100"),
        (4, 2020): Decimal("200"),
        (5, 2020): Decimal("50"),
        (6, 2020): Decimal("30"),
        (7, 2020): Decimal("1"),
    }
    household_by_year = {2020: Decimal("400")}

    with app.app_context(), patch.object(
        eis,
        "_load_ved_consumption_values_map",
        return_value=consumption_by_ved,
    ), patch.object(
        eis,
        "_aggregate_fd_maps_for_rf",
        return_value=({}, product_by_ved, {}, None, {}, {}, None),
    ), patch.object(
        eis,
        "_load_rf_gaes_charge_cells",
        return_value={2020: Decimal("100")},
    ), patch.object(
        eis,
        "_resolve_price_year_for_rf_labels",
        return_value=2025,
    ), patch.object(
        eis,
        "_aggregate_rf_household_and_population_by_year",
        return_value=(household_by_year, {2020: Decimal("1000")}),
    ):
        summary = eis._build_rf_territory_summary(
            version_id=1,
            ved_types=ved_types,
            display_years=[2020],
            rounding_digits=1,
            coeff_base_year=2020,
            fd_filter_ids=frozenset(),
            current_year=2020,
        )

    assert summary is not None
    ref_by_kind = {r["row_kind"]: r for r in summary["reference_rows"]}
    # 3800 (ВЭД без домашних хозяйств) + 400 (ФО) = 4200 млн кВт·ч → 4.2 млрд кВт·ч
    assert ref_by_kind[REF_ROW_RF_VED_CONSUMPTION]["cells"][2020] == Decimal("4.2")


def test_rf_ved_sections_skip_household_ved(app):
    ved_types = _ved_types_with_household()

    with app.app_context(), patch.object(
        eis,
        "_aggregate_fd_maps_for_rf",
        return_value=({}, {}, {}, None, {}, {}, None),
    ), patch.object(
        eis,
        "_resolve_price_year_for_rf_labels",
        return_value=2025,
    ), patch.object(
        eis,
        "_find_industrial_component_veds",
        return_value=[],
    ):
        sections = eis._build_ved_sections_for_rf(
            version_id=1,
            ved_types=ved_types,
            display_years=[2020],
            rounding_digits=1,
            coeff_base_year=2020,
            current_year=2020,
            fd_filter_ids=frozenset(),
        )

    ved_names = [s["ved_name"] for s in sections]
    assert "Домашние хозяйства" not in ved_names
