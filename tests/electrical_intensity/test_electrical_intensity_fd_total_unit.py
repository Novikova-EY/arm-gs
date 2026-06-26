# -*- coding: utf-8 -*-
"""Юнит-тесты сводных строк ФО на странице электроёмкости."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest

from app.electrical_intensity.services import (
    electrical_intensity_services as eis,
)
from app.electrical_intensity.services.electrical_intensity_constants import (
    FD_TOTAL_SECTION_LABEL,
    INDUSTRIAL_GROUP_SECTION_LABEL,
    REF_ROW_CONSUMPTION,
    REF_ROW_FD_NETWORK_LOSSES,
    REF_ROW_FD_POWER_STATION,
    REF_ROW_FD_TOTAL_CONSUMPTION,
    REF_ROW_FD_VED_CONSUMPTION,
    REF_ROW_FD_VRP,
    REF_ROW_HOUSEHOLD_CONSUMPTION,
    ROW_KIND_INTENSITY,
)


class _Ved:
    def __init__(self, ved_id: int, name: str, *, name_2: str | None = None):
        self.id = ved_id
        self.name = name
        self.name_2 = name_2
        self.display_order = ved_id


@pytest.fixture(autouse=True)
def _stub_refdata_ved_types_for_fd_total(monkeypatch):
    monkeypatch.setattr(
        eis,
        "_refdata_ved_types_for_version",
        lambda version_id: [],
    )


def _ved_types(*, with_household: bool = False) -> list[_Ved]:
    types = [
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
    if with_household:
        types.insert(-2, _Ved(7, "Домашние хозяйства", name_2="Домашние хозяйства"))
    return types


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
            fd_id=1,
            version_id=None,
            ved_types=ved_types,
            product_output_by_ved_year=product_by_ved,
            consumption_by_ved_year=consumption_by_ved,
            accum_by_ved_year=accum_by_ved,
            coef_by_ved={},
            display_years=[2020],
            rounding_digits=1,
            price_year=2020,
            current_year=2020,
            coefficient_k_by_row_kind={},
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


def test_build_fd_territory_summary_forecast_consumption_years(app):
    """Прогноз потребления в сводке ФО — для всех лет, не только до текущего."""
    ved_types = _ved_types()
    product_by_ved = {
        (3, 2020): Decimal("100"),
        (3, 2021): Decimal("200"),
        (4, 2020): Decimal("200"),
        (4, 2021): Decimal("400"),
        (5, 2020): Decimal("50"),
        (5, 2021): Decimal("100"),
        (6, 2020): Decimal("30"),
        (6, 2021): Decimal("60"),
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
            fd_id=1,
            version_id=None,
            ved_types=ved_types,
            product_output_by_ved_year=product_by_ved,
            consumption_by_ved_year=consumption_by_ved,
            accum_by_ved_year=accum_by_ved,
            coef_by_ved={},
            display_years=[2020, 2021],
            rounding_digits=1,
            price_year=2020,
            current_year=2020,
            coefficient_k_by_row_kind={},
        )
    ref_by_kind = {r["row_kind"]: r for r in summary["reference_rows"]}
    assert ref_by_kind[REF_ROW_FD_VED_CONSUMPTION]["cells"][2021] is not None
    assert ref_by_kind[REF_ROW_FD_TOTAL_CONSUMPTION]["cells"][2021] is not None
    assert ref_by_kind[REF_ROW_FD_NETWORK_LOSSES]["cells"][2021] is not None
    assert ref_by_kind[REF_ROW_FD_POWER_STATION]["cells"][2021] is not None


def test_build_fd_territory_summary_plan_years_use_k_coefficient(app):
    """Плановые годы «Потери в сетях» и «С.н. электростанций» = потребление ВЭД × k."""
    ved_types = _ved_types()
    product_by_ved = {
        (3, 2020): Decimal("100"),
        (3, 2021): Decimal("200"),
        (4, 2020): Decimal("200"),
        (4, 2021): Decimal("400"),
        (5, 2020): Decimal("50"),
        (5, 2021): Decimal("100"),
        (6, 2020): Decimal("30"),
        (6, 2021): Decimal("60"),
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
    nl_k = Decimal("0.1")
    ps_k = Decimal("0.05")
    k_by_kind = {
        REF_ROW_FD_NETWORK_LOSSES: nl_k,
        REF_ROW_FD_POWER_STATION: ps_k,
    }
    with app.app_context():
        summary = eis._build_fd_territory_summary(
            fd_id=1,
            version_id=None,
            ved_types=ved_types,
            product_output_by_ved_year=product_by_ved,
            consumption_by_ved_year=consumption_by_ved,
            accum_by_ved_year=accum_by_ved,
            coef_by_ved={},
            display_years=[2020, 2021],
            rounding_digits=1,
            price_year=2020,
            current_year=2020,
            year_features={},
            coefficient_k_by_row_kind=k_by_kind,
        )
        cells = eis._build_fd_summary_consumption_cells(
            ved_types=ved_types,
            sum_ved_ids=eis._ved_ids_for_fd_total_sums(ved_types),
            consumption_by_ved_year=consumption_by_ved,
            product_output_by_ved_year=product_by_ved,
            accum_by_ved_year=accum_by_ved,
            coef_by_ved={},
            display_years=[2020, 2021],
            current_year=2020,
            year_features={},
            coefficient_k_by_row_kind=k_by_kind,
        )
    ref_by_kind = {r["row_kind"]: r for r in summary["reference_rows"]}
    ved_2021_mln = cells[0].get(2021)
    nl_2021_mln = cells[1].get(2021)
    ps_2021_mln = cells[2].get(2021)
    assert ved_2021_mln is not None
    assert nl_2021_mln == ved_2021_mln * nl_k
    assert ps_2021_mln == ved_2021_mln * ps_k
    assert ref_by_kind[REF_ROW_FD_NETWORK_LOSSES]["has_coefficient_k"] is True
    assert ref_by_kind[REF_ROW_FD_POWER_STATION]["has_coefficient_k"] is True


def test_sum_displayed_ved_consumption_skips_industrial_group(app):
    ved_sections = [
        {
            "is_industrial_group": True,
            "reference_rows": [
                {
                    "row_kind": REF_ROW_CONSUMPTION,
                    "cells": {2020: Decimal("9999")},
                }
            ],
        },
        {
            "ved_name": "Строительство",
            "reference_rows": [
                {
                    "row_kind": REF_ROW_CONSUMPTION,
                    "cells": {2020: Decimal("500")},
                }
            ],
        },
        {
            "is_population_section": True,
            "reference_rows": [
                {
                    "row_kind": REF_ROW_HOUSEHOLD_CONSUMPTION,
                    "cells": {2020: Decimal("400")},
                }
            ],
        },
    ]
    cells = eis._sum_displayed_ved_consumption_from_fd_sections(
        ved_sections,
        display_years=[2020],
    )
    assert cells[2020] == Decimal("900")


def test_build_fd_territory_summary_includes_household_consumption(app):
    ved_types = _ved_types(with_household=True)
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
        (7, 2020): Decimal("400"),
        (10, 2020): Decimal("300"),
        (11, 2020): Decimal("200"),
    }
    accum_by_ved = {
        (3, 2020): Decimal("10"),
        (4, 2020): Decimal("20"),
        (5, 2020): Decimal("5"),
        (6, 2020): Decimal("3"),
    }
    household_by_year = {2020: Decimal("400")}

    with app.app_context(), patch.object(
        eis,
        "_refdata_ved_types_for_version",
        return_value=ved_types,
    ), patch.object(
        eis,
        "_compute_household_consumption_by_year_for_fd",
        return_value=household_by_year,
    ):
        summary = eis._build_fd_territory_summary(
            fd_id=1,
            version_id=1,
            ved_types=ved_types,
            product_output_by_ved_year=product_by_ved,
            consumption_by_ved_year=consumption_by_ved,
            accum_by_ved_year=accum_by_ved,
            coef_by_ved={},
            display_years=[2020],
            rounding_digits=1,
            price_year=2020,
            current_year=2020,
            coefficient_k_by_row_kind={},
        )

    assert summary is not None
    ref_by_kind = {r["row_kind"]: r for r in summary["reference_rows"]}
    # 3800 (ВЭД) + 400 (домашние хозяйства) = 4200 млн кВт·ч → 4.2 млрд кВт·ч
    assert ref_by_kind[REF_ROW_FD_VED_CONSUMPTION]["cells"][2020] == Decimal("4.2")
    assert ref_by_kind[REF_ROW_FD_TOTAL_CONSUMPTION]["cells"][2020] == Decimal("4.7")
