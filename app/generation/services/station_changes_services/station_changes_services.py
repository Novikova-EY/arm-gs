from config import Config
from app.extensions import db
from sqlalchemy import and_, func, select, or_
from sqlalchemy.orm import selectinload, joinedload

# Модели
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict

# Сервисы
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_rows import (
    get_full_aggregation_rows
    )
from app.generation.services.station_services.station_services import (
    get_current_machine_tes_types_map,
    assign_machine_powers_by_year,
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
    get_regional_energy_system_list_full,
    get_regional_energy_systems_map,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_district_list_full,
    get_rd_to_fd_id_map,
)
from app.common.services.get_services.territories.federal_district_get_services import (
    get_federal_district_list_full,
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
    fetch_machines_with_rowspans,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_energy_units import (
    aggregate_changes_by_energy_units,
    aggregate_changes_energy_units_by_station_types,
    aggregate_changes_energy_units_by_station_types_with_fuel,
    aggregate_changes_energy_units_by_tes_types,
    aggregate_changes_energy_units_by_tes_types_with_fuel,
    aggregate_changes_energy_units_by_tes_machine_types,
    aggregate_changes_energy_units_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_regional_districts import (
    aggregate_changes_by_regional_districts,
    aggregate_changes_regional_districts_by_station_types,
    aggregate_changes_regional_districts_by_station_types_with_fuel,
    aggregate_changes_regional_districts_by_tes_types,
    aggregate_changes_regional_districts_by_tes_types_with_fuel,
    aggregate_changes_regional_districts_by_tes_machine_types,
    aggregate_changes_regional_districts_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_regional_energy_systems import (
    aggregate_changes_by_regional_energy_systems,
    aggregate_changes_regional_energy_systems_by_station_types,
    aggregate_changes_regional_energy_systems_by_station_types_with_fuel,
    aggregate_changes_regional_energy_systems_by_tes_types,
    aggregate_changes_regional_energy_systems_by_tes_types_with_fuel,
    aggregate_changes_regional_energy_systems_by_tes_machine_types,
    aggregate_changes_regional_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_union_energy_systems import (
    aggregate_changes_by_union_energy_systems,
    aggregate_changes_union_energy_systems_by_station_types,
    aggregate_changes_union_energy_systems_by_station_types_with_fuel,
    aggregate_changes_union_energy_systems_by_tes_types,
    aggregate_changes_union_energy_systems_by_tes_types_with_fuel,
    aggregate_changes_union_energy_systems_by_tes_machine_types,
    aggregate_changes_union_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_energy_system_types import (
    aggregate_changes_by_energy_system_types,
    aggregate_changes_energy_system_types_by_station_types,
    aggregate_changes_energy_system_types_by_station_types_with_fuel,
    aggregate_changes_energy_system_types_by_tes_types,
    aggregate_changes_energy_system_types_by_tes_types_with_fuel,
    aggregate_changes_energy_system_types_by_tes_machine_types,
    aggregate_changes_energy_system_types_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_total_energy_system_types import (
    aggregate_changes_by_total_energy_system_types,
    aggregate_changes_total_energy_system_types_by_station_types,
    aggregate_changes_total_energy_system_types_by_station_types_with_fuel,
    aggregate_changes_total_energy_system_types_by_tes_types,
    aggregate_changes_total_energy_system_types_by_tes_types_with_fuel,
    aggregate_changes_total_energy_system_types_by_tes_machine_types,
    aggregate_changes_total_energy_system_types_by_tes_machine_types_with_fuel,
    )


EVENT_TYPES = [
    ("decommission", "Вывод из эксплуатации"),
    ("commission", "Ввод мощности"),
    ("before_modernization", "До модернизации"),
    ("after_modernization", "После модернизации"),
    ("change_power", "Изменение мощности"),
]

def get_tes_type_for_year(self, year):
    for rel in self.machine_tes_types:
        if rel.year_number == year and rel.tes_type:
            return rel.tes_type.id
    return None

def get_fuel_type_for_year(self, year):
    for rel in self.machine_fuels:
        if rel.year_number == year and rel.fuel and rel.fuel.fuel_type:
            return rel.fuel.fuel_type.id
    return None


def get_station_changes_list(
    page=1,
    per_page=None,
    rounding_digits=None,
    start_year=None,
    end_year=None,
    **filters,
):
    from collections import defaultdict

    start_year = start_year or Config.START_YEAR
    end_year = end_year or Config.END_YEAR
    year_range = set(range(start_year, end_year + 1))
    current_year = get_current_year()

    # 1. Общие фильтры по агрегатам
    base_machine_filters = []

    if filters.get("tes_type_filter"):
        base_machine_filters.append(
            Machine.machine_tes_types.any(
                and_(
                    MachineTesType.year_number == current_year,
                    MachineTesType.id_tes_type.in_(filters["tes_type_filter"])
                )
            )
        )

    if filters.get("tes_machine_type_filter"):
        base_machine_filters.append(
            Machine.id_tes_machine_type.in_(filters["tes_machine_type_filter"])
        )

    if filters.get("fuel_type_filter"):
        base_machine_filters.append(
            Machine.machine_fuels.any(
                MachineFuel.fuel.has(Fuel.id_fuel_type.in_(filters["fuel_type_filter"]))
            )
        )

    if filters.get("date_exploitation_filter"):
        base_machine_filters.append(
            Machine.date_exploitation.in_(filters["date_exploitation_filter"])
        )

    if filters.get("date_decompressing_expected_filter"):
        base_machine_filters.append(
            Machine.date_decompressing_expected.in_(filters["date_decompressing_expected_filter"])
        )

    # 2. Агрегаты по вводу/выводу
    query_input_output = db.session.query(
        Machine.id.label("id"),
        Machine.id_station.label("id_station")
    ).filter(
        *base_machine_filters,
        or_(
            and_(
                Machine.date_exploitation >= start_year,
                Machine.date_exploitation <= end_year
            ),
            and_(
                Machine.date_decompressing_expected >= start_year,
                Machine.date_decompressing_expected <= end_year
            )
        )
    )

    # 3. Агрегаты по изменению мощности
    subq = (
        db.session.query(MachinePower.id_machine)
        .filter(MachinePower.year_number.in_(year_range))
        .group_by(MachinePower.id_machine)
        .having(func.count(func.distinct(MachinePower.p_ust)) > 1)
        .subquery()
    )

    query_power_change = db.session.query(
        Machine.id.label("id"),
        Machine.id_station.label("id_station")
    ).filter(
        *base_machine_filters,
        Machine.id.in_(select(subq))
    )

    # 4. Объединение запросов
    machine_query = query_input_output.union_all(query_power_change)
    machine_subquery = machine_query.subquery()

    # 5. Получение station_ids
    station_ids_query = db.session.query(machine_subquery.c.id_station).distinct()
    station_ids_query = station_ids_query.join(Station, Station.id == machine_subquery.c.id_station)

    # 6. Фильтры по станциям
    if filters.get("station_type_filter"):
        station_ids_query = station_ids_query.filter(
            Station.machines.any(Machine.id_station_type.in_(filters["station_type_filter"]))
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
                        EnergySystemType.id.in_(filters["energy_system_type_filter"])
                    )
                )
            )
        )

    # 7. Пагинация
    total_count = station_ids_query.count()

    if isinstance(per_page, str) and per_page.lower() == "all":
        station_ids = [row[0] for row in station_ids_query.all()]
    else:
        per_page = int(per_page or 10)
        offset = (page - 1) * per_page
        station_ids = [row[0] for row in station_ids_query.offset(offset).limit(per_page).all()]

    if not station_ids:
        return {"stations": [], "total_count": 0}

    # 8. Загрузка станций и машин
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

    # 9. Отдельная загрузка агрегатов (если нужна)
    filtered_machines = Machine.query.options(
        selectinload(Machine.machine_fuels),
        selectinload(Machine.machine_powers),
        selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
    ).filter(
        Machine.id.in_(
            db.session.query(machine_subquery.c.id).filter(machine_subquery.c.id_station.in_(station_ids))
        )
    ).all()

    station_machines_map = defaultdict(list)
    for m in filtered_machines:
        station_machines_map[m.id_station].append(m)

    for station in stations:
        station.machines = station_machines_map.get(station.id, [])

    return {
        "stations": stations,
        "total_count": total_count,
    }


def get_station_changes_list_data(
    filters,
    per_page,
    page=1,
    rounding_digits=None,
    start_year=None,
    end_year=None,
    show_all=False,
):
    from collections import defaultdict

    filters = filters.copy()
    filters.pop("page", None)
    filters.pop("start_year", None)
    filters.pop("end_year", None)

    if isinstance(per_page, str) and per_page.lower() == "all":
        show_all = True
        per_page_int = None
    else:
        try:
            per_page_int = int(per_page)
            show_all = False
        except (TypeError, ValueError):
            per_page_int = 10
            show_all = False

    # 1. Все станции без пагинации
    station_data = get_station_changes_list(
        page=1,
        per_page="all",
        rounding_digits=rounding_digits,
        **filters
    )

    # 2. ID и иерархия
    all_stations = station_data["stations"]
    station_ids = [s.id for s in all_stations]
    hierarchy_data = build_hierarchy_structure_for_changes(all_stations, include_names=True)

    # 3. Загрузка всех агрегатов
    all_machines = load_all_machines_with_changes(
        station_ids=station_ids,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        event_type_filter=filters.get("event_type_filter"),
    )

    # 4. Отбираем только машины с event_type
    machines_with_event = [m for m in all_machines if m.event_types]
    rows = get_full_aggregation_rows(machines_with_event)
            
    # 4. Применяем rowspans ко всей выборке
    apply_all_rowspans(all_machines)

    # 5. Привязка машин к станциям
    station_machines_map = defaultdict(list)
    for m in all_machines:
        station_machines_map[m.id_station].append(m)

    for s in all_stations:
        s.machines = station_machines_map.get(s.id, [])
    filtered_stations = [s for s in all_stations if s.machines]

    # 6. Обрезаем по странице

    # 6. Постраничная нарезка
    total_count = len(filtered_stations)
    total_pages = 1 if show_all else max(1, (total_count + per_page_int - 1) // per_page_int)
    if not show_all:
        stations = all_stations[(page - 1) * per_page_int: page * per_page_int]
    else:
        stations = all_stations


    result = {
        "stations": station_data,
        "stations_grouped": hierarchy_data.get("grouped_stations", {}),
        "station_ids": [s.id for s in stations],
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "per_page": per_page,
        }

    if show_all:
        result.update({
            "event_types": EVENT_TYPES,
            "event_types_dict":dict(EVENT_TYPES),
            "aggregate_changes_by_energy_units": aggregate_changes_by_energy_units(rows),
            "aggregate_changes_energy_units_by_station_types": aggregate_changes_energy_units_by_station_types(rows),
            "aggregate_changes_energy_units_by_station_type_with_fuel": aggregate_changes_energy_units_by_station_types_with_fuel(rows),
            "aggregate_changes_energy_units_by_tes_types": aggregate_changes_energy_units_by_tes_types(rows),
            "aggregate_changes_energy_units_by_tes_types_with_fuel": aggregate_changes_energy_units_by_tes_types_with_fuel(rows),
            "aggregate_changes_energy_units_by_tes_machine_types": aggregate_changes_energy_units_by_tes_machine_types(rows),
            "aggregate_changes_energy_units_by_tes_machine_types_with_fuel": aggregate_changes_energy_units_by_tes_machine_types_with_fuel(rows),
            "aggregate_changes_by_regional_districts": aggregate_changes_by_regional_districts(rows),
            "aggregate_changes_regional_districts_by_station_types": aggregate_changes_regional_districts_by_station_types(rows),
            "aggregate_changes_regional_districts_by_station_types_with_fuel": aggregate_changes_regional_districts_by_station_types_with_fuel(rows),
            "aggregate_changes_regional_districts_by_tes_types": aggregate_changes_regional_districts_by_tes_types(rows),
            "aggregate_changes_regional_districts_by_tes_types_with_fuel": aggregate_changes_regional_districts_by_tes_types_with_fuel(rows),
            "aggregate_changes_regional_districts_by_tes_machine_types": aggregate_changes_regional_districts_by_tes_machine_types(rows),
            "aggregate_changes_regional_districts_by_tes_machine_types_with_fuel": aggregate_changes_regional_districts_by_tes_machine_types_with_fuel(rows),
            "aggregate_changes_by_regional_energy_systems": aggregate_changes_by_regional_energy_systems(rows),
            "aggregate_changes_regional_energy_systems_by_station_types": aggregate_changes_regional_energy_systems_by_station_types(rows),
            "aggregate_changes_regional_energy_systems_by_station_types_with_fuel": aggregate_changes_regional_energy_systems_by_station_types_with_fuel(rows),
            "aggregate_changes_regional_energy_systems_by_tes_types": aggregate_changes_regional_energy_systems_by_tes_types(rows),
            "aggregate_changes_regional_energy_systems_by_tes_types_with_fuel": aggregate_changes_regional_energy_systems_by_tes_types_with_fuel(rows),
            "aggregate_changes_regional_energy_systems_by_tes_machine_types": aggregate_changes_regional_energy_systems_by_tes_machine_types(rows),
            "aggregate_changes_regional_energy_systems_by_tes_machine_types_with_fuel": aggregate_changes_regional_energy_systems_by_tes_machine_types_with_fuel(rows),
            "aggregate_changes_by_union_energy_systems": aggregate_changes_by_union_energy_systems(rows),
            "aggregate_changes_union_energy_systems_by_station_types": aggregate_changes_union_energy_systems_by_station_types(rows),
            "aggregate_changes_union_energy_systems_by_station_types_with_fuel": aggregate_changes_union_energy_systems_by_station_types_with_fuel(rows),
            "aggregate_changes_union_energy_systems_by_tes_types": aggregate_changes_union_energy_systems_by_tes_types(rows),
            "aggregate_changes_union_energy_systems_by_tes_types_with_fuel": aggregate_changes_union_energy_systems_by_tes_types_with_fuel(rows),
            "aggregate_changes_union_energy_systems_by_tes_machine_types": aggregate_changes_union_energy_systems_by_tes_machine_types(rows),
            "aggregate_changes_union_energy_systems_by_tes_machine_types_with_fuel": aggregate_changes_union_energy_systems_by_tes_machine_types_with_fuel(rows),
            "aggregate_changes_by_energy_system_types": aggregate_changes_by_energy_system_types(rows),
            "aggregate_changes_energy_system_types_by_station_types": aggregate_changes_energy_system_types_by_station_types(rows),
            "aggregate_changes_energy_system_types_by_station_types_with_fuel": aggregate_changes_energy_system_types_by_station_types_with_fuel(rows),
            "aggregate_changes_energy_system_types_by_tes_types": aggregate_changes_energy_system_types_by_tes_types(rows),
            "aggregate_changes_energy_system_types_by_tes_types_with_fuel": aggregate_changes_energy_system_types_by_tes_types_with_fuel(rows),
            "aggregate_changes_energy_system_types_by_tes_machine_types": aggregate_changes_energy_system_types_by_tes_machine_types(rows),
            "aggregate_changes_energy_system_types_by_tes_machine_types_with_fuel": aggregate_changes_energy_system_types_by_tes_machine_types_with_fuel(rows),
            "aggregate_changes_by_total_energy_system_types": aggregate_changes_by_total_energy_system_types(rows),
            "aggregate_changes_total_energy_system_types_by_station_types": aggregate_changes_total_energy_system_types_by_station_types(rows),
            "aggregate_changes_total_energy_system_types_by_station_types_with_fuel": aggregate_changes_total_energy_system_types_by_station_types_with_fuel(rows),
            "aggregate_changes_total_energy_system_types_by_tes_types": aggregate_changes_total_energy_system_types_by_tes_types(rows),
            "aggregate_changes_total_energy_system_types_by_tes_types_with_fuel": aggregate_changes_total_energy_system_types_by_tes_types_with_fuel(rows),
            "aggregate_changes_total_energy_system_types_by_tes_machine_types": aggregate_changes_total_energy_system_types_by_tes_machine_types(rows),
            "aggregate_changes_total_energy_system_types_by_tes_machine_types_with_fuel": aggregate_changes_total_energy_system_types_by_tes_machine_types_with_fuel(rows),
        }
        )
    return result

    
def load_all_machines_with_changes(
    station_ids: list[int],
    start_year: int,
    end_year: int,
    rounding_digits: int = 1,
    event_type_filter: list[str] | None = None,
) -> list[Machine]:
    machines = Machine.query.options(
        joinedload(Machine.machine_station).joinedload(Station.regional_district),
        joinedload(Machine.gen_company),
        selectinload(Machine.machine_powers),
        selectinload(Machine.machine_fuels),
        selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
        joinedload(Machine.station_type),
        joinedload(Machine.tes_machine_type),
    ).filter(Machine.id_station.in_(station_ids)).all()

    # Назначаем данные по годам
    for m in machines:
        assign_machine_powers_changes_by_year(m, start_year, end_year, rounding_digits)

    # Фильтрация по типу мероприятия
    if event_type_filter:
        machines = [m for m in machines if m.event_type in event_type_filter]

    return machines


def apply_all_rowspans(machines: list[Machine]):
    def apply_rowspan_grouping(machines, key_func, attr_name: str, use_total_rows: bool = False):
        from collections import defaultdict

        group_map = defaultdict(list)
        for m in machines:
            key = key_func(m)
            group_map[key].append(m)

        for group in group_map.values():
            # Суммируем total_rows при необходимости
            rowspan = sum(m.total_rows if use_total_rows else 1 for m in group)

            used_rows = 0
            for m in group:
                if used_rows == 0:
                    setattr(m, attr_name, rowspan)
                else:
                    setattr(m, attr_name, 0)
                used_rows += m.total_rows if use_total_rows else 1

    # Применяем группировки
    apply_rowspan_grouping(
        machines,
        key_func=lambda m: m.machine_station.regional_district.id if m.machine_station and m.machine_station.regional_district else None,
        attr_name="region_rowspan",
        use_total_rows=True,
    )

    apply_rowspan_grouping(
        machines,
        key_func=lambda m: m.machine_station.id if m.machine_station else None,
        attr_name="station_rowspan",
        use_total_rows=True,
    )

    apply_rowspan_grouping(
        machines,
        key_func=lambda m: (m.machine_station.id, m.gen_company.id if m.gen_company else None),
        attr_name="gen_company_rowspan",
        use_total_rows=True,
    )

    apply_rowspan_grouping(
        machines,
        key_func=lambda m: (m.machine_station.id, m.fuel_so or ''),
        attr_name="fuel_rowspan",
        use_total_rows=True,
    )


def apply_rowspan_grouping(machines, key_func, attr_name: str, use_total_rows: bool = False):
    from collections import defaultdict

    group_map = defaultdict(list)

    # Группируем агрегаты по ключу
    for m in machines:
        key = key_func(m)
        group_map[key].append(m)

    for group in group_map.values():
        # Вычисляем суммарное количество строк
        rowspan = sum(m.total_rows if use_total_rows else 1 for m in group)

        current = 0
        for m in group:
            if current == 0:
                setattr(m, attr_name, rowspan)
            else:
                setattr(m, attr_name, 0)
            current += 1


def assign_machine_powers_changes_by_year(machine, start_year, end_year, rounding_digits):
    machine.powers_by_year = []
    machine.event_types = set()
    machine.total_rows = 0

    powers = sorted(
        [(mp.year_number, round(float(mp.p_ust or 0), rounding_digits))
         for mp in machine.machine_powers if start_year <= mp.year_number <= end_year],
        key=lambda x: x[0]
    )

    if not powers:
        return

    prev_value = powers[0][1]
    prev_year = powers[0][0]

    for i in range(1, len(powers)):
        year, value = powers[i]
        if value != prev_value and prev_value > 0 and value > 0:
            delta = value - prev_value
            machine.event_types.add("before_modernization")
            machine.event_types.add("after_modernization")
            machine.event_types.add("change_power")
            machine.powers_by_year.extend([
                {"year": year, "p_ust": prev_value, "event": "before_modernization"},
                {"year": year, "p_ust": value, "event": "after_modernization"},
                {"year": year, "p_ust": delta, "event": "change_power"},
            ])
            machine.total_rows += 3
        prev_value = value
        prev_year = year

    for i in range(len(powers) - 1):
        year, value = powers[i]
        next_value = powers[i + 1][1]
        if value > 0 and next_value == 0:
            machine.event_types.add("decommission")
            machine.powers_by_year.append({
                "year": year + 1,
                "p_ust": value,
                "event": "decommission"
            })
            machine.total_rows += 1

    for year, value in powers:
        if value > 0:
            machine.event_types.add("commission")
            machine.powers_by_year.append({
                "year": year,
                "p_ust": value,
                "event": "commission"
            })
            machine.total_rows += 1
            break  # ввод фиксируем по первому положительному значению

    if not machine.powers_by_year:
        machine.total_rows = 0


def build_hierarchy_structure_for_changes(stations: list[Station], include_names=False):
    from collections import defaultdict

    grouped_data = defaultdict(
        lambda: defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: defaultdict(list)
                )
            )
        )
    )

    # Для отображения имен при include_names=True
    est_names = {}
    ues_names = {}
    res_names = {}
    rd_names = {}
    eu_names = {}

    for station in stations:
        # Пропускаем станции без регионального округа или энергосистем
        if not station.regional_district or not station.regional_district.regional_energy_systems:
            continue

        for res in station.regional_district.regional_energy_systems:
            ues = res.union_energy_system
            if not ues:
                continue

            est_id = ues.id_energy_system_type
            ues_id = ues.id
            res_id = res.id
            rd_id = station.id_regional_district

            # Энергоузел
            if station.id_energy_unit is not None:
                eu_id = station.id_energy_unit
                eu_name = station.energy_unit.name if station.energy_unit else f"id={eu_id}"
            else:
                eu_id = 0
                eu_name = "без энергоузла"

            # Добавляем станцию в иерархию
            grouped_data[est_id][ues_id][res_id][rd_id][eu_id].append(station)

            # 🏷 Сохраняем имена, если требуется
            if include_names:
                est_names[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
                ues_names[ues_id] = ues.name
                res_names[res_id] = res.name
                rd_names[rd_id] = station.regional_district.name
                eu_names[eu_id] = eu_name

    result = {
        "grouped_stations": grouped_data,
        "stations": stations,
    }

    if include_names:
        result.update({
            "energy_system_type_name": est_names,
            "union_energy_system_name": ues_names,
            "regional_energy_system_name": res_names,
            "regional_district_name": rd_names,
            "energy_unit_name": eu_names,
        })

    return result


def get_station_list_template_context(form, data, rounding_digits, filters, show_all=False):
    import time
    start_time = time.time()

    year_features = get_year_feature_dict()

    energy_system_type_list = get_energy_system_type_list_full()
    energy_system_type_names = get_energy_system_type_map()

    union_energy_system_list = get_union_energy_system_list_full()
    union_energy_system_names = get_union_energy_systems_map()
    regional_energy_system_mapping = get_ues_to_res_ids_map()

    regional_energy_system_list = get_regional_energy_system_list_full()
    regional_energy_system_names = get_regional_energy_systems_map()

    federal_district_list = get_federal_district_list_full()
    regional_district_mapping = get_fd_to_rd_ids_map()

    regional_district_list = get_regional_district_list_full()
    regional_district_names = get_rd_to_fd_id_map()

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
            "event_types": EVENT_TYPES,
            "event_types_dict":dict(EVENT_TYPES),
            "stations_grouped": data["stations_grouped"],
            "station_ids": data["station_ids"],
            "total_count": data["total_count"],
            "total_pages": data["total_pages"],
            "current_page": data["page"],
            "per_page": str(data["per_page"]).lower(),
            "start_year": filters.get("start_year"),
            "end_year": filters.get("end_year"),
            "rounding_digits": rounding_digits,
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


def build_energy_unit_aggregates(data):

    return {
        # Основная агрегация
        "energy_units_yearly_p_ust": data["aggregate_changes_by_energy_units"]["aggregated"]["p_ust"],

        # По типам станций
        "energy_units_by_station_types_yearly_p_ust": data["aggregate_changes_energy_units_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций и топливу
        "energy_units_by_station_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_units_by_station_type_with_fuel"]["aggregated"]["p_ust"],

        # По типам ТЭС
        "energy_units_by_tes_types_yearly_p_ust": data["aggregate_changes_energy_units_by_tes_types"]["aggregated"]["p_ust"],

        # По типам ТЭС и топливу
        "energy_units_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_units_by_tes_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам машин ТЭС
        "energy_units_by_tes_machine_types_yearly_p_ust": data["aggregate_changes_energy_units_by_tes_machine_types"]["aggregated"]["p_ust"],

        # По типам машин ТЭС и топливу
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_units_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
    }


def build_regional_district_aggregates(data):

    return {
        # Основная агрегация
        "regional_districts_yearly_p_ust": data["aggregate_changes_by_regional_districts"]["aggregated"]["p_ust"],

        # По типам станций
        "regional_districts_by_station_types_yearly_p_ust": data["aggregate_changes_regional_districts_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций и топливу
        "regional_districts_by_station_types_with_fuel_yearly_p_ust": data["aggregate_changes_regional_districts_by_station_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам ТЭС
        "regional_districts_by_tes_types_yearly_p_ust": data["aggregate_changes_regional_districts_by_tes_types"]["aggregated"]["p_ust"],

        # По типам ТЭС и топливу
        "regional_districts_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_changes_regional_districts_by_tes_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам машин ТЭС
        "regional_districts_by_tes_machine_types_yearly_p_ust": data["aggregate_changes_regional_districts_by_tes_machine_types"]["aggregated"]["p_ust"],

        # По типам машин ТЭС и топливу
        "regional_districts_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_changes_regional_districts_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
    }


def build_regional_energy_system_aggregates(data):

    return {
        # Основная агрегация
        "regional_energy_systems_yearly_p_ust": data["aggregate_changes_by_regional_energy_systems"]["aggregated"]["p_ust"],

        # По типам станций
        "regional_energy_systems_by_station_types_yearly_p_ust": data["aggregate_changes_regional_energy_systems_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций и топливу
        "regional_energy_systems_by_station_types_with_fuel_yearly_p_ust": data["aggregate_changes_regional_energy_systems_by_station_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам ТЭС
        "regional_energy_systems_by_tes_types_yearly_p_ust": data["aggregate_changes_regional_energy_systems_by_tes_types"]["aggregated"]["p_ust"],

        # По типам ТЭС и топливу
        "regional_energy_systems_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_changes_regional_energy_systems_by_tes_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам машин ТЭС
        "regional_energy_systems_by_tes_machine_types_yearly_p_ust": data["aggregate_changes_regional_energy_systems_by_tes_machine_types"]["aggregated"]["p_ust"],

        # По типам машин ТЭС и топливу
        "regional_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_changes_regional_energy_systems_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
    }


def build_union_energy_system_aggregates(data):

    return {
        # Основная агрегация
        "union_energy_systems_yearly_p_ust": data["aggregate_changes_by_union_energy_systems"]["aggregated"]["p_ust"],

        # По типам станций
        "union_energy_systems_by_station_types_yearly_p_ust": data["aggregate_changes_union_energy_systems_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций и топливу
        "union_energy_systems_by_station_types_with_fuel_yearly_p_ust": data["aggregate_changes_union_energy_systems_by_station_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам ТЭС
        "union_energy_systems_by_tes_types_yearly_p_ust": data["aggregate_changes_union_energy_systems_by_tes_types"]["aggregated"]["p_ust"],

        # По типам ТЭС и топливу
        "union_energy_systems_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_changes_union_energy_systems_by_tes_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам машин ТЭС
        "union_energy_systems_by_tes_machine_types_yearly_p_ust": data["aggregate_changes_union_energy_systems_by_tes_machine_types"]["aggregated"]["p_ust"],

        # По типам машин ТЭС и топливу
        "union_energy_systems_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_changes_union_energy_systems_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
    }


def build_energy_system_type_aggregates(data):

    return {
        # Основная агрегация
        "energy_system_types_yearly_p_ust": data["aggregate_changes_by_energy_system_types"]["aggregated"]["p_ust"],

        # По типам станций
        "energy_system_types_by_station_types_yearly_p_ust": data["aggregate_changes_energy_system_types_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций и топливу
        "energy_system_types_by_station_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам ТЭС
        "energy_system_types_by_tes_types_yearly_p_ust": data["aggregate_changes_energy_system_types_by_tes_types"]["aggregated"]["p_ust"],

        # По типам ТЭС и топливу
        "energy_system_types_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам машин ТЭС
        "energy_system_types_by_tes_machine_types_yearly_p_ust": data["aggregate_changes_energy_system_types_by_tes_machine_types"]["aggregated"]["p_ust"],

        # По типам машин ТЭС и топливу
        "energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
    }


def build_total_energy_system_type_aggregates(data):

    return {
        # Основная агрегация
        "total_energy_system_types_yearly_p_ust": data["aggregate_changes_by_total_energy_system_types"]["aggregated"]["p_ust"],

        # По типам станций
        "total_energy_system_types_by_station_types_yearly_p_ust": data["aggregate_changes_total_energy_system_types_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций и топливу
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_ust": data["aggregate_changes_total_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам ТЭС
        "total_energy_system_types_by_tes_types_yearly_p_ust": data["aggregate_changes_total_energy_system_types_by_tes_types"]["aggregated"]["p_ust"],

        # По типам ТЭС и топливу
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_changes_total_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_ust"],

        # По типам машин ТЭС
        "total_energy_system_types_by_tes_machine_types_yearly_p_ust": data["aggregate_changes_total_energy_system_types_by_tes_machine_types"]["aggregated"]["p_ust"],

        # По типам машин ТЭС и топливу
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_changes_total_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
    }
