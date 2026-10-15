# -*- coding: utf-8 -*-
"""JSON-набор hour_info: часовые показатели зоны.

Заглушка: схема полей как в контракте интеграций, значения нулевые.
Реальные часовые ряды в АРМ пока не ведутся.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_HOUR_INFO = "hour_info"

KEY_YEAR = "Год"
KEY_ZONE = "Зона для часа"
KEY_MONTH = "Месяц для часа"
KEY_DAY = "День для часа"
KEY_HOUR = "Час"
KEY_POWER = "Часовое потребление мощности"
KEY_ZONE_CODE = "external_code"

HOUR_INFO_COMMENT = (
    "Будет разработано в 2027 году. "
    "Все поля передаются нулями.\n\n"
    "Месяц: (1 - 12)."
)


def build_hour_info_stub_row() -> dict[str, Any]:
    return {
        KEY_YEAR: 0,
        KEY_ZONE: "",
        KEY_MONTH: 0,
        KEY_DAY: 0,
        KEY_HOUR: 0,
        KEY_POWER: 0,
        KEY_ZONE_CODE: "",
    }


def load_hour_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_HOUR_INFO,
        comment=HOUR_INFO_COMMENT,
        row_factory=build_hour_info_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
