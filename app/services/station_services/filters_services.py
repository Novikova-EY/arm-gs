from config import Config
from app import db
from collections import defaultdict
from sqlalchemy import or_, extract, and_, func
from sqlalchemy.sql import exists
from sqlalchemy.orm import contains_eager, joinedload
from app.models import *
from app.services.station_services.station_services import (
    get_current_year
)


def extract_filters_from_args(args):
    return {
        "page": args.get("page", 1, type=int),
        "start_year": args.get("start_year", Config.START_YEAR, type=int),
        "end_year": args.get("end_year", Config.END_YEAR, type=int),
        "condition_type_filter": args.get("condition_type_filter", ""),
        "energy_system_type_filter": args.getlist("energy_system_type_filter", type=int),
        "union_energy_system_filter": args.getlist("union_energy_system_filter", type=int),
        "regional_energy_system_filter": args.getlist("regional_energy_system_filter", type=int),
        "federal_district_filter": args.getlist("federal_district_filter", type=int),
        "regional_district_filter": args.getlist("regional_district_filter", type=int),
        "gen_company_filter": args.get("gen_company_filter", "").strip(),
        "station_name_filter": args.get("station_name_filter", "").strip(),
        "station_type_filter": args.getlist("station_type_filter", type=int),
        "fuel_type_filter": args.getlist("fuel_type_filter", type=int),
        "tes_type_filter": args.getlist("tes_type_filter", type=int),
        "tes_machine_type_filter": args.getlist("tes_machine_type_filter", type=int),
        "date_exploitation_filter": args.getlist("date_exploitation_filter", type=int),
        "date_decompressing_expected_filter": args.getlist("date_decompressing_expected_filter", type=int),
        "date_modernization_expected_filter": args.getlist("date_modernization_expected_filter", type=int),
        "sort_by": args.get("sort_by", "id"),
        "sort_dir": args.get("sort_dir", "asc"),
    }


def extract_filters_from_form(form):
    return extract_filters_from_args(form)


def fetch_filtered_machines_with_rowspans(station_ids: list[int], filters: dict):
    """
    Загружает агрегаты с применением SQL-фильтров и рассчитывает group_rowspan и fuel_rowspan.
    """
    current_year = get_current_year()

    query = Machine.query.options(
        joinedload(Machine.station_type),
        joinedload(Machine.tes_machine_type),
        joinedload(Machine.machine_station),
        joinedload(Machine.machine_tes_types).joinedload(MachineTesType.tes_type),
    ).filter(Machine.id_station.in_(station_ids))

    # Фильтрация по типу ТЭС
    if filters.get("tes_type_filter"):
        query = query.filter(
            Machine.machine_tes_types.any(
                and_(
                    MachineTesType.year_number == current_year,
                    MachineTesType.id_tes_type.in_(filters["tes_type_filter"])
                )
            )
        )

    # Фильтрация по типу агрегата
    if filters.get("tes_machine_type_filter"):
        query = query.filter(
            Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"])
        )

    # Фильтрация по виду топлива
    if filters.get("fuel_type_filter"):
        query = query.filter(
            Machine.machine_fuels.any(
                MachineFuel.fuel.has(
                    Fuel.fuel_type.has(
                        FuelType.id.in_(filters["fuel_type_filter"])
                    )
                )
            )
        )

    # Фильтрация по датам (ввода, вывода, модернизации)
    if filters.get("date_exploitation_filter"):
        query = query.filter(Machine.date_exploitation.in_(filters["date_exploitation_filter"]))

    if filters.get("date_decompressing_expected_filter"):
        query = query.filter(Machine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"]))

    if filters.get("date_modernization_expected_filter"):
        query = query.filter(Machine.date_modernization_expected.in_(filters["date_modernization_expected_filter"]))

    machines = query.all()

    # Привязываем к станциям
    station_machine_map = defaultdict(list)
    for m in machines:
        station_machine_map[m.id_station].append(m)

    # Для каждой станции сортируем и проставляем rowspan
    for machine_list in station_machine_map.values():
        machine_list.sort(key=lambda m: (
            (m.machine_group or '').lower(),
            (m.fuel_so or '').lower(),
            int(m.machine_number) if m.machine_number and str(m.machine_number).isdigit() else float('inf')
        ))

        group_dict = defaultdict(list)
        for m in machine_list:
            group_key = (m.machine_group or '').strip()
            group_dict[group_key].append(m)
        for group in group_dict.values():
            group[0].group_rowspan = len(group)
            for m in group[1:]:
                m.group_rowspan = 0

        fuel_dict = defaultdict(list)
        for m in machine_list:
            fuel_key = (m.fuel_so or '').strip()
            fuel_dict[fuel_key].append(m)
        for group in fuel_dict.values():
            group[0].fuel_rowspan = len(group)
            for m in group[1:]:
                m.fuel_rowspan = 0

    all_machines = []
    for lst in station_machine_map.values():
        all_machines.extend(lst)

    return all_machines


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
    date_exploitation_filter=None,
):

    # 1) Начинаем с запроса Station, при необходимости join(Station.machines)
    query = db.session.query(Station.id).join(Station.machines)

    current_year = get_current_year()

    # 2) Применяем фильтры.
    if station_type_filter:
        query = query.filter(Machine.id_station_type.in_(station_type_filter))
    if tes_type_filter:
        query = query.filter(
            exists().where(
                MachineTesType.id_machine == Machine.id,
                MachineTesType.year_number == current_year,
                MachineTesType.id_tes_type.in_(tes_type_filter)
            )
        )

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


def get_stations_all(
    energy_system_type_filter=None,
    union_energy_system_filter=None,
    regional_energy_system_filter=None,
    federal_district_filter=None,
    regional_district_filter=None,
    start_year=None,
    end_year=None,
):
    """
    Фильтрует станции по переданным параметрам и по диапазону лет (если заданы).
    Если заданы start_year и end_year, фильтруются только агрегаты с мощностью в указанный период.
    Также отбрасываются агрегаты с планируемым выводом до START_YEAR_SIPR.
    """
    query = db.session.query(Station).distinct().join(Station.machines)

    query = query.options(contains_eager(Station.machines))

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

    # Фильтрация по федеральному округу
    if federal_district_filter:
        if not isinstance(federal_district_filter, list):
            federal_district_filter = [federal_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.federal_district.has(
                    FederalDistrict.id.in_(federal_district_filter)
                )
            )
        )

    # Фильтрация по субъекту РФ
    if regional_district_filter:
        if not isinstance(regional_district_filter, list):
            regional_district_filter = [regional_district_filter]

        query = query.filter(
            Station.regional_district.has(
                RegionalDistrict.id.in_(regional_district_filter)
            )
        )

    # Фильтрация по годам, если заданы
    if start_year is not None and end_year is not None:
        query = query.join(Machine.machine_powers).filter(
            MachinePower.year_number.between(Config.START_YEAR_SIPR, Config.END_YEAR_SIPR)
        ).distinct()

    return query


def has_any_filters(args):
    return any([
        args.getlist('energy_system_type_filter'),
        args.getlist('union_energy_system_filter'),
        args.getlist('regional_energy_system_filter'),
        args.getlist('federal_district_filter'),
        args.getlist('regional_district_filter'),
        args.get('station_name_filter'),
        args.get('gen_company_filter'),
    ])