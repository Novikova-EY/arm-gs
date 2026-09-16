# -*- coding: utf-8 -*-
"""JSON-набор substations_overload_transformer: точки перегрузки трансформаторов.

Заглушка: схема полей как в контракте интеграций, значения нулевые.
Этих параметров в АРМ нет, они заполняются вручную.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_SUBSTATIONS_OVERLOAD_TRANSFORMER = "substations_overload_transformer"

KEY_SUBSTATION_NAME = "Название подстанции"
KEY_TRANSFORMER_NAME = "Название трансформатора"
KEY_TEMP = "Температура, °С"
KEY_OVERLOAD = "Значение перегрузки, о.е."
KEY_CODE = "external_code"

SUBSTATIONS_OVERLOAD_TRANSFORMER_COMMENT = (
    "Данных параметров нет в АРМ, поэтому они заполняются вручную.\n\n"
    "Содержит все точки перегрузки трансформаторов всех субъектов."
)


def build_substations_overload_transformer_stub_row() -> dict[str, Any]:
    return {
        KEY_SUBSTATION_NAME: "",
        KEY_TRANSFORMER_NAME: "",
        KEY_TEMP: 0,
        KEY_OVERLOAD: 0,
        KEY_CODE: "",
    }


def load_substations_overload_transformer_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_SUBSTATIONS_OVERLOAD_TRANSFORMER,
        comment=SUBSTATIONS_OVERLOAD_TRANSFORMER_COMMENT,
        row_factory=build_substations_overload_transformer_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
