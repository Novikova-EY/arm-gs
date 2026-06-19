# -*- coding: utf-8 -*-
"""Юнит-тесты сводных строк РФ на странице электроёмкости."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from app.energy_consumption.electrical_intensity.services import (
    electrical_intensity_services as eis,
)
from app.energy_consumption.electrical_intensity.services.electrical_intensity_constants import (
    REF_ROW_FD_NETWORK_LOSSES,
    REF_ROW_FD_POWER_STATION,
    REF_ROW_FD_TOTAL_CONSUMPTION,
    REF_ROW_FD_VED_CONSUMPTION,
    REF_ROW_RF_GAES,
    REF_ROW_RF_GDP,
    REF_ROW_RF_GDP_INTENSITY,
    REF_ROW_RF_GROWTH_RATE,
    REF_ROW_RF_NETWORK_LOSSES,
    REF_ROW_RF_POWER_STATION,
    REF_ROW_RF_TOTAL_CONSUMPTION,
    REF_ROW_RF_VED_CONSUMPTION,
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


def test_build_rf_territory_summary_rows(app):
    ved_types = _ved_types()
    consumption_by_ved = {
        (3, 2020): Decimal("1000"),
        (4, 2020): Decimal("2000"),
        (5, 2020): Decimal("500"),
        (6, 2020): Decimal("300"),
        (3, 2021): Decimal("1100"),
        (4, 2021): Decimal("2100"),
        (5, 2021): Decimal("550"),
        (6, 2021): Decimal("330"),
        (10, 2020): Decimal("300"),
        (11, 2020): Decimal("200"),
        (10, 2021): Decimal("330"),
        (11, 2021): Decimal("220"),
    }
    product_by_ved = {
        (3, 2020): Decimal("100"),
        (4, 2020): Decimal("200"),
        (5, 2020): Decimal("50"),
        (6, 2020): Decimal("30"),
        (3, 2021): Decimal("110"),
        (4, 2021): Decimal("210"),
        (5, 2021): Decimal("55"),
        (6, 2021): Decimal("33"),
    }
    gaes_cells = {2020: Decimal("100"), 2021: Decimal("110")}

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
        return_value=gaes_cells,
    ), patch.object(
        eis,
        "_resolve_price_year_for_rf_labels",
        return_value=2025,
    ), patch.object(
        eis,
        "_aggregate_rf_summary_chart_intensity_cells",
        return_value={2020: None, 2021: None},
    ):
        summary = eis._build_rf_territory_summary(
            version_id=1,
            ved_types=ved_types,
            display_years=[2020, 2021],
            rounding_digits=1,
            coeff_base_year=2020,
            fd_filter_ids=frozenset(),
            current_year=2020,
        )

    assert summary is not None
    ref_by_kind = {r["row_kind"]: r for r in summary["reference_rows"]}

    assert ref_by_kind[REF_ROW_RF_VED_CONSUMPTION]["cells"][2020] == Decimal("3.8")
    assert ref_by_kind[REF_ROW_RF_TOTAL_CONSUMPTION]["cells"][2020] == Decimal("4.3")
    assert ref_by_kind[REF_ROW_RF_GAES]["cells"][2020] == Decimal("0.1")
    assert ref_by_kind[REF_ROW_RF_GROWTH_RATE]["cells"][2020] is None
    assert ref_by_kind[REF_ROW_RF_GROWTH_RATE]["cells"][2021] == (
        Decimal("4.63") / Decimal("4.3") * Decimal(100) - Decimal(100)
    )
    assert ref_by_kind[REF_ROW_RF_GDP]["row_label"] == "ВВП"
    assert ref_by_kind[REF_ROW_RF_GDP]["cells"][2020] == Decimal("0.38")

    intensity = ref_by_kind[REF_ROW_RF_GDP_INTENSITY]["cells"][2020]
    expected = eis._quantize_ei_value(
        Decimal("4300") / Decimal("380") * Decimal("1000"),
        1,
        row_kind=ROW_KIND_INTENSITY,
    )
    assert intensity == expected
    assert ref_by_kind[REF_ROW_RF_GROWTH_RATE]["label_em"] is True


def test_build_rf_territory_summary_from_fd_summaries_plan_years(app):
    """Сводка РФ по всем годам — сумма сводок ФО с прогнозом на плановые годы."""
    ved_types = _ved_types()
    fd_summary_a = {
        "reference_rows": [
            {
                "row_kind": REF_ROW_FD_VED_CONSUMPTION,
                "cells": {2020: Decimal("2.0"), 2021: Decimal("2.5")},
            },
            {
                "row_kind": REF_ROW_FD_NETWORK_LOSSES,
                "cells": {2020: Decimal("0.2"), 2021: Decimal("0.25")},
            },
            {
                "row_kind": REF_ROW_FD_POWER_STATION,
                "cells": {2020: Decimal("0.1"), 2021: Decimal("0.15")},
            },
            {
                "row_kind": REF_ROW_FD_TOTAL_CONSUMPTION,
                "cells": {2020: Decimal("2.3"), 2021: Decimal("2.9")},
            },
        ]
    }
    fd_summary_b = {
        "reference_rows": [
            {
                "row_kind": REF_ROW_FD_VED_CONSUMPTION,
                "cells": {2020: Decimal("1.8"), 2021: Decimal("2.1")},
            },
            {
                "row_kind": REF_ROW_FD_NETWORK_LOSSES,
                "cells": {2020: Decimal("0.18"), 2021: Decimal("0.21")},
            },
            {
                "row_kind": REF_ROW_FD_POWER_STATION,
                "cells": {2020: Decimal("0.09"), 2021: Decimal("0.11")},
            },
            {
                "row_kind": REF_ROW_FD_TOTAL_CONSUMPTION,
                "cells": {2020: Decimal("2.07"), 2021: Decimal("2.42")},
            },
        ]
    }
    product_by_ved = {
        (3, 2020): Decimal("100"),
        (4, 2020): Decimal("200"),
        (5, 2020): Decimal("50"),
        (6, 2020): Decimal("30"),
        (3, 2021): Decimal("110"),
        (4, 2021): Decimal("210"),
        (5, 2021): Decimal("55"),
        (6, 2021): Decimal("33"),
    }

    with app.app_context(), patch.object(
        eis,
        "_aggregate_fd_maps_for_rf",
        return_value=({}, product_by_ved, {}, None, {}, {}, None),
    ), patch.object(
        eis,
        "_load_rf_gaes_charge_cells",
        return_value={2020: Decimal("100"), 2021: Decimal("110")},
    ), patch.object(
        eis,
        "_resolve_price_year_for_rf_labels",
        return_value=2025,
    ), patch.object(
        eis,
        "_aggregate_rf_summary_chart_intensity_cells",
        return_value={2020: None, 2021: None},
    ):
        summary = eis._build_rf_territory_summary(
            version_id=1,
            ved_types=ved_types,
            display_years=[2020, 2021],
            rounding_digits=1,
            coeff_base_year=2020,
            fd_filter_ids=frozenset(),
            current_year=2020,
            fd_summaries=[fd_summary_a, fd_summary_b],
        )

    assert summary is not None
    ref_by_kind = {r["row_kind"]: r for r in summary["reference_rows"]}
    assert ref_by_kind[REF_ROW_RF_VED_CONSUMPTION]["cells"][2021] == Decimal("4.6")
    assert ref_by_kind[REF_ROW_RF_NETWORK_LOSSES]["cells"][2021] == Decimal("0.46")
    assert ref_by_kind[REF_ROW_RF_POWER_STATION]["cells"][2021] == Decimal("0.26")
    assert ref_by_kind[REF_ROW_RF_TOTAL_CONSUMPTION]["cells"][2021] == Decimal("5.32")
