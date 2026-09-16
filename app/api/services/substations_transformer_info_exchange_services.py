# -*- coding: utf-8 -*-
"""JSON-набор substations_transformer_info: трансформаторы подстанций.

Заглушка: схема полей как в контракте интеграций, значения нулевые.
Этих параметров в АРМ нет, они заполняются вручную.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_SUBSTATIONS_TRANSFORMER_INFO = "substations_transformer_info"

KEY_SUBSTATION_NAME = "Название подстанции"
KEY_SUBJECT = "Субъект подстанции"
KEY_YEAR = "Год"
KEY_VOLTAGE_CLASS = "Класс напряжения ПС, кВ"
KEY_TRANSFORMER_NAME = "Название трансформатора"
KEY_TRANSFORMER_TYPE = "Тип трансформатора"
KEY_COMMISSION_YEAR = "Год ввода трансформатора в эксплуатацию"
KEY_ITS = "ИТС"
KEY_POWER = "Мощность трансформатора, МВт"
KEY_WINTER_LOAD = "Фактическая нагрузка, день зимнего контрольного замера, МВА"
KEY_SUMMER_LOAD = "Фактическая нагрузка, день летнего контрольного замера, МВА"
KEY_LOAD_TRANSFER = (
    "Объем перевода нагрузки по сети 6–35 кВ в течение 20 минут "
    "после нормативных возмущений, МВА"
)
KEY_CODE = "external_code"

SUBSTATIONS_TRANSFORMER_INFO_COMMENT = (
    "Данных параметров нет в АРМ, поэтому они заполняются вручную.\n\n"
    "Содержит все трансформаторы всех субъектов."
)


def build_substations_transformer_info_stub_row() -> dict[str, Any]:
    return {
        KEY_SUBSTATION_NAME: "",
        KEY_SUBJECT: "",
        KEY_YEAR: 0,
        KEY_VOLTAGE_CLASS: "",
        KEY_TRANSFORMER_NAME: "",
        KEY_TRANSFORMER_TYPE: "",
        KEY_COMMISSION_YEAR: 0,
        KEY_ITS: 0,
        KEY_POWER: 0,
        KEY_WINTER_LOAD: 0,
        KEY_SUMMER_LOAD: 0,
        KEY_LOAD_TRANSFER: 0,
        KEY_CODE: "",
    }


def load_substations_transformer_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_SUBSTATIONS_TRANSFORMER_INFO,
        comment=SUBSTATIONS_TRANSFORMER_INFO_COMMENT,
        row_factory=build_substations_transformer_info_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
