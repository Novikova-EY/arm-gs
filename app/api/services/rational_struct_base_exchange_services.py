# -*- coding: utf-8 -*-
"""JSON-набор rational_struct_base: базовые показатели рациональной структуры.

Заглушка: схема полей как в контракте интеграций, значения нулевые.
Таблицы 22, 23 и 24 отчёта этапа 3 будут разработаны в 2027 году.
"""
from __future__ import annotations

from typing import Any

from app.api.services.exchange_common_services import load_stub_exchange_dataset

DATASET_RATIONAL_STRUCT_BASE = "rational_struct_base"

KEY_STATION_TYPE = "Тип станций"
KEY_YEAR = "Год"
KEY_BASE_CAPEX = "Базовые удельные капитальные затраты, тыс. руб./кВт"
KEY_FIXED_COST = "Условно-постоянные затраты, тыс. руб./кВт/год"
# Ключ с завершающим пробелом – как в контракте интеграций.
KEY_SPECIFIC_FUEL = "Удельный расход условного топлива, "
KEY_CONDENSING = "в конденсационном режиме, г у.т./кВт•ч"
KEY_HEAT_EXTRACTION = "в теплофикационном режиме, г у.т./кВт•ч"
KEY_FUEL_COST = "Топливные затраты, руб./кВт•ч"
KEY_OWN_NEEDS = "Расход электрической энергии на собственные нужды, %"
KEY_CONSTRUCTION_YEARS = "Срок строительства, лет"
KEY_UTILIZATION_HOURS = "Число часов использования установленной мощности, ч/год"
KEY_DECOMMISSION_COST = "Затраты на вывод из эксплуатации, тыс. руб./кВт"
KEY_OES = "ОЭС"
KEY_FUEL_PRICE = "Цена топлива на год, тыс. руб./т у.т."
# Ключ с завершающим пробелом – как в контракте интеграций.
KEY_REGIONAL_COEFF = "Региональный коэффициент удорожания, "
KEY_LCOE_BASE = "LCOE (базовые), руб./кВт•ч в ценах расчетного года"
KEY_LCOE_PEAK = "LCOE (пиковые), руб./кВт•ч в ценах расчетного года"
KEY_LCOE_NON_GUARANTEED = (
    "LCOE (негарантированные), руб./кВт•ч в ценах расчетного года"
)
KEY_CODE = "external_code"

# Ответ на вопросы контракта по таблицам 22–24 отчёта этапа 3.
RATIONAL_STRUCT_BASE_COMMENT = (
    "вопрос 1: Какие данные должны быть в таблице 22? (отчет этап 3, стр. 352) "
    "– будет разработано в 2027 году;\n"
    "вопрос 2: Какие данные должны быть в таблице 23? (отчет этап 3, стр. 359) "
    "– будет разработано в 2027 году;\n"
    "вопрос 3: Какие данные должны быть в таблице 24? (отчет этап 3, стр. 367)\n"
    "Соответвующий раздел в АРМ будет разработан в 2027 году."
)


def build_rational_struct_base_stub_row() -> dict[str, Any]:
    return {
        KEY_STATION_TYPE: "",
        KEY_YEAR: 0,
        KEY_BASE_CAPEX: 0,
        KEY_FIXED_COST: 0,
        KEY_SPECIFIC_FUEL: 0,
        KEY_CONDENSING: 0,
        KEY_HEAT_EXTRACTION: 0,
        KEY_FUEL_COST: 0,
        KEY_OWN_NEEDS: 0,
        KEY_CONSTRUCTION_YEARS: 0,
        KEY_UTILIZATION_HOURS: 0,
        KEY_DECOMMISSION_COST: 0,
        KEY_OES: "",
        KEY_FUEL_PRICE: 0.0,
        KEY_REGIONAL_COEFF: 0.0,
        KEY_LCOE_BASE: 0.0,
        KEY_LCOE_PEAK: 0.0,
        KEY_LCOE_NON_GUARANTEED: 0.0,
        KEY_CODE: "",
    }


def load_rational_struct_base_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    return load_stub_exchange_dataset(
        DATASET_RATIONAL_STRUCT_BASE,
        comment=RATIONAL_STRUCT_BASE_COMMENT,
        row_factory=build_rational_struct_base_stub_row,
        version_id=version_id,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
