# -*- coding: utf-8 -*-
"""JSON-набор daymonth_info: суточные показатели зоны.

Заглушка до 2027 года: схема полей как в контракте интеграций,
значения нулевые. Реальные суточные ряды в АРМ пока не ведутся.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_DAYMONTH_INFO = "daymonth_info"

KEY_YEAR = "Год"
KEY_ZONE = "Зона для дня"
KEY_MONTH = "Месяц для дня"
KEY_DAY = "День"
KEY_MAX_POWER = "Дневное максимальное потребление мощности"
KEY_POWER = "Дневное потребление мощности"
KEY_TEMP = "Дневная среднесуточная температура"
KEY_ZONE_CODE = "external_code"

DAYMONTH_INFO_COMMENT = (
    "Данный подраздел будет реализован в 2027 году. "
    "Все поля передаются нулями.\n\n"
    "Месяц: (1 - 12). Должен быть уникальный идентификатор."
)


def build_daymonth_info_stub_row() -> dict[str, Any]:
    return {
        KEY_YEAR: 0,
        KEY_ZONE: "",
        KEY_MONTH: 0,
        KEY_DAY: 0,
        KEY_MAX_POWER: 0,
        KEY_POWER: 0,
        KEY_TEMP: 0,
        KEY_ZONE_CODE: "",
    }


def load_daymonth_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_DAYMONTH_INFO,
        comment=DAYMONTH_INFO_COMMENT,
        row_factory=build_daymonth_info_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
