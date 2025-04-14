from config import Config
from app import db
from app.models.logs_models import Log
from app.models.energy_systems_models import UnionEnergySystem, RegionalEnergySystem, EnergySystemType, EnergyArea
from app.models.territories_models import RegionalDistrict, FederalDistrict
from app.models.stations_models import Station, StationType, Machine, MachinePower, MachineFuel, MachineTesType, ConditionType, MachineType, TesType, TesMachineType, StationGroup, Machine
from app.models import Year, Fuel, GenCompany  
from sqlalchemy.orm import joinedload, contains_eager
from sqlalchemy import func
from decimal import Decimal
from app.services.gen_company_services import clean_name
from collections import defaultdict


def log_to_db(username, action, details=None):
    """Записывает лог действия пользователя в базу данных."""
    try:
        log_entry = Log(username=username, action=action, details=details)
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Ошибка записи лога: {e}")


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
        regional_district_id = station.regional_district.id if station.regional_district else None
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
                    all_stations.extend(regional_district)  # Добавляем станции
    


    return {
        "grouped_stations": grouped_data,
        "stations": all_stations  # Теперь это список!
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


def aggregate_power_by_regional_district(stations):
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


import re
import pandas as pd
from app import db
from datetime import datetime


# Функция для конверстиции даты в формат 'гггг-мм-дд'
def convert_date(date_value):
    """
    Преобразует дату в формат 'гггг-мм-дд'.
    Поддерживает строки в формате 'дд.мм.гггг', pandas.Timestamp и datetime.
    Если дата некорректна, возвращает None.
    
    :param date_value: Строка, Timestamp или datetime
    :return: Строка в формате 'гггг-мм-дд' или None
    """
    if pd.isna(date_value) or not date_value:
        return None

    # Если это pandas.Timestamp или datetime — преобразуем сразу
    if isinstance(date_value, (pd.Timestamp, datetime)):
        return date_value.strftime("%Y-%m-%d")

    # Если это строка — пытаемся распарсить
    if isinstance(date_value, str):
        try:
            date_obj = datetime.strptime(date_value, "%d.%m.%Y")
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            return None

    # Если неизвестный тип данных
    return None
    
# Функция для проверки значений на NaN и замены на None
def safe_value(value):
    return None if pd.isna(value) or value in ['', ' '] else value

# Функция для проверки полей на NaN и замены на None
def safe_lookup(model, field, value, cleaner=clean_name):
    """Безопасный поиск объекта по справочнику. Возвращает .id или None."""
    try:
        if pd.isna(value):
            return None
        cleaned = cleaner(value) if cleaner else value
        if cleaned in [None, '', float('nan')]:
            return None
        obj = model.query.filter_by(**{field: cleaned}).first()
        return obj.id if obj else None
    except Exception as e:
        print(f"❌ Ошибка при поиске {model.__name__}.{field}='{value}':", e)
        return None

# Функция для импорта списка станций с параметрами в базу данных
def import_station_list_from_excel(file, user):
    xls = pd.ExcelFile(file)
    df = xls.parse('список', header=0)
    df = df.dropna(how='all')

    current_station = None
    current_machine = None
    last_machine = None
    previous_was_machine = False

    start_year = 2021
    end_year = 2031

    for index, row in df.iterrows():
        # Пропускаем полностью пустые строки
        if row.isnull().all():
            continue

        print(f"Обрабатываем строку {index}: {row.to_dict()}")

        # Проверка и создание/обновление станции
        if not (pd.isna(row['regional_district']) and pd.isna(row['station_name'])): # если поля regional_district и station_name заполнены, то создаем/обновляем станцию
            print("Выполняется условие если поля regional_district и station_name заполнены, то создаем/обновляем станцию")
            regional_district_name = clean_name(row['regional_district'])
            regional_district = RegionalDistrict.query.filter_by(name=regional_district_name).first()

            if not regional_district:
                energy_area = EnergyArea.query.filter_by(name=regional_district_name).first()
                if energy_area:
                    regional_district = energy_area.regional_districts[0] if energy_area.regional_districts else None

            station_name = clean_name(row['station_name'])
            station = Station.query.filter_by(name=station_name).first()

            condition_type = ConditionType.query.filter_by(name="действующий").first()

            if not station:
                station = Station(
                    name=station_name,
                    id_regional_district=regional_district.id if regional_district else None,
                    id_condition_type=condition_type.id if condition_type else None,
                    id_energy_area=energy_area.id if energy_area else safe_lookup(EnergyArea, 'id', 100, cleaner=None),
                )
                db.session.add(station)
                db.session.commit()
                log_to_db(user, "Создание станции", f"Создана станция: {station_name}")
                print("Создана электростанция", station_name)
            else:
                changes = {}
                if station.id_regional_district != (regional_district.id if regional_district else None):
                    changes['id_regional_district'] = regional_district.id if regional_district else None
                
                if changes:
                    for key, value in changes.items():
                        setattr(station, key, value)
                    db.session.commit()
                    log_to_db(user, "Обновление станции", f"Обновлена станция: {station.name}, изменения: {changes}")
                    print("Обновлена электростанция", station_name)

            current_station = station
            current_machine = None
            previous_was_machine = False

        # Проверка и создание/обновление агрегатов станции
        elif not pd.isna(row['machine_name']) and not pd.isna(row['gen_company']): # если поля regional_district и station_name не заполнены, а поля machine_name и gen_company заполнены, то создаем/обновляем агрегат
            print("Выполняется условие если поля regional_district и station_name не заполнены, а поля machine_name и gen_company заполнены, то создаем/обновляем агрегат, записываем его установленную мощность и топливо")

            machine_group = clean_name(row.get('machine_group'))

            # Проверяем, является ли значение NaN или некорректным
            if pd.isna(machine_group) or machine_group in [None, 'nan', 'NaN', '']:
                machine_group = ""
            else:
                # Если это число (int или float), приводим его к строке без '.0' в случае целых чисел
                if isinstance(machine_group, (int, float)):
                    machine_group = str(int(machine_group)) if machine_group.is_integer() else str(machine_group)
                else:
                    machine_group = str(machine_group).strip()

            machine_number = clean_name(row.get('machine_number'))

            # Проверяем, является ли значение NaN или некорректным
            if pd.isna(machine_number) or machine_number in [None, 'nan', 'NaN', '']:
                machine_number = ""
            else:
                # Если это число (int или float), приводим его к строке без '.0' в случае целых чисел
                if isinstance(machine_number, (int, float)):
                    machine_number = str(int(machine_number)) if machine_number.is_integer() else str(machine_number)
                else:
                    machine_number = str(machine_number).strip()


            machine_name = str(clean_name(row['machine_name']))
            gen_company = GenCompany.query.filter_by(name=clean_name(row['gen_company'])).first()

            condition_type = ConditionType.query.filter_by(name="действующий").first()
            if row.get('p_2024') == 0 or row.get('date_exploitation') > 2025:
                condition_type = ConditionType.query.filter_by(name="планируемый").first()

            # Если machine_number является None, то выполняем запрос по machine_name
            machine = Machine.query.filter_by(machine_number=machine_number, machine_group=machine_group, id_station=current_station.id).first()

            id_tes_machine_type = None
            if not pd.isna(row.get('tes_machine_type')):
                tes_machine_type_obj = TesMachineType.query.filter_by(
                    name=clean_name(row['tes_machine_type'])
                ).first()
                if tes_machine_type_obj:
                    id_tes_machine_type = tes_machine_type_obj.id

            def normalize_date_str(date_str):
                """Преобразует строку/дату в строку формата YYYY-MM-DD (макс. 10 символов)"""
                if isinstance(date_str, datetime):
                    return date_str.strftime("%Y-%m-%d")
                if isinstance(date_str, pd.Timestamp):
                    return date_str.strftime("%Y-%m-%d")
                if isinstance(date_str, str):
                    return date_str.strip()[:10]
                return None

            if machine:
                print(f"Агрегат группы {machine_group} № {machine_number} - {machine_name} уже существует, обновляем данные.")

                changes = []

                if machine.machine_name != machine_name:
                    changes.append(f"machine_name: {machine.machine_name} → {machine_name}")
                    machine.machine_name = machine_name

                if machine.machine_group != machine_group:
                    changes.append(f"machine_group: {machine.machine_group} → {machine_group}")
                    machine.machine_group = machine_group

                if machine.id_gen_company != (gen_company.id if gen_company else None):
                    changes.append(f"id_gen_company: {machine.id_gen_company} → {gen_company.id if gen_company else None}")
                    machine.id_gen_company = gen_company.id if gen_company else None

                id_station_type = safe_lookup(StationType, 'name', row.get('station_type'))
                if machine.id_station_type != id_station_type:
                    changes.append(f"id_station_type: {machine.id_station_type} → {id_station_type}")
                    machine.id_station_type = id_station_type

                id_tes_type = safe_lookup(TesType, 'name', row.get('tes_type'))
                if machine.id_tes_type != id_tes_type:
                    changes.append(f"id_tes_type: {machine.id_tes_type} → {id_tes_type}")
                    machine.id_tes_type = id_tes_type

                id_tes_machine_type = safe_lookup(TesMachineType, 'name', row.get('tes_machine_type'))
                if machine.id_tes_machine_type != id_tes_machine_type:
                    changes.append(f"id_tes_machine_type: {machine.id_tes_machine_type} → {id_tes_machine_type}")
                    machine.id_tes_machine_type = id_tes_machine_type

                id_machine_type = safe_lookup(MachineType, 'id', 100, cleaner=None)
                if machine.id_machine_type != id_machine_type:
                    changes.append(f"id_machine_type: {machine.id_machine_type} → {id_machine_type}")
                    machine.id_machine_type = id_machine_type

                id_energy_area = safe_lookup(EnergyArea, 'id', 100, cleaner=None)
                if machine.id_energy_area != id_energy_area:
                    changes.append(f"id_energy_area: {machine.id_energy_area} → {id_energy_area}")
                    machine.id_energy_area = id_energy_area

                def get_value_safe(key):
                    val = row.get(key)
                    return val if not pd.isna(val) else None

                def normalize_date(date_str):
                    """Преобразует строку в объект datetime.date, если возможно"""
                    if not date_str:
                        return None
                    for fmt in ("%Y-%m-%d", "%Y.%m.%d", "%d.%m.%Y", "%Y"):
                        try:
                            return datetime.strptime(date_str.strip(), fmt).date()
                        except (ValueError, AttributeError):
                            continue
                    return None

                def normalized_str_eq(a, b):
                    """Сравнивает строки как даты"""
                    return normalize_date(a) == normalize_date(b)

                date_fields = [
                    'date_commission_expected', 'date_commission_fact',
                    'date_joining_expected', 'date_joining_fact',
                    'date_detatchment_fact', 'date_decompressing_expected',
                    'date_decompressing_fact', 'date_modernization_expected',
                    'date_relabing_fact', 'date_update_fact'
                ]

                for field in date_fields:
                    new_val = get_value_safe(field)
                    new_val_str = normalize_date_str(new_val)
                    old_val = getattr(machine, field)

                    if not normalized_str_eq(old_val, new_val_str):
                        changes.append(f"{field}: {old_val} → {new_val_str}")
                        setattr(machine, field, new_val_str)

                new_note = clean_name(row['note']) if not pd.isna(row.get('note')) else None
                if machine.note != new_note:
                    changes.append(f"note: {machine.note} → {new_note}")
                    machine.note = new_note

                if changes:
                    db.session.commit()
                    log_to_db(user, "Обновление агрегата", f"Агрегат группы {machine_group} № {machine_number}, {machine_name} обновлен: {', '.join(changes)}")

                print("✅ Проверка завершена, изменения:", changes)
                print(f"Обновлен агрегат группы {machine_group} № {machine_number}, {machine_name}")

            else:
                print(f"Создаем новый агрегат группы  {machine_group} № {machine_number} - {machine_name}.")

                machine = Machine(
                    id_condition_type=condition_type.id if condition_type else None,
                    id_gen_company=gen_company.id if gen_company else None,
                    id_station=current_station.id,
                    machine_number=machine_number,
                    machine_name=machine_name,
                    machine_group=machine_group,
                    date_exploitation=row.get('date_exploitation') if not pd.isna(row.get('date_exploitation')) else None,
                    note=clean_name(row['note']) if not pd.isna(row['note']) else None,
                    id_station_type=safe_lookup(StationType, 'name', row.get('station_type')),
                    id_tes_type=safe_lookup(TesType, 'name', row.get('tes_type')),
                    id_machine_type=safe_lookup(MachineType, 'id', 100, cleaner=None),
                    id_energy_area=safe_lookup(EnergyArea, 'id', 100, cleaner=None),
                    id_tes_machine_type=safe_lookup(TesMachineType, 'name', row.get('tes_machine_type')),
                    date_commission_expected=convert_date(row.get('date_commission_expected')) if not convert_date(pd.isna(row.get('date_commission_expected'))) else None,
                    date_commission_fact=convert_date(row.get('date_commission_fact')) if not convert_date(pd.isna(row.get('date_commission_fact'))) else None,
                    date_joining_expected=convert_date(row.get('date_joining_expected')) if not convert_date(pd.isna(row.get('date_joining_expected'))) else None,
                    date_joining_fact=convert_date(row.get('date_joining_fact')) if not convert_date(pd.isna(row.get('date_joining_fact'))) else None,
                    date_detatchment_fact=convert_date(row.get('date_detatchment_fact')) if not convert_date(pd.isna(row.get('date_detatchment_fact'))) else None,
                    date_decompressing_expected=convert_date(row.get('date_decompressing_expected')) if not convert_date(pd.isna(row.get('date_decompressing_expected'))) else None,
                    date_decompressing_fact=convert_date(row.get('date_decompressing_fact')) if not convert_date(pd.isna(row.get('date_decompressing_fact'))) else None,
                    date_modernization_expected=convert_date(row.get('date_modernization_expected')) if not convert_date(pd.isna(row.get('date_modernization_expected'))) else None,
                    date_relabing_fact=convert_date(row.get('date_relabing_fact')) if not convert_date(pd.isna(row.get('date_relabing_fact'))) else None,
                    date_update_fact=convert_date(row.get('date_update_fact')) if not convert_date(pd.isna(row.get('date_update_fact'))) else None,
                )

                print(f"✅ Успешно создан арегат: {machine_number} - {machine_name}")
                db.session.add(machine)
                db.session.commit()
                log_to_db(user, "Создание агрегата", f"Создан агрегат: {machine_number} - {machine_name}")
                print("Создан агрегат", machine_number, machine_name)

            current_machine = machine
            last_machine = current_machine

            # Вносим установленную мощность, тип ТЭС и топливо     
            last_non_zero_year = None
            was_zero = False

            for year in range(start_year, end_year + 1):
                # Вносим данные о мощности
                p_ust = clean_name(row.get(f'p_{year}'))
                p_ust = None if p_ust in ['', ' ', 'nan', 'NaN'] or pd.isna(p_ust) else p_ust
                try:
                    p_ust = float(p_ust) if p_ust is not None else None
                except ValueError:
                    p_ust = None

                # Приводим к 0, если планируемый
                if p_ust is None or current_machine.id_condition_type == ConditionType.query.filter_by(name="планируемый").first().id:
                    p_ust = 0

                machine_power = MachinePower.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                if machine_power:
                    if machine_power.p_ust != p_ust:
                        machine_power.p_ust = p_ust
                        log_to_db(user, "Обновление мощности", 
                                f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, "
                                f"год {year}: p_ust {machine_power.p_ust} → {p_ust}")
                else:
                    machine_power = MachinePower(year_number=year, id_machine=current_machine.id, p_ust=p_ust)
                    db.session.add(machine_power)
                    log_to_db(user, "Создание мощности", 
                            f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, "
                            f"год {year}: p_ust {p_ust}")

                print(f"Установленная мощность для машины {current_machine.machine_number}, год {year}: {p_ust}")

                # 🔧 Логика вывода и ввода:
                if p_ust > 0:
                    if was_zero and not current_machine.date_commission_expected:
                        # Мощность была нулевая, а стала > 0 — ввод в работу
                        current_machine.date_commission_expected = str(year)
                        log_to_db(user, "Установлен ожидаемый ввод", 
                                f"Агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год: {year}")
                    last_non_zero_year = year
                    was_zero = False
                else:
                    if not was_zero and last_non_zero_year and not current_machine.date_decompressing_expected:
                        # Мощность была > 0, а стала 0 — вывод из эксплуатации
                        current_machine.date_decompressing_expected = str(last_non_zero_year)
                        log_to_db(user, "Установлен ожидаемый вывод", 
                                f"Агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год: {last_non_zero_year}")
                    was_zero = True

                # Вносим данные о типе ТЭС
                tes_type = TesType.query.filter_by(id=current_machine.id_tes_type).first()

                if tes_type:
                    tes_type_id = tes_type.id
                    tes_type_name = tes_type.name

                    machine_tes_type = MachineTesType.query.filter_by(
                        year_number=year, 
                        id_machine=current_machine.id
                    ).first()

                    if p_ust == 0:
                        tes_type_id = 100
                    else:
                        tes_type = TesType.query.filter_by(id=current_machine.id_tes_type).first()
                        tes_type_id = tes_type.id if tes_type else None


                    if machine_tes_type:
                        if machine_tes_type.id_tes_type != tes_type_id:
                            log_to_db(
                                user, "Обновление типа ТЭС", 
                                f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: "
                                f"tes_type {machine_tes_type.tes_type.name if machine_tes_type.tes_type else 'не указано'} → {tes_type_name}"
                            )
                            machine_tes_type.id_tes_type = tes_type_id
                    else:
                        machine_tes_type = MachineTesType(
                            year_number=year, 
                            id_machine=current_machine.id,  # Исправлено (было `machine.id`)
                            id_tes_type=tes_type_id
                        )
                        db.session.add(machine_tes_type)
                        log_to_db(
                            user, "Создание типа ТЭС", 
                            f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: tes_type {tes_type_name}"
                        )

                    print(f"Тип ТЭС для машины {current_machine.machine_number}, год {year}: {tes_type_id}")
                else:
                    print(f"У машины {current_machine.machine_number} нет типа ТЭС.")
                    tes_type_id = None  # Безопасное присвоение None

                # Вносим данные о типе топлива
                fuel_name = clean_name(row.get(f'fuel_{year}'))

                fuel_type_mapping = {
                    "газ": 1,
                    "уголь": 2,
                    "прочее": 3
                }

                fuel_type_id = fuel_type_mapping.get(fuel_name)

                if fuel_type_id:
                    fuel = Fuel.query.filter_by(id_fuel_type=fuel_type_id).first()
                else:
                    fuel = None

                print(f"Топливо для машины {current_machine.machine_number}, год {year}: {fuel}")

                if fuel and current_machine.id_station_type == StationType.query.filter_by(name="ТЭС").first().id:
                    machine_fuel = MachineFuel.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                    
                    if not machine_fuel:
                        machine_fuel = MachineFuel(year_number=year, id_machine=current_machine.id, id_fuel=fuel.id)
                        db.session.add(machine_fuel)
                        log_to_db(user, "Создание вида топлива", f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: machine_fuel {fuel.name}")
                    else:
                        # Обновляем id_fuel, если оно изменилось
                        if machine_fuel.id_fuel != fuel.id:
                            machine_fuel.id_fuel = fuel.id
                            log_to_db(user, "Обновление вида топлива", f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: machine_fuel {fuel.name} → {machine_fuel.fuel.name}")
                        
                        # Обновляем p_ust, если передано новое значение
                        if p_ust is not None:
                            machine_fuel.p_ust = p_ust

            db.session.commit()
            previous_was_machine = True
            print("Установленные мощности, типы ТЭС и топливо внесены")

        # Располагаемая мощность (p_rasp)
        elif previous_was_machine: # если поля regional_district и station_name, machine_name и gen_company не заполнены, но шагом ранее был создан агрегат, то добавляем ему располагаему мощность
                print("если поля regional_district и station_name, machine_name и gen_company не заполнены, но шагом ранее был создан агрегат, то добавляем ему располагаему мощность")
                current_machine = last_machine  # Используем последнюю машину

                for year in range(start_year, end_year + 1):
                    p_rasp = clean_name(row.get(f'p_{year}'))
                    p_rasp = None if p_rasp in ['', ' ', 'nan', 'NaN'] or pd.isna(p_rasp) else p_rasp
                    try:
                        p_rasp = float(p_rasp) if p_rasp is not None else None
                    except ValueError:
                        p_rasp = None

                    if p_rasp is None or current_machine.id_condition_type == ConditionType.query.filter_by(name="планируемый").first().id:
                        p_rasp = 0

                    print(f"Располагаемая мощность для машины {current_machine.machine_number}, год {year}: {p_rasp}")
                    
                    def floats_equal(a, b, eps=1e-6):
                        if a is None and b is None:
                            return True
                        if a is None or b is None:
                            return False
                        return abs(a - b) < eps

                    machine_power = MachinePower.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                    if machine_power:
                        if not floats_equal(machine_power.p_rasp, p_rasp):
                            old_val = machine_power.p_rasp
                            machine_power.p_rasp = p_rasp if p_rasp is not None else old_val
                            machine_power.p_ogr = machine_power.p_ust - machine_power.p_rasp
                            db.session.add(machine_power)
                            log_to_db(
                                user, 
                                "Обновление располагаемой мощности", 
                                f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: p_rasp {old_val} → {p_rasp}"
                            )

                        # Проверка топлива
                        machine_fuel = MachineFuel.query.filter_by(year_number=year, id_machine=current_machine.id).first()
                        if p_rasp == 0 and machine_fuel:
                            db.session.delete(machine_fuel)
                            log_to_db(user, "Удаление топлива", f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: удалено топливо")
                            print(f"Удаляем топливо для машины {current_machine.machine_number}, год {year}, так как p_rasp = 0")
                        elif p_rasp > 0 and not machine_fuel:
                            # Если располагаемая мощность больше 0, но топливо отсутствует, добавляем топливо
                            fuel_name = clean_name(row.get(f'fuel_{year}'))
                            fuel_type_id = fuel_type_mapping.get(fuel_name)

                            if fuel_type_id:
                                fuel = Fuel.query.filter_by(id_fuel_type=fuel_type_id).first()
                                if fuel:
                                    machine_fuel = MachineFuel(
                                        year_number=year,
                                        id_machine=current_machine.id,
                                        id_fuel=fuel.id
                                    )
                                    db.session.add(machine_fuel)
                                    log_to_db(user, "Добавление топлива", f"Станция: {current_station.name}, агрегат: {current_machine.machine_number} - {current_machine.machine_name}, год {year}: добавлено топливо {fuel_name}")
                                    print(f"Добавлено топливо {fuel_name} для машины {current_machine.machine_number}, год {year}")

                db.session.commit()
                previous_was_machine = False 

    return {'message': f'Данные успешно загружены пользователем {user}'}

# Функция для импорта топлива по СО ЕЭС для станций в базу данных
def import_fuel_tes_station_from_excel(file, user):
    xls = pd.ExcelFile(file)

    # Список обрабатываемых листов
    sheet_names = ['Приложение А_ЕЭС', 'Приложение А_ТИТЭС']

    for sheet in sheet_names:
        print(f"\n📄 Обработка листа: {sheet}")
        if sheet not in xls.sheet_names:
            print(f"⚠️ Лист '{sheet}' не найден в файле. Пропускаем.")
            continue

        df = xls.parse(sheet, header=0)
        df = df.dropna(how='all')

        for index, row in df.iterrows():
            if row.isnull().all():
                continue

            print(f"Обрабатываем строку {index}: {row.to_dict()}")

            if not (pd.isna(row['name']) and pd.isna(row['gen_company'])):
                if not pd.isna(row['name']) and pd.isna(row['gen_company']):
                    print("Пропускаем строку, так как есть имя, но нет генкомпании.")
                    continue

                station_name = clean_name(row['name'])
                gen_company_name = clean_name(row['gen_company'])

                if pd.isna(gen_company_name):
                    print("Ошибка: значение генкомпании NaN")
                    continue

                gen_company_obj = GenCompany.query.filter_by(name=gen_company_name).first()
                if gen_company_obj:
                    print(f"Генкомпания найдена: {gen_company_obj.name}")
                else:
                    print(f"⚠️ Генкомпания с именем '{gen_company_name}' не найдена.")
                    continue

                fuel_name = clean_name(row['fuel']) if not pd.isna(row['fuel']) else None
                if pd.isna(fuel_name) or fuel_name is None:
                    print("⚠️ Топливо не указано, пропускаем строку.")
                    continue

                station = Station.query.join(Machine).filter(
                    Station.name == station_name,
                    Machine.gen_company == gen_company_obj
                ).first()

                if station:
                    print(f"✅ Станция найдена: {station_name}")
                    if station.machines:
                        updated_machines = 0
                        for machine in station.machines:
                            if machine.fuel_so != fuel_name:
                                machine.fuel_so = fuel_name
                                updated_machines += 1

                        if updated_machines > 0:
                            db.session.commit()
                            log_to_db(user, "Обновление топлива машин", f"Станция: {station_name}, обновлено агрегатов: {updated_machines}")
                            print(f"🔄 Обновлено топливо для {updated_machines} агрегатов станции '{station_name}'.")
                        else:
                            print(f"ℹ️ Все агрегаты станции '{station_name}' уже имеют актуальное топливо.")
                    else:
                        print(f"⚠️ У станции '{station_name}' нет агрегатов.")
                else:
                    print(f"❌ Станция '{station_name}' с генкомпанией '{gen_company_name}' не найдена.")
            else:
                print("⏭ Имя и генкомпания отсутствуют, пропускаем строку.")

    return {'message': f'Данные по топливу успешно загружены пользователем {user}'}


from datetime import datetime
import re

def convert_to_iso_date(value):
    """
    Преобразует введённую строку в нужный формат:
      - Если введён год (YYYY), возвращает его без изменений.
      - Если введена дата (DD.MM.YYYY), преобразует в YYYY-MM-DD.
      - Если значение пустое, возвращает None.
    """
    if not value or not value.strip():
        return None
    
    value = value.strip()

    # Если введён только год (YYYY), оставляем его без изменений
    if re.match(r'^\d{4}$', value):
        return value

    # Если введена полная дата в формате DD.MM.YYYY
    try:
        date_obj = datetime.strptime(value, '%d.%m.%Y')
        return date_obj.strftime('%Y-%m-%d')
    except ValueError:
        raise ValueError("Некорректный формат даты. Используйте YYYY или DD.MM.YYYY.")

import traceback
from io import BytesIO

def export_station_list_to_excel(user, filters=None):
    """Экспортирует данные электростанций в Excel, создавая отдельный файл для каждого субъекта РФ."""

    log_to_db(user, "Начата выгрузка таблицы электростанций из базы данных")
    log_to_db(user, "Параметры экспорта", f"Фильтры: {filters}")

    query = get_filtered_stations(**filters)
    station_list = query.all()
    station_list = group_machines_by_group_and_fuel(station_list)

    total_stations = len(station_list)
    log_to_db(user, "Найдено станций в БД", f"{total_stations} записей")

    if not station_list:
        log_to_db(user, "Экспорт остановлен", "Нет данных для экспорта.")
        return None

    all_years = list(range(2024, 2032))
    output_files = []
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # Группируем станции по субъекту РФ
    regional_districts = {"Без субъекта": []}
    regional_systems = {}
    for station in station_list:
        district_name = station.regional_district.name if station.regional_district else "Без субъекта"
        if district_name not in regional_districts:
            regional_districts[district_name] = []
        regional_districts[district_name].append(station)

        regional_system_name = station.regional_energy_system if station.regional_energy_system else "Неизвестно"
        if regional_system_name not in regional_systems:
            regional_systems[regional_system_name] = set()
        regional_systems[regional_system_name].add(district_name)

    processed_stations = 0
    
    for district_name, stations in regional_districts.items():
        log_to_db(user, f"Выгрузка данных по форме Приложения А к СиПР ЭЭС: {district_name} (Энергосистема: {regional_system_name}) | Найдено станций: {len(stations)}")
        if not stations:
            continue
        try:
            data = []

            # Добавляем строку с названием региональной энергосистемы
            first_station = stations[0]
            regional_system_name = first_station.regional_energy_system if first_station.regional_energy_system else "Неизвестно"

            # Получаем список субъектов для данной энергосистемы
            subject_list = sorted(regional_systems.get(regional_system_name, set()))

            # Определяем, что писать в region_label
            if len(subject_list) > 1:
                region_label = f"{regional_system_name}, в том числе {district_name}"
            else:
                region_label = regional_system_name  # Если субъект один, пишем его напрямую

            data.append({
                "Электростанция": region_label,
                "Генерирующая компания": "",
                "Станционный номер": "",
                "Тип генерирующего оборудования": "",
                "Вид топлива": "",
                **{year: "" for year in all_years},
                "Примечание": "",
            })

            for station in stations:
                processed_stations += 1
                power_data = station.power_by_year() or {}

                # Добавляем строку с названием электростанции
                data.append({
                    "Электростанция": station.name,
                    "Генерирующая компания": station.gen_companies,
                    "Станционный номер": "",
                    "Тип генерирующего оборудования": "",
                    "Вид топлива": "",
                    **{year: "" for year in all_years},
                    "Примечание": "",
                })

                def extract_year(date_str):
                    """Пытается извлечь год из строки"""
                    if not date_str:
                        return None
                    try:
                        return datetime.strptime(date_str, "%Y-%m-%d").year
                    except ValueError:
                        try:
                            return int(date_str[:4])
                        except ValueError:
                            return None

                def format_full_date(date_str):
                    """Преобразует строку вида '2023-06-16' в '16.06.2023'"""
                    try:
                        dt = datetime.strptime(date_str, "%Y-%m-%d")
                        return dt.strftime("%d.%m.%Y")
                    except Exception:
                        return date_str
    
                # Добавляем строки с установленной мощностью по машинам электростанции
                for machine in station.machines:
                    machine_power_data = {}
                    for mp in machine.machine_powers:
                        if mp.year and mp.p_ust is not None:
                            machine_power_data[mp.year.number] = mp.p_ust

                    note_parts = []
                    if machine.date_commission_expected:
                        year = extract_year(machine.date_commission_expected)
                        if year:
                            note_parts.append(f"Ввод в эксплуатацию в {year} г.")

                    if machine.date_decompressing_expected:
                        year = extract_year(machine.date_decompressing_expected)
                        if year:
                            note_parts.append(f"Вывод из эксплуатации в {year} г.")

                    if machine.date_modernization_expected:
                        year = extract_year(machine.date_modernization_expected)
                        if year:
                            note_parts.append(f"Модернизация в {year} г.")

                    if machine.date_relabing_fact:
                        full_date = format_full_date(machine.date_relabing_fact)
                        note_parts.append(f"Перемаркировка {full_date}")

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
                }
                data.append(total_row)

            df = pd.DataFrame(data)
            df = df.fillna("")

            # Создание Excel-файла
            output = BytesIO()
            sheet_name = f"Приложение А"
            file_name = f"Приложение_А_{district_name}_{timestamp}.xlsx".replace(" ", "_")
            with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, header=False, startrow=6, sheet_name=sheet_name)
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

                text_center_format = workbook.add_format({
                    'font_name': 'Times New Roman',  # Устанавливаем шрифт
                    'font_size': 10,                 # Размер шрифта 10pt
                    'align': 'center',               # Выравнивание текста по центру
                    'valign': 'vcenter',             # Выравнивание по центру по вертикали
                    'text_wrap': True,               # Перенос слов (разрыв строк)
                    'border': 1                      # Границы ячейки
                })

                # Заголовки
                worksheet.merge_range("A1:N1", "ПРИЛОЖЕНИЕ А", title_format)
                worksheet.merge_range("A2:N2", "Перечень электростанций, действующих и планируемых к сооружению, расширению, модернизации и выводу из эксплуатации", title_format)
                worksheet.merge_range("A3:N3", "", title_format)
                worksheet.merge_range("A4:N4", "Таблица А.1 – Перечень действующих электростанций, с указанием состава генерирующего оборудования и планов по выводу из эксплуатации, реконструкции (модернизации или перемаркировке), вводу в эксплуатацию генерирующего оборудования в период до 2030 года", subtitle_format)
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
                first_year = all_years[0]  # Берем первый год из списка
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

                # Применяем ширину (217 пикселей ≈ 30 Excel ширина) и формат только к этому столбцу
                worksheet.set_column(station_col_idx, station_col_idx, 30.29, text_format)
                worksheet.set_column(gen_company_col_idx, gen_company_col_idx, 17, text_center_format)
                worksheet.set_column(machine_number_col_idx, machine_number_col_idx, 12, text_center_format)
                worksheet.set_column(machine_name_col_idx, machine_name_col_idx, 20.86, text_center_format)
                worksheet.set_column(fuel_type_col_idx, fuel_type_col_idx, 11.29, text_center_format)
                
                worksheet.set_column(note_column_col_idx, note_column_col_idx, 28.71, text_format)

                # Определяем диапазон объединения (все столбцы)
                start_col = 0
                end_col = len(df.columns) - 1  # Последний столбец

                # Найти индекс строки, где находится региональная энергосистема (первое её появление в data)
                regional_row_idx = next(
                    (i for i, row in enumerate(data) if row["Электростанция"] == region_label),
                    None
                )

                # Объединяем ячейки в Excel
                worksheet.merge_range(regional_row_idx + 6, start_col, regional_row_idx + 6, end_col,  # +6 из-за заголовков
                                    region_label, text_format)

                # Определяем последнюю заполненную строку
                last_row = len(df) + 6  # +5 из-за заголовков

                # Определяем последний используемый столбец
                last_col = len(df.columns)

                # Создаем пустой стиль (без границ, выравнивания и других атрибутов)
                empty_format = workbook.add_format()

                # Снимаем форматирование с пустых строк после таблицы
                for row_num in range(last_row, 1000):  # 1000 - большое число, можно сделать динамическим
                    worksheet.set_row(row_num, None, empty_format)

                # Снимаем форматирование с пустых столбцов после таблицы
                for col_num in range(last_col + 1, 50):  # 50 - запасное число столбцов
                    worksheet.set_column(col_num, col_num, None, empty_format)

            output.seek(0)
            output_files.append((file_name, output))
    
        except Exception as e:
            error_message = f"❌ Ошибка экспорта субъекта {district_name}: {str(e)}\n{traceback.format_exc()}"
            log_to_db(user, error_message)
            print(error_message)

    log_to_db(user, "Экспорт завершён", f"Обработано {processed_stations} из {total_stations} станций.")

    return output_files[0] if len(output_files) == 1 else output_files





