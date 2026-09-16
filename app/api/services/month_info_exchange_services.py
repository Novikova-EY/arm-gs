# -*- coding: utf-8 -*-
"""JSON-набор month_info: месячные показатели зоны.

Заглушка до 2027 года: схема полей как в контракте интеграций,
значения нулевые. Реальные месячные ряды в АРМ пока не ведутся.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_MONTH_INFO = "month_info"

KEY_YEAR = "Год"
KEY_ZONE = "Зона для месяца"
KEY_MONTH = "Месяц"
KEY_MAX_POWER = "Месячное максимальное потребление мощности"
KEY_POWER = "Месячное потребление мощности"
KEY_TEMP = "Месячная среднесуточная температура"
KEY_ZONE_CODE = "external_code"

MONTH_INFO_COMMENT = (
    "Будет разработано в 2027 году. "
    "Все поля передаются нулями.\n\n"
    "Месяц: (1 - 12)."
)


def build_month_info_stub_row() -> dict[str, Any]:
    return {
        KEY_YEAR: 0,
        KEY_ZONE: "",
        KEY_MONTH: 0,
        KEY_MAX_POWER: 0,
        KEY_POWER: 0,
        KEY_TEMP: 0,
        KEY_ZONE_CODE: "",
    }


def load_month_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_MONTH_INFO,
        comment=MONTH_INFO_COMMENT,
        row_factory=build_month_info_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
