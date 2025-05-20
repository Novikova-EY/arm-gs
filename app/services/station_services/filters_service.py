from config import Config
from app import db
from sqlalchemy.sql import exists
from sqlalchemy.orm import contains_eager
from app.models import (
    Station, Machine, MachineTesType, GenCompany,
    RegionalDistrict, RegionalEnergySystem, UnionEnergySystem,
    EnergySystemType, FederalDistrict
)
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


def filter_machines(
    stations,
    tes_type_filter,
    tes_machine_type_filter,
    fuel_type_filter,
    date_exploitation_filter,
    date_decompressing_expected_filter,
    date_modernization_expected_filter,
):
    if not any([
        tes_type_filter, tes_machine_type_filter,
        date_exploitation_filter, date_decompressing_expected_filter,
        date_modernization_expected_filter, fuel_type_filter
    ]):
        return stations

    current_year = get_current_year()

    # Получаем соответствие machine.id → tes_type_id
    machine_tes_types = (
        db.session.query(MachineTesType)
        .filter(MachineTesType.year_number == current_year)
        .all()
    )
    machine_tes_type_map = {
        mtt.id_machine: mtt.id_tes_type
        for mtt in machine_tes_types
    }

    # Приводим фильтры по годам к множествам int для удобства
    exploitation_years = set(map(int, date_exploitation_filter)) if date_exploitation_filter else set()
    decompressing_years = set(map(int, date_decompressing_expected_filter)) if date_decompressing_expected_filter else set()
    modernization_years = set(map(int, date_modernization_expected_filter)) if date_modernization_expected_filter else set()

    filtered_stations = []
    for station in stations:
        station.machines = [
            m for m in station.machines
            if (not tes_type_filter or machine_tes_type_map.get(m.id) in tes_type_filter)
            and (not tes_machine_type_filter or m.id_tes_machine_type in tes_machine_type_filter)
            and (not exploitation_years or (m.date_exploitation in exploitation_years))
            and (not decompressing_years or (m.date_decompressing_expected in decompressing_years))
            and (not modernization_years or (m.date_modernization_expected in modernization_years))
            and (
                not fuel_type_filter
                or any(
                    mf.fuel and mf.fuel.fuel_type and mf.fuel.fuel_type.id in fuel_type_filter
                    for mf in m.machine_fuels
                )
            )
        ] 

        if station.machines:
            filtered_stations.append(station)
        
    return filtered_stations


def get_filtered_stations_old(
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

