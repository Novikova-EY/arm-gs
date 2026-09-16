# -*- coding: utf-8 -*-
"""JSON-набор substations_load_info: перспективная загрузка подстанций.

Заглушка: схема полей как в контракте интеграций, значения нулевые.
Этих параметров в АРМ нет, они заполняются вручную.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_SUBSTATIONS_LOAD_INFO = "substations_load_info"

KEY_SUBSTATION_NAME = "Название подстанции"
KEY_SUBJECT = "Субъект подстанции"
KEY_YEAR = "Год"
KEY_LOAD = "Перспективная нагрузка, МВА"
KEY_CODE = "external_code"

SUBSTATIONS_LOAD_INFO_COMMENT = (
    "Данных параметров нет в АРМ, поэтому они заполняются вручную.\n\n"
    "Содержит перспективную загрузку всех трансформаторных подстанций."
)


def build_substations_load_info_stub_row() -> dict[str, Any]:
    return {
        KEY_SUBSTATION_NAME: "",
        KEY_SUBJECT: "",
        KEY_YEAR: 0,
        KEY_LOAD: 0,
        KEY_CODE: "",
    }


def load_substations_load_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_SUBSTATIONS_LOAD_INFO,
        comment=SUBSTATIONS_LOAD_INFO_COMMENT,
        row_factory=build_substations_load_info_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
