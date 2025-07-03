
from app import db
from decimal import Decimal
from app.services.logging_services.logging_service import log_to_db
from collections import defaultdict
from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload, joinedload
from sqlalchemy.sql import exists
from app.models import *
from app.services.station_services.help_services import (
    get_current_year,
    get_station_types,
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
    )
from app.services.station_services.filters_services import (
    get_filtered_station_ids,
    extract_filters_from_args,
    extract_filters_from_form,
    )
from app.services.station_services.groupped_services import (
    get_station_hierarchy_aggregates,
    build_hierarchy_structure,
    fetch_machines_with_rowspans,
    )
from app.services.aggregation_services.aggregation_services_common import (
    aggregate_level_with_total,
    get_all_aggregations
    )

from app.services.aggregation_services.aggregation_services_energy_units import (
    aggregate_power_by_energy_units,
    aggregate_energy_units_by_station_types,
    aggregate_energy_units_by_station_types_with_fuel,
    aggregate_energy_units_by_tes_types,
    aggregate_energy_units_by_tes_types_with_fuel,
    aggregate_energy_units_by_tes_machine_types,
    aggregate_energy_units_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services.aggregation_services_regional_districts import (
    aggregate_power_by_regional_districts,
    aggregate_regional_districts_by_station_types,
    aggregate_regional_districts_by_station_types_with_fuel,
    aggregate_regional_districts_by_tes_types,
    aggregate_regional_districts_by_tes_types_with_fuel,
    aggregate_regional_districts_by_tes_machine_types,
    aggregate_regional_districts_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services.aggregation_services_regional_energy_systems import (
    aggregate_power_by_regional_energy_systems,
    aggregate_regional_energy_systems_by_station_types,
    aggregate_regional_energy_systems_by_station_types_with_fuel,
    aggregate_regional_energy_systems_by_tes_types,
    aggregate_regional_energy_systems_by_tes_types_with_fuel,
    aggregate_regional_energy_systems_by_tes_machine_types,
    aggregate_regional_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services.aggregation_services_union_energy_systems import (
    aggregate_power_by_union_energy_systems,
    aggregate_union_energy_systems_by_station_types,
    aggregate_union_energy_systems_by_station_types_with_fuel,
    aggregate_union_energy_systems_by_tes_types,
    aggregate_union_energy_systems_by_tes_types_with_fuel,
    aggregate_union_energy_systems_by_tes_machine_types,
    aggregate_union_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services.aggregation_services_energy_system_types import (
    aggregate_power_by_energy_system_types,
    aggregate_energy_system_types_by_station_types,
    aggregate_energy_system_types_by_station_types_with_fuel,
    aggregate_energy_system_types_by_tes_types,
    aggregate_energy_system_types_by_tes_types_with_fuel,
    aggregate_energy_system_types_by_tes_machine_types,
    aggregate_energy_system_types_by_tes_machine_types_with_fuel,
    )
from app.services.aggregation_services.aggregation_services_total_energy_system_types import (
    aggregate_power_by_total_energy_system_types,
    aggregate_total_energy_system_types_by_station_types,
    aggregate_total_energy_system_types_by_station_types_with_fuel,
    aggregate_total_energy_system_types_by_tes_types,
    aggregate_total_energy_system_types_by_tes_types_with_fuel,
    aggregate_total_energy_system_types_by_tes_machine_types,
    aggregate_total_energy_system_types_by_tes_machine_types_with_fuel,
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

    # 4. Подсчёт и пагинация
    total_count = station_ids_query.count()

    if isinstance(per_page, str) and per_page.lower() == "all":
        station_ids = [row[0] for row in station_ids_query.all()]
    else:
        per_page = int(per_page or 10)
        offset = (page - 1) * per_page
        station_ids = [row[0] for row in station_ids_query.offset(offset).limit(per_page).all()]

    if not station_ids:
        return {"stations": [], "total_count": 0}

    # 5. Загрузка станций с предзагрузкой
    stations = Station.query.options(
        joinedload(Station.regional_district).joinedload(RegionalDistrict.regional_energy_systems),
        joinedload(Station.energy_unit),
        selectinload(Station.machines)
            .selectinload(Machine.machine_powers),
        selectinload(Station.machines)
            .selectinload(Machine.machine_fuels),
        selectinload(Station.machines)
            .selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type)
    ).filter(Station.id.in_(station_ids)).all()

    # 6. Загрузка отфильтрованных агрегатов
    filtered_machines = Machine.query.options(
        selectinload(Machine.machine_fuels),
        selectinload(Machine.machine_powers),
        selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
    ).filter(
        Machine.id.in_(
            db.session.query(machine_subquery.c.id).filter(machine_subquery.c.id_station.in_(station_ids))
        )
    ).all()

    # 7. Привязка агрегатов к станциям
    from collections import defaultdict
    station_machines_map = defaultdict(list)
    for m in filtered_machines:
        station_machines_map[m.id_station].append(m)

    for station in stations:
        station.machines = station_machines_map.get(station.id, [])

    return {
        "stations": stations,
        "total_count": total_count,
    }


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
):
    # 🧹 Очистка служебных полей из filters
    filters = filters.copy()
    filters.pop("page", None)
    filters.pop("start_year", None)
    filters.pop("end_year", None)

    # ⏱ Настройка параметров пагинации
    if isinstance(per_page, str) and per_page.lower() == "all":
        show_all = True
        per_page_int = None
    else:
        show_all = False
        try:
            per_page_int = int(per_page)
        except (TypeError, ValueError):
            per_page_int = 10

    # 🧩 Загружаем отфильтрованные станции
    station_data = get_stations_list(
        page=page,
        per_page=per_page,
        rounding_digits=rounding_digits,
        **filters
    )
    stations = station_data["stations"]
    total_count = station_data["total_count"]
    total_pages = 1 if show_all else max(1, (total_count + per_page_int - 1) // per_page_int)

    # ✅ Получаем агрегаты с рассчитанными rowspan
    station_ids = [s.id for s in stations]
    machines = fetch_machines_with_rowspans(station_ids)

    # 🔗 Привязываем машины обратно к станциям
    station_machines_map = defaultdict(list)
    for m in machines:
        station_machines_map[m.id_station].append(m)

    for station in stations:
        station.machines = station_machines_map.get(station.id, [])

    # 🧩 Назначение мощностей агрегатам
    for station in stations:
        for machine in station.machines:
            assign_machine_powers_by_year(machine, start_year, end_year, rounding_digits)

    # 📊 Перерасчёт мощностей станции
    recalculate_station_powers_by_filtered_machines(
        stations, start_year, end_year, rounding_digits
    )

    # 📥 Агрегация по иерархии
    hierarchy_data = build_hierarchy_structure(stations, include_names=True)

    stations = station_data["stations"]
    station_ids = [s.id for s in stations]

    result = {
        "stations": stations,
        "stations_grouped": hierarchy_data.get("grouped_stations", {}),
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "per_page": per_page,
    }

    if show_all:
        result["aggregate_power_by_energy_units"] = (
            aggregate_power_by_energy_units(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )
                
        result["aggregate_energy_units_by_station_types"] = (
            aggregate_energy_units_by_station_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregated_energy_units_by_station_type_with_fuel"] = (
            aggregate_energy_units_by_station_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_units_by_tes_types"] = (
            aggregate_regional_districts_by_tes_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_units_by_tes_types_with_fuel"] = (
            aggregate_energy_units_by_tes_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_units_by_tes_machine_types"] = (
            aggregate_energy_units_by_tes_machine_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_units_by_tes_machine_types_with_fuel"] = (
            aggregate_energy_units_by_tes_machine_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )
    
        result["aggregate_power_by_regional_districts"] = (
            aggregate_power_by_regional_districts(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )
                
        result["aggregate_regional_districts_by_station_types"] = (
            aggregate_regional_districts_by_station_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_districts_by_station_types_with_fuel"] = (
            aggregate_regional_districts_by_station_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_districts_by_tes_types"] = (
            aggregate_regional_districts_by_tes_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_districts_by_tes_types_with_fuel"] = (
            aggregate_regional_districts_by_tes_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_districts_by_tes_machine_types"] = (
            aggregate_regional_districts_by_tes_machine_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_districts_by_tes_machine_types_with_fuel"] = (
            aggregate_regional_districts_by_tes_machine_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_power_by_regional_energy_systems"] = (
            aggregate_power_by_regional_energy_systems(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )
                
        result["aggregate_regional_energy_systems_by_station_types"] = (
            aggregate_regional_energy_systems_by_station_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_energy_systems_by_station_types_with_fuel"] = (
            aggregate_regional_energy_systems_by_station_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_energy_systems_by_tes_types"] = (
            aggregate_regional_energy_systems_by_tes_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_energy_systems_by_tes_types_with_fuel"] = (
            aggregate_regional_energy_systems_by_tes_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_energy_systems_by_tes_machine_types"] = (
            aggregate_regional_energy_systems_by_tes_machine_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_regional_energy_systems_by_tes_machine_types_with_fuel"] = (
            aggregate_regional_energy_systems_by_tes_machine_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_power_by_union_energy_systems"] = (
            aggregate_power_by_union_energy_systems(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )
                
        result["aggregate_union_energy_systems_by_station_types"] = (
            aggregate_union_energy_systems_by_station_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_union_energy_systems_by_station_types_with_fuel"] = (
            aggregate_union_energy_systems_by_station_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_union_energy_systems_by_tes_types"] = (
            aggregate_union_energy_systems_by_tes_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_union_energy_systems_by_tes_types_with_fuel"] = (
            aggregate_union_energy_systems_by_tes_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_union_energy_systems_by_tes_machine_types"] = (
            aggregate_union_energy_systems_by_tes_machine_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_union_energy_systems_by_tes_machine_types_with_fuel"] = (
            aggregate_union_energy_systems_by_tes_machine_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_power_by_energy_system_types"] = (
            aggregate_power_by_energy_system_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )
                
        result["aggregate_energy_system_types_by_station_types"] = (
            aggregate_energy_system_types_by_station_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_system_types_by_station_types_with_fuel"] = (
            aggregate_energy_system_types_by_station_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_system_types_by_tes_types"] = (
            aggregate_energy_system_types_by_tes_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_system_types_by_tes_types_with_fuel"] = (
            aggregate_energy_system_types_by_tes_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_system_types_by_tes_machine_types"] = (
            aggregate_energy_system_types_by_tes_machine_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_energy_system_types_by_tes_machine_types_with_fuel"] = (
            aggregate_energy_system_types_by_tes_machine_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_power_by_total_energy_system_types"] = (
            aggregate_power_by_total_energy_system_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )
                
        result["aggregate_total_energy_system_types_by_station_types"] = (
            aggregate_total_energy_system_types_by_station_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_total_energy_system_types_by_station_types_with_fuel"] = (
            aggregate_total_energy_system_types_by_station_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_total_energy_system_types_by_tes_types"] = (
            aggregate_total_energy_system_types_by_tes_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_total_energy_system_types_by_tes_types_with_fuel"] = (
            aggregate_total_energy_system_types_by_tes_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_total_energy_system_types_by_tes_machine_types"] = (
            aggregate_total_energy_system_types_by_tes_machine_types(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

        result["aggregate_total_energy_system_types_by_tes_machine_types_with_fuel"] = (
            aggregate_total_energy_system_types_by_tes_machine_types_with_fuel(
                start_year=start_year,
                end_year=end_year,
                station_ids=station_ids,
            )
        )

    return result

def get_station_by_id(station_id):
    return (
        db.session.query(Station)
        .options(joinedload(Station.machines))
        .filter_by(id=station_id)
        .first()
    )


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

        machine.fuel_type_by_year = {
            mf.year_number: mf.fuel.fuel_type.name
            for mf in machine.machine_fuels
            if mf.fuel and mf.fuel.fuel_type
        }

        
def get_station_list_template_context(form, data, rounding_digits, start_year, end_year, filters, show_all=False):
    import time
    start_time = time.time()

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

    context = {
            "form": form,
            "stations_grouped": data["stations_grouped"],
            "total_count": data["total_count"],
            "total_pages": data["total_pages"],
            "current_page": data["page"],
            "per_page": str(data["per_page"]).lower(),
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
    }
    
    if not show_all:
        print(f"[⏱] get_station_list_template_context заняла: {time.time() - start_time:.2f} сек")
        return context
    else:
        # 📦 Генерация агрегатов по уровням
        energy_unit_aggregates = build_energy_unit_aggregates(data)
        regional_district_aggregates = build_regional_district_aggregates(data)
        regional_energy_system_aggregates = build_regional_energy_system_aggregates(data)
        union_energy_system_aggregates = build_union_energy_system_aggregates(data)
        energy_system_type_aggregates = build_energy_system_type_aggregates(data)
        total_energy_system_type_aggregates = build_total_energy_system_type_aggregates(data)

        # ⏬ Включаем агрегаты по уровням в context
        context.update(energy_unit_aggregates)
        context.update(regional_district_aggregates)
        context.update(regional_energy_system_aggregates)
        context.update(union_energy_system_aggregates)
        context.update(energy_system_type_aggregates)
        context.update(total_energy_system_type_aggregates)

        print(f"[⏱] get_station_list_template_context с show_all заняла: {time.time() - start_time:.2f} сек")
        return context


def recalculate_station_power(station, start_year, end_year):
    power_by_year = {
        year: {"p_ust": Decimal("0"), "p_ogr": Decimal("0"), "p_rasp": Decimal("0")}
        for year in range(start_year, end_year + 1)
    }

    for machine in station.machines:
        for mp in machine.machine_powers:
            year = mp.year.number
            if start_year <= year <= end_year:
                power_by_year[year]["p_ust"] += Decimal(str(mp.p_ust or "0"))
                power_by_year[year]["p_ogr"] += Decimal(str(mp.p_ogr or "0"))
                power_by_year[year]["p_rasp"] += Decimal(str(mp.p_rasp or "0"))

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
        "energy_units_by_station_types_with_fuel_yearly_p_ust": data["aggregated_energy_units_by_station_type_with_fuel"]["aggregated"]["p_ust"],
        "energy_units_by_station_types_with_fuel_yearly_p_ogr": data["aggregated_energy_units_by_station_type_with_fuel"]["aggregated"]["p_ogr"],
        "energy_units_by_station_types_with_fuel_yearly_p_rasp": data["aggregated_energy_units_by_station_type_with_fuel"]["aggregated"]["p_rasp"],

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
        # Основная агрегация
        "total_energy_system_types_yearly_p_ust": data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_ust"],
        "total_energy_system_types_yearly_p_ogr": data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_ogr"],
        "total_energy_system_types_yearly_p_rasp": data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_rasp"],

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