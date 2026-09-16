# -*- coding: utf-8 -*-
"""JSON-набор power_energy_export_import_country: экспорт/импорт по странам.

Заглушка до реализации в АРМ: схема полей как в контракте интеграций,
значения нулевые.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_POWER_ENERGY_EXPORT_IMPORT_COUNTRY = "power_energy_export_import_country"

KEY_COUNTRY = "Страна/ЕЭС"
KEY_YEAR = "Год"
KEY_ENERGY = "Энергия, млн кВт•ч"
KEY_POWER = "Мощность, МВт"
KEY_DIRECTION = "Направление"
KEY_COUNTRY_CODE = "external_code"

POWER_ENERGY_EXPORT_IMPORT_COUNTRY_COMMENT = (
    "Пока в АРМ не реализовано, будет сделано в 2026 году."
)


def build_power_energy_export_import_country_stub_row() -> dict[str, Any]:
    return {
        KEY_COUNTRY: "",
        KEY_YEAR: 0,
        KEY_ENERGY: 0,
        KEY_POWER: 0,
        KEY_DIRECTION: "",
        KEY_COUNTRY_CODE: "",
    }


def load_power_energy_export_import_country_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_POWER_ENERGY_EXPORT_IMPORT_COUNTRY,
        comment=POWER_ENERGY_EXPORT_IMPORT_COUNTRY_COMMENT,
        row_factory=build_power_energy_export_import_country_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
