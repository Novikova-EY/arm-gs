from config import Config
from app.extensions import db
from collections import defaultdict
from sqlalchemy import or_, extract, and_, func
from sqlalchemy.sql import exists
from sqlalchemy.orm import contains_eager, joinedload
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.generation.services.station_services.station_services import (
    get_current_year
)


def extract_filters_from_args(args):
    return {
        "page": args.get("page", 1, type=int),
        "start_year": args.get("start_year", Config.START_YEAR, type=int),
        "end_year": args.get("end_year", Config.END_YEAR, type=int),
        "condition_type_filter": args.get("condition_type_filter", ""),
        "event_type_filter":args.getlist("event_type_filter"),
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
        "pgu_tes_machine_type_filter": args.getlist("pgu_tes_machine_type_filter", type=int),
        "date_exploitation_filter": args.getlist("date_exploitation_filter", type=int),
        "date_decompressing_expected_filter": args.getlist("date_decompressing_expected_filter", type=int),
        "date_modernization_expected_filter": args.getlist("date_modernization_expected_filter", type=int),
        "sort_by": args.get("sort_by", "id"),
        "sort_dir": args.get("sort_dir", "asc"),
    }


def extract_filters_from_form(form):
    return extract_filters_from_args(form)


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