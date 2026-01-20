import pandas as pd
from io import BytesIO
from datetime import datetime, date
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
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_explicit_db_version,
)
from app.generation.models.station.station_power_model import StationPower
from app.generation.models.machine.machine_power_model import MachinePower
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
    if val is None:
        return 0
    if val == 0:
        return 0
    # Поддержка режима "Не округлять" (digits is None)
    if digits is None:
        return val
    try:
        return round(val, digits) if digits >= 0 else int(round(val, 0))
    except Exception:
        return val

def build_name_lookup(items, name_attrs=("name_full", "name")):
    """Формирует словарь {id: name} из списка объектов/кортежей/словарей."""
    lookup = {}

    if not items:
        return lookup

    for item in items:
        if item is None:
            continue

        item_id = None
        item_name = None

        if isinstance(item, (tuple, list)):
            if len(item) >= 1:
                item_id = item[0]
            if len(item) >= 2:
                item_name = item[1]

        elif isinstance(item, dict):
            item_id = item.get("id")
            for attr in name_attrs:
                value = item.get(attr)
                if value:
                    item_name = value
                    break
            if item_name is None:
                for fallback_key in ("title", "label", "caption"):
                    value = item.get(fallback_key)
                    if value:
                        item_name = value
                        break

        else:
            item_id = getattr(item, "id", None)
            if item_id is None:
                try:
                    item_id = item[0]
                except (TypeError, KeyError, IndexError):
                    item_id = None

            for attr in name_attrs:
                value = getattr(item, attr, None)
                if value:
                    item_name = value
                    break

            if item_name is None:
                for attr in name_attrs:
                    try:
                        value = item[attr]
                        if value:
                            item_name = value
                            break
                    except (TypeError, KeyError, IndexError):
                        continue

            if item_name is None:
                alt = getattr(item, "title", None)
                if alt:
                    item_name = alt

        if item_id is None:
            continue

        # Для служебного id=0 всегда считаем, что это "не указано",
        # чтобы далее можно было единообразно фильтровать такие записи по названию.
        if item_id == 0:
            if not item_name or str(item_name).strip() == "" or str(item_name).startswith("id="):
                item_name = "не указано"

        if item_name is None:
            # Вместо "id=0" для нулевого идентификатора используем человекочитаемое "не указано"
            if item_id == 0:
                item_name = "не указано"
            else:
                item_name = f"id={item_id}"

        lookup[item_id] = item_name

    return lookup


def attach_all_aggregates(data, rows):
    """
    Привязывает все агрегаты к словарю data на основе уже полученных rows.
    Использует оптимизированную функцию aggregate_all_at_once для создания правильной структуры с database_version_id.
    """
    from app.generation.services.station_services.aggregation_station_services.optimized_aggregation import aggregate_all_at_once
    
    # Используем оптимизированную функцию, которая создает правильную структуру с database_version_id
    all_aggregations = aggregate_all_at_once(rows)
    data.update(all_aggregations)

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
        data["energy_unit_name"] = build_name_lookup(energy_unit_list, ("name_full", "name"))
    except Exception:
        data.setdefault("energy_unit_name", {})

    try:
        regional_district_list = get_regional_district_list_full()
        data["regional_district_name"] = build_name_lookup(regional_district_list, ("name_full", "name"))
    except Exception:
        data.setdefault("regional_district_name", {})

    try:
        regional_energy_system_list = get_regional_energy_system_list_full()
        data["regional_energy_system_name"] = build_name_lookup(regional_energy_system_list, ("name_full", "name"))
    except Exception:
        data.setdefault("regional_energy_system_name", {})

    try:
        union_energy_system_list = get_union_energy_system_list_full()
        data["union_energy_system_name"] = build_name_lookup(union_energy_system_list, ("name_full", "name"))
    except Exception:
        data.setdefault("union_energy_system_name", {})

    try:
        energy_system_type_list = get_energy_system_type_list_full()
        data["energy_system_type_name"] = build_name_lookup(energy_system_type_list, ("name_full", "name"))
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
def generate_excel_export_with_all_totals(data, rows, start_year, end_year, rounding_digits, show_p_ogr=False, show_p_rasp=False, hide_aggregates=False, show_totals=True):
    # Проверка наличия необходимых библиотек
    try:
        import openpyxl
    except ImportError as e:
        error_msg = f"Библиотека openpyxl не установлена. Установите её командой: pip install openpyxl"
        print(f"[EXPORT] ОШИБКА: {error_msg}")
        raise ImportError(error_msg) from e
    
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
            data["energy_unit_name"] = build_name_lookup(energy_unit_list, ("name_full", "name"))
        except Exception:
            data["energy_unit_name"] = {}

    if "regional_district_name" not in data:
        try:
            regional_district_list = get_regional_district_list_full()
            data["regional_district_name"] = build_name_lookup(regional_district_list, ("name_full", "name"))
        except Exception:
            data["regional_district_name"] = {}

    if "regional_energy_system_name" not in data:
        try:
            regional_energy_system_list = get_regional_energy_system_list_full()
            data["regional_energy_system_name"] = build_name_lookup(regional_energy_system_list, ("name_full", "name"))
        except Exception:
            data["regional_energy_system_name"] = {}

    if "union_energy_system_name" not in data:
        try:
            union_energy_system_list = get_union_energy_system_list_full()
            data["union_energy_system_name"] = build_name_lookup(union_energy_system_list, ("name_full", "name"))
        except Exception:
            data["union_energy_system_name"] = {}

    if "energy_system_type_name" not in data:
        try:
            energy_system_type_list = get_energy_system_type_list_full()
            data["energy_system_type_name"] = build_name_lookup(energy_system_type_list, ("name_full", "name"))
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

    print(f"[EXPORT] Начало формирования строк данных. stations_grouped содержит {len(stations_grouped)} групп")

    def add_machine_row(machine, station_name, subject_name):
        # Определяем отображаемое название типа агрегата ТЭС:
        # раньше скрывали по id == 0, теперь скрываем по названию "не указано"
        tes_machine_type_name = "—"
        if machine.tes_machine_type and getattr(machine.tes_machine_type, "name", None):
            name_lower = machine.tes_machine_type.name.lower()
            if "не указано" not in name_lower and "не указан" not in name_lower:
                tes_machine_type_name = machine.tes_machine_type.name

        row_ust = {
            "ID электростанции": machine.machine_station.id if machine.machine_station else "",
            "ID агрегата": machine.id,
            "Электростанция": machine.machine_number,
            " ": machine.machine_name,
            "Генерирующая компания": machine.gen_company.name if machine.gen_company else "—",
            "Год ввода": machine.date_exploitation,
            "Тип мощности": "Руст",
            "Тип станции": machine.machine_station.station_type.name if machine.machine_station and machine.machine_station.station_type else "—",
            "Тип ТЭС": machine.tes_types or "—",
            "Тип агрегата ТЭС": tes_machine_type_name,
            "Примечание": machine.note or "",
        }
        for year in range(start_year, end_year + 1):
            row_ust[str(year)] = round_val(machine.powers_by_year.get(year, {}).get("p_ust"))
            row_ust[f"{year} (топливо)"] = machine.fuel_type_by_year.get(year, "—")
        rows.append(row_ust)

        if show_p_ogr:
            row_ogr = {k: "" for k in row_ust}
            row_ogr.update({
                "Тип мощности": "Рогр",
                "ID электростанции": "",
                "ID агрегата": "",
            })
            for year in range(start_year, end_year + 1):
                row_ogr[str(year)] = round_val(machine.powers_by_year.get(year, {}).get("p_ogr"))
            rows.append(row_ogr)

        if show_p_rasp:
            row_rasp = {k: "" for k in row_ust}
            row_rasp.update({
                "Тип мощности": "Ррасп",
                "ID электростанции": "",
                "ID агрегата": "",
            })
            for year in range(start_year, end_year + 1):
                row_rasp[str(year)] = round_val(machine.powers_by_year.get(year, {}).get("p_rasp"))
            rows.append(row_rasp)

    def add_station_total_row(station):
        def total_row(label, power_key, show_name=False):
            row = {
                "ID электростанции": "",
                "ID агрегата": "",
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
        from collections import defaultdict
        from decimal import Decimal
        from app.common.services.database_version_filter import get_current_db_version_id
        
        config = AGGREGATION_CONFIG[level_key]
        current_version_id = get_current_db_version_id()
        
        # Отладка: проверяем наличие словаря названий
        name_dict_key = config.get("name_dict")
        if name_dict_key and name_dict_key in data:
            level_name = data[name_dict_key].get(level_id, f"id={level_id}")
            print(f"[DEBUG] add_named_total_row: level_key={level_key}, level_id={level_id}, level_name={level_name}")

            # Если для уровня энергоузла / субъекта и т.п. в названии указано "не указано",
            # то агрегаты по такому уровню не выводим (раньше ориентировались на id == 0)
            if level_name and isinstance(level_name, str):
                lvl_name_lower = level_name.lower()
                if "не указано" in lvl_name_lower or "не указан" in lvl_name_lower:
                    print(f"[DEBUG] add_named_total_row: пропуск level_id={level_id} (name='{level_name}') по причине 'не указано'")
                    return
        else:
            print(f"[DEBUG] add_named_total_row: level_key={level_key}, level_id={level_id}, name_dict_key={name_dict_key} NOT FOUND in data keys: {list(data.keys())[:20]}")

        # Для "russia" структура данных плоская (без entity_id), для остальных - вложенная
        if level_key == "russia":
            # Для России данные хранятся с ключом database_version_id
            aggregated_power_data = data.get(config["aggregated_power_key"])
            if not aggregated_power_data:
                print(f"[WARNING] Ключ {config['aggregated_power_key']} отсутствует в data для level_key=russia. Доступные ключи: {list(data.keys())[:20]}")
                aggregated = {}
            else:
                aggregated = aggregated_power_data.get("aggregated", {})
                print(f"[DEBUG] add_named_total_row для russia: aggregated keys = {list(aggregated.keys())}")
            
            # Получаем данные по годам (может быть defaultdict или обычный dict)
            p_ust_dict = aggregated.get("p_ust", {})
            p_ogr_dict = aggregated.get("p_ogr", {})
            p_rasp_dict = aggregated.get("p_rasp", {})
            
            # Проверяем наличие данных и структуру
            if p_ust_dict:
                print(f"[DEBUG] add_named_total_row для russia: p_ust_dict имеет {len(p_ust_dict)} элементов, примеры: {list(p_ust_dict.items())[:3] if p_ust_dict else 'пусто'}")
            else:
                print(f"[DEBUG] add_named_total_row для russia: p_ust_dict пуст или отсутствует")
            
            # Извлекаем данные для текущей версии БД
            p_ust_flat = p_ust_dict
            p_ogr_flat = p_ogr_dict
            p_rasp_flat = p_rasp_dict
            
            if p_ust_dict and isinstance(p_ust_dict, dict) and len(p_ust_dict) > 0:
                # Проверяем, является ли структура вложенной (с ключом version_id) или плоской (с ключом year)
                # Для этого проверяем все ключи - если хотя бы один ключ не в диапазоне [start_year, end_year], 
                # значит это вложенная структура с version_id
                sample_keys = list(p_ust_dict.keys())[:5]  # Проверяем первые 5 ключей
                is_nested_structure = any(
                    not isinstance(k, int) or (k < start_year or k > end_year)
                    for k in sample_keys
                )
                
                if is_nested_structure:
                    # Структура вложенная с ключом version_id, извлекаем по текущей версии
                    if current_version_id in p_ust_dict:
                        p_ust_flat = p_ust_dict[current_version_id]
                        print(f"[DEBUG] add_named_total_row для russia: извлечен словарь по version_id={current_version_id}")
                    else:
                        # Если текущей версии нет, пробуем аккуратно выбрать подходящую:
                        # - если есть ровно одна доступная версия, просто используем её без предупреждения
                        # - если версий несколько, используем первую и пишем мягкий debug-лог
                        available_versions = [
                            k for k in p_ust_dict.keys()
                            if isinstance(k, int) and (k < start_year or k > end_year)
                        ]
                        if available_versions:
                            fallback_version = available_versions[0]
                            p_ust_flat = p_ust_dict[fallback_version]
                            log_level = "DEBUG" if len(available_versions) == 1 else "WARNING"
                            print(f"[{log_level}] add_named_total_row для russia: "
                                  f"version_id={current_version_id} не найден, использован ключ {fallback_version}")
                        else:
                            p_ust_flat = next(iter(p_ust_dict.values()))
                            print(f"[DEBUG] add_named_total_row для russia: "
                                  f"version_id={current_version_id} не найден, использован первый доступный ключ")
                else:
                    # Структура плоская с ключами-годами, используем напрямую
                    p_ust_flat = p_ust_dict
                    print(f"[DEBUG] add_named_total_row для russia: обнаружена плоская структура p_ust (ключи - годы)")
                
            if p_ogr_dict and isinstance(p_ogr_dict, dict) and len(p_ogr_dict) > 0:
                sample_keys = list(p_ogr_dict.keys())[:5]
                is_nested_structure = any(
                    not isinstance(k, int) or (k < start_year or k > end_year)
                    for k in sample_keys
                )
                if is_nested_structure:
                    if current_version_id in p_ogr_dict:
                        p_ogr_flat = p_ogr_dict[current_version_id]
                    else:
                        available_versions = [k for k in p_ogr_dict.keys() if isinstance(k, int) and (k < start_year or k > end_year)]
                        p_ogr_flat = p_ogr_dict.get(available_versions[0] if available_versions else next(iter(p_ogr_dict.keys())), next(iter(p_ogr_dict.values())))
                else:
                    p_ogr_flat = p_ogr_dict
                    
            if p_rasp_dict and isinstance(p_rasp_dict, dict) and len(p_rasp_dict) > 0:
                sample_keys = list(p_rasp_dict.keys())[:5]
                is_nested_structure = any(
                    not isinstance(k, int) or (k < start_year or k > end_year)
                    for k in sample_keys
                )
                if is_nested_structure:
                    if current_version_id in p_rasp_dict:
                        p_rasp_flat = p_rasp_dict[current_version_id]
                    else:
                        available_versions = [k for k in p_rasp_dict.keys() if isinstance(k, int) and (k < start_year or k > end_year)]
                        p_rasp_flat = p_rasp_dict.get(available_versions[0] if available_versions else next(iter(p_rasp_dict.keys())), next(iter(p_rasp_dict.values())))
                else:
                    p_rasp_flat = p_rasp_dict
            
            # Для defaultdict используем прямой доступ [year], чтобы получить значение по умолчанию
            # если данных нет (например, Decimal(0)). Для обычного dict используем .get(year, 0)
            power_data = {}
            for year in range(start_year, end_year + 1):
                if isinstance(p_ust_flat, defaultdict):
                    p_ust_val = p_ust_flat[year]  # Прямой доступ создаст Decimal(0) если ключа нет
                elif isinstance(p_ust_flat, dict):
                    p_ust_val = p_ust_flat.get(year)
                else:
                    p_ust_val = None
                    
                if isinstance(p_ogr_flat, defaultdict):
                    p_ogr_val = p_ogr_flat[year]
                elif isinstance(p_ogr_flat, dict):
                    p_ogr_val = p_ogr_flat.get(year)
                else:
                    p_ogr_val = None
                    
                if isinstance(p_rasp_flat, defaultdict):
                    p_rasp_val = p_rasp_flat[year]
                elif isinstance(p_rasp_flat, dict):
                    p_rasp_val = p_rasp_flat.get(year)
                else:
                    p_rasp_val = None
                    
                power_data[year] = {
                    "p_ust": p_ust_val,
                    "p_ogr": p_ogr_val,
                    "p_rasp": p_rasp_val,
                }
            
            # Проверяем результат
            sample_year_values = {year: power_data[year]["p_ust"] for year in range(start_year, min(start_year + 3, end_year + 1))}
            print(f"[DEBUG] add_named_total_row для russia: примеры значений power_data (первые 3 года): {sample_year_values}")
        else:
            aggregated_power_key_data = data.get(config["aggregated_power_key"])
            if not aggregated_power_key_data:
                print(f"[WARNING] Ключ {config['aggregated_power_key']} отсутствует в data для level_key={level_key}, level_id={level_id}")
                power_data = {year: {"p_ust": None, "p_ogr": None, "p_rasp": None} for year in range(start_year, end_year + 1)}
            else:
                power_data = get_aggregated_power_by_year(
                    level_id,
                    aggregated_power_key_data,
                    start_year,
                    end_year
                )

        # Для "russia" структура данных с ключом version_id, для остальных - вложенная
        if level_key == "russia":
            # Для России данные хранятся с ключом database_version_id
            all_station_type_data = data.get(config["station_type_key"], {}).get("aggregated", {}).get("p_ust", {})
            all_tes_type_data = data.get(config["tes_type_key"], {}).get("aggregated", {}).get("p_ust", {})
            all_tes_machine_type_data = data.get(config["tes_machine_type_key"], {}).get("aggregated", {}).get("p_ust", {})
            all_fuel_type_data = data.get(config["fuel_type_key"], {}).get("aggregated", {}).get("p_ust", {})
            
            # Извлекаем данные для текущей версии
            station_type_data = all_station_type_data.get(current_version_id, all_station_type_data.get(1, {})) if isinstance(all_station_type_data, dict) and all_station_type_data else {}
            tes_type_data = all_tes_type_data.get(current_version_id, all_tes_type_data.get(1, {})) if isinstance(all_tes_type_data, dict) and all_tes_type_data else {}
            tes_machine_type_data = all_tes_machine_type_data.get(current_version_id, all_tes_machine_type_data.get(1, {})) if isinstance(all_tes_machine_type_data, dict) and all_tes_machine_type_data else {}
            fuel_type_data = all_fuel_type_data.get(current_version_id, all_fuel_type_data.get(1, {})) if isinstance(all_fuel_type_data, dict) and all_fuel_type_data else {}
        else:
            station_type_data = data.get(config["station_type_key"], {}).get("aggregated", {}).get("p_ust", {})
            tes_type_data = data.get(config["tes_type_key"], {}).get("aggregated", {}).get("p_ust", {})
            tes_machine_type_data = data.get(config["tes_machine_type_key"], {}).get("aggregated", {}).get("p_ust", {})
            fuel_type_data = data.get(config["fuel_type_key"], {}).get("aggregated", {}).get("p_ust", {})

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


        station_type_data_ogr = data.get(config["station_type_key"], {}).get("aggregated", {}).get("p_ogr", {}) if show_p_ogr else {}
        station_type_data_rasp = data.get(config["station_type_key"], {}).get("aggregated", {}).get("p_rasp", {}) if show_p_rasp else {}

        # Для "russia" данные хранятся без level_id, для остальных - с level_id
        if level_key == "russia":
            # Извлекаем данные для текущей версии
            all_st_data_ogr = station_type_data_ogr
            all_st_data_rasp = station_type_data_rasp
            station_type_dict = station_type_data
            station_type_dict_ogr = all_st_data_ogr.get(current_version_id, all_st_data_ogr.get(1, {})) if isinstance(all_st_data_ogr, dict) and all_st_data_ogr else {}
            station_type_dict_rasp = all_st_data_rasp.get(current_version_id, all_st_data_rasp.get(1, {})) if isinstance(all_st_data_rasp, dict) and all_st_data_rasp else {}
        else:
            station_type_dict = station_type_data.get(level_id, {})
            station_type_dict_ogr = station_type_data_ogr.get(level_id, {})
            station_type_dict_rasp = station_type_data_rasp.get(level_id, {})

        # Объединяем ВЭС и СЭС в группу ВИЭ
        vie_aggregated = {
            "p_ust": defaultdict(lambda: Decimal(0)),
            "p_ogr": defaultdict(lambda: Decimal(0)),
            "p_rasp": defaultdict(lambda: Decimal(0))
        }
        vie_station_type_ids = []  # Запоминаем ID которые объединяем в ВИЭ
        
        for st_id, st_name in station_type_names.items():
            if st_name and ("вэс" in st_name.lower() or "сэс" in st_name.lower() or "виэ" in st_name.lower()):
                vie_station_type_ids.append(st_id)
                # Суммируем данные для ВИЭ
                if st_id in station_type_dict:
                    for year, val in station_type_dict[st_id].items():
                        vie_aggregated["p_ust"][year] += val or Decimal(0)
                if st_id in station_type_dict_ogr:
                    for year, val in station_type_dict_ogr.get(st_id, {}).items():
                        vie_aggregated["p_ogr"][year] += val or Decimal(0)
                if st_id in station_type_dict_rasp:
                    for year, val in station_type_dict_rasp.get(st_id, {}).items():
                        vie_aggregated["p_rasp"][year] += val or Decimal(0)

        # Сортировка типов станций: АЭС, ГЭС, ГАЭС, ТЭС (ВИЭ добавим отдельно ниже)
        def station_type_order(name: str) -> int:
            n = (name or "").lower()
            if "аэс" in n:
                return 0
            if "гэс" in n and "гаэс" not in n:
                return 1
            if "гаэс" in n:
                return 2
            if "тэс" in n:
                return 3
            return 9

        # Преобразуем в отсортированный список пар (id, данные)
        station_type_items_sorted = sorted(
            station_type_dict.items(),
            key=lambda item: (
                station_type_order(station_type_names.get(item[0], f"id={item[0]}")),
                station_type_names.get(item[0], "")
            )
        )

        for station_type_id, st_years in station_type_items_sorted:
            if station_type_id is None:
                continue

            # Пропускаем ВЭС и СЭС - они будут выведены как ВИЭ
            if station_type_id in vie_station_type_ids:
                continue

            station_type_name = station_type_names.get(station_type_id, f"id={station_type_id}")

            # Если тип станции имеет служебное или неопределённое название,
            # то не отображаем его агрегации:
            #  - "не указано"/"не указан"
            #  - технические подписи вида "id=0", "id=123" и т.п.
            st_name_str = station_type_name.strip()
            st_name_lower = st_name_str.lower()
            if "не указано" not in st_name_lower:
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
                        val = station_type_dict_ogr.get(station_type_id, {}).get(year) if isinstance(station_type_dict_ogr, dict) and station_type_id in station_type_dict_ogr else None
                        row_ogr[str(year)] = round_val(val) if val is not None else None
                    rows.append(row_ogr)

                if show_p_rasp:
                    row_rasp = {k: "" for k in row_st}
                    row_rasp["Тип мощности"] = "Ррасп"
                    for year in range(start_year, end_year + 1):
                        val = station_type_dict_rasp.get(station_type_id, {}).get(year) if isinstance(station_type_dict_rasp, dict) and station_type_id in station_type_dict_rasp else None
                        row_rasp[str(year)] = round_val(val) if val is not None else None
                    rows.append(row_rasp)

            # Проверяем, является ли тип станции тепловым (показываем детализацию по ТЭС)
            if "тэс" in st_name_lower:
                tes_type_section = data.get(config["tes_type_key"], {})
                # Извлекаем агрегаты по типам ТЭС с учетом текущей версии для России
                if isinstance(tes_type_section, dict):
                    if show_p_ogr:
                        all_tes_ogr = tes_type_section.get("aggregated", {}).get("p_ogr", {})
                        tes_type_data_ogr = (
                            all_tes_ogr.get(current_version_id, all_tes_ogr.get(1, {}))
                            if level_key == "russia" and isinstance(all_tes_ogr, dict)
                            else all_tes_ogr
                        )
                    else:
                        tes_type_data_ogr = {}
                    if show_p_rasp:
                        all_tes_rasp = tes_type_section.get("aggregated", {}).get("p_rasp", {})
                        tes_type_data_rasp = (
                            all_tes_rasp.get(current_version_id, all_tes_rasp.get(1, {}))
                            if level_key == "russia" and isinstance(all_tes_rasp, dict)
                            else all_tes_rasp
                        )
                    else:
                        tes_type_data_rasp = {}
                else:
                    tes_type_data_ogr = {}
                    tes_type_data_rasp = {}

                # Для "russia" данные хранятся без level_id
                if level_key == "russia":
                    tes_type_dict = tes_type_data
                    tes_type_dict_ogr = tes_type_data_ogr
                    tes_type_dict_rasp = tes_type_data_rasp
                else:
                    tes_type_dict = tes_type_data.get(level_id, {})
                    tes_type_dict_ogr = tes_type_data_ogr.get(level_id, {})
                    tes_type_dict_rasp = tes_type_data_rasp.get(level_id, {})

                for tes_type_id, tt_years in tes_type_dict.items():
                    if tes_type_id is None:
                        continue

                    tes_type_name = tes_type_names.get(tes_type_id, f"id={tes_type_id}")
                    
                    # Пропускаем типы ТЭС с названием "не указано"
                    if tes_type_name and "не указано" in tes_type_name.lower():
                        continue
                    
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
                        row_ogr = {k: "" for k in row_tt}
                        row_ogr["Тип мощности"] = "Рогр"
                        for year in range(start_year, end_year + 1):
                            val = tes_type_dict_ogr.get(tes_type_id, {}).get(year) if isinstance(tes_type_dict_ogr, dict) and tes_type_id in tes_type_dict_ogr else None
                            row_ogr[str(year)] = round_val(val) if val is not None else None
                        rows.append(row_ogr)

                    if show_p_rasp:
                        row_rasp = {k: "" for k in row_tt}
                        row_rasp["Тип мощности"] = "Ррасп"
                        for year in range(start_year, end_year + 1):
                            val = tes_type_dict_rasp.get(tes_type_id, {}).get(year) if isinstance(tes_type_dict_rasp, dict) and tes_type_id in tes_type_dict_rasp else None
                            row_rasp[str(year)] = round_val(val) if val is not None else None
                        rows.append(row_rasp)

                    # Для "russia" данные хранятся без level_id
                    if level_key == "russia":
                        mt_dict = tes_machine_type_data.get(tes_type_id, {})
                        # Для России извлекаем данные по текущей версии
                        if show_p_ogr:
                            all_mt_data_ogr = data[config["tes_machine_type_key"]].get("aggregated", {}).get("p_ogr", {})
                            tes_machine_type_data_ogr = all_mt_data_ogr.get(current_version_id, all_mt_data_ogr.get(1, {})) if isinstance(all_mt_data_ogr, dict) and all_mt_data_ogr else {}
                        else:
                            tes_machine_type_data_ogr = {}
                        if show_p_rasp:
                            all_mt_data_rasp = data[config["tes_machine_type_key"]].get("aggregated", {}).get("p_rasp", {})
                            tes_machine_type_data_rasp = all_mt_data_rasp.get(current_version_id, all_mt_data_rasp.get(1, {})) if isinstance(all_mt_data_rasp, dict) and all_mt_data_rasp else {}
                        else:
                            tes_machine_type_data_rasp = {}
                    else:
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
                            row_ogr = {k: "" for k in row_mt}
                            row_ogr["Тип мощности"] = "Рогр"
                            for year in range(start_year, end_year + 1):
                                if level_key == "russia":
                                    val = tes_machine_type_data_ogr.get(tes_type_id, {}).get(machine_type_id, {}).get(year)
                                else:
                                    val = tes_machine_type_data_ogr.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {}).get(year)
                                row_ogr[str(year)] = round_val(val) if val is not None else None
                            rows.append(row_ogr)

                        if show_p_rasp:
                            row_rasp = {k: "" for k in row_mt}
                            row_rasp["Тип мощности"] = "Ррасп"
                            for year in range(start_year, end_year + 1):
                                if level_key == "russia":
                                    val = tes_machine_type_data_rasp.get(tes_type_id, {}).get(machine_type_id, {}).get(year)
                                else:
                                    val = tes_machine_type_data_rasp.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {}).get(year)
                                row_rasp[str(year)] = round_val(val) if val is not None else None
                            rows.append(row_rasp)

                        # Для "russia" данные хранятся без level_id
                        if level_key == "russia":
                            fuel_dict = fuel_type_data.get(tes_type_id, {}).get(machine_type_id, {})
                            # Для России извлекаем данные по текущей версии
                            if show_p_ogr:
                                all_fuel_data_ogr = data[config["fuel_type_key"]].get("aggregated", {}).get("p_ogr", {})
                                fuel_type_data_ogr = all_fuel_data_ogr.get(current_version_id, all_fuel_data_ogr.get(1, {})) if isinstance(all_fuel_data_ogr, dict) and all_fuel_data_ogr else {}
                            else:
                                fuel_type_data_ogr = {}
                            if show_p_rasp:
                                all_fuel_data_rasp = data[config["fuel_type_key"]].get("aggregated", {}).get("p_rasp", {})
                                fuel_type_data_rasp = all_fuel_data_rasp.get(current_version_id, all_fuel_data_rasp.get(1, {})) if isinstance(all_fuel_data_rasp, dict) and all_fuel_data_rasp else {}
                            else:
                                fuel_type_data_rasp = {}
                        else:
                            fuel_dict = fuel_type_data.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {})
                            fuel_type_data_ogr = data[config["fuel_type_key"]].get("aggregated", {}).get("p_ogr", {}) if show_p_ogr else {}
                            fuel_type_data_rasp = data[config["fuel_type_key"]].get("aggregated", {}).get("p_rasp", {}) if show_p_rasp else {}

                        for fuel_type_id, fuel_years in fuel_dict.items():
                            if fuel_type_id is None:
                                continue
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
                                row_ogr = {k: "" for k in row_ft}
                                row_ogr["Тип мощности"] = "Рогр"
                                for year in range(start_year, end_year + 1):
                                    if level_key == "russia":
                                        val = fuel_type_data_ogr.get(tes_type_id, {}).get(machine_type_id, {}).get(fuel_type_id, {}).get(year)
                                    else:
                                        val = fuel_type_data_ogr.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {}).get(fuel_type_id, {}).get(year)
                                    row_ogr[str(year)] = round_val(val) if val is not None else None
                                rows.append(row_ogr)

                            if show_p_rasp:
                                row_rasp = {k: "" for k in row_ft}
                                row_rasp["Тип мощности"] = "Ррасп"
                                for year in range(start_year, end_year + 1):
                                    if level_key == "russia":
                                        val = fuel_type_data_rasp.get(tes_type_id, {}).get(machine_type_id, {}).get(fuel_type_id, {}).get(year)
                                    else:
                                        val = fuel_type_data_rasp.get(level_id, {}).get(tes_type_id, {}).get(machine_type_id, {}).get(fuel_type_id, {}).get(year)
                                    row_rasp[str(year)] = round_val(val) if val is not None else None
                                rows.append(row_rasp)

        # Добавляем ВИЭ (сумма ВЭС+СЭС) после разбивок по ТЭС
        if vie_station_type_ids and any(vie_aggregated["p_ust"].values()):
            # Сначала общая сумма ВИЭ
            row_vie = {
                "Электростанция": "   ВИЭ",
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
                row_vie[str(year)] = round_val(vie_aggregated["p_ust"].get(year)) if vie_aggregated["p_ust"].get(year) else None
                row_vie[f"Топливо {year}"] = None
            rows.append(row_vie)

            if show_p_ogr:
                row_ogr_vie = {k: "" for k in row_vie}
                row_ogr_vie["Тип мощности"] = "Рогр"
                for year in range(start_year, end_year + 1):
                    row_ogr_vie[str(year)] = round_val(vie_aggregated["p_ogr"].get(year)) if vie_aggregated["p_ogr"].get(year) else None
                rows.append(row_ogr_vie)

            if show_p_rasp:
                row_rasp_vie = {k: "" for k in row_vie}
                row_rasp_vie["Тип мощности"] = "Ррасп"
                for year in range(start_year, end_year + 1):
                    row_rasp_vie[str(year)] = round_val(vie_aggregated["p_rasp"].get(year)) if vie_aggregated["p_rasp"].get(year) else None
                rows.append(row_rasp_vie)

            # Затем разбивка по отдельным типам (ВЭС и СЭС), если строка не нулевая
            for st_id in vie_station_type_ids:
                st_name = station_type_names.get(st_id, f"id={st_id}")
                st_years_data = station_type_dict.get(st_id, {})
                
                # Проверяем, есть ли ненулевые значения
                has_nonzero = any(val and val != 0 for val in st_years_data.values())
                
                if has_nonzero:
                    row_st_detail = {
                        "Электростанция": f"      {st_name}",
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
                        row_st_detail[str(year)] = round_val(st_years_data.get(year)) if st_years_data.get(year) is not None else None
                        row_st_detail[f"Топливо {year}"] = None
                    rows.append(row_st_detail)

                    if show_p_ogr:
                        st_years_ogr = station_type_dict_ogr.get(st_id, {})
                        row_ogr_detail = {k: "" for k in row_st_detail}
                        row_ogr_detail["Тип мощности"] = "Рогр"
                        for year in range(start_year, end_year + 1):
                            row_ogr_detail[str(year)] = round_val(st_years_ogr.get(year)) if st_years_ogr.get(year) is not None else None
                        rows.append(row_ogr_detail)

                    if show_p_rasp:
                        st_years_rasp = station_type_dict_rasp.get(st_id, {})
                        row_rasp_detail = {k: "" for k in row_st_detail}
                        row_rasp_detail["Тип мощности"] = "Ррасп"
                        for year in range(start_year, end_year + 1):
                            row_rasp_detail[str(year)] = round_val(st_years_rasp.get(year)) if st_years_rasp.get(year) is not None else None
                        rows.append(row_rasp_detail)

        # Добавляем пустую строку после итогов по уровню
        rows.append({})
        
    try:
        for es_type_id, es_type_group in stations_grouped.items():
            es_name = data.get("energy_system_type_name", {}).get(es_type_id, f"id={es_type_id}")
            print(f"[EXPORT] Обработка типа энергосистемы {es_type_id}: {es_name}")
            for ues_id, ues_group in es_type_group.items():
                ues_name = data.get("union_energy_system_name", {}).get(ues_id, f"id={ues_id}")
                print(f"[EXPORT]   Обработка ОЭС {ues_id}: {ues_name}")
                for res_id, res_group in ues_group.items():
                    res_name = data.get("regional_energy_system_name", {}).get(res_id, f"id={res_id}")
                    print(f"[EXPORT]     Обработка РЭС {res_id}: {res_name}")
                    for rd_id, rd_group in res_group.items():
                        rd_name = data.get("regional_district_name", {}).get(rd_id, f"id={rd_id}")
                        if rd_name == f"id={rd_id}":
                            print(f"[WARNING] Не найдено название для regional_district_id={rd_id}, словарь содержит ключи: {list(data.get('regional_district_name', {}).keys())[:10]}")

                        print(f"[EXPORT]       Обработка субъекта {rd_id}: {rd_name}, станций: {sum(len(eu_group) for eu_group in rd_group.values())}")

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
                            # Показываем энергоузел только если имя не содержит "не указано"/"не указан"
                            # и не является технической подписью вида "id=0"
                            eu_name_str = str(eu_name) if eu_name is not None else ""
                            name_lower = eu_name_str.lower()
                            show_energy_unit = (
                                bool(eu_name_str)
                                and "не указано" not in name_lower
                                and "не указан" not in name_lower
                                and not eu_name_str.startswith("id=")
                            )
                            if show_energy_unit:
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
                                    "ID электростанции": station.id,
                                    "ID агрегата": "",
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

                                # В режиме "Скрыть агрегаты" не добавляем строк по агрегатам (машинам)
                                if not hide_aggregates:
                                    for machine in station.machines:
                                        add_machine_row(machine, station.name if first_machine else "", rd_name if first_machine else "")
                                        first_machine = False
                                if hasattr(station, "powers_by_year"):
                                    add_station_total_row(station)
                            # Показываем итого по энергоузлу только если энергоузел отображается
                            if show_energy_unit and show_totals:
                                add_named_total_row(eu_id, "energy_unit", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
                        # Показываем итого по субъекту только если в региональной энергосистеме больше одного субъекта
                        if show_totals and len(res_group) > 1:
                            add_named_total_row(rd_id, "regional_district", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
                    if show_totals:
                        add_named_total_row(res_id, "regional_energy_system", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
                if show_totals:
                    add_named_total_row(ues_id, "union_energy_system", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
            if show_totals:
                add_named_total_row(es_type_id, "energy_system_type", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)
        if show_totals:
            add_named_total_row("Россия", "russia", data, rows, start_year, end_year, round_val, show_p_ogr, show_p_rasp)

        print(f"[EXPORT] Завершено формирование строк данных. Всего строк: {len(rows)}")

    except Exception as e:
        print(f"[EXPORT] Ошибка при формировании строк данных: {e}")
        import traceback
        print(traceback.format_exc())
        raise

    print(f"[EXPORT] Формирование строк данных: {time.time() - t4:.2f}с, всего строк: {len(rows)}")

    t5 = time.time()
    year_columns = [str(year) for year in range(start_year, end_year + 1)]
    fuel_columns = [f"{year} (топливо)" for year in range(start_year, end_year + 1)]

    columns = [
        "ID электростанции",
        "ID агрегата",
        "Электростанция", " ", "Генерирующая компания",
        "Год ввода", "Тип мощности"
    ] + year_columns + fuel_columns + [
        "Тип станции", "Тип ТЭС", "Тип агрегата ТЭС", "Примечание"
    ]

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Font
    except ImportError as e:
        error_msg = f"Не удалось импортировать openpyxl: {e}. Установите библиотеку командой: pip install openpyxl"
        print(f"[EXPORT] ОШИБКА: {error_msg}")
        raise ImportError(error_msg) from e
    
    from io import BytesIO

    output = BytesIO()
    try:
        wb = Workbook()
        ws = wb.active
    except Exception as e:
        error_msg = f"Ошибка при создании Excel файла: {e}"
        print(f"[EXPORT] ОШИБКА: {error_msg}")
        import traceback
        print(traceback.format_exc())
        raise

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

    try:
        wb.save(output)
    except Exception as e:
        error_msg = f"Ошибка при сохранении Excel файла: {e}"
        print(f"[EXPORT] ОШИБКА: {error_msg}")
        import traceback
        print(traceback.format_exc())
        raise ValueError(error_msg) from e
    
    output.seek(0, 2)  # Переходим в конец для проверки размера
    final_size = output.tell()
    output.seek(0)  # Возвращаемся в начало

    print(f"[EXPORT] Запись в Excel файл: {time.time() - t5:.2f}с")
    print(f"[EXPORT] Финальный размер файла: {final_size} байт")
    print(f"[EXPORT] ИТОГО время экспорта: {time.time() - start_time:.2f}с")

    if final_size == 0:
        error_msg = "Сгенерированный Excel файл пустой. Возможные причины: нет данных для экспорта или ошибка при создании файла."
        print(f"[EXPORT] ОШИБКА: {error_msg}")
        raise ValueError(error_msg)

    return output

# Выгрузка в эксель по форме Приложения А к СиПР ЭЭС (по субъектам)
def export_station_sipr_ees_application_A_service(user, filters=None):
    log_to_db(user, "Начата выгрузка таблицы электростанций из базы данных")
    log_to_db(user, "Параметры экспорта", f"Фильтры: {filters}")

    query = get_stations_all(**filters)
    station_list = query.all()

    # Всегда работаем в контексте активной версии БД
    current_version_id = get_current_db_version_id()

    import re


    from app.common.services.get_services.years.years_get_services import (
        get_filter_start_year,
        get_filter_end_year,
        get_sipr_start_year,
        get_sipr_end_year,
    )

    year_start = get_filter_start_year()
    year_end = get_filter_end_year()
    sipr_start = get_sipr_start_year()
    sipr_end = get_sipr_end_year()

    # По состоянию на 01.01.<SIPR_START - 1> (например, при SIPR_START=2026 это 01.01.2025):
    # агрегаты/станции с фактической датой вывода ПОЗЖЕ этой даты должны попадать в выборку.
    as_of_date = date(int(sipr_start) - 1, 1, 1)

    def _parse_date_value(value):
        """
        Парсит дату из разных форматов в date.
        Поддерживаем как минимум:
        - YYYY-MM-DD (ISO)
        - DD.MM.YYYY (пользовательский формат)
        - YYYY (год)
        """
        if not value:
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()

        s = str(value).strip()
        if not s:
            return None

        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except Exception:
                continue

        # Иногда может прийти просто год
        if s.isdigit() and len(s) == 4:
            try:
                return date(int(s), 1, 1)
            except Exception:
                return None

        return None

    _DASH_RE = re.compile(r"[\s\-–—_]+", re.UNICODE)

    def _machine_number_sort_key(value):
        """
        Сортировка станционного номера:
        - сначала "чистые цифры": 1,2,3...
        - затем номера с буквами/префиксами: ГТУ-4, ГТУ-5, ПТУ-1...
          (по префиксу, затем по числу, затем по хвосту)
        - пустые/непарсимые — в конец
        """
        if value is None:
            return (2, "", 10**9, "")
        s = str(value).strip()
        if not s:
            return (2, "", 10**9, "")

        # 1) Только цифры -> идут первыми
        if s.isdigit():
            return (0, "", int(s), "")

        # 2) Есть число внутри -> префикс + число + суффикс
        m = re.search(r"\d+", s)
        if m:
            prefix_raw = s[: m.start()]
            prefix_norm = _DASH_RE.sub("", prefix_raw).strip().upper()
            n = int(m.group(0))
            suffix = _DASH_RE.sub("", s[m.end():]).strip().upper()
            return (1, prefix_norm, n, suffix)

        # 3) Вообще без цифр
        return (2, _DASH_RE.sub("", s).strip().upper(), 10**9, "")

    def _machine_sort_key(m):
        return (
            _machine_number_sort_key(getattr(m, "machine_number", None)),
            (getattr(m, "machine_name", None) or "").strip().lower(),
            getattr(m, "id", 0) or 0,
        )

    for station in station_list:
        # Фильтрация агрегатов по активной версии БД
        if hasattr(station, "machines"):
            # Сначала пробуем взять агрегаты именно для активной версии
            version_machines = [
                m for m in station.machines
                if getattr(m, "database_version_id", None) == current_version_id
            ]
            station.machines = version_machines

        # Фильтрация агрегатов по выводу из эксплуатации (по состоянию на 01.01.<SIPR_START - 1>)
        #
        # Правило:
        # - если фактическая дата вывода указана и она <= as_of_date → агрегат исключаем;
        # - если фактическая дата вывода указана и она > as_of_date → агрегат ВКЛЮЧАЕМ
        #   (даже если плановый год вывода раньше START_YEAR_SIPR);
        # - если фактической даты нет → используем прежний фильтр по плановому году вывода.
        filtered_machines = []
        for m in (station.machines or []):
            fact_dt = _parse_date_value(getattr(m, "date_decompressing_fact", None))
            if fact_dt is not None:
                if fact_dt > as_of_date:
                    filtered_machines.append(m)
                continue

            expected_year = getattr(m, "date_decompressing_expected", None)
            try:
                expected_year_int = int(expected_year) if expected_year is not None else None
            except Exception:
                expected_year_int = None

            if expected_year_int is None or expected_year_int >= int(sipr_start):
                filtered_machines.append(m)

        station.machines = filtered_machines
        # Явно фиксируем порядок агрегатов, чтобы он был одинаковым
        # как при выгрузке одного файла, так и при формировании ZIP по всем ЭС.
        station.machines.sort(key=_machine_sort_key)

        total_machines = len(station.machines)

        # Обнуляем значения
        for m in station.machines:
            m.group_rowspan = 0
            m.fuel_rowspan = 0

        def _set_rowspan_for_consecutive_runs(items, key_fn, attr_name):
            """
            Ставит rowspan только для ПОДРЯД идущих одинаковых значений.
            Это критично после сортировки: иначе merge может "перескочить" через чужие строки.
            """
            i = 0
            n = len(items)
            while i < n:
                k = key_fn(items[i])
                # Не объединяем пустые значения (но оставляем rowspan=0)
                if k in (None, ""):
                    i += 1
                    continue
                j = i + 1
                while j < n and key_fn(items[j]) == k:
                    j += 1
                run_len = j - i
                if run_len > 1:
                    setattr(items[i], attr_name, run_len)
                    for t in range(i + 1, j):
                        setattr(items[t], attr_name, 0)
                i = j

        # rowspan по группе агрегатов (machine_group) — только подряд идущие
        _set_rowspan_for_consecutive_runs(
            station.machines,
            key_fn=lambda m: (getattr(m, "machine_group", None) or "").strip(),
            attr_name="group_rowspan",
        )

        # rowspan по виду топлива (fuel_so) — только подряд идущие
        _set_rowspan_for_consecutive_runs(
            station.machines,
            key_fn=lambda m: (getattr(m, "fuel_so", None) or "").strip(),
            attr_name="fuel_rowspan",
        )

    total_stations = len(station_list)
    log_to_db(user, "Найдено станций в БД", f"{total_stations} записей")

    if not station_list:
        log_to_db(user, "Экспорт остановлен", "Нет данных для экспорта.")
        return None

    # Диапазон лет для колонок в выгрузке должен соответствовать фильтрам (зависит от YearService)
    all_years = list(range(int(year_start), int(year_end) + 1))
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

        if station.regional_district:
            regional_system = station.regional_district.regional_energy_system
            regional_system_name = regional_system.name_full if regional_system else "Неизвестно"
        else:
            regional_system_name = "Неизвестно"
        
        if regional_system_name not in regional_systems:
            regional_systems[regional_system_name] = set()
        regional_systems[regional_system_name].add(district_name)

    processed_stations = 0
    
    # Иерархические итоги считаем по периоду СиПР (зависит от YearService)
    aggregated_rows = get_station_hierarchy_aggregates(int(sipr_start), int(sipr_end))
    build_hierarchy_structure(station_list, include_names=False)

    for district_name, stations in regional_districts.items():
        log_to_db(user, f"Выгрузка данных по форме Приложения А к СиПР ЭЭС: {district_name} (Энергосистема: {regional_system_name}) | Найдено станций: {len(stations)}")
        if not stations:
            continue
        try:
            data = []

            # Добавляем строку с названием региональной энергосистемы
            first_station = stations[0]
            if first_station.regional_district and first_station.regional_district.regional_energy_system:
                regional_energy_system = first_station.regional_district.regional_energy_system
                name_full = regional_energy_system.name_full
                
                # Проверяем тип энергосистемы: если ТИТЭС, оставляем "Электроэнергетическая система", иначе заменяем на "Энергосистема"
                is_tites = False
                if regional_energy_system.union_energy_system and regional_energy_system.union_energy_system.energy_system_type:
                    energy_system_type_name = regional_energy_system.union_energy_system.energy_system_type.name
                    if energy_system_type_name and "титэс" in energy_system_type_name.lower():
                        is_tites = True
                
                if is_tites:
                    # Для ТИТЭС оставляем "Электроэнергетическая система"
                    regional_system_name = name_full
                else:
                    # Для остальных заменяем на "Энергосистема"
                    regional_system_name = name_full.replace("Электроэнергетическая система", "Энергосистема")
            else:
                regional_system_name = "Неизвестно"

            if (
                first_station.regional_district
                and first_station.regional_district.regional_energy_system
                and first_station.regional_district.regional_energy_system.regional_district_count > 1
            ):
                # name_dp — наименование субъекта в родительном падеже (нужно для формулировки "территория ...")
                # В данных иногда встречается "Не указано" — считаем это пустым значением и делаем fallback.
                rd = first_station.regional_district
                raw_name_dp = (rd.name_dp or "").strip() if rd else ""
                is_placeholder = raw_name_dp.lower() in {
                    "не указано",
                    "не указана",
                    "не указан",
                    "не указано.",
                    "не указана.",
                    "не указан.",
                }
                territory_name = (
                    (raw_name_dp if raw_name_dp and not is_placeholder else None)
                    or (rd.name_full if rd and rd.name_full else None)
                    or (rd.name if rd and rd.name else None)
                    or "Не указано"
                )
                region_label = f"{regional_system_name}, территория {territory_name}"
            else:
                region_label = regional_system_name

            data.append({
                "Электростанция": region_label,
                "Генерирующая компания": "",
                "Станционный номер": "",
                "Тип генерирующего оборудования": "",
                "Вид топлива": "",
                **{year: None for year in all_years},
                "Примечание": "",
                "_group_rowspan": "",
                "_fuel_rowspan": "",
                "_total_machines": "",
                "Есть группы": "",
            })

            # Определяем наличие групп по агрегатам станции

            def extract_year(date_input):
                """Возвращает год из строки или числа (YYYY-MM-DD / DD.MM.YYYY / YYYY)."""
                if not date_input:
                    return None
                if isinstance(date_input, int):
                    return date_input
                try:
                    return datetime.strptime(date_input, "%Y-%m-%d").year
                except Exception:
                    try:
                        return datetime.strptime(date_input, "%d.%m.%Y").year
                    except Exception:
                        pass
                    try:
                        return int(str(date_input)[:4])
                    except Exception:
                        return None

            # Группируем станции по энергоузлам
            from collections import defaultdict
            stations_by_energy_unit = defaultdict(list)
            for station in stations:
                energy_unit_id = station.id_energy_unit if station.energy_unit else None
                stations_by_energy_unit[energy_unit_id].append(station)

            # Функция для определения порядка типа станции
            def get_station_type_order(station):
                """Возвращает порядковый номер типа станции для сортировки."""
                if not station.station_type or not station.station_type.name:
                    return 99  # Станции без типа в конец
                station_type_name = station.station_type.name.lower()
                if "аэс" in station_type_name:
                    return 0
                elif "гэс" in station_type_name and "гаэс" not in station_type_name:
                    return 1
                elif "гаэс" in station_type_name:
                    return 2
                elif "тэс" in station_type_name:
                    return 3
                elif "вэс" in station_type_name:
                    return 4
                elif "сэс" in station_type_name:
                    return 5
                else:
                    return 99  # Остальные типы в конец

            # Функция для получения суммарной мощности станции на последний год
            def get_station_total_power_last_year(station, last_year, current_version_id):
                """Возвращает суммарную установленную мощность станции на последний год."""
                total_power = 0
                for machine in station.machines:
                    mp_query = (
                        MachinePower.query
                        .filter_by(id_machine=machine.id)
                        .filter(MachinePower.year_number == last_year)
                    )
                    mp_query = filter_by_explicit_db_version(
                        mp_query,
                        MachinePower,
                        current_version_id,
                    )
                    machine_power = mp_query.first()
                    if machine_power and machine_power.p_ust:
                        total_power += machine_power.p_ust
                return total_power

            # Обрабатываем станции, сгруппированные по энергоузлам
            for energy_unit_id, stations_group in stations_by_energy_unit.items():
                # Сортируем станции: сначала по типу, затем по мощности на последний год
                last_year = all_years[-1]  # Последний год периода
                stations_group.sort(key=lambda s: (
                    get_station_type_order(s),
                    -get_station_total_power_last_year(s, last_year, current_version_id)  # Отрицательное значение для сортировки по убыванию
                ))
                # Добавляем строку с названием энергоузла, если он указан
                if energy_unit_id is not None and stations_group and stations_group[0].energy_unit:
                    eu = stations_group[0].energy_unit
                    # Безопасно получаем читаемое имя энергоузла:
                    # сначала пытаемся взять name_full (если есть), затем name.
                    energy_unit_name = getattr(eu, "name_full", None) or getattr(eu, "name", None)

                    # Проверяем, что название энергоузла валидное (не "не указано" и не техническая подпись)
                    if energy_unit_name:
                        energy_unit_name_str = str(energy_unit_name).strip()
                        energy_unit_name_lower = energy_unit_name_str.lower()
                        
                        # Пропускаем, если название содержит "не указано"/"не указан" или является технической подписью
                        if (energy_unit_name_lower and 
                            "не указано" not in energy_unit_name_lower and 
                            "не указан" not in energy_unit_name_lower and
                            not energy_unit_name_str.startswith("id=")):
                            data.append({
                                "Электростанция": energy_unit_name,
                                "Генерирующая компания": "",
                                "Станционный номер": "",
                                "Тип генерирующего оборудования": "",
                                "Вид топлива": "",
                                # Для колонок годов используем None, чтобы они интерпретировались как пустые числовые ячейки
                                **{year: None for year in all_years},
                                "Примечание": "",
                                "_group_rowspan": "",
                                "_fuel_rowspan": "",
                                "_total_machines": "",
                                "Есть группы": "",
                            })

                # Обрабатываем каждую станцию внутри текущего энергоузла
                for station in stations_group:
                    has_groups = any(m.machine_group for m in station.machines)
                    has_groups_text = "Да" if has_groups else "Нет"
                    
                    processed_stations += 1
                    
                    # Мощности станции с учетом активной версии БД
                    power_query = (
                        StationPower.query
                        .filter_by(id_station=station.id)
                        .filter(StationPower.year_number.in_(all_years))
                    )
                    power_query = filter_by_explicit_db_version(
                        power_query,
                        StationPower,
                        current_version_id,
                    )
                    power_data = {
                        sp.year_number: {
                            "p_ust": sp.p_ust,
                            "p_ogr": sp.p_ogr,
                            "p_rasp": sp.p_rasp,
                        }
                        for sp in power_query.all()
                    }

                    # Предварительно проверяем, есть ли у станции агрегаты с ненулевой мощностью
                    # Собираем мощности всех агрегатов для предварительной проверки
                    preliminary_station_total = {year: 0 for year in all_years}
                    for machine in station.machines:
                        mp_query = (
                            MachinePower.query
                            .filter_by(id_machine=machine.id)
                            .filter(MachinePower.year_number.in_(all_years))
                        )
                        mp_query = filter_by_explicit_db_version(
                            mp_query,
                            MachinePower,
                            current_version_id,
                        )
                        machine_power_data = {
                            mp.year_number: mp.p_ust
                            for mp in mp_query.all()
                            if mp.p_ust is not None
                        }
                        for year in all_years:
                            preliminary_station_total[year] += (machine_power_data.get(year) or 0)

                    # Если суммарная установленная мощность станции по всем годам равна нулю
                    # (рассчитанная из агрегатов), станцию полностью не отображаем в Приложении А.
                    has_nonzero_power = any(
                        (preliminary_station_total.get(year) or 0) != 0
                        for year in all_years
                    )
                    if not has_nonzero_power:
                        continue

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

                    # Добавляем строки с установленной мощностью по машинам электростанции
                    # Собираем мощности всех агрегатов для расчета итоговой суммы
                    station_total_p_ust_from_machines = {year: 0 for year in all_years}
                    
                    for machine in station.machines:
                        # Мощности агрегатов с учетом активной версии БД
                        mp_query = (
                            MachinePower.query
                            .filter_by(id_machine=machine.id)
                            .filter(MachinePower.year_number.in_(all_years))
                        )
                        mp_query = filter_by_explicit_db_version(
                            mp_query,
                            MachinePower,
                            current_version_id,
                        )
                        machine_power_data = {
                            mp.year_number: mp.p_ust
                            for mp in mp_query.all()
                            if mp.p_ust is not None
                        }

                        # Проверяем, есть ли у агрегата ненулевая мощность хотя бы в одном году
                        machine_total_power = sum(
                            (machine_power_data.get(year) or 0) for year in all_years
                        )
                        
                        # Если у агрегата мощность = 0 во всех годах, пропускаем его
                        if machine_total_power == 0:
                            continue

                        # Накапливаем мощность станции из агрегатов
                        for year in all_years:
                            station_total_p_ust_from_machines[year] += (machine_power_data.get(year) or 0)

                        note_parts = []

                        # Ввод в эксплуатацию: сначала берём фактическую дату ввода, если есть,
                        # иначе плановый год ввода (date_exploitation).
                        # Показываем только если год попадает в диапазон отображаемых данных.
                        if getattr(machine, "date_commission_fact", None):
                            year = extract_year(machine.date_commission_fact)
                            if year and year in all_years:
                                note_parts.append(f"Ввод в эксплуатацию в {year} г.")
                        elif getattr(machine, "date_exploitation", None):
                            year = extract_year(machine.date_exploitation)
                            if year and year in all_years:
                                note_parts.append(f"Ввод в эксплуатацию в {year} г.")

                        # Вывод из эксплуатации: приоритет фактической дате, затем плановой.
                        # Показываем только если год попадает в диапазон отображаемых данных.
                        if getattr(machine, "date_decompressing_fact", None):
                            year = extract_year(machine.date_decompressing_fact)
                            if year and year in all_years:
                                note_parts.append(f"Вывод из эксплуатации в {year} г.")
                        elif getattr(machine, "date_decompressing_expected", None):
                            year = extract_year(machine.date_decompressing_expected)
                            if year and year in all_years:
                                note_parts.append(f"Вывод из эксплуатации в {year} г.")

                        # Модернизация (плановая)
                        # Показываем только если год попадает в диапазон отображаемых данных.
                        if getattr(machine, "date_modernization_expected", None):
                            year = extract_year(machine.date_modernization_expected)
                            if year and year in all_years:
                                note_parts.append(f"Модернизация в {year} г.")

                        full_note = ". ".join(note_parts)

                        row = {
                            "Электростанция": machine.machine_group,
                            "Генерирующая компания": "",
                            "Станционный номер": machine.machine_number,
                            "Тип генерирующего оборудования": machine.machine_name,
                            "Вид топлива": machine.fuel_so if getattr(machine, 'fuel_so', 0) else "–",
                            **{
                                year: round(machine_power_data.get(year), 1)
                                if machine_power_data.get(year) is not None and machine_power_data.get(year) != 0
                                else None
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

                    # Добавляем строку "Установленная мощность, всего" по станции.
                    # Сумма считается из агрегатов, которые реально попали в таблицу.
                    # Если в каком-то году суммарная мощность равна нулю или отсутствует,
                    # ячейка должна быть пустой.
                    total_year_values = {}
                    for year in all_years:
                        p_ust = station_total_p_ust_from_machines.get(year, 0)
                        if p_ust is None or p_ust == 0:
                            total_year_values[year] = None
                        else:
                            total_year_values[year] = round(p_ust, 1)

                    total_row = {
                        "Электростанция": "Установленная мощность, всего",
                        "Генерирующая компания": "",
                        "Станционный номер": "–",
                        "Тип генерирующего оборудования": "–",
                        "Вид топлива": "–",
                        **total_year_values,
                        "Примечание": "",
                        "_group_rowspan": "",
                        "_fuel_rowspan": "",
                        "_total_machines": "",
                        "Есть группы": "",
                    }
                    data.append(total_row)
            
            # Проверяем, есть ли СЭС в станциях субъекта
            has_ses = False
            for station in stations:
                if station.station_type and station.station_type.name:
                    station_type_name_lower = station.station_type.name.lower()
                    if "сэс" in station_type_name_lower or "солнечная" in station_type_name_lower:
                        has_ses = True
                        break
            
            # Если есть СЭС, добавляем строку с примечанием
            if has_ses:
                note_text = "          Примечание – 1) В соответствии с Правилами оптового рынка электрической энергии и мощности, утвержденными постановлением Правительства Российской Федерации от 27.12.2010 № 1172, поставщики мощности по договорам о предоставлении мощности квалифицированных генерирующих объектов, функционирующих на основе использования возобновляемых источников энергии, заключенным по результатам отбора проектов, вправе изменить планируемое местонахождение генерирующего объекта. В соответствии с постановлением Правительства Российской Федерации от 20.05.2022 № 912 поставщик мощности по указанным договорам вправе до наступления даты начала поставки мощности осуществить отсрочку начала периода поставки мощности."
                data.append({
                    "Электростанция": note_text,
                    "Генерирующая компания": "",
                    "Станционный номер": "",
                    "Тип генерирующего оборудования": "",
                    "Вид топлива": "",
                    **{year: None for year in all_years},
                    "Примечание": "",
                    "_group_rowspan": "",
                    "_fuel_rowspan": "",
                    "_total_machines": "",
                    "Есть группы": "",
                })
            
            df = pd.DataFrame(data)
            # Заполняем пустые значения только для текстовых колонок.
            # Для числовых колонок (годы) оставляем None/NaN, чтобы они оставались числовыми в Excel.
            text_columns = [
                "Электростанция",
                "Генерирующая компания",
                "Станционный номер",
                "Тип генерирующего оборудования",
                "Вид топлива",
                "Примечание",
                "_group_rowspan",
                "_fuel_rowspan",
                "_total_machines",
                "Есть группы",
            ]
            for col in text_columns:
                if col in df.columns:
                    df[col] = df[col].fillna("")

            # Явно приводим колонки годов к числовому типу, чтобы Excel видел их как числа.
            for year in all_years:
                if year in df.columns:
                    df[year] = pd.to_numeric(df[year], errors="coerce")

            # Находим и сохраняем строку с примечанием, если она есть
            note_row_data = None
            note_text = None
            note_row_df_index = None
            for idx, row in df.iterrows():
                station_name_raw = str(row.get("Электростанция", "") or "")
                station_name = station_name_raw.strip()

                # ✅ ловим любые варианты пробелов/тире
                if "Примечание" in station_name and "1)" in station_name:
                    note_row_data = row.to_dict()
                    note_text = station_name_raw  # сохраняем как есть (с отступами)
                    note_row_df_index = idx
                    break
            
            # Удаляем строку с примечанием из DataFrame, если она есть
            if note_row_df_index is not None:
                df = df.drop(index=note_row_df_index)
                df = df.reset_index(drop=True)  # Сбрасываем индексы для правильной последовательности

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

                # Формат для числовых ячеек мощностей: 1 знак после запятой
                power_number_format = workbook.add_format({
                    'font_name': 'Times New Roman',
                    'font_size': 10,
                    'align': 'center',
                    'valign': 'vcenter',
                    'text_wrap': True,
                    'border': 1,
                    'num_format': '0.0',  # один знак после запятой
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
                    f"Таблица А.1 – Перечень действующих электростанций, с указанием состава генерирующего оборудования и планов по выводу из эксплуатации, реконструкции (модернизации или перемаркировке), вводу в эксплуатацию генерирующего оборудования в период до {int(sipr_end)} года",
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
                    col_name = col_names[col_num]
                    # Для "Тип генерирующего оборудования" добавляем верхний индекс "1)"
                    if col_name == "Тип генерирующего оборудования":
                        # Создаем форматы для rich_string
                        superscript_format = workbook.add_format({
                            'font_name': 'Times New Roman',
                            'font_size': 10,
                            'font_script': 1,  # 1 = superscript
                        })
                        header_format = workbook.add_format({
                            'font_name': 'Times New Roman',
                            'font_size': 10,
                            'align': 'center',
                            'valign': 'vcenter',
                            'text_wrap': True,
                            'border': 1
                        })
                        # Объединяем ячейки
                        worksheet.merge_range(4, col_num, 5, col_num, "", header_format)
                        # Записываем текст с верхним индексом в объединенную ячейку
                        worksheet.write_rich_string(4, col_num, 
                            header_format, "Тип генерирующего оборудования",
                            superscript_format, "1)")
                    else:
                        worksheet.merge_range(4, col_num, 5, col_num, col_name, text_center_format)

                # Первая строка над мощностями
                worksheet.merge_range(4, num_cols, 4, num_cols + len(all_years) - 1, "Установленная мощность (МВт)", text_center_format)

                # Заменяем первый год на "По состоянию на 01.01.<год>"
                first_year = all_years[0] + 1  # Берем первый год из списка
                year_headers = ["По состоянию на 01.01.{}".format(first_year)] + [f"{year} г." for year in all_years[1:]]

                # Вторая строка - годы
                for idx, year in enumerate(year_headers):
                    col_num = num_cols + idx
                    worksheet.write(5, col_num, year, text_center_format)

                # Устанавливаем особую ширину для первого года
                first_year_col_idx = num_cols  # Столбец первого года
                worksheet.set_column(first_year_col_idx, first_year_col_idx, 12.86, power_number_format)

                # Устанавливаем стандартную ширину для остальных годов
                for idx in range(1, len(all_years)):  # Пропускаем первый год
                    col_num = num_cols + idx
                    worksheet.set_column(col_num, col_num, 8, power_number_format)

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
                    text_format
                )

                # Определяем последнюю заполненную строку
                last_row = len(df) + 6  # +5 из-за заголовков

                # Определяем последний используемый столбец
                last_col = len(df.columns)

                start_excel_row = 6  # Потому что DataFrame начинается с строки 6 в Excel
                
                # Используем enumerate для последовательного индекса, так как DataFrame может иметь не последовательные индексы
                for row_idx, (i, row) in enumerate(df.iterrows()):
                    excel_row = row_idx + start_excel_row  # Используем row_idx (последовательный), а не i (индекс DataFrame)
                    
                    group_rowspan = int(row["_group_rowspan"] or 0)
                    total_machines = int(row["_total_machines"] or 0)
                    has_groups = row.get("Есть группы", "") == "Да"

                    # Отображаем название группы агрегатов с отступом:
                    # - если в группе несколько агрегатов, объединяем ячейки по вертикали;
                    # - если агрегат в группе один, просто применяем формат с отступом.
                    if has_groups:
                        if 1 <= group_rowspan <= total_machines:
                            # Группа из нескольких агрегатов
                            worksheet.merge_range(
                                excel_row,
                                station_col_idx,
                                excel_row + group_rowspan - 1,
                                station_col_idx,
                                row["Электростанция"],
                                text_format_group
                            )
                        elif group_rowspan == 0 and row["Электростанция"]:
                            # Одиночный агрегат с указанной группой
                            worksheet.write(
                                excel_row,
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
                
                # Добавляем строку с примечанием в самый конец, после всех данных
                note_row_index = None

                if note_text is not None:
                    # ✅ ВАЖНО: df_export уже записан на лист с startrow=6,
                    # поэтому строка примечания должна идти СРАЗУ ПОСЛЕ него
                    note_row_index = start_excel_row + len(df_export)  # <-- вместо len(df)

                    # Последний столбец таблицы (колонка "Примечание")
                    end_col_idx = num_cols + len(all_years)  # это ровно столбец "Примечание"

                    note_format = workbook.add_format({
                        'font_name': 'Times New Roman',
                        'font_size': 13,
                        'align': 'justify',
                        'valign': 'vcenter',
                        'text_wrap': True,
                        'border': 1,
                    })

                    worksheet.merge_range(
                        note_row_index, 0,
                        note_row_index, end_col_idx,
                        note_text.replace("1)", "¹)", 1),
                        note_format
                    )
                    
                    worksheet.set_row(note_row_index, 85.5)

                # Создаем пустой стиль (без границ, выравнивания и других атрибутов)
                empty_format = workbook.add_format()

                # НЕ затираем строку примечания
                clear_from_row = (note_row_index + 1) if note_row_index is not None else (len(df) + start_excel_row)

                # Снимаем форматирование с пустых строк после таблицы
                for row_num in range(clear_from_row, 1000):
                    worksheet.set_row(row_num, None, empty_format)

                # Снимаем форматирование с пустых столбцов после таблицы
                for col_num in range(last_col + 1, 50):
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



