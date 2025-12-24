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
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.energy_zone_model import EnergyZone
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.gen_companies.gen_company_model import GenCompany
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import PGUTesMachineType

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
    get_regional_districts_map,
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
from app.common.services.database_version_filter import (
    get_current_db_version_id,
    filter_by_explicit_db_version,
    filter_by_db_version,
)
from app.common.services.database_version_services import get_current_version

from app.common.services.get_services.stations.station_get_services import (
    get_station_by_id,
)
from app.common.services.get_services.stations.machine_get_services import (
    get_machine_by_id,
)
from app.common.services.get_services.gen_companies.gen_company_get_services import (
    get_gen_company_list_full,
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
    aggregate_changes_regional_energy_systems_by_station_types_with_events,
    aggregate_changes_regional_energy_systems_by_station_types_with_fuel,
    aggregate_changes_regional_energy_systems_by_tes_types,
    aggregate_changes_regional_energy_systems_by_tes_types_with_fuel,
    aggregate_changes_regional_energy_systems_by_tes_machine_types,
    aggregate_changes_regional_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_union_energy_systems import (
    aggregate_changes_by_union_energy_systems,
    aggregate_changes_union_energy_systems_by_station_types,
    aggregate_changes_union_energy_systems_by_station_types_with_events,
    aggregate_changes_union_energy_systems_by_station_types_with_fuel,
    aggregate_changes_union_energy_systems_by_tes_types,
    aggregate_changes_union_energy_systems_by_tes_types_with_fuel,
    aggregate_changes_union_energy_systems_by_tes_machine_types,
    aggregate_changes_union_energy_systems_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_energy_system_types import (
    aggregate_changes_by_energy_system_types,
    aggregate_changes_energy_system_types_by_station_types,
    aggregate_changes_energy_system_types_by_station_types_with_events,
    aggregate_changes_energy_system_types_by_station_types_with_fuel,
    aggregate_changes_energy_system_types_by_tes_types,
    aggregate_changes_energy_system_types_by_tes_types_with_fuel,
    aggregate_changes_energy_system_types_by_tes_machine_types,
    aggregate_changes_energy_system_types_by_tes_machine_types_with_fuel,
    )
from app.generation.services.station_changes_services.aggregation_station_changes_services.aggregation_services_total_energy_system_types import (
    aggregate_changes_by_total_energy_system_types,
    aggregate_changes_total_energy_system_types_by_station_types,
    aggregate_changes_total_energy_system_types_by_station_types_with_events,
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
    current_db_version_id = get_current_db_version_id()

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
            or_(
                Machine.date_exploitation.in_(filters["date_exploitation_filter"]),
                Machine.date_exploitation_expected.in_(filters["date_exploitation_filter"]),
            )
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
    query_input_output = filter_by_explicit_db_version(query_input_output, Machine, current_db_version_id)

    # 3. Агрегаты по изменению мощности
    subq_query = (
        db.session.query(MachinePower.id_machine)
        .filter(MachinePower.year_number.in_(year_range))
    )
    subq_query = filter_by_explicit_db_version(subq_query, MachinePower, current_db_version_id)
    subq = (
        subq_query
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
    query_power_change = filter_by_explicit_db_version(query_power_change, Machine, current_db_version_id)

    # 4. Объединение запросов
    machine_query = query_input_output.union_all(query_power_change)
    machine_subquery = machine_query.subquery()

    # 5. Получение station_ids
    station_ids_query = db.session.query(machine_subquery.c.id_station).distinct()
    station_ids_query = station_ids_query.join(Station, Station.id == machine_subquery.c.id_station)
    station_ids_query = filter_by_explicit_db_version(station_ids_query, Station, current_db_version_id)

    # 6. Фильтры по станциям
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
        )
        gen_company_ids = filter_by_explicit_db_version(gen_company_ids, GenCompany, current_db_version_id).all()
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
    )
    stations = filter_by_explicit_db_version(stations, Station, current_db_version_id)
    stations = stations.filter(Station.id.in_(station_ids)).all()

    # 9. Отдельная загрузка агрегатов (если нужна)
    filtered_machines = Machine.query.options(
        selectinload(Machine.machine_fuels),
        selectinload(Machine.machine_powers),
        selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
    )
    filtered_machines = filter_by_explicit_db_version(filtered_machines, Machine, current_db_version_id)
    filtered_machines = filtered_machines.filter(
        Machine.id.in_(
            db.session.query(machine_subquery.c.id).filter(machine_subquery.c.id_station.in_(station_ids))
        )
    ).all()

    # Фильтруем связанные данные по версии БД после загрузки
    # (selectinload загружает все связанные записи, нужно отфильтровать вручную)
    for m in filtered_machines:
        # Фильтруем machine_powers по версии БД
        if hasattr(m, 'machine_powers') and m.machine_powers:
            m.machine_powers = [
                mp for mp in m.machine_powers
                if getattr(mp, 'database_version_id', None) == current_db_version_id
                or (current_db_version_id is None and getattr(mp, 'database_version_id', None) is None)
            ]
        
        # Фильтруем machine_fuels по версии БД
        if hasattr(m, 'machine_fuels') and m.machine_fuels:
            m.machine_fuels = [
                mf for mf in m.machine_fuels
                if getattr(mf, 'database_version_id', None) == current_db_version_id
                or (current_db_version_id is None and getattr(mf, 'database_version_id', None) is None)
            ]
        
        # Фильтруем machine_tes_types по версии БД
        if hasattr(m, 'machine_tes_types') and m.machine_tes_types:
            m.machine_tes_types = [
                mtt for mtt in m.machine_tes_types
                if getattr(mtt, 'database_version_id', None) == current_db_version_id
                or (current_db_version_id is None and getattr(mtt, 'database_version_id', None) is None)
            ]

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
    current_db_version_id = get_current_db_version_id()

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

    # 3. Загрузка всех агрегатов
    all_machines = load_all_machines_with_changes(
        station_ids=station_ids,
        start_year=start_year,
        end_year=end_year,
        rounding_digits=rounding_digits,
        event_type_filter=filters.get("event_type_filter"),
    )

    # 3.1. Итоги по отображаемому периоду (только годы с признаком "план")
    try:
        from decimal import Decimal
        year_features = get_year_feature_dict() or {}
        plan_years_set = {
            y
            for y in range(int(start_year or 0), int(end_year or -1) + 1)
            if str(year_features.get(y, "")).strip().lower() == "план"
        }

        if plan_years_set:
            for m in all_machines:
                rows = getattr(m, "powers_by_year", None) or []
                has_plan_rows = any((p.get("year") in plan_years_set) for p in rows if isinstance(p, dict))
                if not has_plan_rows:
                    setattr(m, "plan_period_sum", None)
                    setattr(m, "plan_period_sum_by_event", {})
                    continue
                total = Decimal("0")
                by_event: dict = {}
                for p in rows:
                    if not isinstance(p, dict):
                        continue
                    if p.get("year") not in plan_years_set:
                        continue
                    v = p.get("p_ust")
                    if v is None:
                        continue
                    dv = Decimal(str(v))
                    total += dv
                    ev = p.get("event")
                    by_event[ev] = by_event.get(ev, Decimal("0")) + dv
                setattr(m, "plan_period_sum", total)
                setattr(m, "plan_period_sum_by_event", by_event)
        else:
            for m in all_machines:
                setattr(m, "plan_period_sum", None)
                setattr(m, "plan_period_sum_by_event", {})
    except Exception:
        # Итоги — вспомогательный расчёт для UI. Не должен ломать страницу.
        for m in all_machines:
            setattr(m, "plan_period_sum", None)
            setattr(m, "plan_period_sum_by_event", {})

    # 4. Отбираем только машины с event_type
    machines_with_event = [m for m in all_machines if m.event_types]
    rows = get_full_aggregation_rows(machines_with_event)

    # Event-based агрегаты по энергоузлам (нужны для спец-логики ОЭС "ТИТЭС Сибири")
    from collections import defaultdict
    from decimal import Decimal
    eu_events = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))  # eu_id -> event -> year -> sum
    eu_by_station_events = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal))))  # eu_id -> st_id -> event -> year -> sum
    for r in rows:
        eu_id = getattr(r, "energy_unit_id", None) or 0
        st_id = getattr(r, "station_type_id", None) or 0
        ev = getattr(r, "event_type", None)
        year = getattr(r, "year", None)
        val = getattr(r, "p_ust", None) or Decimal(0)
        if not ev or year is None:
            continue
        eu_events[eu_id][ev][year] += val
        eu_by_station_events[eu_id][st_id][ev][year] += val
    
    # 5. Применяем rowspans к машинам каждой станции
    for station in all_stations:
        station.machines = [m for m in all_machines if m.id_station == station.id]
        # Сортируем машины внутри станции по генкомпании
        station.machines.sort(key=lambda m: (
            m.gen_company.id if m.gen_company else 999999,
            m.id
        ))
        if station.machines:
            apply_all_rowspans_for_station(station.machines)
    
    # 6. Глобальное объединение ячеек по субъекту РФ и генкомпании
    # Сначала строим иерархию, чтобы знать фактический порядок рендера (теперь сверху — синхронные зоны)
    hierarchy_data = build_est_then_sync_area_hierarchy_structure_for_changes(all_stations, include_names=True)
    # Формируем последовательность машин В ТОЧНОМ порядке рендера шаблона
    machines_in_display_order: list[Machine] = []
    grouped = rows and hierarchy_data.get("grouped_stations", {}) or {}
    for es_type_id, es_group in grouped.items():
        for sa_id, sa_group in es_group.items():
            for ues_id, ues_group in sa_group.items():
                for res_id, res_group in ues_group.items():
                    for rd_id, stations_in_rd in res_group.items():
                        if rd_id == 0:
                            continue
                        for st in stations_in_rd:
                            if getattr(st, "machines", None):
                                for _m in st.machines:
                                    setattr(_m, "_display_rd_id", rd_id)
                                    setattr(_m, "_display_res_id", res_id)
                                    setattr(_m, "_display_region_key", (res_id, rd_id))
                                    machines_in_display_order.append(_m)

    # На всякий случай сбрасываем предыдущие значения и отфильтровываем невидимые агрегаты
    visible_machines_in_order = []
    for m in machines_in_display_order:
        if getattr(m, "total_rows", 0) and m.total_rows > 0:
            setattr(m, "region_rowspan", 0)
            setattr(m, "gen_company_rowspan", 0)
            visible_machines_in_order.append(m)

    # 6.1. Объединение по субъекту РФ (континуальные блоки в отображаемой последовательности)
    current_region_key = None
    rd_start_idx = 0
    for idx, m in enumerate(visible_machines_in_order):
        region_key = getattr(m, "_display_region_key", None) or (getattr(m, "_display_res_id", None), getattr(m, "_display_rd_id", None))

        if region_key != current_region_key:
            if current_region_key is not None and rd_start_idx < idx:
                total_rows = sum(getattr(visible_machines_in_order[i], "total_rows", 0) for i in range(rd_start_idx, idx))
                if total_rows > 0:
                    visible_machines_in_order[rd_start_idx].region_rowspan = total_rows
                    for i in range(rd_start_idx + 1, idx):
                        visible_machines_in_order[i].region_rowspan = 0

            current_region_key = region_key
            rd_start_idx = idx

    # Завершаем последний блок субъекта
    if current_region_key is not None and rd_start_idx < len(visible_machines_in_order):
        total_rows = sum(getattr(visible_machines_in_order[i], "total_rows", 0) for i in range(rd_start_idx, len(visible_machines_in_order)))
        if total_rows > 0:
            visible_machines_in_order[rd_start_idx].region_rowspan = total_rows
            for i in range(rd_start_idx + 1, len(visible_machines_in_order)):
                visible_machines_in_order[i].region_rowspan = 0

    # 6.2. Объединение по генкомпании (внутри субъекта РФ)
    current_key = None  # (region_key, gen_company_id)
    gc_start_idx = 0
    for idx, m in enumerate(visible_machines_in_order):
        region_key = getattr(m, "_display_region_key", None) or (getattr(m, "_display_res_id", None), getattr(m, "_display_rd_id", None))
        gen_company_id = m.gen_company.id if m.gen_company else None
        key = (region_key, gen_company_id)

        if key != current_key:
            if current_key is not None and gc_start_idx < idx:
                total_rows = sum(getattr(visible_machines_in_order[i], "total_rows", 0) for i in range(gc_start_idx, idx))
                if total_rows > 0:
                    visible_machines_in_order[gc_start_idx].gen_company_rowspan = total_rows
                    for i in range(gc_start_idx + 1, idx):
                        visible_machines_in_order[i].gen_company_rowspan = 0

            current_key = key
            gc_start_idx = idx

    # Завершаем последний блок генкомпании
    if current_key is not None and gc_start_idx < len(visible_machines_in_order):
        total_rows = sum(getattr(visible_machines_in_order[i], "total_rows", 0) for i in range(gc_start_idx, len(visible_machines_in_order)))
        if total_rows > 0:
            visible_machines_in_order[gc_start_idx].gen_company_rowspan = total_rows
            for i in range(gc_start_idx + 1, len(visible_machines_in_order)):
                visible_machines_in_order[i].gen_company_rowspan = 0

    # 7. Строим иерархию с обычными станциями (уже построена выше)
    
    filtered_stations = all_stations

    # Маппинг "субъект РФ -> синхронная зона" (нужен для агрегатов по синхронным зонам)
    rd_to_sa_id: dict[int, int] = {}
    rd_to_ez_id: dict[int, int] = {}
    for st in all_stations:
        rd_id = getattr(st, "id_regional_district", None)
        rd_obj = getattr(st, "regional_district", None)
        if not rd_id or not rd_obj:
            continue
        sa_id = getattr(rd_obj, "id_synchronous_area", None) or 0
        ez_id = getattr(rd_obj, "id_energy_zone", None) or 0
        rd_to_sa_id[int(rd_id)] = int(sa_id)
        rd_to_ez_id[int(rd_id)] = int(ez_id)

    # 9. Постраничная нарезка
    total_count = len(filtered_stations)
    total_pages = 1 if show_all else max(1, (total_count + per_page_int - 1) // per_page_int)
    if not show_all:
        stations = filtered_stations[(page - 1) * per_page_int: page * per_page_int]
    else:
        stations = filtered_stations


    result = {
        "stations": station_data,
        "stations_grouped": hierarchy_data.get("grouped_stations", {}),
        "synchronous_area_names": hierarchy_data.get("synchronous_area_name", {}),
        "energy_unit_names_override": hierarchy_data.get("energy_unit_name", {}),
        "rd_to_synchronous_area_id": rd_to_sa_id,
        "rd_to_energy_zone_id": rd_to_ez_id,
        "station_ids": [s.id for s in stations],
        "total_count": total_count,
        "total_pages": total_pages,
        "page": page,
        "per_page": per_page,
        }
    
    result.update({
        "event_types": EVENT_TYPES,
        "event_types_dict":dict(EVENT_TYPES),
        "aggregate_changes_by_energy_units_events": {"aggregated": {"p_ust": eu_events}},
        "aggregate_changes_energy_units_by_station_types_with_events": {"aggregated": {"p_ust": eu_by_station_events}},
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
        "aggregate_changes_regional_energy_systems_by_station_types_with_events": aggregate_changes_regional_energy_systems_by_station_types_with_events(rows),
        "aggregate_changes_regional_energy_systems_by_station_types_with_fuel": aggregate_changes_regional_energy_systems_by_station_types_with_fuel(rows),
        "aggregate_changes_regional_energy_systems_by_tes_types": aggregate_changes_regional_energy_systems_by_tes_types(rows),
        "aggregate_changes_regional_energy_systems_by_tes_types_with_fuel": aggregate_changes_regional_energy_systems_by_tes_types_with_fuel(rows),
        "aggregate_changes_regional_energy_systems_by_tes_machine_types": aggregate_changes_regional_energy_systems_by_tes_machine_types(rows),
        "aggregate_changes_regional_energy_systems_by_tes_machine_types_with_fuel": aggregate_changes_regional_energy_systems_by_tes_machine_types_with_fuel(rows),
        "aggregate_changes_by_union_energy_systems": aggregate_changes_by_union_energy_systems(rows),
        "aggregate_changes_union_energy_systems_by_station_types": aggregate_changes_union_energy_systems_by_station_types(rows),
        "aggregate_changes_union_energy_systems_by_station_types_with_events": aggregate_changes_union_energy_systems_by_station_types_with_events(rows),
        "aggregate_changes_union_energy_systems_by_station_types_with_fuel": aggregate_changes_union_energy_systems_by_station_types_with_fuel(rows),
        "aggregate_changes_union_energy_systems_by_tes_types": aggregate_changes_union_energy_systems_by_tes_types(rows),
        "aggregate_changes_union_energy_systems_by_tes_types_with_fuel": aggregate_changes_union_energy_systems_by_tes_types_with_fuel(rows),
        "aggregate_changes_union_energy_systems_by_tes_machine_types": aggregate_changes_union_energy_systems_by_tes_machine_types(rows),
        "aggregate_changes_union_energy_systems_by_tes_machine_types_with_fuel": aggregate_changes_union_energy_systems_by_tes_machine_types_with_fuel(rows),
        "aggregate_changes_by_energy_system_types": aggregate_changes_by_energy_system_types(rows),
        "aggregate_changes_energy_system_types_by_station_types": aggregate_changes_energy_system_types_by_station_types(rows),
        "aggregate_changes_energy_system_types_by_station_types_with_events": aggregate_changes_energy_system_types_by_station_types_with_events(rows),
        "aggregate_changes_energy_system_types_by_station_types_with_fuel": aggregate_changes_energy_system_types_by_station_types_with_fuel(rows),
        "aggregate_changes_energy_system_types_by_tes_types": aggregate_changes_energy_system_types_by_tes_types(rows),
        "aggregate_changes_energy_system_types_by_tes_types_with_fuel": aggregate_changes_energy_system_types_by_tes_types_with_fuel(rows),
        "aggregate_changes_energy_system_types_by_tes_machine_types": aggregate_changes_energy_system_types_by_tes_machine_types(rows),
        "aggregate_changes_energy_system_types_by_tes_machine_types_with_fuel": aggregate_changes_energy_system_types_by_tes_machine_types_with_fuel(rows),
        "aggregate_changes_by_total_energy_system_types": aggregate_changes_by_total_energy_system_types(rows),
        "aggregate_changes_total_energy_system_types_by_station_types": aggregate_changes_total_energy_system_types_by_station_types(rows),
        "aggregate_changes_total_energy_system_types_by_station_types_with_events": aggregate_changes_total_energy_system_types_by_station_types_with_events(rows),
        "aggregate_changes_total_energy_system_types_by_station_types_with_fuel": aggregate_changes_total_energy_system_types_by_station_types_with_fuel(rows),
        "aggregate_changes_total_energy_system_types_by_tes_types": aggregate_changes_total_energy_system_types_by_tes_types(rows),
        "aggregate_changes_total_energy_system_types_by_tes_types_with_fuel": aggregate_changes_total_energy_system_types_by_tes_types_with_fuel(rows),
        "aggregate_changes_total_energy_system_types_by_tes_machine_types": aggregate_changes_total_energy_system_types_by_tes_machine_types(rows),
        "aggregate_changes_total_energy_system_types_by_tes_machine_types_with_fuel": aggregate_changes_total_energy_system_types_by_tes_machine_types_with_fuel(rows),
    })

    result["database_version_id"] = current_db_version_id
    return result


def build_tites_total_aggregates(context: dict, event_types: list[tuple[str, str]]):
    """
    Формирует агрегаты "ТИТЭС, всего" как сумму по всем типам энергосистем,
    чье имя содержит 'титэс' (например, 'ТИТЭС Востока', 'ТИТЭС Сибири').
    """
    from decimal import Decimal
    from collections import defaultdict

    energy_system_type_names = context.get("energy_system_type_names", {}) or {}
    energy_system_types_yearly_p_ust = context.get("energy_system_types_yearly_p_ust", {}) or {}
    energy_system_types_by_station_types_yearly_p_ust = context.get("energy_system_types_by_station_types_yearly_p_ust", {}) or {}
    station_type_list = context.get("station_type_list", {}) or {}

    # IDs типов энергосистем, относящихся к ТИТЭС
    tites_es_type_ids = [
        est_id for est_id, name in energy_system_type_names.items()
        if name and "титэс" in str(name).lower().replace(" ", "")
    ]

    # event -> year -> sum
    tites_yearly_p_ust = defaultdict(lambda: defaultdict(Decimal))
    for est_id in tites_es_type_ids:
        ev_map = energy_system_types_yearly_p_ust.get(est_id, {}) or {}
        for ev_code, year_map in (ev_map or {}).items():
            for year, val in (year_map or {}).items():
                if val is None:
                    continue
                tites_yearly_p_ust[ev_code][year] += val or Decimal(0)

    # station_type_id -> event -> year -> sum
    tites_by_station_types = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    for est_id in tites_es_type_ids:
        st_map = energy_system_types_by_station_types_yearly_p_ust.get(est_id, {}) or {}
        for st_id, ev_map in (st_map or {}).items():
            for ev_code, year_map in (ev_map or {}).items():
                for year, val in (year_map or {}).items():
                    if val is None:
                        continue
                    tites_by_station_types[st_id][ev_code][year] += val or Decimal(0)

    # rowspan для блока "ТИТЭС, всего"
    event_codes = [code for code, _ in event_types]
    rows = 0
    for ev_code in event_codes:
        if tites_yearly_p_ust.get(ev_code):
            rows += 1
            # строки по типам станций
            for st_id in station_type_list.keys():
                if st_id == 0:
                    continue
                if (tites_by_station_types.get(st_id, {}) or {}).get(ev_code):
                    rows += 1

    return {
        "tites_es_type_ids": tites_es_type_ids,
        "tites_yearly_p_ust": tites_yearly_p_ust,
        "tites_by_station_types_yearly_p_ust": tites_by_station_types,
        "tites_total_rowspan": rows or 1,
    }

    
def load_all_machines_with_changes(
    station_ids: list[int],
    start_year: int,
    end_year: int,
    rounding_digits: int = 1,
    event_type_filter: list[str] | None = None,
) -> list[Machine]:
    current_db_version_id = get_current_db_version_id()
    machines_query = Machine.query.options(
        joinedload(Machine.machine_station).joinedload(Station.regional_district),
        joinedload(Machine.machine_station).joinedload(Station.station_type),
        joinedload(Machine.gen_company),
        selectinload(Machine.machine_powers),
        selectinload(Machine.machine_fuels),
        selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
        joinedload(Machine.tes_machine_type),
    )
    machines_query = filter_by_explicit_db_version(machines_query, Machine, current_db_version_id)
    machines = machines_query.filter(Machine.id_station.in_(station_ids)).all()

    # Фильтруем связанные данные по версии БД после загрузки
    # (selectinload загружает все связанные записи, нужно отфильтровать вручную)
    for m in machines:
        # Фильтруем machine_powers по версии БД
        if hasattr(m, 'machine_powers') and m.machine_powers:
            m.machine_powers = [
                mp for mp in m.machine_powers
                if getattr(mp, 'database_version_id', None) == current_db_version_id
                or (current_db_version_id is None and getattr(mp, 'database_version_id', None) is None)
            ]
        
        # Фильтруем machine_fuels по версии БД
        if hasattr(m, 'machine_fuels') and m.machine_fuels:
            m.machine_fuels = [
                mf for mf in m.machine_fuels
                if getattr(mf, 'database_version_id', None) == current_db_version_id
                or (current_db_version_id is None and getattr(mf, 'database_version_id', None) is None)
            ]
        
        # Фильтруем machine_tes_types по версии БД
        if hasattr(m, 'machine_tes_types') and m.machine_tes_types:
            m.machine_tes_types = [
                mtt for mtt in m.machine_tes_types
                if getattr(mtt, 'database_version_id', None) == current_db_version_id
                or (current_db_version_id is None and getattr(mtt, 'database_version_id', None) is None)
            ]

    # Назначаем данные по годам
    for m in machines:
        assign_machine_powers_changes_by_year(m, start_year, end_year, rounding_digits)

    # Фильтрация по типу мероприятия
    if event_type_filter:
        # event_type_filter содержит коды событий, а у машины сохранено множество codes в m.event_types
        event_codes = set(event_type_filter)
        
        # Фильтруем машины, у которых есть хотя бы одно выбранное событие
        machines = [m for m in machines if hasattr(m, "event_types") and m.event_types and (m.event_types & event_codes)]
        
        # Для каждой машины фильтруем powers_by_year, оставляя только строки с выбранными событиями
        for m in machines:
            m.powers_by_year = [p for p in m.powers_by_year if p["event"] in event_codes]
            m.total_rows = len(m.powers_by_year)
            # Обновляем event_types - оставляем только те, что есть в отфильтрованных строках
            m.event_types = set(p["event"] for p in m.powers_by_year)

    return machines


def apply_all_rowspans_for_station(machines: list[Machine]):
    """
    Применяет rowspans для всех машин одной станции.
    В списке машины одной станции, но могут быть с разными генкомпаниями.
    
    Устанавливает начальные значения для station_rowspan и fuel_rowspan.
    region_rowspan и gen_company_rowspan устанавливаются глобально.
    """
    def apply_rowspan_grouping(machines, key_func, attr_name: str, use_total_rows: bool = False):
        from collections import defaultdict

        group_map = defaultdict(list)
        for m in machines:
            key = key_func(m)
            group_map[key].append(m)

        for group in group_map.values():
            # Суммируем total_rows при необходимости
            rowspan = sum(m.total_rows if use_total_rows else 1 for m in group)

            if use_total_rows:
                # Назначаем rowspan первому видимому агрегату в группе
                leader_index = next((i for i, gm in enumerate(group) if gm.total_rows > 0), None)
                for i, gm in enumerate(group):
                    if leader_index is not None and i == leader_index and rowspan > 0:
                        setattr(gm, attr_name, rowspan)
                    else:
                        setattr(gm, attr_name, 0)
            else:
                used_rows = 0
                for m in group:
                    if used_rows == 0:
                        setattr(m, attr_name, rowspan)
                    else:
                        setattr(m, attr_name, 0)
                    used_rows += 1

    if not machines:
        return
    
    # Все машины относятся к одной станции, но могут быть с разными генкомпаниями
    # Устанавливаем только station_rowspan и fuel_rowspan
    # region_rowspan и gen_company_rowspan будут установлены глобально
    
    # 1. Станция - объединяем все машины одной станции (по станциям внутри генкомпании)
    apply_rowspan_grouping(
        machines,
        key_func=lambda m: (
            m.machine_station.id if m.machine_station else None,
            m.gen_company.id if m.gen_company else None
        ),
        attr_name="station_rowspan",
        use_total_rows=True,
    )

    # 2. Топливо - группируем по fuel_so (как было)
    apply_rowspan_grouping(
        machines,
        key_func=lambda m: m.fuel_so or '',
        attr_name="fuel_rowspan",
        use_total_rows=True,
    )


def assign_machine_powers_changes_by_year(machine, start_year, end_year, rounding_digits):
    machine.powers_by_year = []
    machine.event_types = set()
    machine.total_rows = 0

    # ВАЖНО:
    # Нельзя считать события только по данным внутри [start_year; end_year]:
    # при сдвиге start_year "ввод мощности" и "изменение мощности" могут
    # ошибочно "перепрыгивать" на первый год диапазона.
    #
    # Поэтому сравнения делаем с учетом граничных лет start_year-1 и end_year+1,
    # но сами события добавляем ТОЛЬКО если их фактический год попадает в диапазон.

    if not getattr(machine, "machine_powers", None):
        return

    # Собираем мощности по годам в словарь (на случай дублей по году берём последнюю)
    year_to_power: dict[int, float] = {}
    for mp in machine.machine_powers:
        y = getattr(mp, "year_number", None)
        if y is None:
            continue
        if y < start_year - 1 or y > end_year + 1:
            continue
        year_to_power[int(y)] = round(float(getattr(mp, "p_ust", 0) or 0), rounding_digits)

    if not year_to_power:
        return

    # 1) Изменение мощности (before/after/delta) — событие относится к году Y,
    # где значение изменилось относительно предыдущего года (Y-1)
    for year in range(start_year, end_year + 1):
        if year not in year_to_power or (year - 1) not in year_to_power:
            continue
        prev_value = year_to_power[year - 1]
        value = year_to_power[year]
        if value != prev_value and prev_value > 0 and value > 0:
            delta = value - prev_value
            machine.event_types.update({"before_modernization", "after_modernization", "change_power"})
            machine.powers_by_year.extend([
                {"year": year, "p_ust": prev_value, "event": "before_modernization"},
                {"year": year, "p_ust": value, "event": "after_modernization"},
                {"year": year, "p_ust": delta, "event": "change_power"},
            ])
            machine.total_rows += 3

    # 2) Вывод из эксплуатации — фиксируем год (Y), где мощность стала 0,
    # а в предыдущем году (Y-1) была > 0.
    for year in range(start_year, end_year + 1):
        if year not in year_to_power or (year - 1) not in year_to_power:
            continue
        prev_value = year_to_power[year - 1]
        value = year_to_power[year]
        if prev_value > 0 and value == 0:
            machine.event_types.add("decommission")
            machine.powers_by_year.append({
                "year": year,
                "p_ust": prev_value,
                "event": "decommission",
            })
            machine.total_rows += 1

    # 3) Ввод мощности — фиксируем ТОЛЬКО фактический год первого положительного значения,
    # но добавляем его лишь если он попадает в [start_year; end_year] (без "перетекания").
    positive_years = sorted([y for y, v in year_to_power.items() if v > 0])
    if positive_years:
        commission_year = positive_years[0]
        if start_year <= commission_year <= end_year:
            machine.event_types.add("commission")
            machine.powers_by_year.append({
                "year": commission_year,
                "p_ust": year_to_power[commission_year],
                "event": "commission",
            })
            machine.total_rows += 1

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

            # 🏷 Сохраняем имена для сортировки (всегда) и для отображения (если include_names=True)
            # Имена нужны для сортировки субъектов РФ по алфавиту
            rd_names[rd_id] = station.regional_district.name if station.regional_district else ""
            
            if include_names:
                est_names[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
                ues_names[ues_id] = ues.name
                res_names[res_id] = res.name
                eu_names[eu_id] = eu_name

    # Упорядочиваем уровень ОЭС по display_order (None и неизвестные — в конец)
    # Используем кэшируемый список ОЭС, уже отсортированный по display_order
    from collections import OrderedDict
    try:
        ues_sorted_list = get_union_energy_system_list_full()
        ues_order_index = {ues.id: idx for idx, ues in enumerate(ues_sorted_list)}
    except Exception:
        # На случай непредвиденной ошибки — не ломаем отображение
        ues_order_index = {}

    # Сортируем типы энергосистем по минимальному display_order ОЭС внутри них
    def _min_ues_index(es_group):
        indices = [ues_order_index.get(ues_id, 10**9) for ues_id in es_group.keys()]
        return min(indices) if indices else 10**9

    sorted_est_items = sorted(
        grouped_data.items(),
        key=lambda kv: _min_ues_index(kv[1])
    )

    sorted_grouped_data = OrderedDict()
    for est_id, ues_group in sorted_est_items:
        # Сортируем ключи ОЭС внутри каждого типа энергосистемы по индексам из ues_order_index
        sorted_ues_items = sorted(
            ues_group.items(),
            key=lambda kv: ues_order_index.get(kv[0], 10**9)
        )
        sorted_ues_dict = OrderedDict()
        for ues_id, res_group in sorted_ues_items:
            # Сортируем РЭС внутри каждого ОЭС
            sorted_res_items = sorted(res_group.items())
            sorted_res_dict = OrderedDict()
            for res_id, rd_group in sorted_res_items:
                # Сортируем субъекты РФ по алфавиту (по name)
                sorted_rd_items = sorted(
                    rd_group.items(),
                    key=lambda kv: (rd_names.get(kv[0], "").lower(), kv[0])
                )
                sorted_rd_dict = OrderedDict()
                for rd_id, eu_group in sorted_rd_items:
                    # Сортируем энергоузлы
                    sorted_eu_items = sorted(eu_group.items())
                    sorted_rd_dict[rd_id] = OrderedDict(sorted_eu_items)
                sorted_res_dict[res_id] = sorted_rd_dict
            sorted_ues_dict[ues_id] = sorted_res_dict
        sorted_grouped_data[est_id] = sorted_ues_dict

    grouped_data = sorted_grouped_data

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


def build_sync_area_hierarchy_structure_for_changes(stations: list[Station], include_names: bool = False):
    """
    Строит иерархию для страницы station_changes_list в требуемом порядке:
    Синхронная зона -> Тип энергосистемы -> ОЭС -> Субъект РФ -> Станции

    Важно:
    - Синхронная зона берется из RegionalDistrict.id_synchronous_area (может быть None -> 0).
    - Станция может попадать в несколько ОЭС/типов энергосистемы, если у субъекта несколько РЭС.
      Чтобы не дублировать станцию многократно в рамках одной и той же ОЭС, делаем дедуп по (est_id, ues_id).
    """
    from collections import defaultdict, OrderedDict
    import re

    grouped_data = defaultdict(  # sa_id
        lambda: defaultdict(      # est_id
            lambda: defaultdict(  # ues_id
                lambda: defaultdict(list)  # rd_id -> [stations]
            )
        )
    )

    # Для отображения имен при include_names=True
    sa_names = {}
    est_names = {}
    ues_names = {}
    rd_names = {}

    # Справочник синхронных зон — для сортировки
    try:
        from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
            get_synchronous_area_list_full,
        )
        sa_list = get_synchronous_area_list_full() or []
        sa_by_id = {sa.id: sa for sa in sa_list if getattr(sa, "id", None) is not None}
    except Exception:
        sa_by_id = {}

    def _sync_area_sort_key(sa_id: int):
        sa = sa_by_id.get(sa_id)
        if not sa:
            # "Не указано" (0/None) и неизвестные — в конец
            return (9, 999, "")

        name = (getattr(sa, "name", "") or "").strip()
        number = (getattr(sa, "number", "") or "").strip()
        name_l = name.lower()

        # 1) Калининград — всегда первым
        if "калининград" in name_l:
            return (0, 0, name_l)

        # 2) Затем зоны по номеру (1, 2, ...), поддерживаем варианты:
        #    - number="1"
        #    - name содержит цифру ("1-ая", "зона 2")
        #    - словесные ("первая", "вторая")
        #    - римские ("I", "II")
        n = None
        # 2.1: явное поле number
        if number.isdigit():
            try:
                n = int(number)
            except Exception:
                n = None
        # 2.2: цифры в имени
        if n is None:
            m = re.search(r"(\d+)", name_l)
            if m:
                try:
                    n = int(m.group(1))
                except Exception:
                    n = None
        # 2.3: словесные порядковые
        if n is None:
            if "перва" in name_l:
                n = 1
            elif "втор" in name_l:
                n = 2
            elif "трет" in name_l:
                n = 3
        # 2.4: римские (I/II/III)
        if n is None:
            roman = name_l.replace(" ", "")
            if roman in ("i", "i-а", "i-я", "i-ая", "i-яя"):
                n = 1
            elif roman in ("ii", "ii-а", "ii-я", "ii-ая", "ii-яя"):
                n = 2
            elif roman in ("iii", "iii-а", "iii-я", "iii-ая", "iii-яя"):
                n = 3
        if n is not None:
            return (1, n, name_l)

        # 3) Остальные — по имени
        return (2, 999, name_l)

    # Упорядочивание ОЭС по display_order (уже реализовано в get_union_energy_system_list_full)
    try:
        ues_sorted_list = get_union_energy_system_list_full()
        ues_order_index = {ues.id: idx for idx, ues in enumerate(ues_sorted_list)}
    except Exception:
        ues_order_index = {}

    def _min_ues_index(es_group):
        indices = [ues_order_index.get(ues_id, 10**9) for ues_id in es_group.keys()]
        return min(indices) if indices else 10**9

    for station in stations:
        # Пропускаем станции без субъекта РФ или без энергосистем
        if not station.regional_district or not station.regional_district.regional_energy_systems:
            continue

        sa_id = getattr(station.regional_district, "id_synchronous_area", None) or 0
        rd_id = station.id_regional_district

        # Для сортировки субъектов РФ по алфавиту
        rd_names[rd_id] = station.regional_district.name if station.regional_district else ""

        # Имена синхронных зон (для include_names)
        if include_names:
            sa_obj = sa_by_id.get(sa_id)
            sa_names[sa_id] = (getattr(sa_obj, "name", None) if sa_obj else None) or ("Не указано" if sa_id == 0 else f"id={sa_id}")

        # Собираем уникальные пары (est_id, ues_id) по всем РЭС субъекта
        seen_pairs: set[tuple[int, int]] = set()
        for res in station.regional_district.regional_energy_systems:
            ues = getattr(res, "union_energy_system", None)
            if not ues:
                continue

            est_id = getattr(ues, "id_energy_system_type", None) or 0
            ues_id = getattr(ues, "id", None)
            if not ues_id:
                continue

            pair = (est_id, ues_id)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            grouped_data[sa_id][est_id][ues_id][rd_id].append(station)

            if include_names:
                est_names[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
                ues_names[ues_id] = ues.name

    # Сортировка иерархии
    sorted_sa_items = sorted(grouped_data.items(), key=lambda kv: (_sync_area_sort_key(kv[0]), kv[0]))
    sorted_grouped_data = OrderedDict()

    for sa_id, est_group in sorted_sa_items:
        # Сортируем типы энергосистем по минимальному display_order ОЭС внутри них
        sorted_est_items = sorted(est_group.items(), key=lambda kv: _min_ues_index(kv[1]))
        sorted_est_dict = OrderedDict()

        for est_id, ues_group in sorted_est_items:
            # Сортируем ОЭС по display_order
            sorted_ues_items = sorted(ues_group.items(), key=lambda kv: ues_order_index.get(kv[0], 10**9))
            sorted_ues_dict = OrderedDict()

            for ues_id, rd_group in sorted_ues_items:
                # Сортируем субъекты РФ по алфавиту (по name)
                sorted_rd_items = sorted(
                    rd_group.items(),
                    key=lambda kv: (rd_names.get(kv[0], "").lower(), kv[0])
                )
                sorted_ues_dict[ues_id] = OrderedDict(sorted_rd_items)

            sorted_est_dict[est_id] = sorted_ues_dict

        sorted_grouped_data[sa_id] = sorted_est_dict

    result = {
        "grouped_stations": sorted_grouped_data,
        "stations": stations,
    }

    if include_names:
        result.update({
            "synchronous_area_name": sa_names,
            "energy_system_type_name": est_names,
            "union_energy_system_name": ues_names,
            "regional_district_name": rd_names,
        })

    return result


def build_est_then_sync_area_hierarchy_structure_for_changes(stations: list[Station], include_names: bool = False):
    """
    Иерархия для station_changes_list в требуемом порядке:
    Тип энергосистемы (ЕЭС -> ТИТЭС -> прочее) ->
      - для ЕЭС/прочих: Синхронная зона (Калининград -> 1 -> 2 -> прочее)
      - для ТИТЭС: без второго уровня (одна группа), далее ОЭС -> РЭС -> субъект
    -> ОЭС -> РЭС -> Субъект РФ -> Станции
    """
    from collections import defaultdict, OrderedDict
    import re

    grouped_data = defaultdict(  # est_id
        lambda: defaultdict(      # second_level_id (sa_id или energy_zone_id)
            lambda: defaultdict(  # ues_id
                lambda: defaultdict(  # res_id (id_regional_energy_system)
                    lambda: defaultdict(list)  # rd_id -> [stations]
                )
            )
        )
    )

    # Для отображения имен при include_names=True
    sa_names = {}
    # Энергоузлы нужны для спец-логики ОЭС "ТИТЭС Сибири"
    eu_names = {}
    est_names = {}
    ues_names = {}
    rd_names = {}

    # Справочник синхронных зон — для сортировки
    try:
        from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
            get_synchronous_area_list_full,
        )
        sa_list = get_synchronous_area_list_full() or []
        sa_by_id = {sa.id: sa for sa in sa_list if getattr(sa, "id", None) is not None}
    except Exception:
        sa_by_id = {}

    # Справочник энергоузлов — для отображения/сортировки в спец-кейсе
    try:
        from app.common.services.get_services.energy_systems.energy_unit_get_services import (
            get_energy_unit_list_full,
        )
        eu_list = get_energy_unit_list_full() or []
        eu_by_id = {eu.id: eu for eu in eu_list if getattr(eu, "id", None) is not None}
    except Exception:
        eu_by_id = {}

    def _sync_area_sort_key(sa_id: int):
        sa = sa_by_id.get(sa_id)
        if not sa:
            return (9, 999, "")

        name = (getattr(sa, "name", "") or "").strip()
        number = (getattr(sa, "number", "") or "").strip()
        name_l = name.lower()

        if "калининград" in name_l:
            return (0, 0, name_l)

        n = None
        if number.isdigit():
            try:
                n = int(number)
            except Exception:
                n = None
        if n is None:
            m = re.search(r"(\d+)", name_l)
            if m:
                try:
                    n = int(m.group(1))
                except Exception:
                    n = None
        if n is None:
            if "перва" in name_l:
                n = 1
            elif "втор" in name_l:
                n = 2
            elif "трет" in name_l:
                n = 3
        if n is None:
            roman = name_l.replace(" ", "")
            if roman in ("i", "i-а", "i-я", "i-ая", "i-яя"):
                n = 1
            elif roman in ("ii", "ii-а", "ii-я", "ii-ая", "ii-яя"):
                n = 2
            elif roman in ("iii", "iii-а", "iii-я", "iii-ая", "iii-яя"):
                n = 3
        if n is not None:
            return (1, n, name_l)
        return (2, 999, name_l)

    def _energy_zone_sort_key(_ez_id: int):
        return (9, 999, "")

    # Упорядочивание ОЭС по display_order (уже реализовано в get_union_energy_system_list_full)
    try:
        ues_sorted_list = get_union_energy_system_list_full()
        ues_order_index = {ues.id: idx for idx, ues in enumerate(ues_sorted_list)}
    except Exception:
        ues_order_index = {}

    def _est_sort_key(est_id: int, est_name: str):
        n = (est_name or "").strip().lower()
        if "еэс" in n:
            return (0, 0, n)
        if "титэс" in n or "титэс" in n.replace(" ", ""):
            return (1, 0, n)
        return (2, 0, n)

    for station in stations:
        if not station.regional_district or not station.regional_district.regional_energy_systems:
            continue

        rd_id = station.id_regional_district
        sa_id = getattr(station.regional_district, "id_synchronous_area", None) or 0

        rd_names[rd_id] = station.regional_district.name if station.regional_district else ""

        if include_names:
            sa_obj = sa_by_id.get(sa_id)
            sa_names[sa_id] = (getattr(sa_obj, "name", None) if sa_obj else None) or ("Не указано" if sa_id == 0 else f"id={sa_id}")

        # Предпочитаем прямую РЭС станции, если она задана (избегаем размножения станции по всем РЭС субъекта)
        res_candidates = []
        direct_res = getattr(station, "regional_energy_system_obj", None)
        if direct_res is not None:
            res_candidates = [direct_res]
        else:
            res_candidates = list(station.regional_district.regional_energy_systems or [])

        # Дедуп станции в рамках (est_id, second_level_id, ues_id, res_id)
        seen_keys: set[tuple[int, int, int, int]] = set()
        for res in res_candidates:
            ues = getattr(res, "union_energy_system", None)
            if not ues:
                continue

            est_id = getattr(ues, "id_energy_system_type", None) or 0
            ues_id = getattr(ues, "id", None)
            if not ues_id:
                continue
            res_id = getattr(res, "id", None) or 0

            est_name = (getattr(getattr(ues, "energy_system_type", None), "name", "") or "")
            is_tites = "титэс" in est_name.lower().replace(" ", "")
            ues_name = (getattr(ues, "name", "") or "")
            is_tites_siberia_ues = ("титэс сибири" in ues_name.lower())

            # Для ТИТЭС второй уровень отсутствует (одна группа)
            second_level_id = 0 if is_tites else int(sa_id)

            key = (est_id, second_level_id, int(ues_id), int(res_id))
            if key in seen_keys:
                continue
            seen_keys.add(key)

            # Спец-логика: для ОЭС "ТИТЭС Сибири" вместо субъекта группируем по энергоузлу
            if is_tites and is_tites_siberia_ues:
                eu_id = getattr(station, "id_energy_unit", None) or 0
                grouped_data[est_id][second_level_id][int(ues_id)][int(res_id)][int(eu_id)].append(station)
                if include_names:
                    eu_obj = eu_by_id.get(eu_id)
                    eu_name = (getattr(eu_obj, "name", None) if eu_obj else None) or ("Без энергоузла" if eu_id == 0 else f"id={eu_id}")
                    eu_names[int(eu_id)] = eu_name
                # для сортировки на этом уровне используем имена энергоузлов
                rd_names[int(eu_id)] = eu_names.get(int(eu_id), "")
            else:
                grouped_data[est_id][second_level_id][int(ues_id)][int(res_id)][rd_id].append(station)

            if include_names:
                est_names[est_id] = ues.energy_system_type.name if ues.energy_system_type else f"id={est_id}"
                ues_names[int(ues_id)] = ues.name

    # Сортировки: тип энергосистемы (ЕЭС -> ТИТЭС), затем синхронная зона (Калининград -> 1 -> 2)
    sorted_est_items = sorted(
        grouped_data.items(),
        key=lambda kv: (_est_sort_key(kv[0], est_names.get(kv[0], "")), kv[0])
    )

    sorted_grouped_data = OrderedDict()
    for est_id, sa_group in sorted_est_items:
        est_name = (est_names.get(est_id, "") or "").lower().replace(" ", "")
        is_tites_est = "титэс" in est_name
        if is_tites_est:
            # Одна группа (0) — фактически пропускаем второй уровень для ТИТЭС
            sorted_second_items = sorted(sa_group.items(), key=lambda kv: (kv[0] != 0, kv[0]))
        else:
            sorted_second_items = sorted(sa_group.items(), key=lambda kv: (_sync_area_sort_key(kv[0]), kv[0]))

        sorted_sa_dict = OrderedDict()

        for sa_id, ues_group in sorted_second_items:
            sorted_ues_items = sorted(ues_group.items(), key=lambda kv: ues_order_index.get(kv[0], 10**9))
            sorted_ues_dict = OrderedDict()

            for ues_id, res_group in sorted_ues_items:
                # РЭС внутри ОЭС (просто по id; если понадобится — можно по name)
                sorted_res_items = sorted(res_group.items(), key=lambda kv: kv[0])
                sorted_res_dict = OrderedDict()

                for res_id, rd_group in sorted_res_items:
                    sorted_rd_items = sorted(
                        rd_group.items(),
                        key=lambda kv: (rd_names.get(kv[0], "").lower(), kv[0])
                    )
                    sorted_res_dict[res_id] = OrderedDict(sorted_rd_items)

                sorted_ues_dict[ues_id] = sorted_res_dict

            sorted_sa_dict[sa_id] = sorted_ues_dict

        sorted_grouped_data[est_id] = sorted_sa_dict

    result = {
        "grouped_stations": sorted_grouped_data,
        "stations": stations,
    }

    if include_names:
        result.update({
            "synchronous_area_name": sa_names,
            "energy_unit_name": eu_names,
            "energy_system_type_name": est_names,
            "union_energy_system_name": ues_names,
            "regional_district_name": rd_names,
        })

    return result


def get_station_list_template_context(form, data, rounding_digits, filters, show_all=False):
    import time

    start_time = time.time()
    year_features = get_year_feature_dict()

    # Сбрасываем LRU-кэши, чтобы не получать оторванные от сессии экземпляры
    cache_functions = [
        get_energy_system_type_list_full,
        get_union_energy_system_list_full,
        get_gen_company_list_full,
    ]
    for func in cache_functions:
        if hasattr(func, "cache_clear"):
            func.cache_clear()

    # Принудительно инициализируем текущую версию для фильтрации данных
    get_current_version()

    energy_system_type_query = EnergySystemType.query
    energy_system_type_query = filter_by_db_version(energy_system_type_query, EnergySystemType)
    energy_system_type_objects = energy_system_type_query.order_by(EnergySystemType.id.asc()).all()
    energy_system_type_list = [
        {"id": est.id, "name": est.name}
        for est in energy_system_type_objects
    ]
    energy_system_type_names = get_energy_system_type_map()

    union_energy_system_query = UnionEnergySystem.query
    union_energy_system_query = filter_by_db_version(union_energy_system_query, UnionEnergySystem)
    union_energy_system_objects = union_energy_system_query.order_by(
        UnionEnergySystem.display_order.asc(), UnionEnergySystem.name.asc()
    ).all()
    union_energy_system_list = [
        {
            "id": ues.id,
            "name": ues.name,
            "name_full": getattr(ues, "name_full", None),
        }
        for ues in union_energy_system_objects
    ]
    union_energy_system_names = get_union_energy_systems_map()
    regional_energy_system_mapping = get_ues_to_res_ids_map()
    
    # Получаем все маппинги для взаимоувязанных фильтров
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_est_to_ues_ids_map,
        get_est_to_res_ids_map,
        get_est_to_rd_ids_map,
        get_est_to_fd_ids_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_ues_to_est_id_map,
        get_ues_to_rd_ids_map,
        get_ues_to_fd_ids_map,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_res_to_est_id_map,
        get_res_to_rd_ids_map,
        get_res_to_fd_ids_map,
        get_res_to_ues_id_map,
    )
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_rd_to_res_ids_map,
        get_rd_to_ues_ids_map,
        get_rd_to_est_ids_map,
        get_rd_to_fd_id_map,
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_fd_to_res_ids_map,
        get_fd_to_ues_ids_map,
        get_fd_to_est_ids_map,
    )
    
    est_to_ues_mapping = get_est_to_ues_ids_map()
    est_to_res_mapping = get_est_to_res_ids_map()
    est_to_rd_mapping = get_est_to_rd_ids_map()
    est_to_fd_mapping = get_est_to_fd_ids_map()
    ues_to_est_mapping = get_ues_to_est_id_map()
    ues_to_rd_mapping = get_ues_to_rd_ids_map()
    ues_to_fd_mapping = get_ues_to_fd_ids_map()
    res_to_est_mapping = get_res_to_est_id_map()
    res_to_rd_mapping = get_res_to_rd_ids_map()
    res_to_fd_mapping = get_res_to_fd_ids_map()
    res_to_ues_mapping_one = get_res_to_ues_id_map()  # один-к-одному
    rd_to_res_mapping = get_rd_to_res_ids_map()
    rd_to_ues_mapping = get_rd_to_ues_ids_map()
    rd_to_est_mapping = get_rd_to_est_ids_map()
    rd_to_fd_mapping_one = get_rd_to_fd_id_map()  # один-к-одному
    fd_to_res_mapping = get_fd_to_res_ids_map()
    fd_to_ues_mapping = get_fd_to_ues_ids_map()
    fd_to_est_mapping = get_fd_to_est_ids_map()

    regional_energy_system_query = RegionalEnergySystem.query
    regional_energy_system_query = filter_by_db_version(regional_energy_system_query, RegionalEnergySystem)
    regional_energy_system_objects = regional_energy_system_query.order_by(
        RegionalEnergySystem.id.asc()
    ).all()
    regional_energy_system_list = [
        {
            "id": res.id,
            "name": res.name,
            "name_full": getattr(res, "name_full", None),
        }
        for res in regional_energy_system_objects
    ]
    regional_energy_system_names = get_regional_energy_systems_map()

    federal_district_query = FederalDistrict.query
    federal_district_query = filter_by_db_version(federal_district_query, FederalDistrict)
    federal_district_objects = federal_district_query.order_by(FederalDistrict.id.asc()).all()
    federal_district_list = [
        {"id": fd.id, "name": fd.name}
        for fd in federal_district_objects
    ]
    regional_district_mapping = get_fd_to_rd_ids_map()

    regional_district_query = RegionalDistrict.query
    regional_district_query = filter_by_db_version(regional_district_query, RegionalDistrict)
    regional_district_objects = regional_district_query.order_by(RegionalDistrict.id.asc()).all()
    regional_district_list = [
        {
            "id": rd.id,
            "name": rd.name,
            "name_full": getattr(rd, "name_full", None),
        }
        for rd in regional_district_objects
    ]
    regional_district_names = get_regional_districts_map()
    # Родительный падеж для итоговых строк "Итого по ..."
    regional_district_names_rp = {rd.id: getattr(rd, "name_rp", None) for rd in regional_district_objects if getattr(rd, "id", None) is not None}

    energy_unit_query = EnergyUnit.query
    energy_unit_query = filter_by_db_version(energy_unit_query, EnergyUnit)
    energy_units = energy_unit_query.order_by(EnergyUnit.id.asc()).all()
    energy_unit_names = {eu.id: eu.name for eu in energy_units}

    station_type_query = StationType.query
    station_type_query = filter_by_db_version(station_type_query, StationType)
    station_type_names = station_type_query.order_by(StationType.id.asc()).all()
    station_type_list = {st.id: st.name for st in station_type_names}

    tes_type_query = TesType.query
    tes_type_query = filter_by_db_version(tes_type_query, TesType)
    tes_type_names = tes_type_query.order_by(TesType.id.asc()).all()
    tes_type_list = {tt.id: tt.name for tt in tes_type_names}

    tes_machine_type_query = TesMachineType.query
    tes_machine_type_query = filter_by_db_version(tes_machine_type_query, TesMachineType)
    tes_machine_type_names = tes_machine_type_query.order_by(TesMachineType.id.asc()).all()
    tes_machine_type_list = {tmt.id: tmt.name for tmt in tes_machine_type_names}

    pgu_tes_machine_type_query = PGUTesMachineType.query
    pgu_tes_machine_type_query = filter_by_db_version(pgu_tes_machine_type_query, PGUTesMachineType)
    pgu_tes_machine_type_names = pgu_tes_machine_type_query.order_by(PGUTesMachineType.id.asc()).all()
    pgu_tes_machine_type_list = {pt.id: pt.name for pt in pgu_tes_machine_type_names}

    fuel_type_query = FuelType.query
    fuel_type_query = filter_by_db_version(fuel_type_query, FuelType)
    fuel_type_names = fuel_type_query.order_by(FuelType.id.asc()).all()
    fuel_type_list = {ft.id: ft.name for ft in fuel_type_names}

    machine_tes_types_map = get_current_machine_tes_types_map()

    # Подготовка сериализуемых списков для Select2 (во избежание ошибок JSON-сериализации моделей)
    regional_energy_system_list_json = [
        {
            "id": res["id"],
            "name": res["name"],
            "name_full": res.get("name_full"),
        }
        for res in regional_energy_system_list
    ]
    regional_district_list_json = [
        {
            "id": rd["id"],
            "name": rd["name"],
            "name_full": rd.get("name_full"),
        }
        for rd in regional_district_list
    ]

    stations_grouped = data.get("stations_grouped", {})
    synchronous_area_names = data.get("synchronous_area_names", {}) or {}
    # Event-based агрегаты по энергоузлам (спец-логика ОЭС "ТИТЭС Сибири")
    energy_units_events_yearly_p_ust = (
        data.get("aggregate_changes_by_energy_units_events", {})
        .get("aggregated", {})
        .get("p_ust", {})
    ) or {}
    energy_units_by_station_types_with_events_yearly_p_ust = (
        data.get("aggregate_changes_energy_units_by_station_types_with_events", {})
        .get("aggregated", {})
        .get("p_ust", {})
    ) or {}

    # Для новой структуры верхний уровень уже отсортирован в сервисе.
    sorted_energy_system_type_ids = list(stations_grouped.keys()) if stations_grouped else []

    # Годы с признаком "план" в отображаемом периоде (для итого-колонки)
    try:
        _sy = int(filters.get("start_year") or 0)
        _ey = int(filters.get("end_year") or -1)
        plan_years = [
            y for y in range(_sy, _ey + 1)
            if str(year_features.get(y, "")).strip().lower() == "план"
        ]
    except Exception:
        plan_years = []

    plan_period_start = plan_years[0] if plan_years else None
    plan_period_end = plan_years[-1] if plan_years else None

    context = {
        "form": form,
        "event_types": EVENT_TYPES,
        "event_types_dict": dict(EVENT_TYPES),
        "stations_grouped": stations_grouped,
        "synchronous_area_names": synchronous_area_names,
        "sorted_energy_system_type_ids": sorted_energy_system_type_ids,
        "station_ids": data.get("station_ids", []),
        "total_count": data.get("total_count", 0),
        "total_pages": data.get("total_pages", 1),
        "current_page": data.get("page", 1),
        "per_page": str(data.get("per_page")).lower() if data.get("per_page") is not None else "none",
        "start_year": filters.get("start_year"),
        "end_year": filters.get("end_year"),
        "plan_years": plan_years,
        "plan_period_start": plan_period_start,
        "plan_period_end": plan_period_end,
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
        "regional_district_names_rp": regional_district_names_rp,
        "regional_district_mapping": regional_district_mapping,
        # Новые маппинги для взаимоувязанных фильтров
        "est_to_ues_mapping": est_to_ues_mapping,
        "est_to_res_mapping": est_to_res_mapping,
        "est_to_rd_mapping": est_to_rd_mapping,
        "est_to_fd_mapping": est_to_fd_mapping,
        "ues_to_est_mapping": ues_to_est_mapping,
        "ues_to_rd_mapping": ues_to_rd_mapping,
        "ues_to_fd_mapping": ues_to_fd_mapping,
        "res_to_est_mapping": res_to_est_mapping,
        "res_to_rd_mapping": res_to_rd_mapping,
        "res_to_fd_mapping": res_to_fd_mapping,
        "res_to_ues_mapping_one": res_to_ues_mapping_one,  # один-к-одному
        "rd_to_res_mapping": rd_to_res_mapping,
        "rd_to_ues_mapping": rd_to_ues_mapping,
        "rd_to_est_mapping": rd_to_est_mapping,
        "rd_to_fd_mapping_one": rd_to_fd_mapping_one,  # один-к-одному
        "fd_to_res_mapping": fd_to_res_mapping,
        "fd_to_ues_mapping": fd_to_ues_mapping,
        "fd_to_est_mapping": fd_to_est_mapping,
        "station_type_name": station_type_names,
        "station_type_list": station_type_list,
        "energy_units_events_yearly_p_ust": energy_units_events_yearly_p_ust,
        "energy_units_by_station_types_with_events_yearly_p_ust": energy_units_by_station_types_with_events_yearly_p_ust,
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
        "station_type_filter": filters.get("station_type_filter") or [],
        "tes_type_filter": filters.get("tes_type_filter") or [],
        "tes_machine_type_filter": filters.get("tes_machine_type_filter") or [],
        "pgu_tes_machine_type_filter": filters.get("pgu_tes_machine_type_filter") or [],
        "energy_system_type_filter": filters.get("energy_system_type_filter") or [],
        "union_energy_system_filter": filters.get("union_energy_system_filter") or [],
        "regional_energy_system_filter": filters.get("regional_energy_system_filter") or [],
        "federal_district_filter": filters.get("federal_district_filter") or [],
        "regional_district_filter": filters.get("regional_district_filter") or [],
        "station_fuel_type_filter": filters.get("station_fuel_type_filter"),
        "year_features": year_features,
        "machine_tes_types_map": machine_tes_types_map,
        "energy_unit_names": energy_unit_names,
        # JSON-готовые данные для Select2 в station_changes
        "regional_energy_system_list_json": regional_energy_system_list_json,
        "regional_district_list_json": regional_district_list_json,
    }

    # 📦 Генерация агрегатов по уровням (всегда добавляем, чтобы в шаблонах были суммы)
    energy_unit_aggregates = build_energy_unit_aggregates(data)
    regional_district_aggregates = build_regional_district_aggregates(data)
    regional_energy_system_aggregates = build_regional_energy_system_aggregates(data)
    union_energy_system_aggregates = build_union_energy_system_aggregates(data)
    energy_system_type_aggregates = build_energy_system_type_aggregates(data)
    total_energy_system_type_aggregates = build_total_energy_system_type_aggregates(data)
    synchronous_area_aggregates = build_synchronous_area_aggregates(data)
    energy_zone_aggregates = build_energy_zone_aggregates(data)

    # ⏬ Включаем агрегаты по уровням в context
    context.update(energy_unit_aggregates)
    context.update(regional_district_aggregates)
    context.update(regional_energy_system_aggregates)
    context.update(union_energy_system_aggregates)
    context.update(energy_system_type_aggregates)
    context.update(total_energy_system_type_aggregates)
    context.update(synchronous_area_aggregates)
    context.update(energy_zone_aggregates)

    # Данные для разбивки по мероприятиям (используется в шаблонах include)
    context["aggregate_changes_union_energy_systems_by_station_types_with_events"] = (
        data.get("aggregate_changes_union_energy_systems_by_station_types_with_events", {})
    )
    context["aggregate_changes_regional_energy_systems_by_station_types_with_events"] = (
        data.get("aggregate_changes_regional_energy_systems_by_station_types_with_events", {})
    )
    context["aggregate_changes_energy_system_types_by_station_types_with_events"] = (
        data.get("aggregate_changes_energy_system_types_by_station_types_with_events", {})
    )
    context["aggregate_changes_total_energy_system_types_by_station_types_with_events"] = (
        data.get("aggregate_changes_total_energy_system_types_by_station_types_with_events", {})
    )

    # Динамический rowspan для субъектов РФ
    context["regional_district_rowspans"] = compute_regional_district_rowspans(
        data,
        station_type_list,
        EVENT_TYPES,
    )

    # Динамический rowspan для объединённых энергосистем (ОЭС)
    context["union_energy_system_rowspans"] = compute_union_energy_system_rowspans(
        data,
        station_type_list,
        EVENT_TYPES,
    )

    # Динамический rowspan для типов энергосистем
    context["energy_system_type_rowspans"] = compute_energy_system_type_rowspans(
        data,
        station_type_list,
        EVENT_TYPES,
    )

    # Динамический rowspan для синхронных зон
    context["synchronous_area_rowspans"] = compute_synchronous_area_rowspans(
        context,
        EVENT_TYPES,
    )

    # Динамический rowspan для "итогов по РЭС как по субъекту" (ТИТЭС + Норильск)
    context["regional_energy_system_event_rowspans"] = compute_regional_energy_system_event_rowspans(
        context,
        EVENT_TYPES,
    )

    # Динамический rowspan для "итогов по энергоузлу как по субъекту" (ОЭС "ТИТЭС Сибири")
    context["energy_unit_event_rowspans"] = compute_energy_unit_event_rowspans(
        context,
        EVENT_TYPES,
    )

    # Динамический rowspan для энергозон (ветка ТИТЭС)
    context["energy_zone_rowspans"] = compute_energy_zone_rowspans(
        context,
        EVENT_TYPES,
    )

    # Динамический rowspan для России в целом
    context["total_energy_system_type_rowspans"] = compute_total_energy_system_type_rowspans(
        data,
        station_type_list,
        EVENT_TYPES,
    )

    # Итог "ТИТЭС, всего" (объединяет ТИТЭС Востока/Сибири и т.п.)
    context.update(build_tites_total_aggregates(context, EVENT_TYPES))

    print(f"[TIME] get_station_list_template_context заняла: {time.time() - start_time:.2f} сек")
    return context


def build_energy_unit_aggregates(data):

    return {
        # Основная агрегация
        "energy_units_yearly_p_ust": data["aggregate_changes_by_energy_units"]["aggregated"].get("p_ust", {}),
        "energy_units_yearly_p_ogr": data["aggregate_changes_by_energy_units"]["aggregated"].get("p_ogr", {}),
        "energy_units_yearly_p_rasp": data["aggregate_changes_by_energy_units"]["aggregated"].get("p_rasp", {}),

        # По типам станций
        "energy_units_by_station_types_yearly_p_ust": data["aggregate_changes_energy_units_by_station_types"]["aggregated"].get("p_ust", {}),
        "energy_units_by_station_types_yearly_p_ogr": data["aggregate_changes_energy_units_by_station_types"]["aggregated"].get("p_ogr", {}),
        "energy_units_by_station_types_yearly_p_rasp": data["aggregate_changes_energy_units_by_station_types"]["aggregated"].get("p_rasp", {}),

        # По типам станций и топливу
        "energy_units_by_station_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_units_by_station_type_with_fuel"]["aggregated"].get("p_ust", {}),
        "energy_units_by_station_types_with_fuel_yearly_p_ogr": data["aggregate_changes_energy_units_by_station_type_with_fuel"]["aggregated"].get("p_ogr", {}),
        "energy_units_by_station_types_with_fuel_yearly_p_rasp": data["aggregate_changes_energy_units_by_station_type_with_fuel"]["aggregated"].get("p_rasp", {}),

        # По типам ТЭС
        "energy_units_by_tes_types_yearly_p_ust": data["aggregate_changes_energy_units_by_tes_types"]["aggregated"].get("p_ust", {}),
        "energy_units_by_tes_types_yearly_p_ogr": data["aggregate_changes_energy_units_by_tes_types"]["aggregated"].get("p_ogr", {}),
        "energy_units_by_tes_types_yearly_p_rasp": data["aggregate_changes_energy_units_by_tes_types"]["aggregated"].get("p_rasp", {}),

        # По типам ТЭС и топливу
        "energy_units_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_units_by_tes_types_with_fuel"]["aggregated"].get("p_ust", {}),
        "energy_units_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_changes_energy_units_by_tes_types_with_fuel"]["aggregated"].get("p_ogr", {}),
        "energy_units_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_changes_energy_units_by_tes_types_with_fuel"]["aggregated"].get("p_rasp", {}),

        # По типам машин ТЭС
        "energy_units_by_tes_machine_types_yearly_p_ust": data["aggregate_changes_energy_units_by_tes_machine_types"]["aggregated"].get("p_ust", {}),
        "energy_units_by_tes_machine_types_yearly_p_ogr": data["aggregate_changes_energy_units_by_tes_machine_types"]["aggregated"].get("p_ogr", {}),
        "energy_units_by_tes_machine_types_yearly_p_rasp": data["aggregate_changes_energy_units_by_tes_machine_types"]["aggregated"].get("p_rasp", {}),

        # По типам машин ТЭС и топливу
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_changes_energy_units_by_tes_machine_types_with_fuel"]["aggregated"].get("p_ust", {}),
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_ogr": data["aggregate_changes_energy_units_by_tes_machine_types_with_fuel"]["aggregated"].get("p_ogr", {}),
        "energy_units_by_tes_machine_types_with_fuel_yearly_p_rasp": data["aggregate_changes_energy_units_by_tes_machine_types_with_fuel"]["aggregated"].get("p_rasp", {}),
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

    # Для кейса "ТИТЭС + Норильск в названии РЭС": нужны итоги по мероприятиям на уровне РЭС
    # (структура как у субъектов: res_id -> event -> year -> value).
    res_by_station_with_events = (
        data.get("aggregate_changes_regional_energy_systems_by_station_types_with_events", {})
        .get("aggregated", {})
        .get("p_ust", {})
    ) or {}

    from collections import defaultdict
    from decimal import Decimal
    res_events = defaultdict(lambda: defaultdict(lambda: defaultdict(Decimal)))
    for res_id, st_map in (res_by_station_with_events or {}).items():
        for _st_id, ev_map in (st_map or {}).items():
            for ev_code, year_map in (ev_map or {}).items():
                for year, val in (year_map or {}).items():
                    if val is None:
                        continue
                    res_events[res_id][ev_code][year] += val or Decimal(0)

    return {
        # Основная агрегация
        "regional_energy_systems_yearly_p_ust": data["aggregate_changes_by_regional_energy_systems"]["aggregated"]["p_ust"],

        # По типам станций
        "regional_energy_systems_by_station_types_yearly_p_ust": data["aggregate_changes_regional_energy_systems_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций с мероприятиями
        "regional_energy_systems_by_station_types_with_events_yearly_p_ust": data.get("aggregate_changes_regional_energy_systems_by_station_types_with_events", {}).get("aggregated", {}).get("p_ust", {}),
        # Итоги по мероприятиям на уровне РЭС (используется для "ТИТЭС + Норильск" как "субъект")
        "regional_energy_systems_events_yearly_p_ust": res_events,

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
        # Основная агрегация (по событиям)
        "union_energy_systems_yearly_p_ust": data["aggregate_changes_by_union_energy_systems"]["aggregated"]["p_ust"],

        # По типам станций (теперь структура {ues_id: {station_type_id: {event_type: {year: value}}}})
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
        # Основная агрегация (по событиям)
        "energy_system_types_yearly_p_ust": data["aggregate_changes_by_energy_system_types"]["aggregated"]["p_ust"],

        # По типам станций (теперь структура {es_type_id: {station_type_id: {event_type: {year: value}}}})
        "energy_system_types_by_station_types_yearly_p_ust": data["aggregate_changes_energy_system_types_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций с мероприятиями
        "energy_system_types_by_station_types_with_events_yearly_p_ust": data.get("aggregate_changes_energy_system_types_by_station_types_with_events", {}).get("aggregated", {}).get("p_ust", {}),

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
        # Основная агрегация (по событиям)
        "total_energy_system_types_yearly_p_ust": data["aggregate_changes_by_total_energy_system_types"]["aggregated"]["p_ust"],

        # По типам станций (теперь структура {station_type_id: {event_type: {year: value}}})
        "total_energy_system_types_by_station_types_yearly_p_ust": data["aggregate_changes_total_energy_system_types_by_station_types"]["aggregated"]["p_ust"],

        # По типам станций с мероприятиями
        "total_energy_system_types_by_station_types_with_events_yearly_p_ust": data.get("aggregate_changes_total_energy_system_types_by_station_types_with_events", {}).get("aggregated", {}).get("p_ust", {}),

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


def build_synchronous_area_aggregates(data):
    """
    Итоги по синхронным зонам для station_changes.

    Считаем через уже готовые агрегаты по субъектам РФ:
      regional_districts_yearly_p_ust: {rd_id: {event_type: {year: value}}}
    и маппинг rd_id -> sa_id (RegionalDistrict.id_synchronous_area).
    """
    from collections import defaultdict
    from decimal import Decimal

    rd_event_map = (
        data.get("aggregate_changes_by_regional_districts", {})
        .get("aggregated", {})
        .get("p_ust", {})
    ) or {}
    rd_by_station_map = (
        data.get("aggregate_changes_regional_districts_by_station_types", {})
        .get("aggregated", {})
        .get("p_ust", {})
    ) or {}
    rd_to_sa = data.get("rd_to_synchronous_area_id", {}) or {}

    sa_event_map = defaultdict(lambda: defaultdict(dict))  # sa_id -> event -> year -> val
    sa_by_station_map = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))  # sa_id -> st_id -> event -> year -> val

    def _to_decimal(v):
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except Exception:
            return None

    for rd_id, events in rd_event_map.items():
        try:
            _rd_id = int(rd_id)
        except Exception:
            continue
        sa_id = rd_to_sa.get(_rd_id, 0) or 0

        for ev_code, years_map in (events or {}).items():
            if not years_map:
                continue
            dest_years = sa_event_map[sa_id].setdefault(ev_code, {})
            for y, v in (years_map or {}).items():
                dv = _to_decimal(v)
                if dv is None:
                    continue
                prev = _to_decimal(dest_years.get(y))
                dest_years[y] = (prev or Decimal("0")) + dv

    # Агрегация по типам станций (sa_id -> station_type_id -> event_type -> year -> sum)
    for rd_id, station_types in rd_by_station_map.items():
        try:
            _rd_id = int(rd_id)
        except Exception:
            continue
        sa_id = rd_to_sa.get(_rd_id, 0) or 0

        for st_id, events in (station_types or {}).items():
            try:
                _st_id = int(st_id)
            except Exception:
                continue
            for ev_code, years_map in (events or {}).items():
                if not years_map:
                    continue
                dest_years = sa_by_station_map[sa_id][_st_id].setdefault(ev_code, {})
                for y, v in (years_map or {}).items():
                    dv = _to_decimal(v)
                    if dv is None:
                        continue
                    prev = _to_decimal(dest_years.get(y))
                    dest_years[y] = (prev or Decimal("0")) + dv

    return {
        "synchronous_areas_yearly_p_ust": sa_event_map,
        "synchronous_areas_by_station_types_yearly_p_ust": sa_by_station_map,
    }


def build_energy_zone_aggregates(data):
    """
    Итоги по энергозонам для ветки ТИТЭС на station_changes.
    Считаем через агрегаты по субъектам РФ и маппинг rd_id -> energy_zone_id.
    """
    from collections import defaultdict
    from decimal import Decimal

    rd_event_map = (
        data.get("aggregate_changes_by_regional_districts", {})
        .get("aggregated", {})
        .get("p_ust", {})
    ) or {}
    rd_by_station_map = (
        data.get("aggregate_changes_regional_districts_by_station_types", {})
        .get("aggregated", {})
        .get("p_ust", {})
    ) or {}
    rd_to_ez = data.get("rd_to_energy_zone_id", {}) or {}

    ez_event_map = defaultdict(lambda: defaultdict(dict))  # ez_id -> event -> year -> val
    ez_by_station_map = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))  # ez_id -> st_id -> event -> year -> val

    def _to_decimal(v):
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        try:
            return Decimal(str(v))
        except Exception:
            return None

    for rd_id, events in rd_event_map.items():
        try:
            _rd_id = int(rd_id)
        except Exception:
            continue
        ez_id = rd_to_ez.get(_rd_id, 0) or 0
        for ev_code, years_map in (events or {}).items():
            if not years_map:
                continue
            dest_years = ez_event_map[ez_id].setdefault(ev_code, {})
            for y, v in (years_map or {}).items():
                dv = _to_decimal(v)
                if dv is None:
                    continue
                prev = _to_decimal(dest_years.get(y))
                dest_years[y] = (prev or Decimal("0")) + dv

    for rd_id, station_types in rd_by_station_map.items():
        try:
            _rd_id = int(rd_id)
        except Exception:
            continue
        ez_id = rd_to_ez.get(_rd_id, 0) or 0
        for st_id, events in (station_types or {}).items():
            try:
                _st_id = int(st_id)
            except Exception:
                continue
            for ev_code, years_map in (events or {}).items():
                if not years_map:
                    continue
                dest_years = ez_by_station_map[ez_id][_st_id].setdefault(ev_code, {})
                for y, v in (years_map or {}).items():
                    dv = _to_decimal(v)
                    if dv is None:
                        continue
                    prev = _to_decimal(dest_years.get(y))
                    dest_years[y] = (prev or Decimal("0")) + dv

    return {
        "energy_zones_yearly_p_ust": ez_event_map,
        "energy_zones_by_station_types_yearly_p_ust": ez_by_station_map,
    }


def compute_energy_zone_rowspans(
    context: dict,
    event_types: list[tuple[str, str]],
) -> dict[int, int]:
    """
    Возвращает {energy_zone_id: rowspan} для блока энергозоны.
    Считаем строки "Всего" по мероприятиям + строки по типам станций.
    """
    ez_event_map = context.get("energy_zones_yearly_p_ust", {}) or {}
    ez_by_station_map = context.get("energy_zones_by_station_types_yearly_p_ust", {}) or {}
    station_type_list = context.get("station_type_list", {}) or {}
    event_codes = [code for code, _ in event_types]

    result: dict[int, int] = {}
    ez_ids = set(ez_event_map.keys()) | set(ez_by_station_map.keys())
    for ez_id in ez_ids:
        rows = 0
        events = ez_event_map.get(ez_id, {}) or {}
        for code in event_codes:
            if (events or {}).get(code):
                rows += 1

        st_map = ez_by_station_map.get(ez_id, {}) or {}
        for code in event_codes:
            for st_id in station_type_list.keys():
                if st_id == 0:
                    continue
                yearly = (st_map.get(st_id, {}) or {}).get(code)
                if yearly:
                    rows += 1

        if rows > 0:
            result[int(ez_id)] = rows
    return result


def compute_synchronous_area_rowspans(
    context: dict,
    event_types: list[tuple[str, str]],
) -> dict[int, int]:
    """
    Возвращает {sa_id: rowspan} для блока синхронной зоны.
    В station_changes сейчас показываем только строки "Всего" по событиям.
    """
    sa_event_map = context.get("synchronous_areas_yearly_p_ust", {}) or {}
    sa_by_station_map = context.get("synchronous_areas_by_station_types_yearly_p_ust", {}) or {}
    station_type_list = context.get("station_type_list", {}) or {}
    event_codes = [code for code, _ in event_types]

    result: dict[int, int] = {}
    sa_ids = set(sa_event_map.keys()) | set(sa_by_station_map.keys())
    for sa_id in sa_ids:
        rows = 0
        events = sa_event_map.get(sa_id, {}) or {}
        for code in event_codes:
            if (events or {}).get(code):
                rows += 1

        # Подстроки по типам станций для каждого мероприятия
        st_map = sa_by_station_map.get(sa_id, {}) or {}
        for code in event_codes:
            for st_id in station_type_list.keys():
                if st_id == 0:
                    continue
                yearly = (st_map.get(st_id, {}) or {}).get(code)
                if yearly:
                    rows += 1

        if rows > 0:
            result[int(sa_id)] = rows
    return result


def compute_regional_energy_system_event_rowspans(
    context: dict,
    event_types: list[tuple[str, str]],
) -> dict[int, int]:
    """
    Rowspan для "итога по РЭС как по субъекту" (res_id -> rowspan),
    считаем строки "Всего" по мероприятиям + строки по типам станций.
    """
    res_event_map = context.get("regional_energy_systems_events_yearly_p_ust", {}) or {}
    res_by_station_with_events = context.get("regional_energy_systems_by_station_types_with_events_yearly_p_ust", {}) or {}
    station_type_list = context.get("station_type_list", {}) or {}
    event_codes = [code for code, _ in event_types]

    res_ids = set(res_event_map.keys()) | set(res_by_station_with_events.keys())
    result: dict[int, int] = {}

    for res_id in res_ids:
        rows = 0
        evs = res_event_map.get(res_id, {}) or {}
        for code in event_codes:
            if evs.get(code):
                rows += 1

        st_map = res_by_station_with_events.get(res_id, {}) or {}
        for code in event_codes:
            for st_id in station_type_list.keys():
                if st_id == 0:
                    continue
                yearly = (st_map.get(st_id, {}) or {}).get(code)
                if yearly:
                    rows += 1

        if rows > 0:
            result[int(res_id)] = rows

    return result


def compute_energy_unit_event_rowspans(
    context: dict,
    event_types: list[tuple[str, str]],
) -> dict[int, int]:
    """
    Rowspan для "итога по энергоузлу как по субъекту" (eu_id -> rowspan),
    строки "Всего" по мероприятиям + строки по типам станций.
    """
    eu_event_map = context.get("energy_units_events_yearly_p_ust", {}) or {}
    eu_by_station_with_events = context.get("energy_units_by_station_types_with_events_yearly_p_ust", {}) or {}
    station_type_list = context.get("station_type_list", {}) or {}
    event_codes = [code for code, _ in event_types]

    eu_ids = set(eu_event_map.keys()) | set(eu_by_station_with_events.keys())
    result: dict[int, int] = {}

    for eu_id in eu_ids:
        rows = 0
        evs = eu_event_map.get(eu_id, {}) or {}
        for code in event_codes:
            if evs.get(code):
                rows += 1

        st_map = eu_by_station_with_events.get(eu_id, {}) or {}
        for code in event_codes:
            for st_id in station_type_list.keys():
                if st_id == 0:
                    continue
                yearly = (st_map.get(st_id, {}) or {}).get(code)
                if yearly:
                    rows += 1

        if rows > 0:
            result[int(eu_id)] = rows

    return result


def compute_regional_district_rowspans(
    data,
    station_type_list: dict,
    event_types: list[tuple[str, str]],
) -> dict[int, int]:
    """Возвращает {rd_id: rowspan} для блока субъекта РФ.

    Считаем количество реально отображаемых строк:
      - по каждому событию, если есть агрегаты для субъекта
      - по каждому событию и типу станции, если есть агрегаты
    """
    rd_event_map = data.get("aggregate_changes_by_regional_districts", {}).get("aggregated", {}).get("p_ust", {})
    rd_by_station_map = data.get("aggregate_changes_regional_districts_by_station_types", {}).get("aggregated", {}).get("p_ust", {})

    # Собираем множество всех rd_id, присутствующих в агрегатах
    rd_ids = set(rd_event_map.keys()) | set(rd_by_station_map.keys())

    result: dict[int, int] = {}
    event_codes = [code for code, _ in event_types]

    for rd_id in rd_ids:
        rows = 0

        # Строки "Всего" по событиям
        rd_events = rd_event_map.get(rd_id, {})
        for code in event_codes:
            if rd_events.get(code):
                rows += 1

        # Строки по типам станций, по событиям
        rd_stations = rd_by_station_map.get(rd_id, {})
        for code in event_codes:
            for st_id in station_type_list.keys():
                if st_id == 0:
                    continue
                event_years_map = rd_stations.get(st_id, {}).get(code)
                if event_years_map:
                    rows += 1

        result[rd_id] = max(rows, 1)

    return result


def compute_union_energy_system_rowspans(
    data,
    station_type_list: dict,
    event_types: list[tuple[str, str]],
) -> dict[int, int]:
    """Возвращает {ues_id: rowspan} для блока объединённой энергосистемы.

    Считаем количество реально отображаемых строк:
      - по каждому событию, если есть агрегаты для ОЭС
      - по каждому событию и типу станции, если есть агрегаты
    """
    ues_event_map = data.get("aggregate_changes_by_union_energy_systems", {}).get("aggregated", {}).get("p_ust", {})
    ues_by_station_map = data.get("aggregate_changes_union_energy_systems_by_station_types", {}).get("aggregated", {}).get("p_ust", {})

    # Собираем множество всех ues_id, присутствующих в агрегатах
    ues_ids = set(ues_event_map.keys()) | set(ues_by_station_map.keys())

    result: dict[int, int] = {}
    event_codes = [code for code, _ in event_types]

    for ues_id in ues_ids:
        rows = 0

        # Строки "Всего" по событиям
        ues_events = ues_event_map.get(ues_id, {})
        for code in event_codes:
            if ues_events.get(code):
                rows += 1

        # Строки по типам станций, по событиям
        ues_stations = ues_by_station_map.get(ues_id, {})
        for code in event_codes:
            for st_id in station_type_list.keys():
                if st_id == 0:
                    continue
                event_years_map = ues_stations.get(st_id, {}).get(code)
                if event_years_map:
                    rows += 1

        result[ues_id] = max(rows, 1)

    return result


def compute_energy_system_type_rowspans(
    data,
    station_type_list: dict,
    event_types: list[tuple[str, str]],
) -> dict[int, int]:
    """Возвращает {es_type_id: rowspan} для блока типа энергосистемы.

    Считаем количество реально отображаемых строк:
      - по каждому событию, если есть агрегаты для типа энергосистемы
      - по каждому событию и типу станции, если есть агрегаты
    """
    es_type_event_map = data.get("aggregate_changes_by_energy_system_types", {}).get("aggregated", {}).get("p_ust", {})
    es_type_by_station_map = data.get("aggregate_changes_energy_system_types_by_station_types", {}).get("aggregated", {}).get("p_ust", {})

    # Собираем множество всех es_type_id, присутствующих в агрегатах
    es_type_ids = set(es_type_event_map.keys()) | set(es_type_by_station_map.keys())

    result: dict[int, int] = {}
    event_codes = [code for code, _ in event_types]

    for es_type_id in es_type_ids:
        rows = 0

        # Строки "Всего" по событиям
        es_type_events = es_type_event_map.get(es_type_id, {})
        for code in event_codes:
            if es_type_events.get(code):
                rows += 1

        # Строки по типам станций, по событиям
        es_type_stations = es_type_by_station_map.get(es_type_id, {})
        for code in event_codes:
            for st_id in station_type_list.keys():
                if st_id == 0:
                    continue
                event_years_map = es_type_stations.get(st_id, {}).get(code)
                if event_years_map:
                    rows += 1

        result[es_type_id] = max(rows, 1)

    return result


def compute_total_energy_system_type_rowspans(
    data,
    station_type_list: dict,
    event_types: list[tuple[str, str]],
) -> int:
    """Возвращает rowspan для блока России в целом.

    Считаем количество реально отображаемых строк:
      - по каждому событию, если есть агрегаты для России
      - по каждому событию и типу станции, если есть агрегаты
    """
    total_event_map = data.get("aggregate_changes_by_total_energy_system_types", {}).get("aggregated", {}).get("p_ust", {})
    total_by_station_map = data.get("aggregate_changes_total_energy_system_types_by_station_types", {}).get("aggregated", {}).get("p_ust", {})

    rows = 0
    event_codes = [code for code, _ in event_types]

    # Строки "Всего" по событиям
    for code in event_codes:
        if total_event_map.get(code):
            rows += 1

    # Строки по типам станций, по событиям
    for code in event_codes:
        for st_id in station_type_list.keys():
            if st_id == 0:
                continue
            event_years_map = total_by_station_map.get(st_id, {}).get(code)
            if event_years_map:
                rows += 1

    return max(rows, 1)
