# -*- coding: utf-8 -*-
"""
Справочник: какие этапы расчёта топлива куда пишутся в БД (для JSON/UI пакетного пересчёта).
"""
from __future__ import annotations

from typing import Any

from config import SCHEMA_FUEL

from app.fuel.services.equipment_groups.equipment_group_fuel_calculation_services import (
    GROUPS,
    TOPLS,
    UGLI,
    UGLI1,
)


def get_fuel_calculation_write_reference() -> dict[str, Any]:
    """
    Структура для вывода в «Результат (JSON)»: что считается и в какие таблицы/колонки пишется.
    """
    t_main = f"{SCHEMA_FUEL}.gs_fue_equipment_group_fuel_param"
    t_extra = f"{SCHEMA_FUEL}.gs_fue_equipment_group_extra_fuel_param"
    t_cons = f"{SCHEMA_FUEL}.gs_fue_equipment_group_specific_fuel_consumption"
    t_formula = f"{SCHEMA_FUEL}.gs_fue_equipment_group_fuel_formula"

    groups_json = {parent: list(children) for parent, children in sorted(GROUPS.items())}

    return {
        "schema_fuel": SCHEMA_FUEL,
        "rows": {
            "fuel_param": {
                "table": t_main,
                "model": "EquipmentGroupFuelParam",
                "natural_key": "equipment_group_id + year_number (после расчёта также database_version_id)",
            },
            "extra_fuel_param": {
                "table": t_extra,
                "model": "EquipmentGroupExtraFuelParam",
                "natural_key": "equipment_group_id + year_number (после расчёта также database_version_id)",
            },
        },
        "stages": [
            {
                "id": "energy_block",
                "title": "Энергетический блок",
                "method": "EquipmentGroupFuelCalculationService._calculate_energy_part",
                "reads_from": [
                    {
                        "table": t_cons,
                        "model": "EquipmentGroupSpecificFuelConsumption",
                        "rule": (
                            "строка с max(year_number) при year_number <= году расчёта по группе "
                            "(не подразумевает «предыдущий календарный год»: берётся последняя имеющаяся запись, "
                            "не превышающая год расчёта)"
                        ),
                        "columns_used": ["y", "snk", "sntp", "bk", "btp"],
                    },
                    {
                        "table": t_main,
                        "model": "EquipmentGroupFuelParam",
                        "rule": "строка на год расчёта — поля энергобаланса",
                        "columns_used": ["qotr", "e", "q", "turt"],
                    },
                ],
                "writes": [
                    {
                        "table": t_main,
                        "columns": [
                            {"column": "ewtp", "description": "Теплофикационная выработка ЭЭ, тыс.кВтч"},
                            {"column": "eotp", "description": "Отпуск ЭЭ, тыс.кВтч"},
                            {"column": "eust", "description": "расход условного топлива на э/э"},
                            {"column": "eurt", "description": "УРУТ на отпуск ЭЭ, г у.т./кВтч"},
                            {"column": "tust", "description": "Расход усл. топлива на ТЭ, тыс. т у.т."},
                            {"column": "b", "description": "суммарный расход условного топлива (база для formtxt)"},
                        ],
                    }
                ],
            },
            {
                "id": "reset_fuels",
                "title": "Сброс рассчитанных колонок топлива",
                "methods": [
                    "_reset_main_fuel_fields",
                    "_reset_extra_fuel_fields",
                ],
                "writes": [
                    {
                        "table": t_main,
                        "columns": sorted(TOPLS | UGLI),
                        "note": "в 0 перед разбором формулы (наборы TOPLS и UGLI в коде сервиса)",
                    },
                    {
                        "table": t_extra,
                        "columns": sorted(UGLI1),
                        "note": "в 0 (набор UGLI1)",
                    },
                ],
            },
            {
                "id": "formula_distribution",
                "title": "Распределение по видам топлива (formtxt)",
                "methods": ["_parse_formtxt", "_apply_parsed_values"],
                "reads_from": [
                    {
                        "table": t_formula,
                        "model": "EquipmentGroupFuelFormula",
                        "rule": (
                            "строка с max(year_number) при year_number <= году расчёта, нужный variant_number, "
                            "учёт database_version_id (аналогично удельному расходу — не обязательно «год минус один»)"
                        ),
                        "columns_used": ["formtxt"],
                    }
                ],
                "writes": [
                    {
                        "table": t_main,
                        "note": "имена из формулы, не входящие в UGLI1 — в одноимённые колонки EquipmentGroupFuelParam",
                    },
                    {
                        "table": t_extra,
                        "note": "имена из UGLI1 — в одноимённые колонки EquipmentGroupExtraFuelParam",
                    },
                ],
            },
            {
                "id": "aggregation",
                "title": "Агрегирование (GROUPS + ugol)",
                "method": "_aggregate_main_fuels",
                "writes": [
                    {
                        "table": t_main,
                        "note": "родительские поля = сумма дочерних в extra по правилам GROUPS",
                        "group_parent_to_child_columns": groups_json,
                    },
                    {
                        "table": t_main,
                        "columns": [{"column": "ugol", "note": "сумма полей UGLI на основной записи, кроме самого ugol"}],
                    },
                ],
            },
            {
                "id": "version_stamp",
                "title": "Версия БД в строках параметров",
                "method": "_stamp_fuel_param_rows_version",
                "writes": [
                    {
                        "table": t_main,
                        "columns": ["database_version_id"],
                    },
                    {
                        "table": t_extra,
                        "columns": ["database_version_id"],
                    },
                ],
            },
        ],
    }

