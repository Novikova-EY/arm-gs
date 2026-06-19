# -*- coding: utf-8 -*-
"""Юнит-тесты секций ВЭД на уровне РФ (агрегат по ФО)."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from app.energy_consumption.electrical_intensity.services import (
    electrical_intensity_services as eis,
)
from app.energy_consumption.electrical_intensity.services.electrical_intensity_constants import (
    INDUSTRIAL_GROUP_SECTION_LABEL,
    REF_ROW_CONSUMPTION,
    REF_ROW_PRODUCT_OUTPUT,
    RF_VED_INTENSITY_ROW_LABEL,
    ROW_KIND_INTENSITY,
)


class _Ved:
    def __init__(self, ved_id: int, name: str, *, name_2: str | None = None):
        self.id = ved_id
        self.name = name
        self.name_2 = name_2
        self.display_order = ved_id


class _Fd:
    def __init__(self, fd_id: int):
        self.id = fd_id
        self.name = f"ФО {fd_id}"
        self.name_full = f"ФО {fd_id}"
        self.name_abr = f"ФО{fd_id}"


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
    ]


def test_build_ved_sections_for_rf_aggregates_fd_values(app):
    ved_types = _ved_types()
    fds = [_Fd(1), _Fd(2)]

    def _product_map(fd_id: int):
        base = 100 if fd_id == 1 else 50
        return {
            (4, 2020): Decimal(str(base)),
            (4, 2021): Decimal(str(base + 10)),
        }

    def _consumption_map(fd_id: int):
        base = 1000 if fd_id == 1 else 500
        return {
            (4, 2020): Decimal(str(base)),
            (4, 2021): Decimal(str(base + 100)),
        }

    def _fake_load_product(*, version_id, model, territory_filter):
        _ = version_id, model
        fd_id = territory_filter.right.value
        return _product_map(fd_id)

    def _fake_load_consumption(*, version_id, model, territory_filter):
        _ = version_id, model
        fd_id = territory_filter.right.value
        return _consumption_map(fd_id)

    with app.app_context(), patch.object(
        eis, "_federal_districts_for_page", return_value=fds
    ), patch.object(
        eis, "_load_product_output_values_map", side_effect=_fake_load_product
    ), patch.object(
        eis, "_load_ved_consumption_values_map", side_effect=_fake_load_consumption
    ), patch.object(
        eis, "_load_accum_fixed_capital_values_map", return_value={}
    ), patch.object(
        eis, "_load_fd_ei_year_values_map", return_value={}
    ), patch.object(
        eis, "_resolve_price_year_for_rf_labels", return_value=2025
    ):
        sections = eis._build_ved_sections_for_rf(
            version_id=1,
            ved_types=ved_types,
            display_years=[2020, 2021],
            rounding_digits=1,
            coeff_base_year=2020,
            current_year=2020,
            fd_filter_ids=frozenset(),
        )

    industrial = next(s for s in sections if s["ved_name"] == INDUSTRIAL_GROUP_SECTION_LABEL)
    manufacturing = next(s for s in sections if s["ved_name"] == "Обрабатывающие производства")

    prod_row = next(
        r for r in manufacturing["reference_rows"] if r["row_kind"] == REF_ROW_PRODUCT_OUTPUT
    )
    assert prod_row["row_label"] == "Выпуск продукции"
    assert prod_row["unit_label"] == "млрд руб."
    assert prod_row["cells"][2020] == Decimal("0.15")

    cons_row = next(
        r for r in manufacturing["reference_rows"] if r["row_kind"] == REF_ROW_CONSUMPTION
    )
    assert cons_row["cells"][2020] == Decimal("1500")

    intensity_row = next(
        r for r in manufacturing["rows"] if r["row_kind"] == ROW_KIND_INTENSITY
    )
    assert intensity_row["row_label"] == RF_VED_INTENSITY_ROW_LABEL
    fd1_intensity = eis._quantize_ei_value(
        Decimal("1000") / Decimal("100") * Decimal("1000"), 1, row_kind=ROW_KIND_INTENSITY
    )
    fd2_intensity = eis._quantize_ei_value(
        Decimal("500") / Decimal("50") * Decimal("1000"), 1, row_kind=ROW_KIND_INTENSITY
    )
    assert intensity_row["cells"][2020] == fd1_intensity + fd2_intensity

    assert industrial["has_ei_model_block"] is False
    assert manufacturing["has_ei_model_block"] is False
