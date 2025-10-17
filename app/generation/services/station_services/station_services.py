"""Сервисный модуль: Список электростанций Российской Федерации."""

from app.extensions import db
from app.logs.services.logging_service import log_to_db
from sqlalchemy import text
from config import SCHEMA_GENERATION
from sqlalchemy import and_
from sqlalchemy.orm import selectinload, joinedload
from decimal import Decimal
from collections import defaultdict

# Модели
from app.generation.models.station.station_model import Station
from app.generation.models.station.station_power_model import StationPower

from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.station.station_group_model import StationGroup
from app.generation.models.pgu_machine.pgu_machine_model import PGUMachine

from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType

from app.refdata.models.fuels.fuel_model import Fuel

from app.refdata.models.gen_companies.gen_company_model import GenCompany

from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType
# Сервисы
from app.common.services.get_services.years.years_get_services import (
    get_current_year,
    get_year_feature_dict,
)
from app.common.services.get_services.fuels.fuel_type_get_services import (
    get_fuel_type_list_full,
)
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
    get_energy_system_type_map,
)
from app.common.services.get_services.energy_systems.energy_unit_get_services import (
    get_energy_unit_list_full,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
    get_union_energy_systems_map,
    get_ues_to_res_ids_map,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_systems_dto_list,
    get_regional_energy_systems_map,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_districts_dto_list,
    get_regional_districts_map,
)
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_districts_dto_list,
    get_federal_districts_map,
    get_fd_to_rd_ids_map,
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

from app.common.services.get_services.stations.station_get_services import (
    get_station_by_id,
)
from app.common.services.get_services.stations.machine_get_services import (
    get_machine_by_id,
)
from app.generation.services.station_services.groupped_services import (
    get_station_hierarchy_aggregates,
    build_hierarchy_structure,
    fetch_machines_with_rowspans,
    )
from app.generation.services.station_services.aggregation_station_services.aggregation_rows import (
    get_full_aggregation_rows
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
    aggregate_regional_districts_by_station_types_with_fuel,
    aggregate_regional_districts_by_tes_types,
    aggregate_regional_districts_by_tes_types_with_fuel,
    aggregate_regional_districts_by_tes_machine_types,
    aggregate_regional_districts_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_services.aggregation_station_services.aggregation_services_regional_energy_systems import (
    aggregate_power_by_regional_energy_systems,
    aggregate_regional_energy_systems_by_station_types,
    aggregate_regional_energy_systems_by_station_types_with_fuel,
    aggregate_regional_energy_systems_by_tes_types,
    aggregate_regional_energy_systems_by_tes_types_with_fuel,
    aggregate_regional_energy_systems_by_tes_machine_types,
    aggregate_regional_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_services.aggregation_station_services.aggregation_services_union_energy_systems import (
    aggregate_power_by_union_energy_systems,
    aggregate_union_energy_systems_by_station_types,
    aggregate_union_energy_systems_by_station_types_with_fuel,
    aggregate_union_energy_systems_by_tes_types,
    aggregate_union_energy_systems_by_tes_types_with_fuel,
    aggregate_union_energy_systems_by_tes_machine_types,
    aggregate_union_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_services.aggregation_station_services.aggregation_services_energy_system_types import (
    aggregate_power_by_energy_system_types,
    aggregate_energy_system_types_by_station_types,
    aggregate_energy_system_types_by_station_types_with_fuel,
    aggregate_energy_system_types_by_tes_types,
    aggregate_energy_system_types_by_tes_types_with_fuel,
    aggregate_energy_system_types_by_tes_machine_types,
    aggregate_energy_system_types_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_services.aggregation_station_services.aggregation_services_total_energy_system_types import (
    aggregate_power_by_total_energy_system_types,
    aggregate_total_energy_system_types_by_station_types,
    aggregate_total_energy_system_types_by_station_types_with_fuel,
    aggregate_total_energy_system_types_by_tes_types,
    aggregate_total_energy_system_types_by_tes_types_with_fuel,
    aggregate_total_energy_system_types_by_tes_machine_types,
    aggregate_total_energy_system_types_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_services.aggregation_station_services.optimized_aggregation import (
    aggregate_all_at_once,
    )
from app.generation.services.station_services.aggregation_cache import (
    cache_aggregation,
    clear_aggregation_cache,
    )
from app.common.services.tranzaction_services import (
    _commit_with_retry,
    _locked_get,
    no_autoflush,
)


def get_stations_list(
    page=1,
    per_page=None,
    rounding_digits=None,
    **filters,
):
    current_year = get_current_year()

    # 1. Фильтрация агрегатов
    machine_query = db.session.query(Machine.id, Machine.id_station)

    if filters.get("tes_type_filter"):
        machine_query = machine_query.filter(
            Machine.machine_tes_types.any(
                and_(
                    MachineTesType.year_number == current_year,
                    MachineTesType.id_tes_type.in_(filters["tes_type_filter"])
                )
            )
        )

    if filters.get("tes_machine_type_filter"):
        machine_query = machine_query.filter(
            Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"])
        )

    if filters.get("fuel_type_filter"):
        machine_query = machine_query.join(Machine.machine_fuels).join(MachineFuel.fuel).filter(
            Fuel.id_fuel_type.in_(filters["fuel_type_filter"])
        )

    if filters.get("date_exploitation_filter"):
        machine_query = machine_query.filter(
            Machine.date_exploitation.in_(filters["date_exploitation_filter"])
        )

    if filters.get("date_decompressing_expected_filter"):
        machine_query = machine_query.filter(
            Machine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"])
        )

    if filters.get("date_modernization_expected_filter"):
        machine_query = machine_query.filter(
            Machine.date_modernization_expected.in_(filters["date_modernization_expected_filter"])
        )

    # 2. Subquery с подходящими агрегатами
    machine_subquery = machine_query.subquery()
    station_ids_query = db.session.query(machine_subquery.c.id_station).distinct()
    station_ids_query = station_ids_query.join(Station, Station.id == machine_subquery.c.id_station)

    # 3. Фильтры по станции

    if filters.get("station_type_filter"):
        station_ids_query = station_ids_query.filter(
            Station.id_station_type.in_(filters["station_type_filter"])
        )

    if filters.get("station_name_filter"):
        station_ids_query = station_ids_query.filter(
            Station.name.ilike(f"%{filters['station_name_filter']}%")
        )

    if filters.get("gen_company_filter"):
        gen_company_ids = db.session.query(GenCompany.id).filter(
            GenCompany.name.ilike(f"%{filters['gen_company_filter']}%")
        ).all()
        ids = [g[0] for g in gen_company_ids]
        station_ids_query = station_ids_query.filter(
            Station.machines.any(Machine.id_gen_company.in_(ids))
        )

    if filters.get("condition_type_filter"):
        station_ids_query = station_ids_query.filter(
            Station.machines.any(Machine.id_condition_type == filters["condition_type_filter"])
        )

    if filters.get("regional_district_filter"):
        station_ids_query = station_ids_query.filter(
            Station.id_regional_district.in_(filters["regional_district_filter"])
        )

    if filters.get("federal_district_filter"):
        station_ids_query = station_ids_query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(
                    FederalDistrict.id.in_(filters["federal_district_filter"])
                )
            )
        )

    if filters.get("regional_energy_system_filter"):
        station_ids_query = station_ids_query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id.in_(filters["regional_energy_system_filter"])
                )
            )
        )

    if filters.get("union_energy_system_filter"):
        station_ids_query = station_ids_query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id_union_energy_system.in_(
                        filters["union_energy_system_filter"]
                    )
                )
            )
        )

    if filters.get("energy_system_type_filter"):
        station_ids_query = station_ids_query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.union_energy_system.has(
                        UnionEnergySystem.energy_system_type.has(
                            EnergySystemType.id.in_(filters["energy_system_type_filter"])
                        )
                    )
                )
            )
        )

    # 4. Подсчет и пагинация (сортировка не нужна, т.к. будет в Python)
    # Получаем уникальные ID станций (важно для случаев с multiple regional_energy_systems)
    raw_station_ids = [row[0] for row in station_ids_query.all()]
    all_station_ids = list(set(raw_station_ids))
    
    # Проверка на дубликаты в SQL запросе
    if len(raw_station_ids) != len(all_station_ids):
        duplicates_count = len(raw_station_ids) - len(all_station_ids)
        print(f"[SQL DUPLICATES] Обнаружено {duplicates_count} дубликатов в SQL запросе station_ids")
        print(f"   До уникализации: {len(raw_station_ids)} станций, после: {len(all_station_ids)} станций")
    
    total_count = len(all_station_ids)
    
    if total_count == 0:
        return {"stations": [], "total_count": 0}

    per_page_int = None if isinstance(per_page, str) and per_page.lower() == "all" else int(per_page or 10)
    
    # Пытаемся получить отсортированный список из кэша
    from app.generation.services.station_services.aggregation_cache import (
        get_cached_sorted_stations, cache_sorted_stations,
        get_cached_page_position, cache_page_position
    )
    
    cached_sorted_ids = get_cached_sorted_stations(filters)
    
    # Получаем кэшированную позицию и информацию о предыдущей странице
    if page > 1:
        cached_start_position, prev_page_last_station_info = get_cached_page_position(filters, page)
        print(f"[CACHE CHECK] Page {page}: cached_start_position={cached_start_position}, prev_info={prev_page_last_station_info}")
    else:
        cached_start_position, prev_page_last_station_info = None, None
    
    if cached_sorted_ids is not None:
        # Используем кэшированный отсортированный список
        # Применяем пагинацию с учетом границ субъектов
        if per_page_int is not None:
            # Используем реальную позицию из кэша (если есть) или стандартный offset
            if cached_start_position is not None:
                # Используем сохраненную позицию (где закончилась предыдущая страница)
                offset_in_sorted_list = cached_start_position
                print(f"[PAGE POSITION CACHE] Используется закэшированная позиция: {offset_in_sorted_list}")
            else:
                # Первая страница или кэш позиции не найден
                offset_in_sorted_list = (page - 1) * per_page_int
            # Берем страницу с запасом для корректировки границ субъектов
            station_ids_for_page = cached_sorted_ids[offset_in_sorted_list:offset_in_sorted_list + per_page_int + 100]
        else:
            offset_in_sorted_list = 0
            station_ids_for_page = cached_sorted_ids
        
        # Загружаем только станции для этой страницы
        stations = Station.query.options(
            selectinload(Station.regional_district).selectinload(RegionalDistrict.regional_energy_systems).joinedload(RegionalEnergySystem.union_energy_system).joinedload(UnionEnergySystem.energy_system_type),
            selectinload(Station.regional_district).joinedload(RegionalDistrict.federal_district),
            joinedload(Station.energy_unit),
            selectinload(Station.machines)
                .selectinload(Machine.machine_powers),
            selectinload(Station.machines)
                .selectinload(Machine.machine_fuels),
            selectinload(Station.machines)
                .selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type)
        ).filter(Station.id.in_(station_ids_for_page)).all()
        
        # Сортируем этот небольшой набор
        # (порядок в SQL может отличаться от кэшированного)
        def get_sorting_key_from_cache(station):
            # Находим позицию станции в кэшированном списке
            try:
                return cached_sorted_ids.index(station.id)
            except ValueError:
                return float('inf')
        
        stations = sorted(stations, key=get_sorting_key_from_cache)
        use_cached_sort = True
    else:
        # Кэша нет - загружаем все станции
        station_ids = all_station_ids
        
        if not station_ids:
            return {"stations": [], "total_count": 0}
        
        # Загрузка станций с предзагрузкой (без SQL сортировки)
        # Используем selectinload для regional_district, чтобы избежать дублирования станций
        # из-за множественных regional_energy_systems
        stations = Station.query.options(
            selectinload(Station.regional_district).selectinload(RegionalDistrict.regional_energy_systems).joinedload(RegionalEnergySystem.union_energy_system).joinedload(UnionEnergySystem.energy_system_type),
            selectinload(Station.regional_district).joinedload(RegionalDistrict.federal_district),
            joinedload(Station.energy_unit),
            selectinload(Station.machines)
                .selectinload(Machine.machine_powers),
            selectinload(Station.machines)
                .selectinload(Machine.machine_fuels),
            selectinload(Station.machines)
                .selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type)
        ).filter(Station.id.in_(station_ids)).all()
        
        use_cached_sort = False
    
    # Сортировка в Python по полной территориальной иерархии
    def get_sorting_key(station):
        """
        Возвращает кортеж для сортировки по полной территориальной иерархии:
        (energy_system_type_id, union_energy_system_id, regional_energy_system_id, 
         regional_district_id, energy_unit_id, min_station_type_id, station_id)
        Это гарантирует, что все станции одного субъекта будут отображаться вместе.
        """
        # Определяем минимальный тип станции по агрегатам
        if station.machines:
            station_types = [m.id_station_type for m in station.machines if m.id_station_type is not None]
            min_type = min(station_types) if station_types else float('inf')
        else:
            min_type = float('inf')
        
        # Получаем иерархию через связи
        energy_system_type_id = 0
        # Для корректной сортировки по ОЭС используем display_order; None уходит в конец
        union_energy_system_order = float('inf')
        regional_energy_system_id = 0
        regional_district_name = ""
        energy_unit_id = station.id_energy_unit or 0
        
        if station.regional_district:
            # Субъекты сортируются ПО АЛФАВИТУ (по name)
            regional_district_name = (station.regional_district.name or "").lower()
            
            if station.regional_district.regional_energy_systems:
                res = station.regional_district.regional_energy_systems[0]
                if res:
                    regional_energy_system_id = res.id
                    if res.union_energy_system:
                        # display_order: чем меньше, тем раньше
                        union_energy_system_order = (
                            res.union_energy_system.display_order
                            if res.union_energy_system.display_order is not None else float('inf')
                        )
                        if res.union_energy_system.energy_system_type:
                            energy_system_type_id = res.union_energy_system.energy_system_type.id
        
        return (
            energy_system_type_id,
            union_energy_system_order,
            regional_energy_system_id,
            regional_district_name,  # ← Сортировка по алфавиту!
            energy_unit_id,
            min_type,
            station.id
        )
    
    if not use_cached_sort:
        # Уникализация станций ПЕРЕД сортировкой (на случай дубликатов из-за JOIN)
        seen_ids = set()
        unique_stations_list = []
        for station in stations:
            if station.id not in seen_ids:
                seen_ids.add(station.id)
                unique_stations_list.append(station)
            else:
                print(f"[WARNING] Дубликат станции обнаружен при загрузке: ID={station.id}, name={station.name}")
        
        stations = unique_stations_list
        
        # Сортировка после уникализации
        stations = sorted(stations, key=get_sorting_key)
        
        # Сохраняем отсортированный список ID в кэш
        sorted_station_ids = [s.id for s in stations]
        cache_sorted_stations(filters, sorted_station_ids)
    else:
        # Кэш уже использован, stations уже отсортированы по кэшированному порядку
        pass
    
    # Сохраняем информацию о следующей станции ДО применения пагинации
    next_station_info = None
    
    # Применяем пагинацию с учетом границ субъектов РФ
    if per_page_int is not None and not use_cached_sort:
        # Для НЕ кэшированного списка (все станции загружены)
        # Используем реальную позицию из кэша (если есть) или стандартный offset
        if cached_start_position is not None:
            start_idx = cached_start_position
            print(f"[PAGE POSITION CACHE] Используется закэшированная позиция: {start_idx}")
        else:
            start_idx = (page - 1) * per_page_int
        
        end_idx = min(start_idx + per_page_int, len(stations))
        
        # НЕ корректируем начало! Это создает перекрытия страниц
        # Только корректируем конец: двигаемся вперед до конца субъекта
        if end_idx < len(stations):
            current_rd_name = (stations[end_idx - 1].regional_district.name or "").lower() if stations[end_idx - 1].regional_district else ""
            while end_idx < len(stations):
                next_rd_name = (stations[end_idx].regional_district.name or "").lower() if stations[end_idx].regional_district else ""
                if next_rd_name == current_rd_name:
                    end_idx += 1
                else:
                    break
        
        # Получаем информацию о следующей станции (если она есть)
        if end_idx < len(stations):
            next_station = stations[end_idx]
            next_station_info = {
                'energy_unit_id': next_station.id_energy_unit,
                'regional_district_id': next_station.id_regional_district,
                'regional_energy_system_id': None,
                'union_energy_system_id': None,
                'energy_system_type_id': None
            }
            if next_station.regional_district and next_station.regional_district.regional_energy_systems:
                res = next_station.regional_district.regional_energy_systems[0]
                if res:
                    next_station_info['regional_energy_system_id'] = res.id
                    if res.union_energy_system:
                        next_station_info['union_energy_system_id'] = res.union_energy_system.id
                        if res.union_energy_system.energy_system_type:
                            next_station_info['energy_system_type_id'] = res.union_energy_system.energy_system_type.id
        
        stations = stations[start_idx:end_idx]
        
        # Отладка: показываем уникальные субъекты на странице
        unique_rd_names = set()
        for st in stations:
            if st.regional_district:
                unique_rd_names.add(st.regional_district.name)
        print(f"[DEBUG SUBJECTS] Page {page}: Субъекты на странице: {sorted(unique_rd_names)}")
        
        # Получаем информацию о последней станции страницы для кэша
        if stations:
            last_station = stations[-1]
            last_station_info_for_cache = {
                'energy_unit_id': last_station.id_energy_unit,
                'regional_district_id': last_station.id_regional_district,
                'regional_energy_system_id': None,
                'union_energy_system_id': None,
                'energy_system_type_id': None
            }
            if last_station.regional_district and last_station.regional_district.regional_energy_systems:
                res = last_station.regional_district.regional_energy_systems[0]
                if res:
                    last_station_info_for_cache['regional_energy_system_id'] = res.id
                    if res.union_energy_system:
                        last_station_info_for_cache['union_energy_system_id'] = res.union_energy_system.id
                        if res.union_energy_system.energy_system_type:
                            last_station_info_for_cache['energy_system_type_id'] = res.union_energy_system.energy_system_type.id
        else:
            last_station_info_for_cache = None
        
        # Сохраняем реальную конечную позицию этой страницы в кэш
        cache_page_position(filters, page, end_idx, last_station_info_for_cache)
        
        print(f"[PAGINATION] Page {page}: start={start_idx}, per_page={per_page_int}, range [{start_idx}:{end_idx}], showing {len(stations)} stations, next_station: {next_station_info}")
    elif per_page_int is not None and use_cached_sort:
        # Для кэшированного списка (загружены только станции страницы)
        # Берем с начала буфера
        start_idx = 0  
        # Определяем, сколько станций уже было показано (из кэша позиций)
        end_idx = min(per_page_int, len(stations))
        
        # Корректируем конец: двигаемся вперед до конца субъекта
        if end_idx < len(stations):
            current_rd_name = (stations[end_idx - 1].regional_district.name or "").lower() if stations[end_idx - 1].regional_district else ""
            while end_idx < len(stations):
                next_rd_name = (stations[end_idx].regional_district.name or "").lower() if stations[end_idx].regional_district else ""
                if next_rd_name == current_rd_name:
                    end_idx += 1
                else:
                    break
        
        # Получаем информацию о следующей станции (если она есть)
        if end_idx < len(stations):
            next_station = stations[end_idx]
            next_station_info = {
                'energy_unit_id': next_station.id_energy_unit,
                'regional_district_id': next_station.id_regional_district,
                'regional_energy_system_id': None,
                'union_energy_system_id': None,
                'energy_system_type_id': None
            }
            if next_station.regional_district and next_station.regional_district.regional_energy_systems:
                res = next_station.regional_district.regional_energy_systems[0]
                if res:
                    next_station_info['regional_energy_system_id'] = res.id
                    if res.union_energy_system:
                        next_station_info['union_energy_system_id'] = res.union_energy_system.id
                        if res.union_energy_system.energy_system_type:
                            next_station_info['energy_system_type_id'] = res.union_energy_system.energy_system_type.id
        
        stations = stations[start_idx:end_idx]
        
        # Отладка: показываем уникальные субъекты на странице
        unique_rd_names = set()
        for st in stations:
            if st.regional_district:
                unique_rd_names.add(st.regional_district.name)
        print(f"[DEBUG SUBJECTS CACHED] Page {page}: Субъекты на странице: {sorted(unique_rd_names)}")
        
        # Получаем информацию о последней станции страницы для кэша
        if stations:
            last_station = stations[-1]
            last_station_info_for_cache = {
                'energy_unit_id': last_station.id_energy_unit,
                'regional_district_id': last_station.id_regional_district,
                'regional_energy_system_id': None,
                'union_energy_system_id': None,
                'energy_system_type_id': None
            }
            if last_station.regional_district and last_station.regional_district.regional_energy_systems:
                res = last_station.regional_district.regional_energy_systems[0]
                if res:
                    last_station_info_for_cache['regional_energy_system_id'] = res.id
                    if res.union_energy_system:
                        last_station_info_for_cache['union_energy_system_id'] = res.union_energy_system.id
                        if res.union_energy_system.energy_system_type:
                            last_station_info_for_cache['energy_system_type_id'] = res.union_energy_system.energy_system_type.id
        else:
            last_station_info_for_cache = None
        
        # Сохраняем реальную конечную позицию этой страницы в кэш
        # Это позиция в кэшированном sorted list, откуда начнется следующая страница
        real_end_position = offset_in_sorted_list + end_idx
        cache_page_position(filters, page, real_end_position, last_station_info_for_cache)
        
        print(f"[PAGINATION CACHED] Page {page}: offset_in_sorted_list={offset_in_sorted_list}, per_page={per_page_int}, range [{start_idx}:{end_idx}], showing {len(stations)} stations, next_station: {next_station_info}, real_end_pos: {real_end_position}")

    # 7. Загрузка отфильтрованных агрегатов (только для финального списка станций)
    final_station_ids = [s.id for s in stations]
    filtered_machines = Machine.query.options(
        selectinload(Machine.machine_fuels),
        selectinload(Machine.machine_powers),
        selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
    ).filter(
        Machine.id.in_(
            db.session.query(machine_subquery.c.id).filter(machine_subquery.c.id_station.in_(final_station_ids))
        )
    ).all()

    # 8. Привязка агрегатов к станциям
    from collections import defaultdict
    station_machines_map = defaultdict(list)
    for m in filtered_machines:
        station_machines_map[m.id_station].append(m)

    for station in stations:
        station.machines = station_machines_map.get(station.id, [])

    return {
        "stations": stations,
        "total_count": total_count,
        "next_station_info": next_station_info,
    }


def get_stations_list_with_pgu_machines(
    page=1,
    per_page=None,
    rounding_digits=None,
    **filters,
):
    current_year = get_current_year()

    # 1. Фильтрация агрегатов (машины)
    machine_query = db.session.query(Machine.id, Machine.id_station)

    if filters.get("tes_type_filter"):
        machine_query = machine_query.filter(
            Machine.machine_tes_types.any(
                and_(
                    MachineTesType.year_number == current_year,
                    MachineTesType.id_tes_type.in_(filters["tes_type_filter"])
                )
            )
        )

    if filters.get("tes_machine_type_filter"):
        machine_query = machine_query.filter(
            Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"])
        )

    if filters.get("fuel_type_filter"):
        machine_query = machine_query.join(Machine.machine_fuels).join(MachineFuel.fuel).filter(
            Fuel.id_fuel_type.in_(filters["fuel_type_filter"])
        )

    if filters.get("date_exploitation_filter"):
        machine_query = machine_query.filter(
            Machine.date_exploitation.in_(filters["date_exploitation_filter"])
        )

    if filters.get("date_decompressing_expected_filter"):
        machine_query = machine_query.filter(
            Machine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"])
        )

    if filters.get("date_modernization_expected_filter"):
        machine_query = machine_query.filter(
            Machine.date_modernization_expected.in_(filters["date_modernization_expected_filter"])
        )

    machine_station_rows = machine_query.all()
    machine_station_ids = [row[1] for row in machine_station_rows if row[1] is not None]

    # 2. Фильтрация ПГУ агрегатов
    pgu_station_ids = []
    if filters.get("pgu_tes_machine_type_filter"):
        pgu_station_ids = [
            pgu.parent_machine.id_station
            for pgu in PGUMachine.query.join(PGUMachine.parent_machine)
            .filter(PGUMachine.id_pgu_tes_machine_type.in_(filters["pgu_tes_machine_type_filter"]))
            .all()
            if pgu.parent_machine and pgu.parent_machine.id_station
        ]

    print("Все станции с ПГУ:", sorted(set(pgu_station_ids)))

    # 3. Объединяем station_ids
    if filters.get("pgu_tes_machine_type_filter"):
        combined_station_ids = list(set(pgu_station_ids))
    else:
        combined_station_ids = list(set(machine_station_ids).union(set(pgu_station_ids)))

    combined_station_ids = sorted([sid for sid in combined_station_ids if sid is not None])

    print("Machine station ids:", sorted(set(machine_station_ids)))
    print("PGU station ids:", sorted(set(pgu_station_ids)))
    print("Final combined station ids:", combined_station_ids)

    total_count = len(combined_station_ids)

    if not combined_station_ids:
        return {"stations": [], "total_count": 0}

    # Пагинация
    if isinstance(per_page, str) and per_page.lower() == "all":
        paged_station_ids = combined_station_ids
    else:
        per_page = int(per_page or 10)
        offset = (page - 1) * per_page
        paged_station_ids = combined_station_ids[offset:offset + per_page]

    print("Paged station ids:", paged_station_ids)

    # 4. Фильтры по Station
    station_query = Station.query.filter(Station.id.in_(paged_station_ids))

    if filters.get("station_type_filter"):
        station_query = station_query.filter(Station.id_station_type.in_(filters["station_type_filter"]))

    if filters.get("station_name_filter"):
        station_query = station_query.filter(Station.name.ilike(f"%{filters['station_name_filter']}%"))

    if filters.get("gen_company_filter"):
        gen_company_ids = [g[0] for g in db.session.query(GenCompany.id).filter(
            GenCompany.name.ilike(f"%{filters['gen_company_filter']}%")
        ).all()]
        station_query = station_query.filter(Station.machines.any(Machine.id_gen_company.in_(gen_company_ids)))

    if filters.get("condition_type_filter"):
        station_query = station_query.filter(Station.machines.any(Machine.id_condition_type == filters["condition_type_filter"]))

    if filters.get("regional_district_filter"):
        station_query = station_query.filter(Station.id_regional_district.in_(filters["regional_district_filter"]))

    if filters.get("federal_district_filter"):
        station_query = station_query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(FederalDistrict.id.in_(filters["federal_district_filter"]))
            )
        )

    if filters.get("regional_energy_system_filter"):
        station_query = station_query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id.in_(filters["regional_energy_system_filter"]))
            )
        )

    if filters.get("union_energy_system_filter"):
        station_query = station_query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id_union_energy_system.in_(filters["union_energy_system_filter"]))
            )
        )

    if filters.get("energy_system_type_filter"):
        station_query = station_query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.union_energy_system.has(
                        UnionEnergySystem.energy_system_type.has(
                            EnergySystemType.id.in_(filters["energy_system_type_filter"]))
                    )
                )
            )
        )

    # Загружаем станции без сортировки (сортировка будет в Python)
    # Используем selectinload для regional_district, чтобы избежать дублирования станций
    # из-за множественных regional_energy_systems
    stations = station_query.options(
        selectinload(Station.regional_district).selectinload(RegionalDistrict.regional_energy_systems).joinedload(RegionalEnergySystem.union_energy_system).joinedload(UnionEnergySystem.energy_system_type),
        selectinload(Station.regional_district).joinedload(RegionalDistrict.federal_district),
        joinedload(Station.energy_unit),
        selectinload(Station.machines).selectinload(Machine.machine_powers),
        selectinload(Station.machines).selectinload(Machine.machine_fuels),
        selectinload(Station.machines).selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
    ).all()
    
    # Уникализация станций ПЕРЕД сортировкой (на случай дубликатов из-за JOIN)
    seen_ids = set()
    unique_stations_list = []
    for station in stations:
        if station.id not in seen_ids:
            seen_ids.add(station.id)
            unique_stations_list.append(station)
        else:
            print(f"[WARNING] Дубликат станции обнаружен при загрузке (with PGU): ID={station.id}, name={station.name}")
    
    stations = unique_stations_list
    
    # Сортировка в Python по полной территориальной иерархии
    def get_sorting_key(station):
        """
        Возвращает кортеж для сортировки по полной территориальной иерархии:
        (energy_system_type_id, union_energy_system_id, regional_energy_system_id, 
         regional_district_id, energy_unit_id, min_station_type_id, station_id)
        Это гарантирует, что все станции одного субъекта будут отображаться вместе.
        """
        # Определяем минимальный тип станции по агрегатам
        if station.machines:
            station_types = [m.id_station_type for m in station.machines if m.id_station_type is not None]
            min_type = min(station_types) if station_types else float('inf')
        else:
            min_type = float('inf')
        
        # Получаем иерархию через связи
        energy_system_type_id = 0
        union_energy_system_id = 0
        regional_energy_system_id = 0
        regional_district_id = station.id_regional_district or 0
        energy_unit_id = station.id_energy_unit or 0
        
        if station.regional_district and station.regional_district.regional_energy_systems:
            res = station.regional_district.regional_energy_systems[0]
            if res:
                regional_energy_system_id = res.id
                if res.union_energy_system:
                    union_energy_system_id = res.union_energy_system.id
                    if res.union_energy_system.energy_system_type:
                        energy_system_type_id = res.union_energy_system.energy_system_type.id
        
        return (
            energy_system_type_id,
            union_energy_system_id,
            regional_energy_system_id,
            regional_district_id,
            energy_unit_id,
            min_type,
            station.id
        )
    
    stations = sorted(stations, key=get_sorting_key)

    filtered_machine_ids = [m[0] for m in db.session.query(Machine.id).filter(Machine.id_station.in_(paged_station_ids)).all()]

    filtered_machines = Machine.query.options(
        selectinload(Machine.machine_fuels),
        selectinload(Machine.machine_powers),
        selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
    ).filter(Machine.id.in_(filtered_machine_ids)).all()

    pgu_machines = PGUMachine.query.join(PGUMachine.parent_machine).filter(
        PGUMachine.parent_machine.has(Machine.id_station.in_(paged_station_ids))
    ).all()

    from collections import defaultdict
    station_machines_map = defaultdict(list)
    station_pgu_map = defaultdict(list)

    for m in filtered_machines:
        station_machines_map[m.id_station].append(m)

    for pgu in pgu_machines:
        if pgu.parent_machine and pgu.parent_machine.id_station:
            station_pgu_map[pgu.parent_machine.id_station].append(pgu)

    for station in stations:
        station.machines = station_machines_map.get(station.id, [])
        station.pgu_machines = station_pgu_map.get(station.id, [])

    for station in stations:
        print(f"Station {station.id}: Machines={len(station.machines)}, PGUs={len(station.pgu_machines)}")

    return {
        "stations": stations,
        "total_count": total_count,
    }


def determine_first_headers(stations_on_page, prev_page_last_station_info=None):
    """
    Определяет, какие заголовки групп нужно показать на текущей странице.
    Заголовок показывается только если это первое появление группы.
    
    Args:
        stations_on_page: станции на текущей странице
        prev_page_last_station_info: информация о последней станции предыдущей страницы
    
    Returns:
        dict с информацией о том, какие заголовки показывать
    """
    if not stations_on_page:
        return {}
    
    first_station = stations_on_page[0]
    
    # Определяем, какие группы показать для первой станции
    show_headers = {
        'energy_system_types': set(),
        'union_energy_systems': set(),
        'regional_energy_systems': set(),
        'regional_districts': set(),
        'energy_units': set(),
    }
    
    # Получаем иерархию первой станции
    est_id = ues_id = res_id = rd_id = eu_id = None
    
    if first_station.regional_district and first_station.regional_district.regional_energy_systems:
        res = first_station.regional_district.regional_energy_systems[0]
        if res:
            res_id = res.id
            rd_id = first_station.id_regional_district
            eu_id = first_station.id_energy_unit or 0
            
            if res.union_energy_system:
                ues_id = res.union_energy_system.id
                if res.union_energy_system.energy_system_type:
                    est_id = res.union_energy_system.energy_system_type.id
    
    # Если нет информации о предыдущей странице - показываем все заголовки
    if prev_page_last_station_info is None:
        if est_id is not None:
            show_headers['energy_system_types'].add(est_id)
        if ues_id is not None:
            show_headers['union_energy_systems'].add(ues_id)
        if res_id is not None:
            show_headers['regional_energy_systems'].add(res_id)
        if rd_id is not None:
            show_headers['regional_districts'].add(rd_id)
        if eu_id is not None and eu_id != 0:
            show_headers['energy_units'].add(eu_id)
    else:
        # Сравниваем с предыдущей страницей - показываем только если группа изменилась
        prev_est = prev_page_last_station_info.get('energy_system_type_id')
        prev_ues = prev_page_last_station_info.get('union_energy_system_id')
        prev_res = prev_page_last_station_info.get('regional_energy_system_id')
        prev_rd = prev_page_last_station_info.get('regional_district_id')
        prev_eu = prev_page_last_station_info.get('energy_unit_id')
        
        if est_id != prev_est and est_id is not None:
            show_headers['energy_system_types'].add(est_id)
        if ues_id != prev_ues and ues_id is not None:
            show_headers['union_energy_systems'].add(ues_id)
        if res_id != prev_res and res_id is not None:
            show_headers['regional_energy_systems'].add(res_id)
        if rd_id != prev_rd and rd_id is not None:
            show_headers['regional_districts'].add(rd_id)
        if eu_id != prev_eu and eu_id is not None and eu_id != 0:
            show_headers['energy_units'].add(eu_id)
    
    # Проверяем остальные станции на странице - добавляем заголовки при смене группы
    prev_est = est_id
    prev_ues = ues_id
    prev_res = res_id
    prev_rd = rd_id
    prev_eu = eu_id
    
    for station in stations_on_page[1:]:
        if station.regional_district and station.regional_district.regional_energy_systems:
            res = station.regional_district.regional_energy_systems[0]
            if res:
                curr_res_id = res.id
                curr_rd_id = station.id_regional_district
                curr_eu_id = station.id_energy_unit or 0
                curr_ues_id = res.union_energy_system.id if res.union_energy_system else None
                curr_est_id = res.union_energy_system.energy_system_type.id if res.union_energy_system and res.union_energy_system.energy_system_type else None
                
                if curr_est_id != prev_est and curr_est_id is not None:
                    show_headers['energy_system_types'].add(curr_est_id)
                if curr_ues_id != prev_ues and curr_ues_id is not None:
                    show_headers['union_energy_systems'].add(curr_ues_id)
                if curr_res_id != prev_res and curr_res_id is not None:
                    show_headers['regional_energy_systems'].add(curr_res_id)
                if curr_rd_id != prev_rd and curr_rd_id is not None:
                    show_headers['regional_districts'].add(curr_rd_id)
                if curr_eu_id != prev_eu and curr_eu_id is not None and curr_eu_id != 0:
                    show_headers['energy_units'].add(curr_eu_id)
                
                prev_est = curr_est_id
                prev_ues = curr_ues_id
                prev_res = curr_res_id
                prev_rd = curr_rd_id
                prev_eu = curr_eu_id
    
    return show_headers


def get_regional_districts_count_per_res():
    """
    Возвращает словарь {res_id: количество субъектов РФ в этой РЭС}.
    """
    from collections import defaultdict
    res_to_rd_count = defaultdict(int)
    
    # Запрашиваем все региональные энергосистемы с их субъектами
    res_list = db.session.query(RegionalEnergySystem).options(
        joinedload(RegionalEnergySystem.regional_districts)
    ).all()
    
    for res in res_list:
        res_to_rd_count[res.id] = len(res.regional_districts)
    
    return res_to_rd_count


def get_regional_districts_with_stations_per_res(filters=None):
    """
    Возвращает словарь {res_id: количество субъектов РФ с станциями в этой РЭС}.
    Учитывает фильтры - только субъекты, у которых есть станции после фильтрации.
    """
    from collections import defaultdict
    
    # Получаем все станции с учетом фильтров
    query = db.session.query(
        Station.id_regional_district,
        RegionalEnergySystem.id.label('res_id')
    ).join(
        Station.regional_district
    ).join(
        RegionalDistrict.regional_energy_systems
    ).distinct()
    
    # Применяем территориальные фильтры
    if filters:
        if filters.get("regional_district_filter"):
            query = query.filter(Station.id_regional_district.in_(filters["regional_district_filter"]))
        
        if filters.get("federal_district_filter"):
            query = query.filter(
                Station.regional_district.has(
                    RegionalDistrict.id_federal_district.in_(filters["federal_district_filter"])
                )
            )
        
        if filters.get("regional_energy_system_filter"):
            query = query.filter(RegionalEnergySystem.id.in_(filters["regional_energy_system_filter"]))
        
        if filters.get("union_energy_system_filter"):
            query = query.filter(
                RegionalEnergySystem.id_union_energy_system.in_(filters["union_energy_system_filter"])
            )
        
        if filters.get("energy_system_type_filter"):
            query = query.filter(
                RegionalEnergySystem.union_energy_system.has(
                    UnionEnergySystem.energy_system_type.has(
                        EnergySystemType.id.in_(filters["energy_system_type_filter"])
                    )
                )
            )
    
    rows = query.all()
    
    res_to_rd_count = defaultdict(int)
    for rd_id, res_id in rows:
        if rd_id and res_id:
            res_to_rd_count[res_id] += 1
    
    return dict(res_to_rd_count)


def determine_totals_to_show(stations_on_page, total_count, page, per_page, filters, next_station_info=None):
    """
    Определяет, какие агрегированные итоги нужно показать на текущей странице.
    Итог показывается если группа меняется внутри страницы или завершается на этой странице.
    Итоги по субъектам РФ показываются только если в РЭС более одного субъекта.
    
    Args:
        next_station_info: информация о следующей станции после текущей страницы (из отсортированного списка)
    """
    # Получаем маппинг: сколько субъектов в каждой РЭС (нужен во всех режимах)
    res_to_rd_count = get_regional_districts_count_per_res()
    # Получаем реальное количество субъектов со станциями в каждой РЭС (с учетом фильтров)
    res_to_rd_with_stations_global = get_regional_districts_with_stations_per_res(filters)
    
    if not stations_on_page or per_page is None:
        # Для per_page='all' показываем все итоги, но учитываем правило для regional_districts
        # Создаем маппинг rd_to_res для всех станций
        rd_to_res = {}
        all_rd_ids = set()
        
        for station in stations_on_page:
            if station.id_regional_district:
                all_rd_ids.add(station.id_regional_district)
                if station.regional_district and station.regional_district.regional_energy_systems:
                    res = station.regional_district.regional_energy_systems[0]
                    if res:
                        rd_to_res[station.id_regional_district] = res.id
        
        # Определяем, какие regional_districts показывать
        # Показываем только если в РЭС >1 субъекта по БД И >1 субъекта имеют станции
        allowed_rd_ids = {}
        for rd_id in all_rd_ids:
            res_id = rd_to_res.get(rd_id)
            if res_id:
                total_rd_in_res = res_to_rd_count.get(res_id, 0)
                rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                
                if total_rd_in_res > 1 and rd_with_stations_count > 1:
                    allowed_rd_ids[rd_id] = True
                    print(f"[DEBUG] [per_page=all] Regional district итог показывается (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями): {rd_id}")
                else:
                    print(f"[DEBUG] [per_page=all] Regional district итог НЕ показывается (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями): {rd_id}")
        
        return {
            'show_all': True,
            'regional_districts': allowed_rd_ids  # Только РД из РЭС с >1 субъектом И >1 субъектом со станциями
        }
    
    # Проверяем, есть ли еще станции после текущей страницы
    current_position = page * per_page
    has_more_stations = current_position < total_count
    
    print(f"[DEBUG] Page: {page}, per_page: {per_page}, total_count: {total_count}, current_position: {current_position}, has_more: {has_more_stations}")
    
    show_totals = {
        'energy_units': {},
        'regional_districts': {},
        'regional_energy_systems': {},
        'union_energy_systems': {},
        'energy_system_types': {},
        'total': False
    }
    
    # Собираем все уникальные группы на странице
    groups_on_page = {
        'energy_units': set(),
        'regional_districts': set(),
        'regional_energy_systems': set(),
        'union_energy_systems': set(),
        'energy_system_types': set()
    }
    
    # Маппинг: какой regional_district принадлежит какой regional_energy_system
    rd_to_res = {}
    
    for station in stations_on_page:
        if station.id_energy_unit:
            groups_on_page['energy_units'].add(station.id_energy_unit)
        if station.id_regional_district:
            groups_on_page['regional_districts'].add(station.id_regional_district)
        
        if station.regional_district and station.regional_district.regional_energy_systems:
            res = station.regional_district.regional_energy_systems[0]
            if res:
                groups_on_page['regional_energy_systems'].add(res.id)
                # Запоминаем связь RD -> RES
                if station.id_regional_district:
                    rd_to_res[station.id_regional_district] = res.id
                if res.union_energy_system:
                    groups_on_page['union_energy_systems'].add(res.union_energy_system.id)
                    if res.union_energy_system.energy_system_type:
                        groups_on_page['energy_system_types'].add(res.union_energy_system.energy_system_type.id)
    
    # Получаем последнюю станцию на странице
    last_station = stations_on_page[-1]
    last_energy_unit_id = last_station.id_energy_unit
    last_regional_district_id = last_station.id_regional_district
    last_regional_energy_system_id = None
    last_union_energy_system_id = None
    last_energy_system_type_id = None
    
    if last_station.regional_district and last_station.regional_district.regional_energy_systems:
        res = last_station.regional_district.regional_energy_systems[0]
        if res:
            last_regional_energy_system_id = res.id
            if res.union_energy_system:
                last_union_energy_system_id = res.union_energy_system.id
                if res.union_energy_system.energy_system_type:
                    last_energy_system_type_id = res.union_energy_system.energy_system_type.id
    
    if not has_more_stations:
        # Последняя страница - показываем итоги для всех групп на странице
        for eu_id in groups_on_page['energy_units']:
            show_totals['energy_units'][eu_id] = True
        for rd_id in groups_on_page['regional_districts']:
            # Показываем итог по субъекту только если:
            # 1. В РЭС более одного субъекта (по БД)
            # 2. И на странице станции есть у более чем одного субъекта этой РЭС
            res_id = rd_to_res.get(rd_id)
            if res_id:
                total_rd_in_res = res_to_rd_count.get(res_id, 0)
                rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                
                if total_rd_in_res > 1 and rd_with_stations_count > 1:
                    show_totals['regional_districts'][rd_id] = True
                    print(f"[DEBUG] [OK] Regional district итог показывается (РЭС содержит {total_rd_in_res} субъектов, {rd_with_stations_count} со станциями ГЛОБАЛЬНО): {rd_id}")
                else:
                    print(f"[DEBUG] [SKIP] Regional district итог НЕ показывается (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями ГЛОБАЛЬНО): {rd_id}")
        for res_id in groups_on_page['regional_energy_systems']:
            show_totals['regional_energy_systems'][res_id] = True
        for ues_id in groups_on_page['union_energy_systems']:
            show_totals['union_energy_systems'][ues_id] = True
        for est_id in groups_on_page['energy_system_types']:
            show_totals['energy_system_types'][est_id] = True
        show_totals['total'] = True
    else:
        # Используем переданную информацию о следующей станции
        next_station = next_station_info
        
        print(f"[DEBUG] Last station - EU: {last_energy_unit_id}, RD: {last_regional_district_id}, RES: {last_regional_energy_system_id}")
        print(f"[DEBUG] Next station: {next_station}")
        
        if next_station:
            # Находим точки смены групп на странице (группы, которые завершились внутри страницы)
            # Для этого проходим по всем станциям и отслеживаем изменения
            
            # Energy Units - находим завершившиеся на странице
            prev_eu = None
            for station in stations_on_page:
                curr_eu = station.id_energy_unit
                if prev_eu is not None and prev_eu != curr_eu and prev_eu in groups_on_page['energy_units']:
                    show_totals['energy_units'][prev_eu] = True
                    print(f"[DEBUG] Energy unit завершается внутри страницы: {prev_eu}")
                prev_eu = curr_eu
            # Проверяем последний energy unit - завершается ли на следующей странице?
            if last_energy_unit_id and next_station.get('energy_unit_id') != last_energy_unit_id:
                show_totals['energy_units'][last_energy_unit_id] = True
                print(f"[DEBUG] Energy unit завершается на границе страниц: {last_energy_unit_id}")
            
            # Regional Districts - находим завершившиеся на странице
            prev_rd = None
            for station in stations_on_page:
                curr_rd = station.id_regional_district
                if prev_rd is not None and prev_rd != curr_rd and prev_rd in groups_on_page['regional_districts']:
                    # Показываем итог по субъекту только если:
                    # 1. В РЭС более одного субъекта (по БД)
                    # 2. И на странице станции есть у более чем одного субъекта этой РЭС
                    res_id = rd_to_res.get(prev_rd)
                    if res_id:
                        total_rd_in_res = res_to_rd_count.get(res_id, 0)
                        rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                        
                        if total_rd_in_res > 1 and rd_with_stations_count > 1:
                            show_totals['regional_districts'][prev_rd] = True
                            print(f"[DEBUG] [OK] Regional district завершается внутри страницы (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями ГЛОБАЛЬНО): {prev_rd}")
                        else:
                            print(f"[DEBUG] [SKIP] Regional district завершается внутри страницы, но НЕ показывается (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями ГЛОБАЛЬНО): {prev_rd}")
                prev_rd = curr_rd
            # Проверяем последний regional district
            if last_regional_district_id and next_station.get('regional_district_id') != last_regional_district_id:
                # Показываем итог по субъекту только если:
                # 1. В РЭС более одного субъекта (по БД)
                # 2. И на странице станции есть у более чем одного субъекта этой РЭС
                res_id = rd_to_res.get(last_regional_district_id)
                if res_id:
                    total_rd_in_res = res_to_rd_count.get(res_id, 0)
                    rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                    
                    if total_rd_in_res > 1 and rd_with_stations_count > 1:
                        show_totals['regional_districts'][last_regional_district_id] = True
                        print(f"[DEBUG] [OK] Regional district завершается на границе страниц (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями ГЛОБАЛЬНО): {last_regional_district_id}")
                    else:
                        print(f"[DEBUG] [SKIP] Regional district завершается на границе страниц, но НЕ показывается (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями ГЛОБАЛЬНО): {last_regional_district_id}")
            
            # Regional Energy Systems - находим завершившиеся на странице
            prev_res = None
            for station in stations_on_page:
                curr_res = None
                if station.regional_district and station.regional_district.regional_energy_systems:
                    res = station.regional_district.regional_energy_systems[0]
                    if res:
                        curr_res = res.id
                if prev_res is not None and prev_res != curr_res and prev_res in groups_on_page['regional_energy_systems']:
                    show_totals['regional_energy_systems'][prev_res] = True
                    print(f"[DEBUG] Regional energy system завершается внутри страницы: {prev_res}")
                prev_res = curr_res
            # Проверяем последнюю regional energy system
            if last_regional_energy_system_id and next_station.get('regional_energy_system_id') != last_regional_energy_system_id:
                show_totals['regional_energy_systems'][last_regional_energy_system_id] = True
                print(f"[DEBUG] Regional energy system завершается на границе страниц: {last_regional_energy_system_id}")
            
            # Union Energy Systems - находим завершившиеся на странице
            prev_ues = None
            for station in stations_on_page:
                curr_ues = None
                if station.regional_district and station.regional_district.regional_energy_systems:
                    res = station.regional_district.regional_energy_systems[0]
                    if res and res.union_energy_system:
                        curr_ues = res.union_energy_system.id
                if prev_ues is not None and prev_ues != curr_ues and prev_ues in groups_on_page['union_energy_systems']:
                    show_totals['union_energy_systems'][prev_ues] = True
                    print(f"[DEBUG] Union energy system завершается внутри страницы: {prev_ues}")
                prev_ues = curr_ues
            # Проверяем последнюю union energy system
            if last_union_energy_system_id and next_station.get('union_energy_system_id') != last_union_energy_system_id:
                show_totals['union_energy_systems'][last_union_energy_system_id] = True
                print(f"[DEBUG] Union energy system завершается на границе страниц: {last_union_energy_system_id}")
            
            # Energy System Types - находим завершившиеся на странице
            prev_est = None
            for station in stations_on_page:
                curr_est = None
                if station.regional_district and station.regional_district.regional_energy_systems:
                    res = station.regional_district.regional_energy_systems[0]
                    if res and res.union_energy_system and res.union_energy_system.energy_system_type:
                        curr_est = res.union_energy_system.energy_system_type.id
                if prev_est is not None and prev_est != curr_est and prev_est in groups_on_page['energy_system_types']:
                    show_totals['energy_system_types'][prev_est] = True
                    print(f"[DEBUG] Energy system type завершается внутри страницы: {prev_est}")
                prev_est = curr_est
            # Проверяем последний energy system type
            if last_energy_system_type_id and next_station.get('energy_system_type_id') != last_energy_system_type_id:
                show_totals['energy_system_types'][last_energy_system_type_id] = True
                print(f"[DEBUG] Energy system type завершается на границе страниц: {last_energy_system_type_id}")
        else:
            print(f"[DEBUG] Next station is None - показываем итоги для всех групп на странице")
            for eu_id in groups_on_page['energy_units']:
                show_totals['energy_units'][eu_id] = True
            for rd_id in groups_on_page['regional_districts']:
                # Показываем итог по субъекту только если:
                # 1. В РЭС более одного субъекта (по БД)
                # 2. И на странице станции есть у более чем одного субъекта этой РЭС
                res_id = rd_to_res.get(rd_id)
                if res_id:
                    total_rd_in_res = res_to_rd_count.get(res_id, 0)
                    rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                    
                    if total_rd_in_res > 1 and rd_with_stations_count > 1:
                        show_totals['regional_districts'][rd_id] = True
                        print(f"[DEBUG] [OK] Regional district итог показывается (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями ГЛОБАЛЬНО): {rd_id}")
                    else:
                        print(f"[DEBUG] [SKIP] Regional district итог НЕ показывается (РЭС: {total_rd_in_res} субъектов всего, {rd_with_stations_count} со станциями ГЛОБАЛЬНО): {rd_id}")
            for res_id in groups_on_page['regional_energy_systems']:
                show_totals['regional_energy_systems'][res_id] = True
            for ues_id in groups_on_page['union_energy_systems']:
                show_totals['union_energy_systems'][ues_id] = True
            for est_id in groups_on_page['energy_system_types']:
                show_totals['energy_system_types'][est_id] = True
    
    print(f"[DEBUG] show_totals: {show_totals}")
    return show_totals


def get_next_station_info(current_page, per_page, filters):
    """Получает информацию о первой станции после текущей страницы."""
    try:
        # Нужна станция с номером (current_page * per_page + 1)
        # Это первая станция следующей страницы
        # Используем offset для точного позиционирования
        offset_needed = current_page * per_page
        
        # Запрашиваем данные с правильным offset
        # Используем большой per_page и берем только одну станцию с нужным offset
        from sqlalchemy import and_
        
        # Создаем базовый запрос как в get_stations_list
        current_year = get_current_year()
        
        # 1. Фильтрация агрегатов
        machine_query = db.session.query(Machine.id, Machine.id_station)
        
        if filters.get("tes_type_filter"):
            machine_query = machine_query.filter(
                Machine.machine_tes_types.any(
                    and_(
                        MachineTesType.year_number == current_year,
                        MachineTesType.id_tes_type.in_(filters["tes_type_filter"])
                    )
                )
            )
        
        if filters.get("tes_machine_type_filter"):
            machine_query = machine_query.filter(
                Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"])
            )
        
        if filters.get("fuel_type_filter"):
            machine_query = machine_query.join(Machine.machine_fuels).join(MachineFuel.fuel).filter(
                Fuel.id_fuel_type.in_(filters["fuel_type_filter"])
            )
        
        if filters.get("date_exploitation_filter"):
            machine_query = machine_query.filter(
                Machine.date_exploitation.in_(filters["date_exploitation_filter"])
            )
        
        if filters.get("date_decompressing_expected_filter"):
            machine_query = machine_query.filter(
                Machine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"])
            )
        
        if filters.get("date_modernization_expected_filter"):
            machine_query = machine_query.filter(
                Machine.date_modernization_expected.in_(filters["date_modernization_expected_filter"])
            )
        
        # 2. Subquery с подходящими агрегатами
        machine_subquery = machine_query.subquery()
        station_ids_query = db.session.query(machine_subquery.c.id_station).distinct()
        station_ids_query = station_ids_query.join(Station, Station.id == machine_subquery.c.id_station)
        
        # 3. Применяем фильтры по станции (как в get_stations_list)
        if filters.get("station_type_filter"):
            station_ids_query = station_ids_query.filter(
                Station.id_station_type.in_(filters["station_type_filter"])
            )
        
        if filters.get("station_name_filter"):
            station_ids_query = station_ids_query.filter(
                Station.name.ilike(f"%{filters['station_name_filter']}%")
            )
        
        if filters.get("gen_company_filter"):
            gen_company_ids = db.session.query(GenCompany.id).filter(
                GenCompany.name.ilike(f"%{filters['gen_company_filter']}%")
            ).all()
            ids = [g[0] for g in gen_company_ids]
            station_ids_query = station_ids_query.filter(
                Station.machines.any(Machine.id_gen_company.in_(ids))
            )
        
        if filters.get("condition_type_filter"):
            station_ids_query = station_ids_query.filter(
                Station.machines.any(Machine.id_condition_type == filters["condition_type_filter"])
            )
        
        if filters.get("regional_district_filter"):
            station_ids_query = station_ids_query.filter(
                Station.id_regional_district.in_(filters["regional_district_filter"])
            )
        
        if filters.get("federal_district_filter"):
            station_ids_query = station_ids_query.filter(
                Station.regional_district.has(
                    RegionalDistrict.federal_district.has(
                        FederalDistrict.id.in_(filters["federal_district_filter"])
                    )
                )
            )
        
        if filters.get("regional_energy_system_filter"):
            station_ids_query = station_ids_query.filter(
                Station.regional_district.has(
                    RegionalDistrict.regional_energy_systems.any(
                        RegionalEnergySystem.id.in_(filters["regional_energy_system_filter"])
                    )
                )
            )
        
        if filters.get("union_energy_system_filter"):
            station_ids_query = station_ids_query.filter(
                Station.regional_district.has(
                    RegionalDistrict.regional_energy_systems.any(
                        RegionalEnergySystem.id_union_energy_system.in_(
                            filters["union_energy_system_filter"]
                        )
                    )
                )
            )
        
        if filters.get("energy_system_type_filter"):
            station_ids_query = station_ids_query.filter(
                Station.regional_district.has(
                    RegionalDistrict.regional_energy_systems.any(
                        RegionalEnergySystem.union_energy_system.has(
                            UnionEnergySystem.energy_system_type.has(
                                EnergySystemType.id.in_(filters["energy_system_type_filter"])
                            )
                        )
                    )
                )
            )
        
        # Получаем station_id с нужным offset
        # Примечание: Эта функция может работать некорректно с новой Python-сортировкой
        # так как offset применяется к SQL запросу без учета сортировки по id_station_type
        station_ids = [row[0] for row in station_ids_query.offset(offset_needed).limit(1).all()]
        
        if not station_ids:
            return None
        
        # Загружаем станцию
        station = Station.query.options(
            joinedload(Station.regional_district).joinedload(RegionalDistrict.regional_energy_systems)
        ).filter(Station.id == station_ids[0]).first()
        
        if station:
            info = {
                'energy_unit_id': station.id_energy_unit,
                'regional_district_id': station.id_regional_district,
            }
            if station.regional_district and station.regional_district.regional_energy_systems:
                res = station.regional_district.regional_energy_systems[0]
                if res:
                    info['regional_energy_system_id'] = res.id
                    if res.union_energy_system:
                        info['union_energy_system_id'] = res.union_energy_system.id
                        if res.union_energy_system.energy_system_type:
                            info['energy_system_type_id'] = res.union_energy_system.energy_system_type.id
            return info
    except Exception as e:
        print(f"[ERROR] get_next_station_info: {e}")
        import traceback
        traceback.print_exc()
    return None


def get_station_ids_for_aggregation(stations_on_page, should_show_totals, filters):
    """
    Получает все station_ids для групп, которые завершаются на текущей странице.
    Нужно для вычисления агрегированных сумм только по завершенным группам.
    Применяет территориальные фильтры для корректного расчета агрегатов.
    """
    if should_show_totals.get('show_all'):
        # Для per_page='all' возвращаем ID текущих станций
        return [s.id for s in stations_on_page]
    
    # Для постраничного режима нужно получить ВСЕ станции из завершившихся групп
    # Это требуется для корректного подсчета агрегатов
    station_ids = set()
    
    # Получаем территориальные фильтры
    regional_district_filter = filters.get('regional_district_filter', [])
    federal_district_filter = filters.get('federal_district_filter', [])
    regional_energy_system_filter = filters.get('regional_energy_system_filter', [])
    union_energy_system_filter = filters.get('union_energy_system_filter', [])
    energy_system_type_filter = filters.get('energy_system_type_filter', [])
    
    # Добавляем ID станций для каждой завершившейся группы
    for energy_unit_id, should_show in should_show_totals.get('energy_units', {}).items():
        if should_show:
            # Получаем все станции этого энергоузла с учетом фильтров
            query = Station.query.filter_by(id_energy_unit=energy_unit_id)
            
            # Применяем территориальные фильтры
            if regional_district_filter:
                query = query.filter(Station.id_regional_district.in_(regional_district_filter))
            if federal_district_filter:
                query = query.filter(
                    Station.regional_district.has(
                        RegionalDistrict.id_federal_district.in_(federal_district_filter)
                    )
                )
            
            eu_stations = query.all()
            station_ids.update([s.id for s in eu_stations])
    
    # Региональные энергосистемы
    for res_id, should_show in should_show_totals.get('regional_energy_systems', {}).items():
        if should_show:
            # Получаем РЭС с её субъектами
            res = db.session.query(RegionalEnergySystem).options(
                joinedload(RegionalEnergySystem.regional_districts)
            ).filter_by(id=res_id).first()
            
            if res and res.regional_districts:
                # Получаем субъекты этой РЭС с учетом фильтров
                rd_ids_in_res = [rd.id for rd in res.regional_districts]
                
                # Применяем фильтры по субъектам и федеральным округам
                if regional_district_filter:
                    rd_ids_in_res = [rd_id for rd_id in rd_ids_in_res if rd_id in regional_district_filter]
                
                if federal_district_filter:
                    # Фильтруем по федеральному округу
                    filtered_rd_ids = []
                    for rd in res.regional_districts:
                        if rd.id in rd_ids_in_res and rd.id_federal_district in federal_district_filter:
                            filtered_rd_ids.append(rd.id)
                    rd_ids_in_res = filtered_rd_ids
                
                if rd_ids_in_res:
                    res_stations = Station.query.filter(
                        Station.id_regional_district.in_(rd_ids_in_res)
                    ).all()
                    station_ids.update([s.id for s in res_stations])
                    print(f"[DEBUG] Добавлены станции для РЭС {res_id}: {len(res_stations)} станций из {len(rd_ids_in_res)} субъектов")
    
    # Субъекты РФ - добавляем только если итог по субъекту показывается явно
    for rd_id, should_show in should_show_totals.get('regional_districts', {}).items():
        if should_show:
            # Проверяем, что субъект соответствует фильтрам
            if regional_district_filter and rd_id not in regional_district_filter:
                continue
            
            if federal_district_filter:
                rd = db.session.query(RegionalDistrict).filter_by(id=rd_id).first()
                if rd and rd.id_federal_district not in federal_district_filter:
                    continue
            
            # Получаем все станции этого субъекта
            rd_stations = Station.query.filter_by(id_regional_district=rd_id).all()
            station_ids.update([s.id for s in rd_stations])
            print(f"[DEBUG] Добавлены станции для субъекта {rd_id}: {len(rd_stations)} станций")
    
    # Объединенные энергосистемы
    for ues_id, should_show in should_show_totals.get('union_energy_systems', {}).items():
        if should_show:
            # Проверяем фильтр по ОЭС
            if union_energy_system_filter and ues_id not in union_energy_system_filter:
                continue
            
            # Получаем все РЭС в этой ОЭС
            query = db.session.query(RegionalEnergySystem).options(
                joinedload(RegionalEnergySystem.regional_districts)
            ).filter_by(id_union_energy_system=ues_id)
            
            # Применяем фильтр по РЭС, если есть
            if regional_energy_system_filter:
                query = query.filter(RegionalEnergySystem.id.in_(regional_energy_system_filter))
            
            res_list = query.all()
            
            ues_station_count_before = len(station_ids)
            for res in res_list:
                if res.regional_districts:
                    rd_ids_in_res = [rd.id for rd in res.regional_districts]
                    
                    # Применяем фильтры по субъектам и федеральным округам
                    if regional_district_filter:
                        rd_ids_in_res = [rd_id for rd_id in rd_ids_in_res if rd_id in regional_district_filter]
                    
                    if federal_district_filter:
                        filtered_rd_ids = []
                        for rd in res.regional_districts:
                            if rd.id in rd_ids_in_res and rd.id_federal_district in federal_district_filter:
                                filtered_rd_ids.append(rd.id)
                        rd_ids_in_res = filtered_rd_ids
                    
                    if rd_ids_in_res:
                        ues_stations = Station.query.filter(
                            Station.id_regional_district.in_(rd_ids_in_res)
                        ).all()
                        station_ids.update([s.id for s in ues_stations])
            
            ues_station_count_added = len(station_ids) - ues_station_count_before
            if ues_station_count_added > 0:
                print(f"[DEBUG] Добавлены станции для ОЭС {ues_id}: +{ues_station_count_added} уникальных станций из {len(res_list)} РЭС")
    
    # Типы энергосистем
    for est_id, should_show in should_show_totals.get('energy_system_types', {}).items():
        if should_show:
            # Проверяем фильтр по типу энергосистемы
            if energy_system_type_filter and est_id not in energy_system_type_filter:
                continue
            
            # Получаем все ОЭС этого типа
            query = db.session.query(UnionEnergySystem).filter_by(id_energy_system_type=est_id)
            
            # Применяем фильтр по ОЭС, если есть
            if union_energy_system_filter:
                query = query.filter(UnionEnergySystem.id.in_(union_energy_system_filter))
            
            ues_list = query.all()
            
            est_station_count_before = len(station_ids)
            for ues in ues_list:
                res_query = db.session.query(RegionalEnergySystem).options(
                    joinedload(RegionalEnergySystem.regional_districts)
                ).filter_by(id_union_energy_system=ues.id)
                
                # Применяем фильтр по РЭС, если есть
                if regional_energy_system_filter:
                    res_query = res_query.filter(RegionalEnergySystem.id.in_(regional_energy_system_filter))
                
                res_list = res_query.all()
                
                for res in res_list:
                    if res.regional_districts:
                        rd_ids_in_res = [rd.id for rd in res.regional_districts]
                        
                        # Применяем фильтры по субъектам и федеральным округам
                        if regional_district_filter:
                            rd_ids_in_res = [rd_id for rd_id in rd_ids_in_res if rd_id in regional_district_filter]
                        
                        if federal_district_filter:
                            filtered_rd_ids = []
                            for rd in res.regional_districts:
                                if rd.id in rd_ids_in_res and rd.id_federal_district in federal_district_filter:
                                    filtered_rd_ids.append(rd.id)
                            rd_ids_in_res = filtered_rd_ids
                        
                        if rd_ids_in_res:
                            est_stations = Station.query.filter(
                                Station.id_regional_district.in_(rd_ids_in_res)
                            ).all()
                            station_ids.update([s.id for s in est_stations])
            
            est_station_count_added = len(station_ids) - est_station_count_before
            if est_station_count_added > 0:
                print(f"[DEBUG] Добавлены станции для типа энергосистемы {est_id}: +{est_station_count_added} уникальных станций из {len(ues_list)} ОЭС")
    
    # Если нет завершающихся групп, возвращаем хотя бы текущие станции для их итогов
    if not station_ids:
        station_ids = set([s.id for s in stations_on_page])
    
    print(f"[DEBUG] Итого station_ids для агрегации: {len(station_ids)}")
    return list(station_ids)


def get_station_list_data(
    filters,
    per_page,
    page=1,
    rounding_digits=None,
    start_year=None,
    end_year=None,
    show_p_ogr=False,
    show_p_rasp=False,
    show_all=False,
    show_totals=False,
):
    # Очистка служебных полей из filters
    filters = filters.copy()
    filters.pop("page", None)
    filters.pop("start_year", None)
    filters.pop("end_year", None)

    # Настройка параметров пагинации
    if isinstance(per_page, str) and per_page.lower() == "all":
        show_all = True
        per_page_int = None
    else:
        show_all = False
        try:
            per_page_int = int(per_page)
        except (TypeError, ValueError):
            per_page_int = 10

    # Загружаем отфильтрованные станции
    station_data = get_stations_list(
        page=page,
        per_page=per_page,
        rounding_digits=rounding_digits,
        **filters
    )
    stations = station_data["stations"]
    total_count = station_data["total_count"]
    next_station_info = station_data.get("next_station_info")
    total_pages = 1 if show_all else max(1, (total_count + per_page_int - 1) // per_page_int)

    # Получаем агрегаты с рассчитанными rowspan (только если не per_page=all для ускорения)
    station_ids = [s.id for s in stations]
    
    if not show_all:
        machines, station_totals = fetch_machines_with_rowspans(station_ids, show_p_ogr=show_p_ogr, show_p_rasp=show_p_rasp)
        
        # Привязываем машины обратно к станциям
        station_machines_map = defaultdict(list)
        for m in machines:
            station_machines_map[m.id_station].append(m)

        for station in stations:
            station.machines = station_machines_map.get(station.id, [])
            
        # 🧩 Назначение мощностей агрегатам
        for station in stations:
            for machine in station.machines:
                assign_machine_powers_by_year(machine, start_year, end_year, rounding_digits)
    else:
        # Для per_page=all считаем rowspan и итоги так же, как в постраничном режиме
        machines, station_totals = fetch_machines_with_rowspans(
            station_ids, show_p_ogr=show_p_ogr, show_p_rasp=show_p_rasp
        )
        # Привязываем машины обратно к станциям
        station_machines_map = defaultdict(list)
        for m in machines:
            station_machines_map[m.id_station].append(m)
        for station in stations:
            station.machines = station_machines_map.get(station.id, [])
        # Назначаем мощности агрегатам
        for station in stations:
            for machine in station.machines:
                assign_machine_powers_by_year(machine, start_year, end_year, rounding_digits)

    # Перерасчет мощностей станции
    recalculate_station_powers_by_filtered_machines(
        stations, start_year, end_year, rounding_digits
    )

    # Агрегация по иерархии
    hierarchy_data = build_hierarchy_structure(stations, include_names=True)

    stations = station_data["stations"]
    station_ids = [s.id for s in stations]

    # Определяем, какие группы завершаются на текущей странице и какие заголовки показывать
    # В зависимости от параметра show_totals
    if show_totals or show_all:
        # В режиме "С суммами" вычисляем, какие итоги показывать
        # Для show_all используем per_page=None, для постраничного - per_page_int
        should_show_totals = determine_totals_to_show(
            stations, total_count, page, 
            None if show_all else per_page_int, 
            filters, next_station_info
        )
        
        # Для show_all показываем все заголовки, для постраничного - только первые вхождения
        if show_all:
            show_headers = None
        else:
            from app.generation.services.station_services.aggregation_cache import get_cached_page_position
            _, prev_page_last_info = get_cached_page_position(filters, page) if page > 1 else (None, None)
            show_headers = determine_first_headers(stations, prev_page_last_info)
            print(f"[HEADERS] Page {page}: show_headers = {show_headers}")
            print(f"[HEADERS] prev_page_last_info = {prev_page_last_info}")
        
        # Для вычисления агрегаций загружаем необходимые station_ids
        aggregation_station_ids = get_station_ids_for_aggregation(stations, should_show_totals, filters)
        rows = get_full_aggregation_rows(start_year, end_year, aggregation_station_ids, filters)
    else:
        # В постраничном режиме без сумм - не показываем итоги
        should_show_totals = {
            'energy_units': {},
            'regional_districts': {},
            'regional_energy_systems': {},
            'union_energy_systems': {},
            'energy_system_types': {},
            'total': False
        }
        
        # Получаем информацию о последней станции предыдущей страницы из кэша
        from app.generation.services.station_services.aggregation_cache import get_cached_page_position
        _, prev_page_last_info = get_cached_page_position(filters, page) if page > 1 else (None, None)
        show_headers = determine_first_headers(stations, prev_page_last_info)
        print(f"[HEADERS] Page {page}: show_headers = {show_headers}")
        print(f"[HEADERS] prev_page_last_info = {prev_page_last_info}")
        
        # Не загружаем данные для агрегаций
        aggregation_station_ids = []
        rows = []

    result = {
        "stations": stations,
        "stations_grouped": hierarchy_data.get("grouped_stations", {}),
        "station_ids": station_ids,
        "total_count": total_count,
        "total_pages": total_pages,
        "station_totals":station_totals,
        "show_p_ogr":show_p_ogr,
        "show_p_rasp":show_p_rasp,
        "page": page,
        "per_page": per_page,
        "should_show_totals": should_show_totals,
        "show_headers": show_headers,
    }

    # Выполняем агрегации если включено отображение сумм или режим "Все станции"
    if show_totals or show_all:
        # Выполняем все агрегации за один проход по данным
        all_aggregations = aggregate_all_at_once(rows)
        result.update(all_aggregations)

    return result


def get_station_list_template_context(form, data, rounding_digits, filters, show_all=False):
    import time
    start_time = time.time()

    year_features = get_year_feature_dict()

    energy_system_type_list = get_energy_system_type_list_full()
    energy_system_type_names = get_energy_system_type_map()

    regional_energy_system_list = get_regional_energy_systems_dto_list()
    regional_energy_system_names = get_regional_energy_systems_map()
    regional_energy_system_mapping = get_ues_to_res_ids_map()

    federal_district_list = get_federal_districts_dto_list()
    regional_district_mapping = get_fd_to_rd_ids_map()

    regional_district_list = get_regional_districts_dto_list()
    regional_district_names = get_regional_districts_map()

    union_energy_system_list = get_union_energy_system_list_full()
    union_energy_system_names    = get_union_energy_systems_map()

    # Порядок типов энергосистем по минимальному порядку ОЭС внутри них
    ues_order_index = {ues.id: idx for idx, ues in enumerate(union_energy_system_list)}

    def _min_ues_index(es_group: dict) -> int:
        indices = [ues_order_index.get(ues_id, 10**9) for ues_id in es_group.keys()]
        return min(indices) if indices else 10**9

    sorted_energy_system_type_ids = sorted(
        data["stations_grouped"].keys(),
        key=lambda est_id: _min_ues_index(data["stations_grouped"][est_id])
    )

    energy_units = get_energy_unit_list_full()
    energy_unit_names = {eu.id: eu.name for eu in energy_units}
    
    station_type_names = get_station_type_list_full()
    station_type_list = {st.id: st.name for st in station_type_names}

    tes_type_names = get_tes_type_list_full()
    tes_type_list = {tt.id: tt.name for tt in tes_type_names}

    tes_machine_type_names = get_tes_machine_type_list_full()
    tes_machine_type_list = {tmt.id: tmt.name for tmt in tes_machine_type_names}

    pgu_tes_machine_type_names = get_pgu_tes_machine_type_list_full()
    pgu_tes_machine_type_list = {pt.id: pt.name for pt in pgu_tes_machine_type_names}

    fuel_type_names = get_fuel_type_list_full()
    fuel_type_list = {ft.id: ft.name for ft in fuel_type_names}

    machine_tes_types_map = get_current_machine_tes_types_map()

    context = {
            "form": form,
            "stations_grouped": data["stations_grouped"],
            "station_ids": data["station_ids"],
            "total_count": data["total_count"],
            "total_pages": data["total_pages"],
            "current_page": data["page"],
            "per_page": str(data["per_page"]).lower(),
            "start_year": filters.get("start_year"),
            "end_year": filters.get("end_year"),
            "station_totals": data["station_totals"],
            "show_p_ogr":data["show_p_ogr"],
            "show_p_rasp":data["show_p_rasp"],
            "rounding_digits": rounding_digits,
            "should_show_totals": data.get("should_show_totals", {}),
            "energy_system_type_list": energy_system_type_list,
            "energy_system_type_names": energy_system_type_names,
            "union_energy_system_list": union_energy_system_list,
            "union_energy_system_names": union_energy_system_names,
            "regional_energy_system_list": regional_energy_system_list,
            "regional_energy_system_names": regional_energy_system_names,
            "regional_energy_system_mapping": regional_energy_system_mapping,
            "federal_district_list": federal_district_list,
            "regional_district_list": regional_district_list,
            "regional_district_names": regional_district_names,
            "regional_district_mapping": regional_district_mapping,
            "station_type_name": station_type_names,
            "station_type_list": station_type_list,
            "tes_type_names": tes_type_names,
            "tes_type_list": tes_type_list,
            "fuel_type_names": fuel_type_names,
            "fuel_type_list": fuel_type_list,
            "tes_machine_type_list": tes_machine_type_list,
            "tes_machine_type_names": tes_machine_type_names,
            "pgu_tes_machine_type_names": pgu_tes_machine_type_names,
            "pgu_tes_machine_type_list": pgu_tes_machine_type_list,
            "condition_type_filter": filters.get("condition_type_filter"),
            "gen_company_filter": filters.get("gen_company_filter"),
            "station_name_filter": filters.get("station_name_filter"),
            "station_type_filter": filters.get("station_type_filter"),
            "tes_type_filter": filters.get("tes_type_filter"),
            "tes_machine_type_filter": filters.get("tes_machine_type_filter"),
            "pgu_tes_machine_type_filter": filters.get("pgu_tes_machine_type_filter"),
            "energy_system_type_filter": filters.get("energy_system_type_filter"),
            "union_energy_system_filter": filters.get("union_energy_system_filter"),
            "regional_energy_system_filter": filters.get("regional_energy_system_filter"),
            "federal_district_filter": filters.get("federal_district_filter"),
            "regional_district_filter": filters.get("regional_district_filter"),
            "station_fuel_type_filter": filters.get("station_fuel_type_filter"),
            "year_features": year_features,
            "machine_tes_types_map": machine_tes_types_map,
            "energy_unit_names": energy_unit_names,
            "sorted_energy_system_type_ids": sorted_energy_system_type_ids,
    }
    
    # Проверяем, есть ли агрегированные данные в data (для режима с суммами или show_all)
    has_aggregations = any([
        data.get('aggregate_power_by_energy_units'),
        data.get('aggregate_power_by_regional_districts'),
        data.get('aggregate_power_by_regional_energy_systems'),
        data.get('aggregate_power_by_union_energy_systems'),
        data.get('aggregate_power_by_energy_system_types'),
        data.get('aggregate_power_by_total_energy_system_types'),
    ])
    
    if has_aggregations:
        # Генерация агрегатов по уровням (когда включено отображение сумм)
        energy_unit_aggregates = build_energy_unit_aggregates(data)
        regional_district_aggregates = build_regional_district_aggregates(data)
        regional_energy_system_aggregates = build_regional_energy_system_aggregates(data)
        union_energy_system_aggregates = build_union_energy_system_aggregates(data)
        energy_system_type_aggregates = build_energy_system_type_aggregates(data)
        total_energy_system_type_aggregates = build_total_energy_system_type_aggregates(data)

        # Включаем агрегаты по уровням в context
        context.update(energy_unit_aggregates)
        context.update(regional_district_aggregates)
        context.update(regional_energy_system_aggregates)
        context.update(union_energy_system_aggregates)
        context.update(energy_system_type_aggregates)
        context.update(total_energy_system_type_aggregates)

    print(f"[TIME] get_station_list_template_context заняла: {time.time() - start_time:.2f} сек")
    return context


def extract_station_data_from_form(form):
    from collections import defaultdict
    station_data = []
    regional_districts_mapping = defaultdict(list)

    for system_id in form.getlist("station_ids[]"):
        selected_districts = form.getlist(f"regional_districts_{system_id}[]")
        regional_districts_mapping[int(system_id)] = [int(d) for d in selected_districts if d.isdigit()]

    for station_id, station_name, union_energy_system_id in zip(
        form.getlist("station_ids[]"),
        form.getlist("station_names[]"),
        form.getlist("union_energy_system_ids[]")
    ):
        station_data.append({
            "id": int(station_id),
            "name": station_name.strip(),
            "union_energy_system_id": int(union_energy_system_id) if union_energy_system_id else None,
            "regional_districts": regional_districts_mapping.get(int(station_id), [])
        })

    return station_data


def get_current_machine_tes_types_map():
    current_year = get_current_year()

    machine_tes_types = (
        db.session.query(MachineTesType)
        .options(joinedload(MachineTesType.tes_type))
        .filter(MachineTesType.year_number == current_year)
        .all()
    )

    return {mtt.id_machine: mtt for mtt in machine_tes_types}


def load_station_power_by_year(station, start_year=None, end_year=None, rounding_digits=None):
    result = {}

    for year in range(start_year, end_year + 1):
        p_ust = Decimal(0)
        p_ogr = Decimal(0)
        p_rasp = Decimal(0)

        for machine in station.machines:
            for mp in machine.machine_powers:
                if mp.year_number == year:
                    p_ust += Decimal(mp.p_ust or 0)
                    p_ogr += Decimal(mp.p_ogr or 0)
                    p_rasp += Decimal(mp.p_rasp or 0)

        result[year] = {
            "p_ust": p_ust if p_ust else None,
            "p_ogr": p_ogr if p_ogr else None,
            "p_rasp": p_rasp if p_rasp else None
        }

    return result


def recalculate_station_powers_by_filtered_machines(stations, start_year, end_year, rounding_digits):
    for station in stations:
        powers_by_year = defaultdict(lambda: {"p_ust": Decimal(0), "p_ogr": Decimal(0), "p_rasp": Decimal(0)})

        for machine in station.machines:
            for mp in machine.machine_powers:
                if start_year <= mp.year_number <= end_year:
                    year = mp.year_number
                    if mp.p_ust is not None:
                        powers_by_year[year]["p_ust"] += Decimal(mp.p_ust)
                    if mp.p_ogr is not None:
                        powers_by_year[year]["p_ogr"] += Decimal(mp.p_ogr)
                    if mp.p_rasp is not None:
                        powers_by_year[year]["p_rasp"] += Decimal(mp.p_rasp)

        # Округляем
        for year_data in powers_by_year.values():
            for k in year_data:
                year_data[k] = year_data[k]

        station.powers_by_year = powers_by_year


def assign_machine_powers_by_year(machine, start_year, end_year, rounding_digits):
    machine.powers_by_year = {}
    for mp in machine.machine_powers:
        if not (start_year <= mp.year_number <= end_year):
            continue
        machine.powers_by_year.setdefault(mp.year_number, {})
        machine.powers_by_year[mp.year_number]["p_ust"] = mp.p_ust
        machine.powers_by_year[mp.year_number]["p_ogr"] = mp.p_ogr
        machine.powers_by_year[mp.year_number]["p_rasp"] = mp.p_rasp

        # Предрасчет справочника топлива по годам для шаблона
        machine.fuel_type_by_year = {
            mf.year_number: (mf.fuel.fuel_type.name if mf.fuel and mf.fuel.fuel_type else None)
            for mf in machine.machine_fuels
        }


@no_autoflush
def recalculate_station_power(station, start_year, end_year):
    """Оптимизированный пересчет мощностей станции."""
    power_by_year = {
        year: {"p_ust": Decimal("0"), "p_ogr": Decimal("0"), "p_rasp": Decimal("0")}
        for year in range(start_year, end_year + 1)
    }

    # Оптимизация: используем предзагруженные данные
    for machine in station.machines:
        for mp in machine.machine_powers:
            # Проверяем, что year загружен
            if hasattr(mp, 'year') and mp.year:
                year = mp.year.number
            else:
                # Fallback для случаев, когда year не загружен
                continue
                
            if start_year <= year <= end_year:
                power_by_year[year]["p_ust"] += Decimal(str(mp.p_ust or "0"))
                power_by_year[year]["p_ogr"] += Decimal(str(mp.p_ogr or "0"))
                power_by_year[year]["p_rasp"] += Decimal(str(mp.p_rasp or "0"))

    # Оптимизация: загружаем существующие мощности одним запросом
    existing_spowers = {
        sp.year_number: sp
        for sp in StationPower.query.filter_by(id_station=station.id)
        .filter(StationPower.year_number.in_(range(start_year, end_year + 1)))
        .all()
    }

    # Оптимизация: собираем изменения и коммитим одним запросом
    powers_to_update = []
    powers_to_create = []
    
    for year, values in power_by_year.items():
        if year in existing_spowers:
            sp = existing_spowers[year]
            # Проверяем, изменились ли значения
            if (sp.p_ust != values["p_ust"] or 
                sp.p_ogr != values["p_ogr"] or 
                sp.p_rasp != values["p_rasp"]):
                sp.p_ust = values["p_ust"]
                sp.p_ogr = values["p_ogr"]
                sp.p_rasp = values["p_rasp"]
                powers_to_update.append(sp)
        else:
            sp = StationPower(
                id_station=station.id,
                year_number=year,
                p_ust=values["p_ust"],
                p_ogr=values["p_ogr"],
                p_rasp=values["p_rasp"],
            )
            powers_to_create.append(sp)

    # Коммитим только если есть изменения
    if powers_to_update or powers_to_create:
        if powers_to_create:
            # Перед вставкой убеждаемся, что последовательность PK синхронизирована (для PostgreSQL)
            try:
                seq_name = f"{SCHEMA_GENERATION}.station_powers_id_seq"
                db.session.execute(
                    text(
                        "SELECT setval(:seq, COALESCE((SELECT MAX(id) FROM "
                        f"{SCHEMA_GENERATION}.station_powers), 0))"
                    ),
                    {"seq": seq_name},
                )
            except Exception:
                # Если БД не PostgreSQL или нет последовательности — тихо пропускаем
                pass
        db.session.add_all(powers_to_create)
        _commit_with_retry()
        clear_aggregation_cache()  # Очищаем кэш после изменения мощностей


def build_energy_unit_aggregates(data):

    return {
        # Основная агрегация
        "energy_units_yearly_p_ust": data["aggregate_power_by_energy_units"]["aggregated"]["p_ust"],
        "energy_units_yearly_p_ogr": data["aggregate_power_by_energy_units"]["aggregated"]["p_ogr"],
        "energy_units_yearly_p_rasp": data["aggregate_power_by_energy_units"]["aggregated"]["p_rasp"],

        # По типам станций
        "energy_units_by_station_types_yearly_p_ust": data["aggregate_energy_units_by_station_types"]["aggregated"]["p_ust"],
        "energy_units_by_station_types_yearly_p_ogr": data["aggregate_energy_units_by_station_types"]["aggregated"]["p_ogr"],
        "energy_units_by_station_types_yearly_p_rasp": data["aggregate_energy_units_by_station_types"]["aggregated"]["p_rasp"],

        # По типам станций и топливу
        "energy_units_by_station_types_with_fuel_yearly_p_ust": data["aggregate_energy_units_by_station_type_with_fuel"]["aggregated"]["p_ust"],
        "energy_units_by_station_types_with_fuel_yearly_p_ogr": data["aggregate_energy_units_by_station_type_with_fuel"]["aggregated"]["p_ogr"],
        "energy_units_by_station_types_with_fuel_yearly_p_rasp": data["aggregate_energy_units_by_station_type_with_fuel"]["aggregated"]["p_rasp"],

        # По типам ТЭС
        "energy_units_by_tes_types_yearly_p_ust": data["aggregate_energy_units_by_tes_types"]["aggregated"]["p_ust"],
        "energy_units_by_tes_types_yearly_p_ogr": data["aggregate_energy_units_by_tes_types"]["aggregated"]["p_ogr"],
        "energy_units_by_tes_types_yearly_p_rasp": data["aggregate_energy_units_by_tes_types"]["aggregated"]["p_rasp"],

        # По типам ТЭС и топливу
        "energy_units_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_energy_units_by_tes_types_with_fuel"]["aggregated"]["p_ust"],
        "energy_units_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_energy_units_by_tes_types_with_fuel"]["aggregated"]["p_ogr"],
        "energy_units_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_energy_units_by_tes_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС
        "energy_units_by_tes_machine_types_yearly_p_ust": data["aggregate_energy_units_by_tes_machine_types"]["aggregated"]["p_ust"],
        "energy_units_by_tes_machine_types_yearly_p_ogr": data["aggregate_energy_units_by_tes_machine_types"]["aggregated"]["p_ogr"],
        "energy_units_by_tes_machine_types_yearly_p_rasp": data["aggregate_energy_units_by_tes_machine_types"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС и топливу
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_energy_units_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_ogr": data["aggregate_energy_units_by_tes_machine_types_with_fuel"]["aggregated"]["p_ogr"],
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_rasp": data["aggregate_energy_units_by_tes_machine_types_with_fuel"]["aggregated"]["p_rasp"],
    }


def build_regional_district_aggregates(data):

    return {
        # Основная агрегация
        "regional_districts_yearly_p_ust": data["aggregate_power_by_regional_districts"]["aggregated"]["p_ust"],
        "regional_districts_yearly_p_ogr": data["aggregate_power_by_regional_districts"]["aggregated"]["p_ogr"],
        "regional_districts_yearly_p_rasp": data["aggregate_power_by_regional_districts"]["aggregated"]["p_rasp"],

        # По типам станций
        "regional_districts_by_station_types_yearly_p_ust": data["aggregate_regional_districts_by_station_types"]["aggregated"]["p_ust"],
        "regional_districts_by_station_types_yearly_p_ogr": data["aggregate_regional_districts_by_station_types"]["aggregated"]["p_ogr"],
        "regional_districts_by_station_types_yearly_p_rasp": data["aggregate_regional_districts_by_station_types"]["aggregated"]["p_rasp"],

        # По типам станций и топливу
        "regional_districts_by_station_types_with_fuel_yearly_p_ust": data["aggregate_regional_districts_by_station_types_with_fuel"]["aggregated"]["p_ust"],
        "regional_districts_by_station_types_with_fuel_yearly_p_ogr": data["aggregate_regional_districts_by_station_types_with_fuel"]["aggregated"]["p_ogr"],
        "regional_districts_by_station_types_with_fuel_yearly_p_rasp": data["aggregate_regional_districts_by_station_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам ТЭС
        "regional_districts_by_tes_types_yearly_p_ust": data["aggregate_regional_districts_by_tes_types"]["aggregated"]["p_ust"],
        "regional_districts_by_tes_types_yearly_p_ogr": data["aggregate_regional_districts_by_tes_types"]["aggregated"]["p_ogr"],
        "regional_districts_by_tes_types_yearly_p_rasp": data["aggregate_regional_districts_by_tes_types"]["aggregated"]["p_rasp"],

        # По типам ТЭС и топливу
        "regional_districts_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_regional_districts_by_tes_types_with_fuel"]["aggregated"]["p_ust"],
        "regional_districts_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_regional_districts_by_tes_types_with_fuel"]["aggregated"]["p_ogr"],
        "regional_districts_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_regional_districts_by_tes_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС
        "regional_districts_by_tes_machine_types_yearly_p_ust": data["aggregate_regional_districts_by_tes_machine_types"]["aggregated"]["p_ust"],
        "regional_districts_by_tes_machine_types_yearly_p_ogr": data["aggregate_regional_districts_by_tes_machine_types"]["aggregated"]["p_ogr"],
        "regional_districts_by_tes_machine_types_yearly_p_rasp": data["aggregate_regional_districts_by_tes_machine_types"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС и топливу
        "regional_districts_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_regional_districts_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
        "regional_districts_by_tes_machine_types_with_fuel_yearly_p_ogr": data["aggregate_regional_districts_by_tes_machine_types_with_fuel"]["aggregated"]["p_ogr"],
        "regional_districts_by_tes_machine_types_with_fuel_yearly_p_rasp": data["aggregate_regional_districts_by_tes_machine_types_with_fuel"]["aggregated"]["p_rasp"],
    }


def build_regional_energy_system_aggregates(data):

    return {
        # Основная агрегация
        "regional_energy_systems_yearly_p_ust": data["aggregate_power_by_regional_energy_systems"]["aggregated"]["p_ust"],
        "regional_energy_systems_yearly_p_ogr": data["aggregate_power_by_regional_energy_systems"]["aggregated"]["p_ogr"],
        "regional_energy_systems_yearly_p_rasp": data["aggregate_power_by_regional_energy_systems"]["aggregated"]["p_rasp"],

        # По типам станций
        "regional_energy_systems_by_station_types_yearly_p_ust": data["aggregate_regional_energy_systems_by_station_types"]["aggregated"]["p_ust"],
        "regional_energy_systems_by_station_types_yearly_p_ogr": data["aggregate_regional_energy_systems_by_station_types"]["aggregated"]["p_ogr"],
        "regional_energy_systems_by_station_types_yearly_p_rasp": data["aggregate_regional_energy_systems_by_station_types"]["aggregated"]["p_rasp"],

        # По типам станций и топливу
        "regional_energy_systems_by_station_types_with_fuel_yearly_p_ust": data["aggregate_regional_energy_systems_by_station_types_with_fuel"]["aggregated"]["p_ust"],
        "regional_energy_systems_by_station_types_with_fuel_yearly_p_ogr": data["aggregate_regional_energy_systems_by_station_types_with_fuel"]["aggregated"]["p_ogr"],
        "regional_energy_systems_by_station_types_with_fuel_yearly_p_rasp": data["aggregate_regional_energy_systems_by_station_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам ТЭС
        "regional_energy_systems_by_tes_types_yearly_p_ust": data["aggregate_regional_energy_systems_by_tes_types"]["aggregated"]["p_ust"],
        "regional_energy_systems_by_tes_types_yearly_p_ogr": data["aggregate_regional_energy_systems_by_tes_types"]["aggregated"]["p_ogr"],
        "regional_energy_systems_by_tes_types_yearly_p_rasp": data["aggregate_regional_energy_systems_by_tes_types"]["aggregated"]["p_rasp"],

        # По типам ТЭС и топливу
        "regional_energy_systems_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_regional_energy_systems_by_tes_types_with_fuel"]["aggregated"]["p_ust"],
        "regional_energy_systems_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_regional_energy_systems_by_tes_types_with_fuel"]["aggregated"]["p_ogr"],
        "regional_energy_systems_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_regional_energy_systems_by_tes_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС
        "regional_energy_systems_by_tes_machine_types_yearly_p_ust": data["aggregate_regional_energy_systems_by_tes_machine_types"]["aggregated"]["p_ust"],
        "regional_energy_systems_by_tes_machine_types_yearly_p_ogr": data["aggregate_regional_energy_systems_by_tes_machine_types"]["aggregated"]["p_ogr"],
        "regional_energy_systems_by_tes_machine_types_yearly_p_rasp": data["aggregate_regional_energy_systems_by_tes_machine_types"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС и топливу
        "regional_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_regional_energy_systems_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
        "regional_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ogr": data["aggregate_regional_energy_systems_by_tes_machine_types_with_fuel"]["aggregated"]["p_ogr"],
        "regional_energy_systems_by_tes_machine_types_with_fuel_yearly_p_rasp": data["aggregate_regional_energy_systems_by_tes_machine_types_with_fuel"]["aggregated"]["p_rasp"],
    }


def build_union_energy_system_aggregates(data):

    return {
        # Основная агрегация
        "union_energy_systems_yearly_p_ust": data["aggregate_power_by_union_energy_systems"]["aggregated"]["p_ust"],
        "union_energy_systems_yearly_p_ogr": data["aggregate_power_by_union_energy_systems"]["aggregated"]["p_ogr"],
        "union_energy_systems_yearly_p_rasp": data["aggregate_power_by_union_energy_systems"]["aggregated"]["p_rasp"],

        # По типам станций
        "union_energy_systems_by_station_types_yearly_p_ust": data["aggregate_union_energy_systems_by_station_types"]["aggregated"]["p_ust"],
        "union_energy_systems_by_station_types_yearly_p_ogr": data["aggregate_union_energy_systems_by_station_types"]["aggregated"]["p_ogr"],
        "union_energy_systems_by_station_types_yearly_p_rasp": data["aggregate_union_energy_systems_by_station_types"]["aggregated"]["p_rasp"],

        # По типам станций и топливу
        "union_energy_systems_by_station_types_with_fuel_yearly_p_ust": data["aggregate_union_energy_systems_by_station_types_with_fuel"]["aggregated"]["p_ust"],
        "union_energy_systems_by_station_types_with_fuel_yearly_p_ogr": data["aggregate_union_energy_systems_by_station_types_with_fuel"]["aggregated"]["p_ogr"],
        "union_energy_systems_by_station_types_with_fuel_yearly_p_rasp": data["aggregate_union_energy_systems_by_station_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам ТЭС
        "union_energy_systems_by_tes_types_yearly_p_ust": data["aggregate_union_energy_systems_by_tes_types"]["aggregated"]["p_ust"],
        "union_energy_systems_by_tes_types_yearly_p_ogr": data["aggregate_union_energy_systems_by_tes_types"]["aggregated"]["p_ogr"],
        "union_energy_systems_by_tes_types_yearly_p_rasp": data["aggregate_union_energy_systems_by_tes_types"]["aggregated"]["p_rasp"],

        # По типам ТЭС и топливу
        "union_energy_systems_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_union_energy_systems_by_tes_types_with_fuel"]["aggregated"]["p_ust"],
        "union_energy_systems_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_union_energy_systems_by_tes_types_with_fuel"]["aggregated"]["p_ogr"],
        "union_energy_systems_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_union_energy_systems_by_tes_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС
        "union_energy_systems_by_tes_machine_types_yearly_p_ust": data["aggregate_union_energy_systems_by_tes_machine_types"]["aggregated"]["p_ust"],
        "union_energy_systems_by_tes_machine_types_yearly_p_ogr": data["aggregate_union_energy_systems_by_tes_machine_types"]["aggregated"]["p_ogr"],
        "union_energy_systems_by_tes_machine_types_yearly_p_rasp": data["aggregate_union_energy_systems_by_tes_machine_types"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС и топливу
        "union_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_union_energy_systems_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
        "union_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ogr": data["aggregate_union_energy_systems_by_tes_machine_types_with_fuel"]["aggregated"]["p_ogr"],
        "union_energy_systems_by_tes_machine_types_with_fuel_yearly_p_rasp": data["aggregate_union_energy_systems_by_tes_machine_types_with_fuel"]["aggregated"]["p_rasp"],
    }


def build_energy_system_type_aggregates(data):

    return {
        # Основная агрегация
        "energy_system_types_yearly_p_ust": data["aggregate_power_by_energy_system_types"]["aggregated"]["p_ust"],
        "energy_system_types_yearly_p_ogr": data["aggregate_power_by_energy_system_types"]["aggregated"]["p_ogr"],
        "energy_system_types_yearly_p_rasp": data["aggregate_power_by_energy_system_types"]["aggregated"]["p_rasp"],

        # По типам станций
        "energy_system_types_by_station_types_yearly_p_ust": data["aggregate_energy_system_types_by_station_types"]["aggregated"]["p_ust"],
        "energy_system_types_by_station_types_yearly_p_ogr": data["aggregate_energy_system_types_by_station_types"]["aggregated"]["p_ogr"],
        "energy_system_types_by_station_types_yearly_p_rasp": data["aggregate_energy_system_types_by_station_types"]["aggregated"]["p_rasp"],

        # По типам станций и топливу
        "energy_system_types_by_station_types_with_fuel_yearly_p_ust": data["aggregate_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_ust"],
        "energy_system_types_by_station_types_with_fuel_yearly_p_ogr": data["aggregate_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_ogr"],
        "energy_system_types_by_station_types_with_fuel_yearly_p_rasp": data["aggregate_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам ТЭС
        "energy_system_types_by_tes_types_yearly_p_ust": data["aggregate_energy_system_types_by_tes_types"]["aggregated"]["p_ust"],
        "energy_system_types_by_tes_types_yearly_p_ogr": data["aggregate_energy_system_types_by_tes_types"]["aggregated"]["p_ogr"],
        "energy_system_types_by_tes_types_yearly_p_rasp": data["aggregate_energy_system_types_by_tes_types"]["aggregated"]["p_rasp"],

        # По типам ТЭС и топливу
        "energy_system_types_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_ust"],
        "energy_system_types_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_ogr"],
        "energy_system_types_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС
        "energy_system_types_by_tes_machine_types_yearly_p_ust": data["aggregate_energy_system_types_by_tes_machine_types"]["aggregated"]["p_ust"],
        "energy_system_types_by_tes_machine_types_yearly_p_ogr": data["aggregate_energy_system_types_by_tes_machine_types"]["aggregated"]["p_ogr"],
        "energy_system_types_by_tes_machine_types_yearly_p_rasp": data["aggregate_energy_system_types_by_tes_machine_types"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС и топливу
        "energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
        "energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ogr": data["aggregate_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_ogr"],
        "energy_system_types_by_tes_machine_types_with_fuel_yearly_p_rasp": data["aggregate_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_rasp"],
    }


def build_total_energy_system_type_aggregates(data):

    return {
        # Итоги по России (общие итоги - это уже aggregate_power_by_total_energy_system_types)
        "total_yearly_p_ust": data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_ust"],
        "total_yearly_p_ogr": data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_ogr"],
        "total_yearly_p_rasp": data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_rasp"],

        # По типам станций
        "total_energy_system_types_by_station_types_yearly_p_ust": data["aggregate_total_energy_system_types_by_station_types"]["aggregated"]["p_ust"],
        "total_energy_system_types_by_station_types_yearly_p_ogr": data["aggregate_total_energy_system_types_by_station_types"]["aggregated"]["p_ogr"],
        "total_energy_system_types_by_station_types_yearly_p_rasp": data["aggregate_total_energy_system_types_by_station_types"]["aggregated"]["p_rasp"],

        # По типам станций и топливу
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_ust": data["aggregate_total_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_ust"],
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_ogr": data["aggregate_total_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_ogr"],
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_rasp": data["aggregate_total_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам ТЭС
        "total_energy_system_types_by_tes_types_yearly_p_ust": data["aggregate_total_energy_system_types_by_tes_types"]["aggregated"]["p_ust"],
        "total_energy_system_types_by_tes_types_yearly_p_ogr": data["aggregate_total_energy_system_types_by_tes_types"]["aggregated"]["p_ogr"],
        "total_energy_system_types_by_tes_types_yearly_p_rasp": data["aggregate_total_energy_system_types_by_tes_types"]["aggregated"]["p_rasp"],

        # По типам ТЭС и топливу
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_total_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_ust"],
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_total_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_ogr"],
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_total_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС
        "total_energy_system_types_by_tes_machine_types_yearly_p_ust": data["aggregate_total_energy_system_types_by_tes_machine_types"]["aggregated"]["p_ust"],
        "total_energy_system_types_by_tes_machine_types_yearly_p_ogr": data["aggregate_total_energy_system_types_by_tes_machine_types"]["aggregated"]["p_ogr"],
        "total_energy_system_types_by_tes_machine_types_yearly_p_rasp": data["aggregate_total_energy_system_types_by_tes_machine_types"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС и топливу
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_total_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ogr": data["aggregate_total_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_ogr"],
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_rasp": data["aggregate_total_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_rasp"],
    }


# -------------------------------
# Мутации по станциям/агрегатам
# -------------------------------

def add_station_service(user, name: str, id_regional_district: int) -> Station:
    name = (name or "").strip()
    if not name:
        raise ValueError("Не указано название станции")
    try:
        station = Station(name=name, id_regional_district=id_regional_district)
        db.session.add(station)
        _commit_with_retry()
        clear_aggregation_cache()  # Очищаем кэш после добавления станции
        rd = db.session.query(RegionalDistrict).get(id_regional_district)
        rd_name = rd.name if rd else "не указано"
        log_to_db(user, f"Создана новая станция: {station.name}", entity_type="station", entity_id=station.id, details=f"Субъект РФ: {rd_name}")
        return station
    except Exception:
        db.session.rollback()
        raise


def update_station_from_form_service(user, station: Station, form, regional_district_list) -> list:
    changes = []
    try:
        # Название
        if station.name != form.name.data:
            changes.append(f"Название: {station.name} → {form.name.data}")
            station.name = form.name.data

        # Состояние
        new_condition_type_id = int(form.id_condition_type.data)
        new_condition_type = db.session.query(ConditionType).filter_by(id=new_condition_type_id).first()
        if new_condition_type:
            old_value = station.condition_type.name if station.condition_type else "не указано"
            new_value = new_condition_type.name
            if old_value != new_value:
                changes.append(f"Состояние: {old_value} → {new_value}")
            station.id_condition_type = new_condition_type.id

        # Группа станции
        new_group_id = form.id_station_group.data
        if new_group_id:
            group_exists = db.session.query(StationGroup).filter_by(id=new_group_id).first()
            if group_exists and station.id_group != new_group_id:
                old_group = station.group.name if station.group else "не указано"
                new_group = group_exists.name
                changes.append(f"Группа: {old_group} → {new_group}")
                station.id_group = new_group_id

        # Примечание
        old_note = station.note.strip() if station.note and station.note.strip() else None
        new_note = form.note.data.strip() if form.note.data and form.note.data.strip() else None
        if old_note != new_note:
            changes.append(f"Примечание: {station.note} → {new_note}")
            station.note = new_note

        # Субъект РФ
        if station.id_regional_district != form.id_regional_district.data:
            old_value = station.regional_district.name if station.regional_district else "не указано"
            new_value = next((d[1] if isinstance(d, tuple) else d["name"] for d in regional_district_list if (d[0] if isinstance(d, tuple) else d["id"]) == form.id_regional_district.data), "не указано")
            changes.append(f"Субъект РФ: {old_value} → {new_value}")
            station.id_regional_district = form.id_regional_district.data

            # Обновление связанных энергосистем для нового субъекта
            new_regional_district_obj = (
                db.session.query(RegionalDistrict)
                .options(
                    joinedload(RegionalDistrict.federal_district),
                    joinedload(RegionalDistrict.regional_energy_systems)
                        .joinedload(UnionEnergySystem.energy_system_type)
                )
                .filter_by(id=form.id_regional_district.data)
                .first()
            )
            if new_regional_district_obj:
                old_federal_district = station.regional_district.federal_district.name if station.regional_district and station.regional_district.federal_district else "не указано"
                new_federal_district = new_regional_district_obj.federal_district.name if new_regional_district_obj.federal_district else "не указано"
                if old_federal_district != new_federal_district:
                    changes.append(f"Федеральный округ: {old_federal_district} → {new_federal_district}")

                old_energy_systems = station.regional_district.regional_energy_systems if station.regional_district else []
                new_energy_systems = new_regional_district_obj.regional_energy_systems
                if old_energy_systems != new_energy_systems:
                    old_res_name = old_energy_systems[0].name if old_energy_systems else "не указано"
                    new_res_name = new_energy_systems[0].name if new_energy_systems else "не указано"
                    if old_res_name != new_res_name:
                        changes.append(f"Региональная энергосистема: {old_res_name} → {new_res_name}")

                    old_ues_name = (
                        old_energy_systems[0].union_energy_system.name 
                        if old_energy_systems and old_energy_systems[0].union_energy_system 
                        else "не указано"
                    )
                    new_ues_name = (
                        new_energy_systems[0].union_energy_system.name 
                        if new_energy_systems and new_energy_systems[0].union_energy_system 
                        else "не указано"
                    )
                    if old_ues_name != new_ues_name:
                        changes.append(f"ОЭС: {old_ues_name} → {new_ues_name}")

                    old_est_name = (
                        old_energy_systems[0].union_energy_system.energy_system_type.name 
                        if old_energy_systems and old_energy_systems[0].union_energy_system and old_energy_systems[0].union_energy_system.energy_system_type 
                        else "не указано"
                    )
                    new_est_name = (
                        new_energy_systems[0].union_energy_system.energy_system_type.name 
                        if new_energy_systems and new_energy_systems[0].union_energy_system and new_energy_systems[0].union_energy_system.energy_system_type 
                        else "не указано"
                    )
                    if old_est_name != new_est_name:
                        changes.append(f"Часть энергосистемы России: {old_est_name} → {new_est_name}")

                station.regional_district = new_regional_district_obj

        # Местоположение
        new_location = form.location.data.strip() if form.location.data.strip() else None
        if station.location != new_location:
            changes.append(f"Местоположение: {station.location} → {new_location}")
            station.location = new_location

        _commit_with_retry()
        clear_aggregation_cache()  # Очищаем кэш после обновления станции

        if changes:
            rd_name = station.regional_district.name if station.regional_district else "не указано"
            log_to_db(user, f"Изменения в электростанции {station.name} ({rd_name})", details="; ".join(changes), entity_type="station", entity_id=station.id)

        return changes
    except Exception:
        db.session.rollback()
        raise


def delete_machines_service(user, station: Station, machine_ids_to_delete: list) -> list:
    if not machine_ids_to_delete:
        return []
    changes = []
    try:
        machines_to_delete = Machine.query.filter(Machine.id.in_(machine_ids_to_delete)).all()
        affected_station_ids = set()
        for machine in machines_to_delete:
            affected_station_ids.add(machine.id_station)
            for mp in machine.machine_powers:
                db.session.delete(mp)
            for mf in machine.machine_fuels:
                db.session.delete(mf)
            for mtt in machine.machine_tes_types:
                db.session.delete(mtt)
            changes.append(f"Агрегат {machine.machine_number or '—'} и связанные данные удалены")
            db.session.delete(machine)

        for station_id in affected_station_ids:
            remaining_machines = Machine.query.filter_by(id_station=station_id).count()
            if remaining_machines == 0:
                powers_to_delete = StationPower.query.filter_by(id_station=station_id).all()
                for sp in powers_to_delete:
                    db.session.delete(sp)
                changes.append(f"Мощности станции ID={station_id} удалены, так как все агрегаты были удалены")

        _commit_with_retry()
        clear_aggregation_cache()  # Очищаем кэш после удаления агрегатов

        if changes:
            log_to_db(user, f"Агрегаты удалены на станции {station.name}", details="; ".join(changes), entity_type="station", entity_id=station.id)

        return changes
    except Exception:
        db.session.rollback()
        raise


def update_machines_from_form_service(user, station: Station, form_machines, form_data) -> list:
    changes = []
    try:
        if not form_machines.validate():
            return changes

        for machine in station.machines:
            fuel_so_key = f"fuel_so_{machine.id}"
            gen_company_key = f"id_gen_company_{machine.id}"
            new_note_key = f"note_{machine.id}"

            new_fuel_so = (form_data.get(fuel_so_key, "") or "").strip()
            new_gen_company_id = form_data.get(gen_company_key, type=int) if hasattr(form_data, 'get') else None
            if new_gen_company_id is None:
                try:
                    new_gen_company_id = int(form_data.get(gen_company_key)) if gen_company_key in form_data else None
                except Exception:
                    new_gen_company_id = None
            new_note = (form_data.get(new_note_key, "") or "").strip()

            if machine.fuel_so != new_fuel_so:
                changes.append(f"Агрегат {machine.machine_number}: Топливо {machine.fuel_so} → {new_fuel_so}")
                machine.fuel_so = new_fuel_so

            if machine.note != new_note:
                changes.append(f"Агрегат {machine.machine_number}: Примечание {machine.note} → {new_note}")
                machine.note = new_note

            if new_gen_company_id:
                new_gen_company = db.session.query(GenCompany).filter_by(id=new_gen_company_id).first()
                if new_gen_company:
                    old_gen_company_name = machine.gen_company.name if machine.gen_company else "не указано"
                    if machine.gen_company is None or machine.gen_company.id != new_gen_company_id:
                        changes.append(f"Агрегат {machine.machine_number}: Собственник {old_gen_company_name} → {new_gen_company.name}")
                        machine.gen_company = new_gen_company

        _commit_with_retry()
        clear_aggregation_cache()  # Очищаем кэш после обновления агрегатов

        if changes:
            log_to_db(user, f"Обновлены агрегаты станции {station.name}", details="; ".join(changes), entity_type="station", entity_id=station.id)
        return changes
    except Exception:
        db.session.rollback()
        raise