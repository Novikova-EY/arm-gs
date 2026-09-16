# -*- coding: utf-8 -*-
"""JSON-набор newlines_building: титулы нового строительства ЛЭП.

Заглушка: схема полей как в контракте интеграций, значения нулевые.
Этих параметров в АРМ нет, они заполняются вручную.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import (
    MANUAL_FILL_EXCHANGE_COMMENT,
    load_stub_exchange_dataset,
)

DATASET_NEWLINES_BUILDING = "newlines_building"

KEY_TITLE_NAME = "Наименование титула"
KEY_SUBJECT = "Субъект документа"
KEY_KM = "Км по титулу, км"
KEY_MVA = "МВА по титулу, МВА"
KEY_COMMISSION_YEAR = "Год ввода по титулу"
KEY_TITLE_CODE = "external_code"

NEWLINES_BUILDING_COMMENT = MANUAL_FILL_EXCHANGE_COMMENT


def build_newlines_building_stub_row() -> dict[str, Any]:
    return {
        KEY_TITLE_NAME: "",
        KEY_SUBJECT: "",
        KEY_KM: 0,
        KEY_MVA: 0,
        KEY_COMMISSION_YEAR: 0,
        KEY_TITLE_CODE: "",
    }


def load_newlines_building_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_NEWLINES_BUILDING,
        comment=NEWLINES_BUILDING_COMMENT,
        row_factory=build_newlines_building_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
