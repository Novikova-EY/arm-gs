# -*- coding: utf-8 -*-
"""JSON-набор substations_customers_info: потребители подстанций.

Заглушка до 2027 года: схема полей как в контракте интеграций,
значения нулевые.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_SUBSTATIONS_CUSTOMERS_INFO = "substations_customers_info"

KEY_SUBSTATION_NAME = "Название подстанции"
KEY_GENERAL_INFO = (
    "Общая информация по заявителю/дате заключения договора/номера договора "
    "(если есть)"
)
KEY_APPLICANT = "Заявитель"
KEY_CONTRACT_DATE = "Дата заключения договора ТП "
KEY_CONTRACT_NUMBER = "Номер договора ТП"
KEY_PLANNED_YEAR = "Планируемый год реализации ТП"
KEY_MAX_POWER = "Максимальная мощность по ТУ для ТП, МВт"
KEY_PREV_POWER = "Ранее присоединенная мощность (по документам о ТП), МВт"
KEY_UNOM = "Uном перспективной нагрузки, кВ"
KEY_LOAD_GROWTH = (
    "Прирост нагрузки по ТУ для ТП с учетом коэффициента набора, МВт"
)
KEY_PS_NAME = "Наименование ПС"
KEY_CODE = "external_code"

SUBSTATIONS_CUSTOMERS_INFO_COMMENT = (
    "Будет реализовано в 2027 году. "
    "Все поля передаются нулями.\n\n"
    "Содержит все потребители всех субъектов трансформаторных подстанций."
)


def build_substations_customers_info_stub_row() -> dict[str, Any]:
    return {
        KEY_SUBSTATION_NAME: "",
        KEY_GENERAL_INFO: "",
        KEY_APPLICANT: "",
        KEY_CONTRACT_DATE: "",
        KEY_CONTRACT_NUMBER: "",
        KEY_PLANNED_YEAR: 0,
        KEY_MAX_POWER: 0,
        KEY_PREV_POWER: 0,
        KEY_UNOM: 0,
        KEY_LOAD_GROWTH: 0,
        KEY_PS_NAME: "",
        KEY_CODE: "",
    }


def load_substations_customers_info_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_SUBSTATIONS_CUSTOMERS_INFO,
        comment=SUBSTATIONS_CUSTOMERS_INFO_COMMENT,
        row_factory=build_substations_customers_info_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
