"""Исходные параметры расчета из таблицы технологий по территориям."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.services.exchange_common_services import (
    clip_years,
    dataset_envelope,
    resolve_database_version,
)
from app.extensions import db
from app.rational_structure.models.territory_technology_model import TerritoryTechnology
from app.rational_structure.services.territory_technology_matching import FUEL_CATEGORIES
from app.refdata.services.year_management_services import (
    get_current_year_info,
    get_general_scheme_end_year,
)

DATASET_RATIONAL_STRUCT_IMPORT_TO_JAVA = "rational_struct_import_to_java"

RATIONAL_STRUCT_IMPORT_COMMENT = (
    "Год - значение, для которого производится расчет рац. структуры, например, 2026. "
    "По умолчанию используется год окончания периода Генеральной схемы "
    "со страницы /refdata/ выбранной версии БД. "
    "Исходное приближенное значение отсутствует в АРМ ГС и передается как null. "
    "external_code - отсутствует в АРМ ГС и передается как null"
)

# Названия и порядок полей соответствуют контракту интеграций.
TECHNOLOGY_EXCHANGE_FIELDS = (
    ("КИУМ по квартально (1)", "capacity_factor_1"),
    ("КИУМ по квартально (2)", "capacity_factor_2"),
    ("КИУМ по квартально (3)", "capacity_factor_3"),
    ("КИУМ по квартально (4)", "capacity_factor_4"),
    ("СКО, о.е.", "standard_deviation"),
    ("Капитальные затраты, млн. руб./МВт", "capital_cost"),
    ("Затраты на модернизацию, млн руб./МВт", "modernization_cost"),
    ("Топл.затраты (ОЗП), руб./кВт.ч", "fuel_cost_winter"),
    ("Топл.затраты (ВЛП), руб./кВт.ч", "fuel_cost_summer"),
    ("Усл.пост.затраты, млн руб./МВт.год", "fixed_cost"),
    ("Затраты на передачу ЕНЭС, руб./кВт.ч", "transmission_cost"),
    ("Вер-ть простоя (ОЗП)", "outage_probability_winter"),
    ("Вер-ть простоя (ВЛП)", "outage_probability_summer"),
    ("Эмиссия СО2", "co2_per_energy"),
    ("Количество единиц или МВт на год конца ПДП. Мин.", "quantity_min"),
    ("Количество единиц или МВт на год конца ПДП. Мод.", "quantity_mod"),
    ("Количество единиц или МВт на год конца ПДП. Макс.", "quantity_max"),
)


def build_rational_struct_import_row(
    technology: TerritoryTechnology, year: int,
) -> dict[str, Any]:
    fuel = FUEL_CATEGORIES.get(technology.fuel_category, "").lower()
    if technology.fuel_category == "other" and technology.technology_type is not None:
        if technology.technology_type.name == "АЭС":
            fuel = "атомное"
    minimum_power = None
    if technology.minimum_power is not None and technology.unit_power is not None:
        minimum_power = technology.minimum_power * technology.unit_power
    zone = technology.energy_zone
    row = {
        "Тип технологии": technology.name,
        "Тип топлива для технологии": fuel,
        "Год": year,
        "Код энергозоны (код, используемый при задании исходных данных)": (
            int(zone.number) if zone.number.isdigit() else zone.number
        ),
        "Ред., МВт": technology.unit_power,
        "Рmin, МВт": minimum_power,
    }
    row.update({key: getattr(technology, field) for key, field in TECHNOLOGY_EXCHANGE_FIELDS})
    row["Исходное приближенное значение"] = None
    row["external_code"] = None
    return row


def load_rational_struct_import_to_java_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    resolved_id, version_number = resolve_database_version(version_id)
    rows = []
    if resolved_id is not None:
        if year is None:
            info = get_current_year_info(resolved_id)
            year = get_general_scheme_end_year(info["current_year"])
        years = clip_years(
            [year] if year is not None else [],
            start_year=start_year,
            end_year=end_year,
        )
        if years:
            statement = select(TerritoryTechnology).options(
                joinedload(TerritoryTechnology.energy_zone),
                joinedload(TerritoryTechnology.technology_type),
            ).where(
                TerritoryTechnology.database_version_id == resolved_id,
            ).order_by(TerritoryTechnology.source_row, TerritoryTechnology.id)
            rows = [
                build_rational_struct_import_row(technology, calculation_year)
                for technology in db.session.scalars(statement)
                for calculation_year in years
            ]
    return dataset_envelope(
        DATASET_RATIONAL_STRUCT_IMPORT_TO_JAVA,
        database_version=resolved_id,
        version_number=version_number,
        rows=rows,
        comment=RATIONAL_STRUCT_IMPORT_COMMENT,
    )
