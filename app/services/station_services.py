from config import Config
from app import db
from app.services.logging_service import log_to_db
from decimal import Decimal
from collections import defaultdict
from sqlalchemy import func
from sqlalchemy.orm import joinedload
from app.models import (
    EnergyUnit, RegionalDistrict, Station, StationType, Machine, FuelType,
    MachinePower, MachineFuel, MachineTesType, ConditionType, MachineType, 
    TesType, TesMachineType,  Machine, StationPower, Fuel, GenCompany
)
from app.services.help_service import (
        get_current_year,
        get_station_types_list,
        get_gen_companies,
        get_gen_companies_list,
        get_station_groups,
        get_condition_type,
        get_station_types,
        get_machine_type,
        get_tes_types,
        get_tes_machine_types,
        get_fuel_types,
        get_energy_units,
        get_energy_system_types,
        get_union_energy_systems,
        get_regional_energy_systems,
        get_regional_districts,
        get_federal_districts,
        get_year_features,
        maybe_round,
        round_nested_power_dict,
    )
from app.services.filters_service import (
        get_filtered_station_ids,
        get_filtered_stations
    )
from app.services.groupped_service import (
        group_stations_hierarchy,
        group_machines_by_group_and_fuel
    )
from app.services.gen_company_services import (
        clean_name
)
from app.services.aggregation_services_energy_units import (
        aggregate_power_by_energy_unit,
        aggregate_energy_units_by_station_types,
        aggregate_energy_units_by_station_types_with_fuel,
        aggregate_energy_units_by_tes_types,
        aggregate_energy_units_by_tes_types_with_fuel,
        aggregate_energy_units_by_tes_machine_types,
        aggregate_energy_units_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services_regional_districts import (
        aggregate_power_by_regional_district,
        aggregate_regional_districts_by_station_types,
        aggregate_regional_districts_by_station_types_with_fuel,
        aggregate_regional_districts_by_tes_types,
        aggregate_regional_districts_by_tes_types_with_fuel,
        aggregate_regional_districts_by_tes_machine_types,
        aggregate_regional_districts_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services_regional_energy_systems import (
        aggregate_power_by_regional_energy_system,
        aggregate_regional_energy_systems_by_station_types,
        aggregate_regional_energy_systems_by_station_types_with_fuel,
        aggregate_regional_energy_systems_by_tes_types,
        aggregate_regional_energy_systems_by_tes_types_with_fuel,
        aggregate_regional_energy_systems_by_tes_machine_types,
        aggregate_regional_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services_union_energy_systems import (
        aggregate_power_by_union_energy_system,
        aggregate_union_energy_systems_by_station_types,
        aggregate_union_energy_systems_by_station_types_with_fuel,
        aggregate_union_energy_systems_by_tes_types,
        aggregate_union_energy_systems_by_tes_types_with_fuel,
        aggregate_union_energy_systems_by_tes_machine_types,
        aggregate_union_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services_energy_system_types import (
        aggregate_power_by_energy_system_type,
        aggregate_energy_system_types_by_station_types,
        aggregate_energy_system_types_by_station_types_with_fuel,
        aggregate_energy_system_types_by_tes_types,
        aggregate_energy_system_types_by_tes_types_with_fuel,
        aggregate_energy_system_types_by_tes_machine_types,
        aggregate_energy_system_types_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services_total_energy_system_types import (
        aggregate_power_by_total_energy_system_type,
        aggregate_total_energy_system_types_by_station_types,
        aggregate_total_energy_system_types_by_station_types_with_fuel,
        aggregate_total_energy_system_types_by_tes_types,
        aggregate_total_energy_system_types_by_tes_types_with_fuel,
        aggregate_total_energy_system_types_by_tes_machine_types,
        aggregate_total_energy_system_types_by_tes_machine_types_with_fuel,
    )

def get_stations_list(
    page=None,
    per_page=None,
    filters=None,
    rounding_digits=None,
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
    station_fuel_type_filter=None,
    sort_by=None,
    sort_dir=None,
):
    if filters is not None:
        station_query = (
            db.session.query(Station)
            .options(
                joinedload(Station.regional_district)
                    .joinedload(RegionalDistrict.regional_energy_systems),
                joinedload(Station.energy_unit),
                joinedload(Station.machines),
            )
        )

        station_query = station_query.filter(*filters)

        total_count = station_query.count()

        if per_page is None:
            stations = station_query.all()
            total_pages = 1
        else:
            stations = (
                station_query
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            total_pages = max(1, (total_count + per_page - 1) // per_page)

    else:
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

        total_count = db.session.query(func.count()).select_from(station_ids_subq).scalar()

        station_query = (
            db.session.query(Station)
            .options(
                joinedload(Station.regional_district)
                    .joinedload(RegionalDistrict.regional_energy_systems),
                joinedload(Station.energy_unit),
                joinedload(Station.machines),
            )
            .filter(
                Station.id.in_(db.session.query(station_ids_subq.c.id))
            )
        )

        if per_page is None:
            stations = station_query.all()
            total_pages = 1
        else:
            stations = (
                station_query
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            total_pages = max(1, (total_count + per_page - 1) // per_page)

    grouped_data = group_stations_hierarchy(stations, rounding_digits)

    return {
        "total_count": total_count,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "grouped_stations": grouped_data["grouped_stations"],
        "stations": grouped_data["stations"]
    }


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


def extract_filters_from_args(args):
    return {
        "page": args.get("page", 1, type=int),
        "per_page": None if args.get("per_page") == "all" else args.get("per_page", 10, type=int),
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
        "tes_type_filter": args.getlist("tes_type_filter", type=int),
        "tes_machine_type_filter": args.getlist("tes_machine_type_filter", type=int),
        "station_fuel_type_filter": args.get("station_fuel_type_filter", ""),
        "sort_by": args.get("sort_by", "id"),
        "sort_dir": args.get("sort_dir", "asc"),
    }


def extract_filters_from_form(form):
    return extract_filters_from_args(form)


def get_current_machine_tes_types_map():
    current_year = get_current_year()

    machine_tes_types = (
        db.session.query(MachineTesType)
        .options(joinedload(MachineTesType.tes_type))
        .filter(MachineTesType.year_number == current_year)
        .all()
    )

    return {mtt.id_machine: mtt for mtt in machine_tes_types}


def get_station_types_str_by_station(station_id):
    types = (
        db.session.query(StationType.name)
        .join(Machine, Machine.id_station_type == StationType.id)
        .filter(Machine.id_station == station_id)
        .filter(Machine.id_station_type != None)
        .distinct()
        .order_by(StationType.name)
        .all()
    )
    return ", ".join(name for (name,) in types)


def filter_machines(stations, tes_type_filter, tes_machine_type_filter):
    if not tes_type_filter and not tes_machine_type_filter:
        return stations

    current_year = get_current_year()

    # Получаем мапу id_машины -> tes_type_id (только для текущего года)
    machine_tes_types = (
        db.session.query(MachineTesType)
        .filter(MachineTesType.year_number == current_year)
        .all()
    )
    machine_tes_type_map = {
        mtt.id_machine: mtt.id_tes_type
        for mtt in machine_tes_types
    }

    filtered_stations = []
    for station in stations:
        station.machines = [
            m for m in station.machines
            if (not tes_type_filter or machine_tes_type_map.get(m.id) in tes_type_filter) and
               (not tes_machine_type_filter or m.id_tes_machine_type in tes_machine_type_filter)
        ]
        if station.machines:
            filtered_stations.append(station)

    return filtered_stations


def load_station_power_by_year(station, start_year=None, end_year=None, rounding_digits=None):
    query = StationPower.query.filter_by(id_station=station.id)

    if start_year is not None:
        query = query.filter(StationPower.year_number >= start_year)
    if end_year is not None:
        query = query.filter(StationPower.year_number <= end_year)

    result = query.all()

    return {
        sp.year_number: {
            "p_ust": maybe_round(sp.p_ust, rounding_digits),
            "p_ogr": maybe_round(sp.p_ogr, rounding_digits),
            "p_rasp": maybe_round(sp.p_rasp, rounding_digits)
        }
        for sp in result
    }


def load_machines_power_by_year(machines, start_year=None, end_year=None, rounding_digits=1):
    machine_ids = [machine.id for machine in machines]
    query = MachinePower.query.filter(MachinePower.id_machine.in_(machine_ids))

    if start_year is not None:
        query = query.filter(MachinePower.year_number >= start_year)
    if end_year is not None:
        query = query.filter(MachinePower.year_number <= end_year)

    machine_powers = query.all()

    powers_by_machine = defaultdict(list)
    for mp in machine_powers:
        # СРАЗУ округляем загруженные мощности
        mp.p_ust = maybe_round(mp.p_ust, rounding_digits)
        mp.p_ogr = maybe_round(mp.p_ogr, rounding_digits)
        mp.p_rasp = maybe_round(mp.p_rasp, rounding_digits)
        powers_by_machine[mp.id_machine].append(mp)

    for machine in machines:
        machine.machine_powers = powers_by_machine.get(machine.id, [])


def get_station_list_template_context(form, pagination, rounding_digits, filters):
    year_features = get_year_features()
    energy_system_type_list, energy_system_type_names = get_energy_system_types()
    union_energy_system_list, union_energy_system_names, regional_energy_system_mapping = get_union_energy_systems()
    regional_energy_system_list, regional_energy_system_names = get_regional_energy_systems()
    federal_district_list, regional_district_mapping = get_federal_districts()
    regional_district_list, regional_district_names = get_regional_districts()
    regional_district_dict = {int(r["id"]): r for r in regional_district_list}
    
    energy_units = get_energy_units()
    energy_unit_names = {eu.id: eu.name for eu in energy_units}
    
    station_type_names = get_station_types()
    station_type_list = {st.id: st.name for st in station_type_names}

    tes_type_names = get_tes_types()
    tes_type_list = {tt.id: tt.name for tt in tes_type_names}

    tes_machine_type_names = get_tes_machine_types()
    tes_machine_type_list = {tmt.id: tmt.name for tmt in tes_machine_type_names}

    fuel_type_names = get_fuel_types()
    fuel_type_list = {ft.id: ft.name for ft in fuel_type_names}

    machine_tes_types_map = get_current_machine_tes_types_map()

    energy_units_power = aggregate_power_by_energy_unit(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_units_by_station_types_power = aggregate_energy_units_by_station_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_units_by_station_types_with_fuel_power = aggregate_energy_units_by_station_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_units_by_tes_types_power = aggregate_energy_units_by_tes_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_units_by_tes_machine_types_power = aggregate_energy_units_by_tes_machine_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_units_by_tes_types_with_fuel_power = aggregate_energy_units_by_tes_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_units_by_tes_machine_types_with_fuel_power = aggregate_energy_units_by_tes_machine_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))

    regional_districts_power = aggregate_power_by_regional_district(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_districts_by_station_types_power = aggregate_regional_districts_by_station_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_districts_by_station_types_with_fuel_power = aggregate_regional_districts_by_station_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_districts_by_tes_types_power = aggregate_regional_districts_by_tes_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_districts_by_tes_machine_types_power = aggregate_regional_districts_by_tes_machine_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_districts_by_tes_types_with_fuel_power = aggregate_regional_districts_by_tes_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_districts_by_tes_machine_types_with_fuel_power = aggregate_regional_districts_by_tes_machine_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))

    regional_energy_systems_power = aggregate_power_by_regional_energy_system(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_energy_systems_by_station_types_power = aggregate_regional_energy_systems_by_station_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_energy_systems_by_station_types_with_fuel_power = aggregate_regional_energy_systems_by_station_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_energy_systems_by_tes_types_power = aggregate_regional_energy_systems_by_tes_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_energy_systems_by_tes_machine_types_power = aggregate_regional_energy_systems_by_tes_machine_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_energy_systems_by_tes_types_with_fuel_power = aggregate_regional_energy_systems_by_tes_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    regional_energy_systems_by_tes_machine_types_with_fuel_power = aggregate_regional_energy_systems_by_tes_machine_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))

    union_energy_systems_power = aggregate_power_by_union_energy_system(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    union_energy_systems_by_station_types_power = aggregate_union_energy_systems_by_station_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    union_energy_systems_by_station_types_with_fuel_power = aggregate_union_energy_systems_by_station_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    union_energy_systems_by_tes_types_power = aggregate_union_energy_systems_by_tes_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    union_energy_systems_by_tes_machine_types_power = aggregate_union_energy_systems_by_tes_machine_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    union_energy_systems_by_tes_types_with_fuel_power = aggregate_union_energy_systems_by_tes_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    union_energy_systems_by_tes_machine_types_with_fuel_power = aggregate_union_energy_systems_by_tes_machine_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))

    energy_system_types_power = aggregate_power_by_energy_system_type(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_system_types_by_station_types_power = aggregate_energy_system_types_by_station_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_system_types_by_station_types_with_fuel_power = aggregate_energy_system_types_by_station_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_system_types_by_tes_types_power = aggregate_energy_system_types_by_tes_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_system_types_by_tes_machine_types_power = aggregate_energy_system_types_by_tes_machine_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_system_types_by_tes_types_with_fuel_power = aggregate_energy_system_types_by_tes_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    energy_system_types_by_tes_machine_types_with_fuel_power = aggregate_energy_system_types_by_tes_machine_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))

    total_energy_system_types_power = aggregate_power_by_total_energy_system_type(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    total_energy_system_types_by_station_types_power = aggregate_total_energy_system_types_by_station_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    total_energy_system_types_by_station_types_with_fuel_power = aggregate_total_energy_system_types_by_station_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    total_energy_system_types_by_tes_types_power = aggregate_total_energy_system_types_by_tes_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    total_energy_system_types_by_tes_machine_types_power = aggregate_total_energy_system_types_by_tes_machine_types(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    total_energy_system_types_by_tes_types_with_fuel_power = aggregate_total_energy_system_types_by_tes_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))
    total_energy_system_types_by_tes_machine_types_with_fuel_power = aggregate_total_energy_system_types_by_tes_machine_types_with_fuel(pagination, rounding_digits, filters.get("start_year"), filters.get("end_year"))

    return {
        "form": form,
        "stations_grouped": pagination["grouped_stations"],
        "total_count": pagination["total_count"],
        "total_pages": pagination["total_pages"],
        "current_page": pagination["page"],
        "per_page": pagination["per_page"],
        "start_year": filters.get("start_year"),
        "end_year": filters.get("end_year"),
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
        "regional_district_dict": regional_district_dict,
        "regional_district_mapping": regional_district_mapping,
        "station_type_name": station_type_names,
        "station_type_list": station_type_list,
        "tes_type_names": tes_type_names,
        "tes_type_list": tes_type_list,
        "fuel_type_names": fuel_type_names,
        "fuel_type_list": fuel_type_list,
        "tes_machine_type_list": tes_machine_type_list,
        "tes_machine_type_names": tes_machine_type_names,
        "condition_type_filter": filters.get("condition_type_filter"),
        "gen_company_filter": filters.get("gen_company_filter"),
        "station_name_filter": filters.get("station_name_filter"),
        "station_type_filter": filters.get("station_type_filter"),
        "tes_type_filter": filters.get("tes_type_filter"),
        "tes_machine_type_filter": filters.get("tes_machine_type_filter"),
        "energy_system_type_filter": filters.get("energy_system_type_filter"),
        "union_energy_system_filter": filters.get("union_energy_system_filter"),
        "regional_energy_system_filter": filters.get("regional_energy_system_filter"),
        "federal_district_filter": filters.get("federal_district_filter"),
        "regional_district_filter": filters.get("regional_district_filter"),
        "station_fuel_type_filter": filters.get("station_fuel_type_filter"),
        "year_features": year_features,
        "machine_tes_types_map": machine_tes_types_map,
        "energy_unit_names": energy_unit_names,

        "energy_units_yearly_p_ust": energy_units_power['aggregated']['p_ust'],
        "energy_units_yearly_p_ogr": energy_units_power['aggregated']['p_ogr'],
        "energy_units_yearly_p_rasp": energy_units_power['aggregated']['p_rasp'],

        "energy_units_by_station_types_yearly_p_ust": energy_units_by_station_types_power["aggregated"]["p_ust"],
        "energy_units_by_station_types_yearly_p_ogr": energy_units_by_station_types_power["aggregated"]["p_ogr"],
        "energy_units_by_station_types_yearly_p_rasp": energy_units_by_station_types_power["aggregated"]["p_rasp"],

        "energy_units_by_station_types_with_fuel_yearly_p_ust": energy_units_by_station_types_with_fuel_power["aggregated"]["p_ust"],
        "energy_units_by_station_types_with_fuel_yearly_p_ogr": energy_units_by_station_types_with_fuel_power["aggregated"]["p_ogr"],
        "energy_units_by_station_types_with_fuel_yearly_p_rasp": energy_units_by_station_types_with_fuel_power["aggregated"]["p_rasp"],

        "energy_units_by_tes_types_yearly_p_ust": energy_units_by_tes_types_power["aggregated"]["p_ust"],
        "energy_units_by_tes_types_yearly_p_ogr": energy_units_by_tes_types_power["aggregated"]["p_ogr"],
        "energy_units_by_tes_types_yearly_p_rasp": energy_units_by_tes_types_power["aggregated"]["p_rasp"],

        "energy_units_by_tes_types_with_fuel_yearly_p_ust": energy_units_by_tes_types_with_fuel_power["aggregated"]["p_ust"],
        "energy_units_by_tes_types_with_fuel_yearly_p_ogr": energy_units_by_tes_types_with_fuel_power["aggregated"]["p_ogr"],
        "energy_units_by_tes_types_with_fuel_yearly_p_rasp": energy_units_by_tes_types_with_fuel_power["aggregated"]["p_rasp"],

        "energy_units_by_tes_machine_types_yearly_p_ust": energy_units_by_tes_machine_types_power["aggregated"]["p_ust"],
        "energy_units_by_tes_machine_types_yearly_p_ogr": energy_units_by_tes_machine_types_power["aggregated"]["p_ogr"],
        "energy_units_by_tes_machine_types_yearly_p_rasp": energy_units_by_tes_machine_types_power["aggregated"]["p_rasp"],

        "energy_units_by_tes_machine_types_with_fuel_yearly_p_ust": energy_units_by_tes_machine_types_with_fuel_power["aggregated"]["p_ust"],
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_ogr": energy_units_by_tes_machine_types_with_fuel_power["aggregated"]["p_ogr"],
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_rasp": energy_units_by_tes_machine_types_with_fuel_power["aggregated"]["p_rasp"],

        "regional_districts_yearly_p_ust": regional_districts_power['aggregated']['p_ust'],
        "regional_districts_yearly_p_ogr": regional_districts_power['aggregated']['p_ogr'],
        "regional_districts_yearly_p_rasp": regional_districts_power['aggregated']['p_rasp'],

        "regional_districts_by_station_types_yearly_p_ust": regional_districts_by_station_types_power["aggregated"]["p_ust"],
        "regional_districts_by_station_types_yearly_p_ogr": regional_districts_by_station_types_power["aggregated"]["p_ogr"],
        "regional_districts_by_station_types_yearly_p_rasp": regional_districts_by_station_types_power["aggregated"]["p_rasp"],

        "regional_districts_by_station_types_with_fuel_yearly_p_ust": regional_districts_by_station_types_with_fuel_power["aggregated"]["p_ust"],
        "regional_districts_by_station_types_with_fuel_yearly_p_ogr": regional_districts_by_station_types_with_fuel_power["aggregated"]["p_ogr"],
        "regional_districts_by_station_types_with_fuel_yearly_p_rasp": regional_districts_by_station_types_with_fuel_power["aggregated"]["p_rasp"],

        "regional_districts_by_tes_types_yearly_p_ust": regional_districts_by_tes_types_power["aggregated"]["p_ust"],
        "regional_districts_by_tes_types_yearly_p_ogr": regional_districts_by_tes_types_power["aggregated"]["p_ogr"],
        "regional_districts_by_tes_types_yearly_p_rasp": regional_districts_by_tes_types_power["aggregated"]["p_rasp"],

        "regional_districts_by_tes_types_with_fuel_yearly_p_ust": regional_districts_by_tes_types_with_fuel_power["aggregated"]["p_ust"],
        "regional_districts_by_tes_types_with_fuel_yearly_p_ogr": regional_districts_by_tes_types_with_fuel_power["aggregated"]["p_ogr"],
        "regional_districts_by_tes_types_with_fuel_yearly_p_rasp": regional_districts_by_tes_types_with_fuel_power["aggregated"]["p_rasp"],

        "regional_districts_by_tes_machine_types_yearly_p_ust": regional_districts_by_tes_machine_types_power["aggregated"]["p_ust"],
        "regional_districts_by_tes_machine_types_yearly_p_ogr": regional_districts_by_tes_machine_types_power["aggregated"]["p_ogr"],
        "regional_districts_by_tes_machine_types_yearly_p_rasp": regional_districts_by_tes_machine_types_power["aggregated"]["p_rasp"],

        "regional_districts_by_tes_machine_types_with_fuel_yearly_p_ust": regional_districts_by_tes_machine_types_with_fuel_power["aggregated"]["p_ust"],
        "regional_districts_by_tes_machine_types_with_fuel_yearly_p_ogr": regional_districts_by_tes_machine_types_with_fuel_power["aggregated"]["p_ogr"],
        "regional_districts_by_tes_machine_types_with_fuel_yearly_p_rasp": regional_districts_by_tes_machine_types_with_fuel_power["aggregated"]["p_rasp"],

        "regional_energy_systems_yearly_p_ust": regional_energy_systems_power['aggregated']['p_rasp'],
        "regional_energy_systems_yearly_p_ogr": regional_energy_systems_power['aggregated']['p_ogr'],
        "regional_energy_systems_yearly_p_rasp": regional_energy_systems_power['aggregated']['p_rasp'],

        "regional_energy_systems_by_station_types_yearly_p_ust": regional_energy_systems_by_station_types_power["aggregated"]["p_ust"],
        "regional_energy_systems_by_station_types_yearly_p_ogr": regional_energy_systems_by_station_types_power["aggregated"]["p_ogr"],
        "regional_energy_systems_by_station_types_yearly_p_rasp": regional_energy_systems_by_station_types_power["aggregated"]["p_rasp"],

        "regional_energy_systems_by_station_types_with_fuel_yearly_p_ust": regional_energy_systems_by_station_types_with_fuel_power["aggregated"]["p_ust"],
        "regional_energy_systems_by_station_types_with_fuel_yearly_p_ogr": regional_energy_systems_by_station_types_with_fuel_power["aggregated"]["p_ogr"],
        "regional_energy_systems_by_station_types_with_fuel_yearly_p_rasp": regional_energy_systems_by_station_types_with_fuel_power["aggregated"]["p_rasp"],

        "regional_energy_systems_by_tes_types_yearly_p_ust": regional_energy_systems_by_tes_types_power["aggregated"]["p_ust"],
        "regional_energy_systems_by_tes_types_yearly_p_ogr": regional_energy_systems_by_tes_types_power["aggregated"]["p_ogr"],
        "regional_energy_systems_by_tes_types_yearly_p_rasp": regional_energy_systems_by_tes_types_power["aggregated"]["p_rasp"],

        "regional_energy_systems_by_tes_types_with_fuel_yearly_p_ust": regional_energy_systems_by_tes_types_with_fuel_power["aggregated"]["p_ust"],
        "regional_energy_systems_by_tes_types_with_fuel_yearly_p_ogr": regional_energy_systems_by_tes_types_with_fuel_power["aggregated"]["p_ogr"],
        "regional_energy_systems_by_tes_types_with_fuel_yearly_p_rasp": regional_energy_systems_by_tes_types_with_fuel_power["aggregated"]["p_rasp"],

        "regional_energy_systems_by_tes_machine_types_yearly_p_ust": regional_energy_systems_by_tes_machine_types_power["aggregated"]["p_ust"],
        "regional_energy_systems_by_tes_machine_types_yearly_p_ogr": regional_energy_systems_by_tes_machine_types_power["aggregated"]["p_ogr"],
        "regional_energy_systems_by_tes_machine_types_yearly_p_rasp": regional_energy_systems_by_tes_machine_types_power["aggregated"]["p_rasp"],

        "regional_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ust": regional_energy_systems_by_tes_machine_types_with_fuel_power["aggregated"]["p_ust"],
        "regional_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ogr": regional_energy_systems_by_tes_machine_types_with_fuel_power["aggregated"]["p_ogr"],
        "regional_energy_systems_by_tes_machine_types_with_fuel_yearly_p_rasp": regional_energy_systems_by_tes_machine_types_with_fuel_power["aggregated"]["p_rasp"],
        
        "union_energy_systems_yearly_p_ust": union_energy_systems_power["aggregated"]["p_ust"],
        "union_energy_systems_yearly_p_ogr": union_energy_systems_power["aggregated"]["p_ogr"],
        "union_energy_systems_yearly_p_rasp": union_energy_systems_power["aggregated"]["p_rasp"],

        "union_energy_systems_by_station_types_yearly_p_ust": union_energy_systems_by_station_types_power["aggregated"]["p_ust"],
        "union_energy_systems_by_station_types_yearly_p_ogr": union_energy_systems_by_station_types_power["aggregated"]["p_ogr"],
        "union_energy_systems_by_station_types_yearly_p_rasp": union_energy_systems_by_station_types_power["aggregated"]["p_rasp"],

        "union_energy_systems_by_station_types_with_fuel_yearly_p_ust": union_energy_systems_by_station_types_with_fuel_power["aggregated"]["p_ust"],
        "union_energy_systems_by_station_types_with_fuel_yearly_p_ogr": union_energy_systems_by_station_types_with_fuel_power["aggregated"]["p_ogr"],
        "union_energy_systems_by_station_types_with_fuel_yearly_p_rasp": union_energy_systems_by_station_types_with_fuel_power["aggregated"]["p_rasp"],

        "union_energy_systems_by_tes_types_yearly_p_ust": union_energy_systems_by_tes_types_power["aggregated"]["p_ust"],
        "union_energy_systems_by_tes_types_yearly_p_ogr": union_energy_systems_by_tes_types_power["aggregated"]["p_ogr"],
        "union_energy_systems_by_tes_types_yearly_p_rasp": union_energy_systems_by_tes_types_power["aggregated"]["p_rasp"],

        "union_energy_systems_by_tes_types_with_fuel_yearly_p_ust": union_energy_systems_by_tes_types_with_fuel_power["aggregated"]["p_ust"],
        "union_energy_systems_by_tes_types_with_fuel_yearly_p_ogr": union_energy_systems_by_tes_types_with_fuel_power["aggregated"]["p_ogr"],
        "union_energy_systems_by_tes_types_with_fuel_yearly_p_rasp": union_energy_systems_by_tes_types_with_fuel_power["aggregated"]["p_rasp"],

        "union_energy_systems_by_tes_machine_types_yearly_p_ust": union_energy_systems_by_tes_machine_types_power["aggregated"]["p_ust"],
        "union_energy_systems_by_tes_machine_types_yearly_p_ogr": union_energy_systems_by_tes_machine_types_power["aggregated"]["p_ogr"],
        "union_energy_systems_by_tes_machine_types_yearly_p_rasp": union_energy_systems_by_tes_machine_types_power["aggregated"]["p_rasp"],

        "union_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ust": union_energy_systems_by_tes_machine_types_with_fuel_power["aggregated"]["p_ust"],
        "union_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ogr": union_energy_systems_by_tes_machine_types_with_fuel_power["aggregated"]["p_ogr"],
        "union_energy_systems_by_tes_machine_types_with_fuel_yearly_p_rasp": union_energy_systems_by_tes_machine_types_with_fuel_power["aggregated"]["p_rasp"],

        "energy_system_types_yearly_p_ust": energy_system_types_power["aggregated"]["p_ust"],
        "energy_system_types_yearly_p_ogr": energy_system_types_power["aggregated"]["p_ogr"],
        "energy_system_types_yearly_p_rasp": energy_system_types_power["aggregated"]["p_rasp"],

        "energy_system_types_by_station_types_yearly_p_ust": energy_system_types_by_station_types_power["aggregated"]["p_ust"],
        "energy_system_types_by_station_types_yearly_p_ogr": energy_system_types_by_station_types_power["aggregated"]["p_ogr"],
        "energy_system_types_by_station_types_yearly_p_rasp": energy_system_types_by_station_types_power["aggregated"]["p_rasp"],

        "energy_system_types_by_station_types_with_fuel_yearly_p_ust": energy_system_types_by_station_types_with_fuel_power["aggregated"]["p_ust"],
        "energy_system_types_by_station_types_with_fuel_yearly_p_ogr": energy_system_types_by_station_types_with_fuel_power["aggregated"]["p_ogr"],
        "energy_system_types_by_station_types_with_fuel_yearly_p_rasp": energy_system_types_by_station_types_with_fuel_power["aggregated"]["p_rasp"],

        "energy_system_types_by_tes_types_yearly_p_ust": energy_system_types_by_tes_types_power["aggregated"]["p_ust"],
        "energy_system_types_by_tes_types_yearly_p_ogr": energy_system_types_by_tes_types_power["aggregated"]["p_ogr"],
        "energy_system_types_by_tes_types_yearly_p_rasp": energy_system_types_by_tes_types_power["aggregated"]["p_rasp"],

        "energy_system_types_by_tes_types_with_fuel_yearly_p_ust": energy_system_types_by_tes_types_with_fuel_power["aggregated"]["p_ust"],
        "energy_system_types_by_tes_types_with_fuel_yearly_p_ogr": energy_system_types_by_tes_types_with_fuel_power["aggregated"]["p_ogr"],
        "energy_system_types_by_tes_types_with_fuel_yearly_p_rasp": energy_system_types_by_tes_types_with_fuel_power["aggregated"]["p_rasp"],

        "energy_system_types_by_tes_machine_types_yearly_p_ust": energy_system_types_by_tes_machine_types_power["aggregated"]["p_ust"],
        "energy_system_types_by_tes_machine_types_yearly_p_ogr": energy_system_types_by_tes_machine_types_power["aggregated"]["p_ogr"],
        "energy_system_types_by_tes_machine_types_yearly_p_rasp": energy_system_types_by_tes_machine_types_power["aggregated"]["p_rasp"],

        "energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust": energy_system_types_by_tes_machine_types_with_fuel_power["aggregated"]["p_ust"],
        "energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ogr": energy_system_types_by_tes_machine_types_with_fuel_power["aggregated"]["p_ogr"],
        "energy_system_types_by_tes_machine_types_with_fuel_yearly_p_rasp": energy_system_types_by_tes_machine_types_with_fuel_power["aggregated"]["p_rasp"],

        "total_energy_system_types_yearly_p_ust": total_energy_system_types_power["aggregated"]["p_ust"],
        "total_energy_system_types_yearly_p_ogr": total_energy_system_types_power["aggregated"]["p_ogr"],
        "total_energy_system_types_yearly_p_rasp": total_energy_system_types_power["aggregated"]["p_rasp"],

        "total_energy_system_types_by_station_types_yearly_p_ust": total_energy_system_types_by_station_types_power["aggregated"]["p_ust"],
        "total_energy_system_types_by_station_types_yearly_p_ogr": total_energy_system_types_by_station_types_power["aggregated"]["p_ogr"],
        "total_energy_system_types_by_station_types_yearly_p_rasp": total_energy_system_types_by_station_types_power["aggregated"]["p_rasp"],

        "total_energy_system_types_by_station_types_with_fuel_yearly_p_ust": total_energy_system_types_by_station_types_with_fuel_power["aggregated"]["p_ust"],
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_ogr": total_energy_system_types_by_station_types_with_fuel_power["aggregated"]["p_ogr"],
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_rasp": total_energy_system_types_by_station_types_with_fuel_power["aggregated"]["p_rasp"],

        "total_energy_system_types_by_tes_types_yearly_p_ust": total_energy_system_types_by_tes_types_power["aggregated"]["p_ust"],
        "total_energy_system_types_by_tes_types_yearly_p_ogr": total_energy_system_types_by_tes_types_power["aggregated"]["p_ogr"],
        "total_energy_system_types_by_tes_types_yearly_p_rasp": total_energy_system_types_by_tes_types_power["aggregated"]["p_rasp"],

        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_ust": total_energy_system_types_by_tes_types_with_fuel_power["aggregated"]["p_ust"],
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_ogr": total_energy_system_types_by_tes_types_with_fuel_power["aggregated"]["p_ogr"],
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_rasp": total_energy_system_types_by_tes_types_with_fuel_power["aggregated"]["p_rasp"],

        "total_energy_system_types_by_tes_machine_types_yearly_p_ust": total_energy_system_types_by_tes_machine_types_power["aggregated"]["p_ust"],
        "total_energy_system_types_by_tes_machine_types_yearly_p_ogr": total_energy_system_types_by_tes_machine_types_power["aggregated"]["p_ogr"],
        "total_energy_system_types_by_tes_machine_types_yearly_p_rasp": total_energy_system_types_by_tes_machine_types_power["aggregated"]["p_rasp"],

        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust": total_energy_system_types_by_tes_machine_types_with_fuel_power["aggregated"]["p_ust"],
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ogr": total_energy_system_types_by_tes_machine_types_with_fuel_power["aggregated"]["p_ogr"],
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_rasp": total_energy_system_types_by_tes_machine_types_with_fuel_power["aggregated"]["p_rasp"],

        
    }


def recalculate_station_power(station, start_year, end_year):
    # Готовим агрегаторы по годам
    power_by_year = {
        year: {"p_ust": 0.0, "p_ogr": 0.0, "p_rasp": 0.0}
        for year in range(start_year, end_year + 1)
    }

    for machine in station.machines:
        for mp in machine.machine_powers:
            year = mp.year.number
            if start_year <= year <= end_year:
                power_by_year[year]["p_ust"] += mp.p_ust or 0
                power_by_year[year]["p_ogr"] += mp.p_ogr or 0
                power_by_year[year]["p_rasp"] += mp.p_rasp or 0

    # Загружаем или создаём StationPower по годам
    existing_spowers = {
        sp.year_number: sp
        for sp in StationPower.query.filter_by(id_station=station.id)
        .filter(StationPower.year_number.in_(range(start_year, end_year + 1)))
        .all()
    }

    for year, values in power_by_year.items():
        if year in existing_spowers:
            sp = existing_spowers[year]
            sp.p_ust = values["p_ust"]
            sp.p_ogr = values["p_ogr"]
            sp.p_rasp = values["p_rasp"]
        else:
            sp = StationPower(
                id_station=station.id,
                year_number=year,
                p_ust=values["p_ust"],
                p_ogr=values["p_ogr"],
                p_rasp=values["p_rasp"],
            )
            db.session.add(sp)

    db.session.commit()


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
                energy_unit = EnergyUnit.query.filter_by(name=regional_district_name).first()
                print("energy_unit=", energy_unit)
                if energy_unit:
                    regional_district = energy_unit.regional_district if energy_unit.regional_district else None
                    print(f"[!] Регион '{regional_district}' не найден напрямую, получен из EnergyUnit ID={energy_unit.id}")

            station_name = clean_name(row['station_name'])
            station = Station.query.filter_by(name=station_name).first()

            condition_type = ConditionType.query.filter_by(name="действующий").first()

            if not station:
                station = Station(
                    name=station_name,
                    id_regional_district=regional_district.id if regional_district else None,
                    id_condition_type=condition_type.id if condition_type else None,
                    id_energy_unit=energy_unit.id if energy_unit else safe_lookup(EnergyUnit, 'id', 100, cleaner=None),
                )
                db.session.add(station)
                db.session.commit()
                log_to_db(user, "Создание станции", f"Создана станция: {station_name}")
                print("Создана электростанция", station_name)
            else:
                changes = {}
                if station.id_regional_district != (regional_district.id if regional_district else None):
                    changes['id_regional_district'] = regional_district.id if regional_district else None
                
                if station.id_energy_unit != (energy_unit.id if energy_unit else None):
                    changes['id_energy_unit'] = energy_unit.id if energy_unit else None

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

                # Расчёт и обновление StationPower после обработки всех машин станции ===
                for year in range(start_year, end_year + 1):
                    total_values = db.session.query(
                        db.func.sum(MachinePower.p_ust).label("total_p_ust"),
                        db.func.sum(MachinePower.p_ogr).label("total_p_ogr"),
                        db.func.sum(MachinePower.p_rasp).label("total_p_rasp")
                    ).join(Machine).filter(
                        Machine.id_station == current_station.id,
                        MachinePower.year_number == year
                    ).first()

                    total_p_ust = total_values.total_p_ust or 0
                    total_p_ogr = total_values.total_p_ogr or 0
                    total_p_rasp = total_values.total_p_rasp or 0

                    station_power = StationPower.query.filter_by(id_station=current_station.id, year_number=year).first()
                    if station_power:
                        updates = []
                        if station_power.p_ust != total_p_ust:
                            updates.append(f"p_ust {station_power.p_ust} → {total_p_ust}")
                            station_power.p_ust = total_p_ust
                        if station_power.p_ogr != total_p_ogr:
                            updates.append(f"p_ogr {station_power.p_ogr} → {total_p_ogr}")
                            station_power.p_ogr = total_p_ogr
                        if station_power.p_rasp != total_p_rasp:
                            updates.append(f"p_rasp {station_power.p_rasp} → {total_p_rasp}")
                            station_power.p_rasp = total_p_rasp

                        if updates:
                            log_to_db(user, "Обновление мощности станции",
                                    f"Станция: {current_station.name}, год {year}: " + ", ".join(updates))
                    else:
                        station_power = StationPower(
                            id_station=current_station.id,
                            year_number=year,
                            p_ust=total_p_ust,
                            p_ogr=total_p_ogr,
                            p_rasp=total_p_rasp
                        )
                        db.session.add(station_power)
                        log_to_db(user, "Создание мощности станции",
                                f"Станция: {current_station.name}, год {year}: p_ust {total_p_ust}, "
                                f"p_ogr {total_p_ogr}, p_rasp {total_p_rasp}")

                    print(f"Станция {current_station.name}, год {year} — p_ust: {total_p_ust}, p_ogr: {total_p_ogr}, p_rasp: {total_p_rasp}")

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


def convert_to_iso_date(value):
    """
    Преобразует введённую строку в нужный формат:
      - YYYY → возвращается как есть
      - DD.MM.YYYY → преобразуется в YYYY-MM-DD
      - YYYY-MM-DD → возвращается как есть (если корректно)
      - None/пусто → None
    """
    if not value or not value.strip():
        return None

    value = value.strip()

    # Если только год (YYYY)
    if re.match(r'^\d{4}$', value):
        return value

    # Если уже ISO-формат YYYY-MM-DD
    if re.match(r'^\d{4}-\d{2}-\d{2}$', value):
        try:
            datetime.strptime(value, '%Y-%m-%d')  # просто проверка
            return value
        except ValueError:
            raise ValueError("Некорректный формат даты. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.")

    # Если формат DD.MM.YYYY
    try:
        date_obj = datetime.strptime(value, '%d.%m.%Y')
        return date_obj.strftime('%Y-%m-%d')
    except ValueError:
        raise ValueError("Некорректный формат даты. Используйте YYYY, DD.MM.YYYY или YYYY-MM-DD.")

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





