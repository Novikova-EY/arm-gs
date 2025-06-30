from app import db
import pandas as pd
from datetime import datetime, date
from app.models.energy_systems_models import UnionEnergySystem, RegionalEnergySystem, EnergySystemType, EnergyArea
from app.models.territories_models import RegionalDistrict, FederalDistrict
from app.models.stations_models import Station, StationType, Machine, MachinePower, MachineFuel, MachineTesType, ConditionType, MachineType, TesType, TesMachineType, StationGroup, Machine
from app.models import Year, Fuel, GenCompany  
from sqlalchemy.orm import joinedload, contains_eager
from sqlalchemy import func
from decimal import Decimal
from app.services.reference_services.gen_company_services import clean_name
from app.services.station_services.help_services import convert_to_date
from collections import defaultdict
from app.services.logging_services.logging_service import log_to_db
from app.models import Machine, MachinePower, db
from sqlalchemy import and_, func
import pandas as pd

def get_machines_with_power_changes(station_id=None):
    """
    Получает всю выборку агрегатов по всем годам и отмечает изменения p_ust.
    """

    # Подзапрос: получаем предыдущие значения p_ust для каждого агрегата
    subquery = db.session.query(
        MachinePower.id_machine,
        MachinePower.year_number.label("prev_year"),
        MachinePower.p_ust.label("prev_p_ust")
    ).subquery()

    # Основной запрос: выбираем все агрегаты и их мощности по годам
    query = db.session.query(
        Machine.id,
        Machine.machine_name,
        Machine.id_station,
        MachinePower.year_number,
        MachinePower.p_ust,
        subquery.c.prev_p_ust.label("prev_p_ust"),
        (MachinePower.p_ust != subquery.c.prev_p_ust).label("is_changed")  # Флаг изменения мощности
    ).join(MachinePower, Machine.id == MachinePower.id_machine
    ).outerjoin(subquery, and_(
        MachinePower.id_machine == subquery.c.id_machine,
        MachinePower.year_number == subquery.c.prev_year + 1  # Берем мощность за предыдущий год
    )).order_by(Machine.id, MachinePower.year_number)

    # Фильтр по станции, если передан
    if station_id:
        query = query.filter(Machine.id_station == station_id)

    results = query.all()

    # Формируем JSON-ответ
    data = []
    for machine in results:
        data.append({
            "id": machine.id,
            "name": machine.machine_name,
            "station_id": machine.id_station,
            "year": machine.year_number,
            "p_ust": machine.p_ust,
            "prev_p_ust": machine.prev_p_ust,
            "is_changed": bool(machine.is_changed)  # Преобразуем SQLAlchemy-булево значение в Python
        })

    return data


def get_stations_list(
    page=None, 
    per_page=None,
    condition_type_filter=None, 
    gen_company_filter=None, 
    station_name_filter=None, 
    station_type_filter=None, 
    tes_type_filter=None, 
    tes_machine_type_filter=None, 
    energy_system_type_filter=None, 
    union_energy_system_filter=None, 
    regional_energy_system_filter=None, 
    federal_district_filter=None, 
    regional_district_filter=None, 
):
    """
    Получает список СТАНЦИЙ с учётом фильтров и корректной пагинацией.
    1) Фильтруем станции + машины (если нужно) -> subquery с уникальными ID станций
    2) Считаем total_count по этому subquery
    3) Выбираем объекты Station, у которых ID в subquery, применяя OFFSET/LIMIT
    """

    # 1) Получаем subquery с уникальными Station.id, учитывая все фильтры
    station_ids_subq = get_filtered_station_ids(
        condition_type_filter,
        gen_company_filter,
        station_name_filter,
        station_type_filter,
        tes_type_filter,
        tes_machine_type_filter,
        energy_system_type_filter,
        union_energy_system_filter,
        regional_energy_system_filter,
        federal_district_filter,
        regional_district_filter,
    )

    # Считаем общее число станций (уникальных ID) 
    total_count = db.session.query(func.count()).select_from(station_ids_subq).scalar()

    # Расчёт общего числа страниц
    if per_page is None:
        total_pages = 1
    else:
        total_pages = max(1, (total_count + per_page - 1) // per_page)

    station_query = db.session.query(Station).filter(
        Station.id.in_(db.session.query(station_ids_subq.c.id))
    )

    if per_page is None:
        stations = station_query.all()
    else:
        stations = (
            station_query
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

    grouped_data = group_stations_hierarchy(stations)

    return {
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "grouped_stations": grouped_data["grouped_stations"],  # Сохраняем иерархию
        "stations": grouped_data["stations"]  # ✅ Теперь это список!
    }


def get_filtered_station_ids(
    condition_type_filter=None,
    gen_company_filter=None,
    station_name_filter=None,
    station_type_filter=None,
    tes_type_filter=None,
    tes_machine_type_filter=None,
    energy_system_type_filter=None,
    union_energy_system_filter=None,
    regional_energy_system_filter=None,
    federal_district_filter=None,
    regional_district_filter=None,
):
    """
    Возвращает subquery с ОДНИМ столбцом: distinct(Station.id).
    Учитывает все фильтры, join на machines, если нужно, 
    но при этом не загружает лишних полей.
    """

    # 1) Начинаем с запроса Station, при необходимости join(Station.machines)
    query = db.session.query(Station.id).join(Station.machines)

    # 2) Применяем фильтры.
    if station_type_filter:
        query = query.filter(Machine.id_station_type.in_(station_type_filter))
    if tes_type_filter:
        query = query.filter(Machine.id_tes_type.in_(tes_type_filter))
    if tes_machine_type_filter:
        query = query.filter(Machine.id_tes_machine_type.in_(tes_machine_type_filter))
    # Фильтрация по названию генерирующей компании
    if gen_company_filter:
        gen_companies = GenCompany.query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%")).all()
        gen_company_ids = [company.id for company in gen_companies]
        
        query = query.join(Station.machines).filter(Machine.id_gen_company.in_(gen_company_ids))

    # Фильтрация по названию электростанции
    if station_name_filter:
        query = query.filter(Station.name.ilike(f"%{station_name_filter}%"))
    
    # Фильтрация по типу энергосистемы
    if energy_system_type_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.union_energy_system.has(
                        UnionEnergySystem.energy_system_type.has(
                            EnergySystemType.id.in_(energy_system_type_filter)
                        )
                    )
                )
            )
        )

    # Фильтрация по объединённой энергосистеме
    if union_energy_system_filter:
        if not isinstance(union_energy_system_filter, list):
            union_energy_system_filter = [union_energy_system_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id_union_energy_system.in_(union_energy_system_filter)
                )
            )
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        if not isinstance(regional_energy_system_filter, list):
            regional_energy_system_filter = [regional_energy_system_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id.in_(regional_energy_system_filter)
                )
            )
        )

    # Фильтрация по ФО
    if federal_district_filter:
        if not isinstance(federal_district_filter, list):
            federal_district_filter = [federal_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(
                    FederalDistrict.id.in_(federal_district_filter)  # Используем .in_()
                )
            )
        )

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        if not isinstance(regional_district_filter, list):
            regional_district_filter = [regional_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.id.in_(regional_district_filter)  # Используем .in_()
            )
        )

    # Фильтрация по состоянию электростанции
    if condition_type_filter:
        query = query.join(Station.machines).filter(Machine.id_condition_type == condition_type_filter)


    # 3) Делаем distinct(Station.id), чтобы каждая станция была 1 раз
    query = query.distinct(Station.id)

    # 4) Возвращаем подзапрос 
    return query.subquery()


def group_machines_by_group_and_fuel(stations):
    """Сначала группирует машины по fuel_so, затем по machine_group, рассчитывает rowspan независимо."""

    for station in stations:
        # Группировка машин по fuel_so (топливо сначала)
        fuel_groups = defaultdict(list)
        for machine in station.machines:
            fuel_groups[machine.fuel_so].append(machine)

        # Теперь внутри каждой группы fuel_so группируем по machine_group
        fuel_sorted_machines = []  # Список с машинами в новом порядке
        for fuel, fuel_machines in fuel_groups.items():
            # Применяем rowspan для fuel_so
            fuel_machines[0].fuel_rowspan = len(fuel_machines)
            for machine in fuel_machines[1:]:
                machine.fuel_rowspan = 0  # Остальные скрывают ячейку топлива

            # Группировка внутри fuel_so по machine_group
            group_groups = defaultdict(list)
            for machine in fuel_machines:
                group_groups[machine.machine_group].append(machine)

            # Применяем rowspan для machine_group внутри fuel_so
            for group, group_machines in group_groups.items():
                group_machines[0].group_rowspan = len(group_machines)
                for machine in group_machines[1:]:
                    machine.group_rowspan = 0  # Остальные скрывают ячейку группы

                # Добавляем в итоговый список
                fuel_sorted_machines.extend(group_machines)

        # Обновляем порядок машин в станции
        station.machines = fuel_sorted_machines

    return stations


def group_stations_hierarchy(stations):
    grouped_data = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list))))
    
    for station in stations:
        regional_district_id = station.regional_district.id
        regional_energy_systems = station.regional_district.regional_energy_systems

        for regional_energy_system in regional_energy_systems:
            regional_energy_system_id = regional_energy_system.id
            union_energy_system_id = regional_energy_system.id_union_energy_system
            energy_system_type_id = regional_energy_system.union_energy_system.id_energy_system_type

            grouped_data[energy_system_type_id][union_energy_system_id][regional_energy_system_id][regional_district_id].append(station)

    # Сортируем станции внутри субъектов
    for energy_system_type in grouped_data.values():
        for union_energy_system in energy_system_type.values():
            for regional_energy_system in union_energy_system.values():
                for regional_district in regional_energy_system.values():
                    regional_district.sort(key=lambda station: (station.machines[0].station_type.id, station.name))


    # Пагинация: формируем список всех станций
    all_stations = []
    for energy_system_type in grouped_data.values():
        for union_energy_system in energy_system_type.values():
            for regional_energy_system in union_energy_system.values():
                for regional_district in regional_energy_system.values():
                    all_stations.extend(regional_district)
    


    return {
        "grouped_stations": grouped_data,
        "stations": all_stations
    }


def get_filtered_stations(
    condition_type_filter=None,
    gen_company_filter=None,
    station_name_filter=None,
    station_type_filter=None,
    tes_type_filter=None,
    tes_machine_type_filter=None,
    energy_system_type_filter=None,
    union_energy_system_filter=None,
    regional_energy_system_filter=None,
    federal_district_filter=None,
    regional_district_filter=None,
    sort_by="id",
    sort_dir="asc"
):
    """Фильтрует станции по переданным параметрам"""

    query = db.session.query(Station).distinct().join(Station.machines)

    if station_type_filter:
        query = query.filter(Machine.id_station_type.in_(station_type_filter))

    if tes_type_filter:
        query = query.filter(Machine.id_tes_type.in_(tes_type_filter))

    if tes_machine_type_filter:
        query = query.filter(Machine.id_tes_machine_type.in_(tes_machine_type_filter))

    query = query.options(contains_eager(Station.machines))

    # Фильтрация по названию генерирующей компании
    if gen_company_filter:
        gen_companies = GenCompany.query.filter(GenCompany.name.ilike(f"%{gen_company_filter}%")).all()
        gen_company_ids = [company.id for company in gen_companies]
        
        query = query.join(Station.machines).filter(Machine.id_gen_company.in_(gen_company_ids))

    # Фильтрация по названию электростанции
    if station_name_filter:
        query = query.filter(Station.name.ilike(f"%{station_name_filter}%"))
    
    # Фильтрация по типу энергосистемы
    if energy_system_type_filter:
        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.union_energy_system.has(
                        UnionEnergySystem.energy_system_type.has(
                            EnergySystemType.id.in_(energy_system_type_filter)
                        )
                    )
                )
            )
        )

    # Фильтрация по объединённой энергосистеме
    if union_energy_system_filter:
        if not isinstance(union_energy_system_filter, list):
            union_energy_system_filter = [union_energy_system_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id_union_energy_system.in_(union_energy_system_filter)
                )
            )
        )

    # Фильтрация по региональной энергосистеме
    if regional_energy_system_filter:
        if not isinstance(regional_energy_system_filter, list):
            regional_energy_system_filter = [regional_energy_system_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.regional_energy_systems.any(
                    RegionalEnergySystem.id.in_(regional_energy_system_filter)
                )
            )
        )

    # Фильтрация по ФО
    if federal_district_filter:
        if not isinstance(federal_district_filter, list):
            federal_district_filter = [federal_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(
                    FederalDistrict.id.in_(federal_district_filter)  # Используем .in_()
                )
            )
        )

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        if not isinstance(regional_district_filter, list):
            regional_district_filter = [regional_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.id.in_(regional_district_filter)  # Используем .in_()
            )
        )

    # Фильтрация по состоянию электростанции
    if condition_type_filter:
        query = query.join(Station.machines).filter(Machine.id_condition_type == condition_type_filter)

    return query


def get_station_by_id(station_id):
    station = (
        db.session.query(Station)
        .filter_by(id=station_id)
        .join(Station.machines)
        .first()
    )
    
    return station


def get_machine_by_id(machine_id):
    machine = (
        db.session.query(Machine)
        .filter_by(id=machine_id)
        .first()
    )
    
    return machine


def get_station_types_list(station):
    if not hasattr(station, "machines") or not station.machines:
        return None  # Убедимся, что у station есть атрибут "machines"

    station_type = next((machine.station_type for machine in station.machines if hasattr(machine, "station_type") and machine.station_type), None)
    
    return station_type


def get_gen_companies():
    """Получает список генкомпаний'."""
    return GenCompany.query.order_by(GenCompany.id).all()

def get_gen_companies_list(station):
    if not station or not station.machines:
        return None

    gen_companies = {machine.gen_company.name for machine in station.machines if machine.gen_company}
    return ", ".join(gen_companies) if gen_companies else None


def get_station_groups():
    """Получает список групп электростанций'."""
    return StationGroup.query.all()


def get_condition_type():
    """Получает список типов состояний."""
    return ConditionType.query.all()


def get_station_type():
    """Получает список типов электростанций'."""
    return StationType.query.order_by(StationType.id).all()


def get_machine_type():
    """Получает список типов агрегатов электростанций'."""
    return MachineType.query.all()


def get_tes_types():
    """Получает список типов электростанций'."""
    return TesType.query.order_by(TesType.id).all()


def get_tes_machine_types():
    """Получает список типов электростанций'."""
    return TesMachineType.query.order_by(TesMachineType.id).all()


def get_energy_system_types():
    """Получает список типов энергосистем."""
    energy_system_type_list = EnergySystemType.query.order_by(EnergySystemType.id).all()

    energy_system_type_names = {
        energy_system_type.id: energy_system_type.name for energy_system_type in db.session.query(EnergySystemType).all()
    }

    return energy_system_type_list, energy_system_type_names


def get_union_energy_systems():
    """Получаем список ОЭС с привязанными региональными энергосистемами"""
    
    # Запрашиваем все ОЭС, загружая связанные региональные энергосистемы заранее (чтобы избежать дополнительных SQL-запросов)
    union_energy_systems = UnionEnergySystem.query.options(
        joinedload(UnionEnergySystem.regional_energy_systems)
    ).order_by(UnionEnergySystem.id).all()

    union_energy_system_names = {
        union_energy_system.id: union_energy_system.name for union_energy_system in db.session.query(UnionEnergySystem).all()
    }

    # Создаем словарь, где ключ - ID ОЭС, а значение - список ID региональных энергосистем
    regional_energy_system_mapping = {
        ues.id: [res.id for res in ues.regional_energy_systems] if ues.regional_energy_systems else []
        for ues in union_energy_systems
    }

    return union_energy_systems, union_energy_system_names, regional_energy_system_mapping


def get_regional_energy_systems():
    """Получает список региональных энергосистем с предварительной загрузкой ОЭС."""
    
    # Оптимизация запроса: загружаем ОЭС заранее (уменьшаем количество SQL-запросов)
    regional_energy_systems = RegionalEnergySystem.query.options(
        joinedload(RegionalEnergySystem.union_energy_system)
    ).order_by(RegionalEnergySystem.id).all()
    
    regional_energy_system_names = {
        regional_energy_system.id: regional_energy_system.name_full for regional_energy_system in db.session.query(RegionalEnergySystem).all()
    }
    
    # Преобразуем данные в удобный формат
    regional_energy_systems_list = [
        {
            "id": res.id,
            "name": res.name,
            "union_energy_system_id": res.id_union_energy_system if res.union_energy_system else None,
            "union_energy_system_name": res.union_energy_system.name if res.union_energy_system else None,
        }
        for res in regional_energy_systems
    ]

    return regional_energy_systems_list, regional_energy_system_names


def get_federal_districts():
    """Получаем список ФО с привязанными субъектами РФ (региональными округами)."""

    # Оптимизируем запрос: загружаем все ФО и сразу привязываем субъекты (уменьшаем SQL-запросы)
    federal_districts = FederalDistrict.query.options(
        joinedload(FederalDistrict.regional_districts)  # Предварительная загрузка субъектов РФ
    ).order_by(FederalDistrict.id).all()

    # Создаём список ФО и словарь соответствий "ФО → субъекты"
    regional_district_mapping = {
        fd.id: [rd.id for rd in fd.regional_districts] if fd.regional_districts else []
        for fd in federal_districts
    }

    return federal_districts, regional_district_mapping


def get_regional_districts():
    """Получает список субъектов РФ с привязанными федеральными округами."""
    
    # Оптимизируем запрос: загружаем все субъекты с привязанными ФО, чтобы не делать дополнительные SQL-запросы
    regional_districts = RegionalDistrict.query.options(
        joinedload(RegionalDistrict.federal_district)  # Предварительная загрузка ФО
    ).order_by(RegionalDistrict.id).all()
    
    regional_district_names = {
        regional_district.id: regional_district.name for regional_district in db.session.query(RegionalDistrict).all()
    }

    # Создаём список субъектов РФ с дополнительной информацией о ФО
    regional_districts_list = [
        {
            "id": rd.id,
            "name": rd.name,
            "federal_district_id": rd.id_federal_district if rd.federal_district else None,
            "federal_district_name": rd.federal_district.name if rd.federal_district else None
        }
        for rd in regional_districts
    ]

    return regional_districts_list, regional_district_names


def get_year_features():
    """
    Получает словарь с year.number как ключом и year.year_feature как значением.
    :return: Словарь year_features
    """
    return {year.number: year.year_feature for year in Year.query.options(db.joinedload(Year.year_feature)).all()}

from collections import defaultdict
from decimal import Decimal

def aggregate_station_power_values(stations):
    # Словари для хранения мощностей
    stations_yearly_p_ust = defaultdict(lambda: defaultdict(Decimal))
    stations_yearly_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    stations_yearly_p_rasp = defaultdict(lambda: defaultdict(Decimal))
    
    total_yearly_p_ust = defaultdict(Decimal)
    total_yearly_p_ogr = defaultdict(Decimal)
    total_yearly_p_rasp = defaultdict(Decimal)

    # Для каждой станции
    for station in stations:
        # Создаем словари для хранения мощностей по годам для каждой станции
        yearly_p_ust_station = defaultdict(Decimal)
        yearly_p_ogr_station = defaultdict(Decimal)
        yearly_p_rasp_station = defaultdict(Decimal)
        
        # Для каждой машины на станции
        for machine in station.machines:
            if not machine.machine_powers:
                continue  # Пропускаем машину, если нет данных по мощности

            # Для каждой записи о мощности машины
            for machine_power in machine.machine_powers:
                try:
                    p_ust = Decimal(str(machine_power.p_ust)) if machine_power.p_ust is not None else Decimal(0)
                    p_ogr = Decimal(str(machine_power.p_ogr)) if machine_power.p_ogr is not None else Decimal(0)
                    p_rasp = Decimal(str(machine_power.p_rasp)) if machine_power.p_rasp is not None else Decimal(0)
                except (ValueError, TypeError) as e:
                    p_ust = p_ogr = p_rasp = Decimal(0)

                year = machine_power.year.number

                # Подсчеты по мощности для каждой станции
                yearly_p_ust_station[year] += p_ust
                yearly_p_ogr_station[year] += p_ogr
                yearly_p_rasp_station[year] += p_rasp
                
                # Подсчеты по мощности для всех станций (по всем годам)
                total_yearly_p_ust[year] += p_ust
                total_yearly_p_ogr[year] += p_ogr
                total_yearly_p_rasp[year] += p_rasp

        # Записываем данные в общий словарь для станций
        for year in yearly_p_ust_station:
            stations_yearly_p_ust[station.id][year] = yearly_p_ust_station[year]
            stations_yearly_p_ogr[station.id][year] = yearly_p_ogr_station[year]
            stations_yearly_p_rasp[station.id][year] = yearly_p_rasp_station[year]

    # Возвращаем данные по мощностям для всех станций и общие суммарные значения
    return {
        'stations': {
            'p_ust': stations_yearly_p_ust,
            'p_ogr': stations_yearly_p_ogr,
            'p_rasp': stations_yearly_p_rasp,
        },
        'total': {
            'p_ust': total_yearly_p_ust,
            'p_ogr': total_yearly_p_ogr,
            'p_rasp': total_yearly_p_rasp,
        }
    }


def aggregate_power_by_regional_districts(stations):
    # Словари для хранения мощностей по субъектам
    regional_district_yearly_p_ust = defaultdict(lambda: defaultdict(Decimal))
    regional_district_yearly_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    regional_district_yearly_p_rasp = defaultdict(lambda: defaultdict(Decimal))

    # Для каждой станции
    for station in stations:
        regional_district_id = station.regional_district.id  # Получаем ID субъекта станции
        
        # Для каждой машины на станции
        for machine in station.machines:
            if not machine.machine_powers:
                continue  # Пропускаем машину, если нет данных по мощности

            # Для каждой записи о мощности машины
            for machine_power in machine.machine_powers:
                try:
                    p_ust = Decimal(str(machine_power.p_ust)) if machine_power.p_ust is not None else Decimal(0)
                    p_ogr = Decimal(str(machine_power.p_ogr)) if machine_power.p_ogr is not None else Decimal(0)
                    p_rasp = Decimal(str(machine_power.p_rasp)) if machine_power.p_rasp is not None else Decimal(0)
                except (ValueError, TypeError):
                    p_ust = p_ogr = p_rasp = Decimal(0)

                year = machine_power.year.number

                # Агрегируем мощности по субъектам и годам
                regional_district_yearly_p_ust[regional_district_id][year] += p_ust
                regional_district_yearly_p_ogr[regional_district_id][year] += p_ogr
                regional_district_yearly_p_rasp[regional_district_id][year] += p_rasp

    # Возвращаем агрегированные данные по субъектам
    return {
        'regional_districts': {
            'p_ust': regional_district_yearly_p_ust,
            'p_ogr': regional_district_yearly_p_ogr,
            'p_rasp': regional_district_yearly_p_rasp,
        }
    }


def aggregate_power_by_regional_energy_system(stations):
    # Словари для хранения мощностей по региональным энергосистемам
    regional_energy_system_yearly_p_ust = defaultdict(lambda: defaultdict(Decimal))
    regional_energy_system_yearly_p_ogr = defaultdict(lambda: defaultdict(Decimal))
    regional_energy_system_yearly_p_rasp = defaultdict(lambda: defaultdict(Decimal))

    # Для каждой станции
    for station in stations:
        for regional_energy_system in station.regional_district.regional_energy_systems:
            regional_energy_system_id = regional_energy_system.id  # ID региональной энергосистемы
        
        # Для каждой машины на станции
        for machine in station.machines:
            if not machine.machine_powers:
                continue  # Пропускаем машину, если нет данных по мощности

            # Для каждой записи о мощности машины
            for machine_power in machine.machine_powers:
                try:
                    p_ust = Decimal(str(machine_power.p_ust)) if machine_power.p_ust is not None else Decimal(0)
                    p_ogr = Decimal(str(machine_power.p_ogr)) if machine_power.p_ogr is not None else Decimal(0)
                    p_rasp = Decimal(str(machine_power.p_rasp)) if machine_power.p_rasp is not None else Decimal(0)
                except (ValueError, TypeError):
                    p_ust = p_ogr = p_rasp = Decimal(0)

                year = machine_power.year.number

                # Агрегируем мощности по региональным энергосистемам и годам
                regional_energy_system_yearly_p_ust[regional_energy_system_id][year] += p_ust
                regional_energy_system_yearly_p_ogr[regional_energy_system_id][year] += p_ogr
                regional_energy_system_yearly_p_rasp[regional_energy_system_id][year] += p_rasp

    # Возвращаем агрегированные данные по региональным энергосистемам
    return {
        'regional_energy_systems': {
            'p_ust': regional_energy_system_yearly_p_ust,
            'p_ogr': regional_energy_system_yearly_p_ogr,
            'p_rasp': regional_energy_system_yearly_p_rasp,
        }
    }


def aggregate_total_power_values(stations):
    # Словари для хранения мощностей
    total_yearly_p_ust = defaultdict(Decimal)
    total_yearly_p_ogr = defaultdict(Decimal)
    total_yearly_p_rasp = defaultdict(Decimal)

    # Для каждой станции
    for station in stations:
        # Для каждой машины на станции
        for machine in station.machines:
            if not machine.machine_powers:
                continue  # Пропускаем машину, если нет данных по мощности

            # Для каждой записи о мощности машины
            for machine_power in machine.machine_powers:
                try:
                    p_ust = Decimal(str(machine_power.p_ust)) if machine_power.p_ust is not None else Decimal(0)
                    p_ogr = Decimal(str(machine_power.p_ogr)) if machine_power.p_ogr is not None else Decimal(0)
                    p_rasp = Decimal(str(machine_power.p_rasp)) if machine_power.p_rasp is not None else Decimal(0)
                except (ValueError, TypeError) as e:
                    p_ust = p_ogr = p_rasp = Decimal(0)

                year = machine_power.year.number

                # Подсчеты по мощности для всех станций (по всем годам)
                total_yearly_p_ust[year] += p_ust
                total_yearly_p_ogr[year] += p_ogr
                total_yearly_p_rasp[year] += p_rasp

    # Возвращаем данные по мощностям для всех станций и общие суммарные значения
    return {
        'total': {
            'p_ust': total_yearly_p_ust,
            'p_ogr': total_yearly_p_ogr,
            'p_rasp': total_yearly_p_rasp,
        }
    }
    

# Функция для проверки значений на NaN и замены на None
def safe_value(value):
    return None if pd.isna(value) or value in ['', ' '] else value

