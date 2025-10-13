import pandas as pd
from io import BytesIO
from datetime import datetime
from config import Config
from openpyxl import load_workbook
from openpyxl.styles import Font
import traceback
from app.logs.services.logging_service import log_to_db

from app.generation.services.station_services.station_services import (
    get_station_list_data,
    build_energy_unit_aggregates,
    build_regional_district_aggregates,
    build_regional_energy_system_aggregates,
    build_union_energy_system_aggregates,
    build_energy_system_type_aggregates,
    build_total_energy_system_type_aggregates,
)
from app.generation.services.station_services.groupped_services import (
    get_station_hierarchy_aggregates,
    build_hierarchy_structure,
    fetch_machines_with_rowspans,
)
from app.generation.services.station_services.filters_services import (
        get_stations_all
)
from app.common.services.get_services.years.years_get_services import (
    get_current_year,
    get_year_feature_dict,
)
from app.common.services.get_services.fuels.fuel_type_get_services import (
    get_fuel_type_list_full,
)
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
)
from app.common.services.get_services.energy_systems.energy_unit_get_services import (
    get_energy_unit_list_full,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_system_list_full,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_list_full,
)
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_district_list_full,
)
from app.common.services.get_services.stations.station_type_get_services import (
    get_station_type_list_full,
)
from app.common.services.get_services.stations.tes_type_get_services import (
    get_tes_type_list_full,
)
from app.common.services.get_services.stations.tes_machine_type_get_services import (
    get_tes_machine_type_list_full,
)
from app.common.services.get_services.stations.pgu_tes_machine_type_get_services import (
    get_pgu_tes_machine_type_list_full,
)
from app.generation.services.station_services.aggregation_station_services.aggregation_services_energy_units import (
    aggregate_power_by_energy_units,
    aggregate_energy_units_by_station_types,
    aggregate_energy_units_by_station_types_with_fuel,
    aggregate_energy_units_by_tes_types,
    aggregate_energy_units_by_tes_types_with_fuel,
    aggregate_energy_units_by_tes_machine_types,
    aggregate_energy_units_by_tes_machine_types_with_fuel,
)
from app.generation.services.station_services.aggregation_station_services.aggregation_services_regional_districts import (
    aggregate_power_by_regional_districts,
    aggregate_regional_districts_by_station_types,
    aggregate_regional_districts_by_tes_types,
    aggregate_regional_districts_by_tes_machine_types,
    aggregate_regional_districts_by_tes_machine_types_with_fuel,
)
from app.generation.services.station_services.aggregation_station_services.aggregation_services_regional_energy_systems import (
    aggregate_power_by_regional_energy_systems,
    aggregate_regional_energy_systems_by_station_types,
    aggregate_regional_energy_systems_by_tes_types,
    aggregate_regional_energy_systems_by_tes_machine_types,
    aggregate_regional_energy_systems_by_tes_machine_types_with_fuel,
)
from app.generation.services.station_services.aggregation_station_services.aggregation_services_union_energy_systems import (
    aggregate_power_by_union_energy_systems,
    aggregate_union_energy_systems_by_station_types,
    aggregate_union_energy_systems_by_tes_types,
    aggregate_union_energy_systems_by_tes_machine_types,
    aggregate_union_energy_systems_by_tes_machine_types_with_fuel,
)
from app.generation.services.station_services.aggregation_station_services.aggregation_services_energy_system_types import (
    aggregate_power_by_energy_system_types,
    aggregate_energy_system_types_by_station_types,
    aggregate_energy_system_types_by_tes_types,
    aggregate_energy_system_types_by_tes_machine_types,
    aggregate_energy_system_types_by_tes_machine_types_with_fuel,
)
from app.generation.services.station_services.aggregation_station_services.aggregation_services_total_energy_system_types import (
    aggregate_power_by_total_energy_system_types,
    aggregate_total_energy_system_types_by_station_types,
    aggregate_total_energy_system_types_by_tes_types,
    aggregate_total_energy_system_types_by_tes_machine_types,
    aggregate_total_energy_system_types_by_tes_machine_types_with_fuel,
)


def round_value(val, digits):
    if val is None or val == 0:
        return ""
    # Поддержка режима "Не округлять" (digits is None)
    if digits is None:
        return val
    try:
        return round(val, digits) if digits >= 0 else int(round(val, 0))
    except Exception:
        return val

def attach_all_aggregates(data, rows):
    """
    Привязывает все агрегаты к словарю data на основе уже полученных rows.
    """
    data["aggregate_power_by_energy_units"] = aggregate_power_by_energy_units(rows)
    data["aggregate_energy_units_by_station_types"] = aggregate_energy_units_by_station_types(rows)
    data["aggregate_energy_units_by_tes_types"] = aggregate_energy_units_by_tes_types(rows)
    data["aggregate_energy_units_by_tes_types_with_fuel"] = aggregate_energy_units_by_tes_types_with_fuel(rows)
    data["aggregate_energy_units_by_tes_machine_types"] = aggregate_energy_units_by_tes_machine_types(rows)
    data["aggregate_energy_units_by_tes_machine_types_with_fuel"] = aggregate_energy_units_by_tes_machine_types_with_fuel(rows)

    data["aggregate_power_by_regional_districts"] = aggregate_power_by_regional_districts(rows)
    data["aggregate_regional_districts_by_station_types"] = aggregate_regional_districts_by_station_types(rows)
    data["aggregate_regional_districts_by_tes_types"] = aggregate_regional_districts_by_tes_types(rows)
    data["aggregate_regional_districts_by_tes_machine_types"] = aggregate_regional_districts_by_tes_machine_types(rows)
    data["aggregate_regional_districts_by_tes_machine_types_with_fuel"] = aggregate_regional_districts_by_tes_machine_types_with_fuel(rows)

    data["aggregate_power_by_regional_energy_systems"] = aggregate_power_by_regional_energy_systems(rows)
    data["aggregate_regional_energy_systems_by_station_types"] = aggregate_regional_energy_systems_by_station_types(rows)
    data["aggregate_regional_energy_systems_by_tes_types"] = aggregate_regional_energy_systems_by_tes_types(rows)
    data["aggregate_regional_energy_systems_by_tes_machine_types"] = aggregate_regional_energy_systems_by_tes_machine_types(rows)
    data["aggregate_regional_energy_systems_by_tes_machine_types_with_fuel"] = aggregate_regional_energy_systems_by_tes_machine_types_with_fuel(rows)

    data["aggregate_power_by_union_energy_systems"] = aggregate_power_by_union_energy_systems(rows)
    data["aggregate_union_energy_systems_by_station_types"] = aggregate_union_energy_systems_by_station_types(rows)
    data["aggregate_union_energy_systems_by_tes_types"] = aggregate_union_energy_systems_by_tes_types(rows)
    data["aggregate_union_energy_systems_by_tes_machine_types"] = aggregate_union_energy_systems_by_tes_machine_types(rows)
    data["aggregate_union_energy_systems_by_tes_machine_types_with_fuel"] = aggregate_union_energy_systems_by_tes_machine_types_with_fuel(rows)

    data["aggregate_power_by_energy_system_types"] = aggregate_power_by_energy_system_types(rows)
    data["aggregate_energy_system_types_by_station_types"] = aggregate_energy_system_types_by_station_types(rows)
    data["aggregate_energy_system_types_by_tes_types"] = aggregate_energy_system_types_by_tes_types(rows)
    data["aggregate_energy_system_types_by_tes_machine_types"] = aggregate_energy_system_types_by_tes_machine_types(rows)
    data["aggregate_energy_system_types_by_tes_machine_types_with_fuel"] = aggregate_energy_system_types_by_tes_machine_types_with_fuel(rows)

    data["aggregate_power_by_total_energy_system_types"] = aggregate_power_by_total_energy_system_types(rows)
    data["aggregate_total_energy_system_types_by_station_types"] = aggregate_total_energy_system_types_by_station_types(rows)
    data["aggregate_total_energy_system_types_by_tes_types"] = aggregate_total_energy_system_types_by_tes_types(rows)
    data["aggregate_total_energy_system_types_by_tes_machine_types"] = aggregate_total_energy_system_types_by_tes_machine_types(rows)
    data["aggregate_total_energy_system_types_by_tes_machine_types_with_fuel"] = aggregate_total_energy_system_types_by_tes_machine_types_with_fuel(rows)

    station_type_names = get_station_type_list_full()
    data["station_type_name"] = {
        st.id: st.name
        for st in station_type_names
    }

    tes_type_names = get_tes_type_list_full()
    data["tes_type_name"] = {
        tt.id: tt.name
        for tt in tes_type_names
    }

    tes_machine_type_names = get_tes_machine_type_list_full()
    data["tes_machine_type_name"] = {
        tmt.id: tmt.name
        for tmt in tes_machine_type_names
    }

    fuel_type_names = get_fuel_type_list_full()
    data["fuel_type_name"] = {
        ft.id: ft.name
        for ft in fuel_type_names
    }

    # Дополняем словари имён для уровней иерархии (для экспорта)
    try:
        energy_unit_list = get_energy_unit_list_full()
        data["energy_unit_name"] = {
            eu.id: getattr(eu, "name_full", getattr(eu, "name", str(eu.id)))
            for eu in energy_unit_list
        }
    except Exception:
        data.setdefault("energy_unit_name", {})

    try:
        regional_district_list = get_regional_district_list_full()
        data["regional_district_name"] = {
            rd.id: getattr(rd, "name_full", getattr(rd, "name", str(rd.id)))
            for rd in regional_district_list
        }
    except Exception:
        data.setdefault("regional_district_name", {})

    try:
        regional_energy_system_list = get_regional_energy_system_list_full()
        data["regional_energy_system_name"] = {
            res.id: getattr(res, "name_full", getattr(res, "name", str(res.id)))
            for res in regional_energy_system_list
        }
    except Exception:
        data.setdefault("regional_energy_system_name", {})

    try:
        union_energy_system_list = get_union_energy_system_list_full()
        data["union_energy_system_name"] = {
            ues.id: getattr(ues, "name_full", getattr(ues, "name", str(ues.id)))
            for ues in union_energy_system_list
        }
    except Exception:
        data.setdefault("union_energy_system_name", {})

    try:
        energy_system_type_list = get_energy_system_type_list_full()
        data["energy_system_type_name"] = {
            est.id: getattr(est, "name_full", getattr(est, "name", str(est.id)))
            for est in energy_system_type_list
        }
    except Exception:
        data.setdefault("energy_system_type_name", {})

    return data


# Универсальная конфигурация агрегации для разных уровней иерархии
AGGREGATION_CONFIG = {
    "energy_unit": {
        "aggregated_power_key": "aggregate_power_by_energy_units",
        "station_type_key": "aggregate_energy_units_by_station_types",
        "tes_type_key": "aggregate_energy_units_by_tes_types",
        "tes_machine_type_key": "aggregate_energy_units_by_tes_machine_types",
        "fuel_type_key": "aggregate_energy_units_by_tes_machine_types_with_fuel",
        "name_dict": "energy_unit_name",
    },
    "regional_district": {
        "aggregated_power_key": "aggregate_power_by_regional_districts",
        "station_type_key": "aggregate_regional_districts_by_station_types",
        "tes_type_key": "aggregate_regional_districts_by_tes_types",
        "tes_machine_type_key": "aggregate_regional_districts_by_tes_machine_types",
        "fuel_type_key": "aggregate_regional_districts_by_tes_machine_types_with_fuel",
        "name_dict": "regional_district_name",
    },
    "regional_energy_system": {
        "aggregated_power_key": "aggregate_power_by_regional_energy_systems",
        "station_type_key": "aggregate_regional_energy_systems_by_station_types",
        "tes_type_key": "aggregate_regional_energy_systems_by_tes_types",
        "tes_machine_type_key": "aggregate_regional_energy_systems_by_tes_machine_types",
        "fuel_type_key": "aggregate_regional_energy_systems_by_tes_machine_types_with_fuel",
        "name_dict": "regional_energy_system_name",
    },
    "union_energy_system": {
        "aggregated_power_key": "aggregate_power_by_union_energy_systems",
        "station_type_key": "aggregate_union_energy_systems_by_station_types",
        "tes_type_key": "aggregate_union_energy_systems_by_tes_types",
        "tes_machine_type_key": "aggregate_union_energy_systems_by_tes_machine_types",
        "fuel_type_key": "aggregate_union_energy_systems_by_tes_machine_types_with_fuel",
        "name_dict": "union_energy_system_name",
    },
    "energy_system_type": {
        "aggregated_power_key": "aggregate_power_by_energy_system_types",
        "station_type_key": "aggregate_energy_system_types_by_station_types",
        "tes_type_key": "aggregate_energy_system_types_by_tes_types",
        "tes_machine_type_key": "aggregate_energy_system_types_by_tes_machine_types",
        "fuel_type_key": "aggregate_energy_system_types_by_tes_machine_types_with_fuel",
        "name_dict": "energy_system_type_name",
    },
    "russia": {
        "aggregated_power_key": "aggregate_power_by_total_energy_system_types",
        "station_type_key": "aggregate_total_energy_system_types_by_station_types",
        "tes_type_key": "aggregate_total_energy_system_types_by_tes_types",
        "tes_machine_type_key": "aggregate_total_energy_system_types_by_tes_machine_types",
        "fuel_type_key": "aggregate_total_energy_system_types_by_tes_machine_types_with_fuel",
        "name_dict": None,
    },
}


def get_aggregated_power_by_year(entity_id, source, start_year, end_year):
    # source содержит структуру: {"aggregated": {"p_ust": {entity_id: {year: value}}, "p_ogr": ..., "p_rasp": ...}}
    aggregated = source.get("aggregated", {})
    return {
        year: {
            "p_ust": aggregated.get("p_ust", {}).get(entity_id, {}).get(year),
            "p_ogr": aggregated.get("p_ogr", {}).get(entity_id, {}).get(year),
            "p_rasp": aggregated.get("p_rasp", {}).get(entity_id, {}).get(year),
        }
        for year in range(start_year, end_year + 1)
    }


# Выгрузка в эксель по форме файла "Список станций"
def generate_excel_export_with_all_totals(data, rows, start_year, end_year, rounding_digits, show_p_ogr=False, show_p_rasp=False):
    import time
    start_time = time.time()
    print(f"[EXPORT] Начало экспорта в Excel")
    
    def round_val(val):
        return round_value(val, rounding_digits)

    # ⚠️ Агрегаты уже должны быть в data (вызываются в get_station_list_data с show_totals=True)
    # Если их нет — дополняем вручную (для совместимости)
    t1 = time.time()
    if "aggregate_power_by_regional_districts" not in data:
        attach_all_aggregates(data, rows)
    print(f"[EXPORT] Проверка/создание агрегатов: {time.time() - t1:.2f}с")
    
    # 🏷️ Всегда дополняем словари имён (на случай если они отсутствуют)
    t2 = time.time()
    if "station_type_name" not in data:
        station_type_names = get_station_type_list_full()
        data["station_type_name"] = {st.id: st.name for st in station_type_names}
    
    if "tes_type_name" not in data:
        tes_type_names = get_tes_type_list_full()
        data["tes_type_name"] = {tt.id: tt.name for tt in tes_type_names}
    
    if "tes_machine_type_name" not in data:
        tes_machine_type_names = get_tes_machine_type_list_full()
        data["tes_machine_type_name"] = {tmt.id: tmt.name for tmt in tes_machine_type_names}
    
    if "fuel_type_name" not in data:
        fuel_type_names = get_fuel_type_list_full()
        data["fuel_type_name"] = {ft.id: ft.name for ft in fuel_type_names}
    
    if "energy_unit_name" not in data:
        try:
            energy_unit_list = get_energy_unit_list_full()
            data["energy_unit_name"] = {
                eu.id: getattr(eu, "name_full", getattr(eu, "name", str(eu.id)))
                for eu in energy_unit_list
            }
        except Exception:
            data["energy_unit_name"] = {}
    
    if "regional_district_name" not in data:
        try:
            regional_district_list = get_regional_district_list_full()
            data["regional_district_name"] = {
                rd.id: getattr(rd, "name_full", getattr(rd, "name", str(rd.id)))
                for rd in regional_district_list
            }
        except Exception:
            data["regional_district_name"] = {}
    
    if "regional_energy_system_name" not in data:
        try:
            regional_energy_system_list = get_regional_energy_system_list_full()
            data["regional_energy_system_name"] = {
                res.id: getattr(res, "name_full", getattr(res, "name", str(res.id)))
                for res in regional_energy_system_list
            }
        except Exception:
            data["regional_energy_system_name"] = {}
    
    if "union_energy_system_name" not in data:
        try:
            union_energy_system_list = get_union_energy_system_list_full()
            data["union_energy_system_name"] = {
                ues.id: getattr(ues, "name_full", getattr(ues, "name", str(ues.id)))
                for ues in union_energy_system_list
            }
        except Exception:
            data["union_energy_system_name"] = {}
    
    if "energy_system_type_name" not in data:
        try:
            energy_system_type_list = get_energy_system_type_list_full()
            data["energy_system_type_name"] = {
                est.id: getattr(est, "name_full", getattr(est, "name", str(est.id)))
                for est in energy_system_type_list
            }
        except Exception:
            data["energy_system_type_name"] = {}
    print(f"[EXPORT] Создание словарей имён: {time.time() - t2:.2f}с")

    # 📦 Формируем все словари агрегатов для шаблона
    t3 = time.time()
    energy_unit_aggregates = build_energy_unit_aggregates(data)
    regional_district_aggregates = build_regional_district_aggregates(data)
    regional_energy_system_aggregates = build_regional_energy_system_aggregates(data)
    union_energy_system_aggregates = build_union_energy_system_aggregates(data)
    energy_system_type_aggregates = build_energy_system_type_aggregates(data)
    total_energy_system_type_aggregates = build_total_energy_system_type_aggregates(data)

    # ✅ Собираем все агрегаты в один словарь
    aggregates = {}
    aggregates.update(energy_unit_aggregates)
    aggregates.update(regional_district_aggregates)
    aggregates.update(regional_energy_system_aggregates)
    aggregates.update(union_energy_system_aggregates)
    aggregates.update(energy_system_type_aggregates)
    aggregates.update(total_energy_system_type_aggregates)
    print(f"[EXPORT] Формирование словарей агрегатов: {time.time() - t3:.2f}с")

    t4 = time.time()
    stations_grouped = data.get("stations_grouped") or data.get("grouped_stations", {})
    rows = []

    def add_machine_row(machine, station_name, subject_name):
        row_ust = {
            "Электростанция": machine.machine_number,
            " ": machine.machine_name,
            "Генерирующая компания": machine.gen_company.name if machine.gen_company else "—",
            "Год ввода": machine.date_exploitation,
            "Тип мощности": "Руст",
            "Тип станции": machine.station_type.name if machine.station_type else "—",
            "Тип ТЭС": machine.tes_types or "—",
            "Тип агрегата ТЭС": machine.tes_machine_type.name if machine.tes_machine_type and machine.tes_machine_type.id != 0 else "—",
            "Примечание": machine.note or "",
        }
        for year in range(start_year, end_year + 1):
            row_ust[str(year)] = round_val(machine.powers_by_year.get(year, {}).get("p_ust"))
            row_ust[f"{year} (топливо)"] = machine.fuel_type_by_year.get(year, "—")
        rows.append(row_ust)

        if show_p_ogr:
            row_ogr = {k: "" for k in row_ust}
            row_ogr.update({"Тип мощности": "Рогр"})
            for year in range(start_year, end_year + 1):
                row_ogr[str(year)] = round_val(machine.powers_by_year.get(year, {}).get("p_ogr"))
            rows.append(row_ogr)

        if show_p_rasp:
            row_rasp = {k: "" for k in row_ust}
            row_rasp.update({"Тип мощности": "Ррасп"})
            for year in range(start_year, end_year + 1):
                row_rasp[str(year)] = round_val(machine.powers_by_year.get(year, {}).get("p_rasp"))
            rows.append(row_rasp)

    def add_station_total_row(station):
        def total_row(label, power_key, show_name=False):
            row = {
                "Электростанция": f"{station.name}, всего" if show_name else "",
                " ": "",
                "Генерирующая компания": "",
                "Год ввода": "",
                "Тип мощности": label,
                "Тип станции": "",
                "Тип ТЭС": "",
                "Тип агрегата ТЭС": "",
                "Примечание": "",
            }
            for year in range(start_year, end_year + 1):
                value = station.powers_by_year.get(year, {}).get(power_key)
                row[str(year)] = round_val(value) if value is not None else None
                row[f"Топливо {year}"] = ""
            rows.append(row)

        # Только для p_ust выводим название станции
        total_row("Руст", "p_ust", show_name=True)
        if show_p_ogr:
            total_row("Рогр", "p_ogr", show_name=False)
        if show_p_rasp:
            total_row("Ррасп", "p_rasp", show_name=False)

        rows.append({})

    def add_named_total_row(level_id, level_key, data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp):
        config = AGGREGATION_CONFIG[level_key]

        power_data = get_aggregated_power_by_year(
            level_id,
            data[config["aggregated_power_key"]],
            start_year,
            end_year
        )

        station_type_data = data[config["station_type_key"]].get("aggregated", {}).get("p_ust", {})
        tes_type_data = data[config["tes_type_key"]].get("aggregated", {}).get("p_ust", {})
        tes_machine_type_data = data[config["tes_machine_type_key"]].get("aggregated", {}).get("p_ust", {})
        fuel_type_data = data[config["fuel_type_key"]].get("aggregated", {}).get("p_ust", {})

        station_type_names = data.get("station_type_name", {})
        tes_type_names = data.get("tes_type_name", {})
        machine_type_names = data.get("tes_machine_type_name", {})
        fuel_type_names = data.get("fuel_type_name", {})

        def total_row(label, key, show_name=False):
            row = {
                "Электростанция": f"{level_id if not config['name_dict'] else data.get(config['name_dict'], {}).get(level_id, f'id={level_id}')}" if show_name else "",
                " ": "",
                "Генерирующая компания": "",
                "Год ввода": "",
                "Тип мощности": label,
                "Тип станции": "",
                "Тип ТЭС": "",
                "Тип агрегата ТЭС": "",
                "Примечание": "",
            }
            for year in range(start_year, end_year + 1):
                row[str(year)] = round_val(power_data.get(year, {}).get(key)) if power_data.get(year) else None
                row[f"Топливо {year}"] = ""
            rows.append(row)

        total_row("Руст", "p_ust", show_name=True)
        if show_p_ogr:
            total_row("Рогр", "p_ogr")
        if show_p_rasp:
            total_row("Ррасп", "p_rasp")


        station_type_data_ogr = data[config["station_type_key"]].get("aggregated", {}).get("p_ogr", {}) if show_p_ogr else {}
        station_type_data_rasp = data[config["station_type_key"]].get("aggregated", {}).get("p_rasp", {}) if show_p_rasp else {}

        for station_type_id, st_years in station_type_data.get(level_id, {}).items():
            if station_type_id is None:
                continue

            station_type_name = station_type_names.get(station_type_id, f"id={station_type_id}")
            row_st = {
                "Электростанция": f"   {station_type_name}",
                " ": "",
                "Генерирующая компания": "",
                "Год ввода": "",
                "Тип мощности": "Руст",
                "Тип станции": "",
                "Тип ТЭС": "",
                "Тип агрегата ТЭС": "",
                "Примечание": ""
            }
            for year in range(start_year, end_year + 1):
                row_st[str(year)] = round_val(st_years.get(year)) if st_years.get(year) is not None else None
                row_st[f"Топливо {year}"] = None
            rows.append(row_st)

            if show_p_ogr:
                row_ogr = {k: "" for k in row_st}
                row_ogr["Тип мощности"] = "Рогр"
                for year in range(start_year, end_year + 1):
                    val = station_type_data_ogr.get(level_id, {}).get(station_type_id, {}).get(year)
                    row_ogr[str(year)] = round_val(val) if val is not None else None
                rows.append(row_ogr)

            if show_p_rasp:
                row_rasp = {k: "" for k in row_st}
                row_rasp["Тип мощности"] = "Ррасп"
                for year in range(start_year, end_year + 1):
                    val = station_type_data_rasp.get(level_id, {}).get(station_type_id, {}).get(year)
                    row_rasp[str(year)] = round_val(val) if val is not None else None
                rows.append(row_rasp)

            if station_type_id == 4:
                tes_type_data_ogr = data[config["tes_type_key"]].get("aggregated", {}).get("p_ogr", {}) if show_p_ogr else {}
                tes_type_data_rasp = data[config["tes_type_key"]].get("aggregated", {}).get("p_rasp", {}) if show_p_rasp else {}

                for tes_type_id, tt_years in tes_type_data.get(level_id, {}).items():
                    if tes_type_id is None:
                        continue

                    tes_type_name = tes_type_names.get(tes_type_id, f"id={tes_type_id}")
                    row_tt = {
                            "Электростанция": f"      {tes_type_name}",
                            " ": "",
                            "Генерирующая компания": "",
                            "Год ввода": "",
                            "Тип мощности": "Руст",
                            "Тип станции": "",
                            "Тип ТЭС": "",
                            "Тип агрегата ТЭС": "",
                            "Примечание": ""
                        }
                    for year in range(start_year, end_year + 1):
                        row_tt[str(year)] = round_val(tt_years.get(year)) if tt_years.get(year) is not None else None
                        row_tt[f"Топливо {year}"] = None
                    rows.append(row_tt)

                    if show_p_ogr:
                        row_ogr = {k: "" for k in row_st}
                        row_ogr["Тип мощности"] = "Рогр"
                        for year in range(start_year, end_year + 1):
                            val = station_type_data_ogr.get(level_id, {}).get(station_type_id, {}).get(year)
                            row_ogr[str(year)] = round_val(val) if val is not None else None
                        rows.append(row_ogr)

                    if show_p_rasp:
                        row_rasp = {k: "" for k in row_st}
                        row_rasp["Тип мощности"] = "Ррасп"
                        for year in range(start_year, end_year + 1):
                            val = tes_type_data_rasp.get(level_id, {}).get(tes_type_id, {}).get(year)
                            row_rasp[str(year)] = round_val(val) if val is not None else None
                        rows.append(row_rasp)

                    mt_dict = tes_machine_type_data.get(level_id, {}).get(tes_type_id, {})
                    tes_machine_type_data_ogr = data[config["tes_machine_type_key"]].get("aggregated", {}).get("p_ogr", {}) if show_p_ogr else {}
                    tes_machine_type_data_rasp = data[config["tes_machine_type_key"]].get("aggregated", {}).get("p_rasp", {}) if show_p_rasp else {}

                    for machine_type_id, mt_years in mt_dict.items():
                        if machine_type_id is None:
                            continue
                        machine_type_name = machine_type_names.get(machine_type_id, f"id={machine_type_id}")
                        row_mt = {
                                "Электростанция": f"         {machine_type_name}",
                                " ": "",
                                "Генерирующая компания": "",
                                "Год ввода": "",
                                "Тип мощности": "Руст",
                                "Тип станции": "",
                                "Тип ТЭС": "",
                                "Тип агрегата ТЭС": "",
                                "Примечание": ""
                            }
                        for year in range(start_year, end_year + 1):
                            row_mt[str(year)] = round_val(mt_years.get(year)) if mt_years.get(year) is not None else None
                            row_mt[f"Топливо {year}"] = None
                        rows.append(row_mt)

                        if show_p_ogr:
                            row_ogr = {k: "" for k in row_st}
                            row_ogr["Тип мощности"] = "Рогр"
                            for year in range(start_year, end_year + 1):
                                val = tes_machine_type_data_ogr.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {}).get(year)
                                row_ogr[str(year)] = round_val(val) if val is not None else None
                            rows.append(row_ogr)

                        if show_p_rasp:
                            row_rasp = {k: "" for k in row_st}
                            row_rasp["Тип мощности"] = "Ррасп"
                            for year in range(start_year, end_year + 1):
                                val = tes_machine_type_data_rasp.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {}).get(year)
                                row_rasp[str(year)] = round_val(val) if val is not None else None
                            rows.append(row_rasp)

                        fuel_dict = fuel_type_data.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {})
                        fuel_type_data_ogr = data[config["fuel_type_key"]].get("aggregated", {}).get("p_ogr", {}) if show_p_ogr else {}
                        fuel_type_data_rasp = data[config["fuel_type_key"]].get("aggregated", {}).get("p_rasp", {}) if show_p_rasp else {}

                        for fuel_type_id, fuel_years in fuel_dict.items():
                            fuel_type_name = fuel_type_names.get(fuel_type_id, f"id={fuel_type_id}")
                            row_ft = {
                                    "Электростанция": f"            {fuel_type_name}",
                                    " ": "",
                                    "Генерирующая компания": "",
                                    "Год ввода": "",
                                    "Тип мощности": "Руст",
                                    "Тип станции": "",
                                    "Тип ТЭС": "",
                                    "Тип агрегата ТЭС": "",
                                    "Примечание": ""
                                }
                            for year in range(start_year, end_year + 1):
                                row_ft[str(year)] = round_val(fuel_years.get(year)) if fuel_years.get(year) is not None else None
                                row_ft[f"Топливо {year}"] = None
                            rows.append(row_ft)

                            if show_p_ogr:
                                row_ogr = {k: "" for k in row_st}
                                row_ogr["Тип мощности"] = "Рогр"
                                for year in range(start_year, end_year + 1):
                                    val = fuel_type_data_ogr.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {}).get(fuel_type_id, {}).get(year)
                                    row_ogr[str(year)] = round_val(val) if val is not None else None
                                rows.append(row_ogr)

                            if show_p_rasp:
                                row_rasp = {k: "" for k in row_st}
                                row_rasp["Тип мощности"] = "Ррасп"
                                for year in range(start_year, end_year + 1):
                                    val = fuel_type_data_rasp.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {}).get(fuel_type_id, {}).get(year)
                                    row_rasp[str(year)] = round_val(val) if val is not None else None
                                rows.append(row_rasp)

                                rows.append({})

        
    for es_type_id, es_type_group in stations_grouped.items():
        es_name = data.get("energy_system_type_name", {}).get(es_type_id, f"id={es_type_id}")
        for ues_id, ues_group in es_type_group.items():
            ues_name = data.get("union_energy_system_name", {}).get(ues_id, f"id={ues_id}")
            for res_id, res_group in ues_group.items():
                res_name = data.get("regional_energy_system_name", {}).get(res_id, f"id={res_id}")
                for rd_id, rd_group in res_group.items():
                    rd_name = data.get("regional_district_name", {}).get(rd_id, f"id={rd_id}")
                    row_rd = {
                        "Электростанция": rd_name,
                        " ": "",
                        "Генерирующая компания": "",
                        "Год ввода": "",
                        "Тип мощности": "",
                        "Тип станции": "",
                        "Тип ТЭС": "",
                        "Тип агрегата ТЭС": "",
                        "Примечание": "",
                    }
                    rows.append(row_rd)
                    rows.append({})

                    for eu_id, eu_group in rd_group.items():
                        eu_name = data.get("energy_unit_name", {}).get(eu_id, f"id={eu_id}")
                        if eu_id != 0:
                            row_eu = {
                                "Электростанция": eu_name,
                                " ": "",
                                "Генерирующая компания": "",
                                "Год ввода": "",
                                "Тип мощности": "",
                                "Тип станции": "",
                                "Тип ТЭС": "",
                                "Тип агрегата ТЭС": "",
                                "Примечание": "",
                            }
                            rows.append(row_eu)
                        for station in eu_group:
                            first_machine = True
                            row_station = {
                                "Электростанция": station.name,
                                " ": "",
                                "Генерирующая компания": "",
                                "Год ввода": "",
                                "Тип мощности": "",
                                "Тип станции": "",
                                "Тип ТЭС": "",
                                "Тип агрегата ТЭС": "",
                                "Примечание": station.note,
                            }
                            rows.append(row_station)

                            for machine in station.machines:
                                add_machine_row(machine, station.name if first_machine else "", rd_name if first_machine else "")
                                first_machine = False
                            if hasattr(station, "powers_by_year"):
                                add_station_total_row(station)
                        if eu_id != 0:
                            add_named_total_row(eu_id, "energy_unit", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
                    add_named_total_row(rd_id, "regional_district", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
                add_named_total_row(res_id, "regional_energy_system", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
            add_named_total_row(ues_id, "union_energy_system", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
        add_named_total_row(es_type_id, "energy_system_type", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
    add_named_total_row("Россия", "russia", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
    print(f"[EXPORT] Формирование строк данных: {time.time() - t4:.2f}с, всего строк: {len(rows)}")

    t5 = time.time()
    year_columns = [str(year) for year in range(start_year, end_year + 1)]
    fuel_columns = [f"{year} (топливо)" for year in range(start_year, end_year + 1)]

    columns = [
        "Электростанция", " ", "Генерирующая компания",
        "Год ввода", "Тип мощности"
    ] + year_columns + fuel_columns + [
        "Тип станции", "Тип ТЭС", "Тип агрегата ТЭС", "Примечание"
    ]

    from openpyxl import Workbook
    from openpyxl.styles import Font
    from io import BytesIO

    output = BytesIO()
    wb = Workbook()
    ws = wb.active

    # Заголовки
    ws.append(columns)

    # Данные
    for row in rows:
        excel_row = []
        for col in columns:
            val = row.get(col)

            # Преобразуем только числовые колонки (годы)
            if isinstance(val, float) or isinstance(val, int):
                excel_row.append(val)
            elif isinstance(val, str):
                try:
                    float_val = float(val.replace(',', '.'))
                    excel_row.append(float_val)
                except:
                    excel_row.append(val)
            else:
                excel_row.append(val)
        ws.append(excel_row)

    # Жирный шрифт для итогов
    bold_font = Font(bold=True)
    for row in ws.iter_rows(min_row=2):
        if row[1].value and isinstance(row[1].value, str) and row[1].value.startswith("ИТОГО"):
            for cell in row:
                cell.font = bold_font

    wb.save(output)
    output.seek(0)
    print(f"[EXPORT] Запись в Excel файл: {time.time() - t5:.2f}с")
    print(f"[EXPORT] ИТОГО время экспорта: {time.time() - start_time:.2f}с")
    return output


# Выгрузка в эксель по форме Приложения 2 к СиПР ЭЭС (по субъектам)
def export_station_sipr_ees_application_2_service(user, filters=None):
    log_to_db(user, "Начата выгрузка таблицы электростанций из базы данных")
    log_to_db(user, "Параметры экспорта", f"Фильтры: {filters}")

    query = get_stations_all(**filters)
    station_list = query.all()

    from collections import defaultdict


    for station in station_list:
        # Фильтрация агрегатов по дате вывода
        station.machines = [
            m for m in station.machines
            if m.date_decompressing_expected is None
            or (m.date_decompressing_expected >= Config.START_YEAR_SIPR)
        ]

        total_machines = len(station.machines)

        # Обнуляем значения
        for m in station.machines:
            m.group_rowspan = 0
            m.fuel_rowspan = 0

        # Группировка по machine_group
        group_map = defaultdict(list)
        for m in station.machines:
            if m.machine_group:
                group_map[m.machine_group].append(m)

        for group_machines in group_map.values():
            count = len(group_machines)
            if count > 1:
                for i, m in enumerate(group_machines):
                    m.group_rowspan = count if i == 0 else 0

    total_stations = len(station_list)
    log_to_db(user, "Найдено станций в БД", f"{total_stations} записей")

    if not station_list:
        log_to_db(user, "Экспорт остановлен", "Нет данных для экспорта.")
        return None

    all_years = list(range(Config.START_YEAR_SIPR - 2, Config.END_YEAR_SIPR + 1))
    output_files = []
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # Группируем станции по субъекту РФ
    regional_districts = {"Без субъекта": []}
    regional_systems = {}
    for station in station_list:
        district_name = station.regional_district.name_full if station.regional_district else "Без субъекта"
        if district_name not in regional_districts:
            regional_districts[district_name] = []
        regional_districts[district_name].append(station)

        regional_system = station.regional_district.regional_energy_system
        regional_system_name = regional_system.name_full if regional_system else "Неизвестно"
        if regional_system_name not in regional_systems:
            regional_systems[regional_system_name] = set()
        regional_systems[regional_system_name].add(district_name)

    processed_stations = 0
    
    aggregated_rows = get_station_hierarchy_aggregates(Config.START_YEAR_SIPR, Config.END_YEAR_SIPR)
    build_hierarchy_structure(aggregated_rows, station_list, include_names=False)

    for district_name, stations in regional_districts.items():
        log_to_db(user, f"Выгрузка данных по форме Приложения А к СиПР ЭЭС: {district_name} (Энергосистема: {regional_system_name}) | Найдено станций: {len(stations)}")
        if not stations:
            continue
        try:
            data = []

            # Добавляем строку с названием региональной энергосистемы
            first_station = stations[0]
            regional_system_name = (
                first_station.regional_district.regional_energy_system.name_full.replace("Электроэнергетическая система", "Энергосистема")
                if first_station.regional_district and first_station.regional_district.regional_energy_system
                else "Неизвестно"
            )

            if first_station.regional_district.regional_energy_system.regional_district_count > 1:
                region_label = f"{regional_system_name}, территория {district_name}"
            else:
                region_label = regional_system_name

            data.append({
                "Электростанция": region_label,
                "Генерирующая компания": "",
                "Станционный номер": "",
                "Тип генерирующего оборудования": "",
                "Вид топлива": "",
                **{year: "" for year in all_years},
                "Примечание": "",
                "_group_rowspan": "",
                "_fuel_rowspan": "",
                "_total_machines": "",
                "Есть группы": "",
            })

            # Определяем наличие групп по агрегатам станции

            for station in stations:
                has_groups = any(m.machine_group for m in station.machines)
                has_groups_text = "Да" if has_groups else "Нет"
                
                processed_stations += 1
                
                power_data = {
                    sp.year_number: {
                        "p_ust": sp.p_ust,
                        "p_ogr": sp.p_ogr,
                        "p_rasp": sp.p_rasp
                    }
                    for sp in station.station_powers
                    if sp.year_number in all_years
                }

                # Добавляем строку с названием электростанции
                data.append({
                    "Электростанция": station.name,
                    "Генерирующая компания": station.gen_companies,
                    "Станционный номер": "",
                    "Тип генерирующего оборудования": "",
                    "Вид топлива": "",
                    **{year: "" for year in all_years},
                    "Примечание": "",
                    "_group_rowspan": "",
                    "_fuel_rowspan": "",
                    "_total_machines": "",
                    "Есть группы": "",
                })

                def extract_year(date_input):
                    """Возвращает год из строки или числа."""
                    if not date_input:
                        return None
                    if isinstance(date_input, int):
                        return date_input
                    try:
                        return datetime.strptime(date_input, "%Y-%m-%d").year
                    except Exception:
                        try:
                            return int(str(date_input)[:4])
                        except Exception:
                            return None


                # Добавляем строки с установленной мощностью по машинам электростанции
                for machine in station.machines:
                    machine_power_data = {}
                    for mp in machine.machine_powers:
                        if mp.year and mp.p_ust is not None:
                            machine_power_data[mp.year.number] = mp.p_ust

                    note_parts = []
                    if machine.date_decompressing_expected:
                        year = extract_year(machine.date_decompressing_expected)
                        if year:
                            note_parts.append(f"Вывод из эксплуатации в {year} г.")

                    if machine.date_modernization_expected:
                        year = extract_year(machine.date_modernization_expected)
                        if year:
                            note_parts.append(f"Модернизация в {year} г.")

                    full_note = ". ".join(note_parts)
                    if machine.note:
                        if full_note:
                            full_note = f"{full_note}. {machine.note}"
                        else:
                            full_note = machine.note

                    row = {
                        "Электростанция": machine.machine_group,
                        "Генерирующая компания": "",
                        "Станционный номер": machine.machine_number,
                        "Тип генерирующего оборудования": machine.machine_name,
                        "Вид топлива": machine.fuel_so if getattr(machine, 'fuel_so', 0) else "–",
                        **{
                            year: f"{machine_power_data.get(year):.1f}".replace('.', ',')
                            if machine_power_data.get(year)
                            else ""
                            for year in all_years
                        },
                        "Примечание": full_note or "",
                            
                        # Скрытые поля для Excel
                        "_group_rowspan": machine.group_rowspan or 0,
                        "_fuel_rowspan": machine.fuel_rowspan or 0,
                        "_total_machines": len(station.machines),
                        "Есть группы": has_groups_text,
                    }

                    data.append(row)

                # Добавляем строку "Установленная мощность, всего" по станции
                total_row = {
                    "Электростанция": "Установленная мощность, всего",
                    "Генерирующая компания": "",
                    "Станционный номер": "–",
                    "Тип генерирующего оборудования": "–",
                    "Вид топлива": "–",
                    **{year: f"{power_data.get(year, {}).get('p_ust', 0):.1f}".replace('.', ',') for year in all_years},
                    "Примечание": "",
                    "_group_rowspan": "",
                    "_fuel_rowspan": "",
                    "_total_machines": "",
                    "Есть группы": "",
                }
                data.append(total_row)
            
            df = pd.DataFrame(data)
            df = df.fillna("")

            # Отдельная копия — без служебных колонок — для экспорта
            df_export = df.drop(
                columns=["_group_rowspan", "_fuel_rowspan", "_total_machines", "Есть группы"],
                errors="ignore"
            )

            # Создание Excel-файла
            output = BytesIO()
            sheet_name = f"Приложение А"
            file_name = f"Приложение_А_{district_name}_{timestamp}.xlsx".replace(" ", "_")
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df_export.to_excel(writer, index=False, header=False, startrow=6, sheet_name=sheet_name)
                workbook = writer.book
                worksheet = writer.sheets['Приложение А']

                title_format =  workbook.add_format({
                    'font_name': 'Times New Roman',  # Устанавливаем шрифт
                    'font_size': 13,                 # Размер шрифта 13pt
                    'bold': True,
                    'align': 'center',               # Выравнивание текста по левому краю
                    'valign': 'vcenter',             # Выравнивание по центру по вертикали
                })

                subtitle_format = workbook.add_format({
                    'font_name': 'Times New Roman',  # Устанавливаем шрифт
                    'font_size': 13,                 # Размер шрифта 13pt
                    'align': 'left',                 # Выравнивание текста по левому краю
                    'valign': 'vcenter',             # Выравнивание по центру по вертикали
                    'text_wrap': True,               # Перенос слов (разрыв строк)
                })

                text_format = workbook.add_format({
                    'font_name': 'Times New Roman',  # Устанавливаем шрифт
                    'font_size': 10,                 # Размер шрифта 10pt
                    'align': 'left',                 # Выравнивание текста по левому краю
                    'valign': 'vcenter',             # Выравнивание по центру по вертикали
                    'text_wrap': True,               # Перенос слов (разрыв строк)
                    'border': 1                      # Границы ячейки
                })
                
                text_format_group = workbook.add_format({
                    'font_name': 'Times New Roman',  # Устанавливаем шрифт
                    'font_size': 10,                 # Размер шрифта 10pt
                    'align': 'left',                 # Выравнивание текста по левому краю
                    'valign': 'vcenter',             # Вертикальное выравнивание по центру
                    'text_wrap': True,              # Перенос текста
                    'border': 1,                    # Граница
                    'indent': 2                     # Отступ слева
                })

                text_center_format = workbook.add_format({
                    'font_name': 'Times New Roman',  # Устанавливаем шрифт
                    'font_size': 10,                 # Размер шрифта 10pt
                    'align': 'center',               # Выравнивание текста по центру
                    'valign': 'vcenter',             # Выравнивание по центру по вертикали
                    'text_wrap': True,               # Перенос слов (разрыв строк)
                    'border': 1                      # Границы ячейки
                })

                # Заголовки
                worksheet.merge_range(
                    "A1:N1", 
                    "ПРИЛОЖЕНИЕ А", 
                    title_format)
                worksheet.merge_range(
                    "A2:N2", 
                    "Перечень электростанций, действующих и планируемых к сооружению, расширению, модернизации и выводу из эксплуатации", 
                    title_format)
                worksheet.merge_range(
                    "A3:N3", 
                    "",
                    title_format)
                worksheet.merge_range(
                    "A4:N4",
                    f"Таблица А.1 – Перечень действующих электростанций, с указанием состава генерирующего оборудования и планов по выводу из эксплуатации, реконструкции (модернизации или перемаркировке), вводу в эксплуатацию генерирующего оборудования в период до {Config.END_YEAR_SIPR} года",
                    subtitle_format
                )
                worksheet.set_row(3, 42)

                # Шапка таблицы
                col_names = ["Электростанция", "Генерирующая компания", "Станционный номер",
                            "Тип генерирующего оборудования", "Вид топлива", "Примечание"]
                num_cols = len(col_names) - 1  # Без "Примечание"

                # Объединяем и форматируем первый столбец (первая колонка шапки)
                worksheet.merge_range(4, 0, 5, 0, col_names[0], text_format)

                # Объединяем и форматируем остальные столбцы
                for col_num in range(1, num_cols):  # Начинаем с 1, чтобы не дублировать первый столбец
                    worksheet.merge_range(4, col_num, 5, col_num, col_names[col_num], text_center_format)

                # Первая строка над мощностями
                worksheet.merge_range(4, num_cols, 4, num_cols + len(all_years) - 1, "Установленная мощность (МВт)", text_center_format)

                # Заменяем первый год на "По состоянию на 01.01.<год>"
                first_year = all_years[0] + 1  # Берем первый год из списка
                year_headers = ["По состоянию на 01.01.{}".format(first_year)] + [str(year) for year in all_years[1:]]

                # Вторая строка - годы
                for idx, year in enumerate(year_headers):
                    col_num = num_cols + idx
                    worksheet.write(5, col_num, year, text_center_format)

                # Устанавливаем особую ширину для первого года
                first_year_col_idx = num_cols  # Столбец первого года
                worksheet.set_column(first_year_col_idx, first_year_col_idx, 12.86, text_center_format)

                # Устанавливаем стандартную ширину для остальных годов
                for idx in range(1, len(all_years)):  # Пропускаем первый год
                    col_num = num_cols + idx
                    worksheet.set_column(col_num, col_num, 8, text_center_format)

                # Добавляем "Примечание" в 1 строке
                worksheet.merge_range(4, num_cols + len(all_years), 5, num_cols + len(all_years), "Примечание", text_center_format)

                # Определяем индекс нужного столбца
                station_column_name = "Электростанция"
                gen_company_column_name = "Генерирующая компания"
                machine_number_column_name = "Станционный номер"
                machine_name_column_name = "Тип генерирующего оборудования"
                fuel_type_name = "Вид топлива"
                note_column_name = "Примечание"

                station_col_idx = df.columns.get_loc(station_column_name)
                gen_company_col_idx = df.columns.get_loc(gen_company_column_name)
                machine_number_col_idx = df.columns.get_loc(machine_number_column_name)
                machine_name_col_idx = df.columns.get_loc(machine_name_column_name)
                fuel_type_col_idx = df.columns.get_loc(fuel_type_name)
                p_ust_col_idxs = {year: df.columns.get_loc(year) for year in all_years}
                note_column_col_idx = df.columns.get_loc(note_column_name)

                # Применяем ширину и формат к столбцам
                worksheet.set_column(station_col_idx, station_col_idx, 30.29, text_format)
                worksheet.set_column(gen_company_col_idx, gen_company_col_idx, 17, text_center_format)
                worksheet.set_column(machine_number_col_idx, machine_number_col_idx, 12, text_center_format)
                worksheet.set_column(machine_name_col_idx, machine_name_col_idx, 20.86, text_center_format)
                worksheet.set_column(fuel_type_col_idx, fuel_type_col_idx, 11.29, text_center_format)
                
                worksheet.set_column(note_column_col_idx, note_column_col_idx, 28.71, text_center_format)

                # Определяем диапазон объединения (все столбцы)
                start_col = 0
                end_col = len(df.columns) - 5  # Последний столбец

                # Найти индекс строки, где находится региональная энергосистема (первое ее появление в data)
                regional_row_idx = next(
                    (i for i, row in enumerate(data) if row["Электростанция"] == region_label),
                    None
                )

                # Объединяем ячейки в Excel
                worksheet.merge_range(
                    regional_row_idx + 6, 
                    start_col, 
                    regional_row_idx + 6, 
                    end_col,  # +6 из-за заголовков
                    region_label, 
                    text_format)

                # Определяем последнюю заполненную строку
                last_row = len(df) + 6  # +5 из-за заголовков

                # Определяем последний используемый столбец
                last_col = len(df.columns)

                start_excel_row = 6  # Потому что DataFrame начинается с строки 6 в Excel
                for i, row in df.iterrows():
                    excel_row = i + start_excel_row
                    
                    group_rowspan = int(row["_group_rowspan"] or 0)
                    total_machines = int(row["_total_machines"] or 0)
                    has_groups = row.get("Есть группы", "") == "Да"

                    if has_groups and 1 <= group_rowspan <= total_machines:
                        worksheet.merge_range(
                            excel_row,
                            station_col_idx,
                            excel_row + group_rowspan - 1,
                            station_col_idx,
                            row["Электростанция"],
                            text_format_group
                        )

                    # Объединение "Вид топлива"
                    fuel_rowspan = int(row["_fuel_rowspan"] or 0)

                    if fuel_rowspan > 1:
                        worksheet.merge_range(
                            excel_row,
                            fuel_type_col_idx,
                            excel_row + fuel_rowspan - 1,
                            fuel_type_col_idx,
                            row["Вид топлива"],
                            text_center_format
                        )
                        
                # Создаем пустой стиль (без границ, выравнивания и других атрибутов)
                empty_format = workbook.add_format()

                # Снимаем форматирование с пустых строк после таблицы
                for row_num in range(last_row, 1000):  # 1000 - большое число, можно сделать динамическим
                    worksheet.set_row(row_num, None, empty_format)

                # Снимаем форматирование с пустых столбцов после таблицы
                for col_num in range(last_col + 1, 50):  # 50 - запасное число столбцов
                    worksheet.set_column(col_num, col_num, None, empty_format)

            df = df.drop(
                columns=["_group_rowspan", "_fuel_rowspan", "_total_machines", "Есть группы"],
                errors="ignore"
            )
            output.seek(0)
            output_files.append((file_name, output))
    
        except Exception as e:
            error_message = f"❌ Ошибка экспорта субъекта {district_name}: {str(e)}\n{traceback.format_exc()}"
            log_to_db(user, error_message)
            print(error_message)

    log_to_db(user, "Экспорт завершен", f"Обработано {processed_stations} из {total_stations} станций.")

    return output_files[0] if len(output_files) == 1 else output_files



