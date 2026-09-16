# -*- coding: utf-8 -*-
"""JSON-набор load_forecast: прогноз потребления.

Заглушка: набор пока не используется, данные есть в gentypes_info.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_LOAD_FORECAST = "load_forecast"

KEY_YEAR = "Год"
KEY_TYPE = "Тип"
KEY_SUBJECT = "Субъект прогноза"
KEY_CONSUMPTION = "Потребление электрической энергии, млн кВт•ч"
KEY_CONSUMPTION_WITHOUT_GAES = (
    "Потребление электрической энергии без учета ГАЭС в насосном режиме, млн кВт•ч"
)
KEY_CODE = "external_code"

LOAD_FORECAST_COMMENT = (
    "Пока не используется, информация есть в gen_types_info.json"
)


def build_load_forecast_stub_row() -> dict[str, Any]:
    return {
        KEY_YEAR: 0,
        KEY_TYPE: "",
        KEY_SUBJECT: "",
        KEY_CONSUMPTION: 0,
        KEY_CONSUMPTION_WITHOUT_GAES: 0,
        KEY_CODE: "",
    }


def load_load_forecast_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_LOAD_FORECAST,
        comment=LOAD_FORECAST_COMMENT,
        row_factory=build_load_forecast_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
