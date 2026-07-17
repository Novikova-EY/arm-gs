"""Сервисный модуль: Список электростанций."""

import logging

from app.extensions import db

logger = logging.getLogger(__name__)
from app.logs.services.logging_service import log_to_db
from sqlalchemy.exc import IntegrityError
from config import (
    SCHEMA_ENERGY_BALANCE,
    SCHEMA_GENERATION,
    STATION_UNIQUE_EXCLUDED_DISTRICT_IDS,
    STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS,
)
from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload, joinedload
from decimal import Decimal
from collections import defaultdict
import psycopg2.errors

# Функции для работы с версионированием БД
from app.common.services.database_version_filter import (
    filter_by_db_version,
    set_db_version_on_create,
    get_current_db_version_id
)

# Модели
from app.generation.models.station.station_model import Station
from flask_login import current_user
from app.generation.models.station.station_constants import (
    STATION_SIGN_ESPP,
    STATION_SIGN_UNSPECIFIED,
)
from app.generation.models.station.station_power_model import StationPower

from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.station.station_power_model import StationPower
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.generation.models.machine.machine_name_model import MachineName
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
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
# Сервисы
from app.common.services.database_version_services import (
    get_current_version,
    get_current_version_year_range_from_name,
)
from app.common.services.get_services.years.years_get_services import (
    get_current_year,
    get_filter_end_year,
    get_filter_start_year,
    get_year_feature_dict,
    get_year_list_full,
)
from app.common.services.get_services.fuels.fuel_type_get_services import (
    get_fuel_type_list_full,
)
from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
    get_energy_system_type_list_full,
    get_energy_system_type_map,
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
from app.generation.services.station_services.station_access_services import (
    DECENTRALIZED_ZONE_SYNTHETIC_RES_ID,
    DECENTRALIZED_ZONE_SYNTHETIC_UES_ID,
    get_decentralized_zone_energy_system_type_id,
    get_decentralized_zone_res_ids,
    get_station_list_group_info,
    is_decentralized_zone_station,
)


def _normalize_stations_grouped_for_template(grouped) -> dict:
    """defaultdict → обычный dict, чтобы Jinja надёжно читала вложенные ключи (в т.ч. -1)."""
    if not grouped:
        return {}

    def _convert(value):
        if isinstance(value, defaultdict):
            return {key: _convert(nested) for key, nested in value.items()}
        if isinstance(value, list):
            return value
        return value

    return _convert(grouped)


def _enrich_rd_to_fd_mapping_from_stations(mapping, stations) -> dict:
    """Дополняет rd→fd из станций страницы (страховка для ДЭЗ при устаревшем кэше)."""
    enriched = dict(mapping or {})
    for station in stations or []:
        rd_id = getattr(station, "id_regional_district", None)
        if rd_id is None:
            continue
        if enriched.get(rd_id) is not None:
            continue
        rd = getattr(station, "regional_district", None) or getattr(
            station, "regional_district_obj", None
        )
        fd_id = getattr(rd, "id_federal_district", None) if rd is not None else None
        if fd_id is not None:
            enriched[rd_id] = fd_id
    return enriched


def _lookup_grouped_level(grouped: dict, key):
    """Доступ к уровню иерархии по int/str ключу."""
    if not grouped:
        return None
    if key in grouped:
        return grouped[key]
    str_key = str(key)
    if str_key in grouped:
        return grouped[str_key]
    return None


def _extract_decentralized_zone_rd_groups(stations_grouped, dz_est_id) -> dict:
    """Субъекты РФ → энергоузлы → станции для блока децентрализованной зоны."""
    if dz_est_id is None or not stations_grouped:
        return {}

    est_group = _lookup_grouped_level(stations_grouped, dz_est_id)
    if not est_group:
        return {}

    ues_group = _lookup_grouped_level(est_group, DECENTRALIZED_ZONE_SYNTHETIC_UES_ID)
    if not ues_group:
        return {}

    res_group = _lookup_grouped_level(ues_group, DECENTRALIZED_ZONE_SYNTHETIC_RES_ID)
    return res_group if isinstance(res_group, dict) else {}


def _pagination_station_group_info(station):
    """Словарь групп для пагинации и кэша позиций страницы."""
    gi = get_station_list_group_info(station)
    return {
        "sort_tier": gi["sort_tier"],
        "energy_unit_id": gi["energy_unit_id"],
        "regional_district_id": gi["regional_district_id"],
        "regional_energy_system_id": gi["regional_energy_system_id"],
        "union_energy_system_id": gi["union_energy_system_id"],
        "energy_system_type_id": gi["energy_system_type_id"],
        "is_decentralized_zone": gi["is_decentralized_zone"],
    }


def _station_energy_system_type_sql_filter(energy_system_type_ids):
    """Фильтр типа энергосистемы с отдельной трактовкой «Децентрализованной зоны»."""
    ids = {int(x) for x in (energy_system_type_ids or []) if x is not None}
    if not ids:
        return None

    dz_est_id = get_decentralized_zone_energy_system_type_id()
    regular_ids = set(ids)
    conditions = []

    if dz_est_id is not None and dz_est_id in regular_ids:
        regular_ids.remove(dz_est_id)
        dz_res_ids = list(get_decentralized_zone_res_ids())
        if dz_res_ids:
            conditions.append(Station.id_regional_energy_system.in_(dz_res_ids))

    if regular_ids:
        conditions.append(
            Station.regional_energy_system_obj.has(
                RegionalEnergySystem.union_energy_system.has(
                    UnionEnergySystem.energy_system_type.has(
                        EnergySystemType.id.in_(regular_ids)
                    )
                )
            )
        )

    if not conditions:
        return False
    return or_(*conditions)


def _apply_machine_display_names(machines, year_features=None, use_machine_name_only=False):
    """
    Вычисляет отображаемое название агрегата (Machine.display_name).

    По умолчанию (station_details, station_list, equipment_group, machine_details):
      - базовое имя: MachineName.name за год версии БД, иначе Machine.machine_name;
      - если в плановом периоде есть отличающееся имя, добавляем в скобках: "<текущ.> (<план>)".

    При use_machine_name_only=True: display_name = Machine.machine_name.
    """
    if not machines:
        return

    if use_machine_name_only:
        for m in machines:
            setattr(m, "display_name", (getattr(m, "machine_name", None) or "").strip())
        return

    # Собираем ID агрегатов
    machine_ids = [m.id for m in machines if getattr(m, "id", None)]
    if not machine_ids:
        return

    # ВАЖНО: берем MachineName БЕЗ фильтра по версии БД,
    # ровно как в handle_machine_get (карточка агрегата),
    # чтобы логика формирования названия была идентичной.
    names_query = MachineName.query.filter(MachineName.id_machine.in_(machine_ids))
    names_by_machine = defaultdict(dict)
    for mn in names_query.all():
        if mn.year_number is None or not mn.name:
            continue
        names_by_machine[mn.id_machine][mn.year_number] = mn.name.strip()

    # Признаки годов (план/факт) — как в handle_machine_get
    if year_features is None:
        year_features = get_year_feature_dict()

    # Диапазон лет текущей версии (start = текущий/факт, end = план)
    version_year_start, version_year_end = get_current_version_year_range_from_name()
    # Базовое имя — из года начала диапазона (текущий/факт), иначе из конца
    version_year_for_base = version_year_start if version_year_start is not None else version_year_end

    for m in machines:
        machine_names = names_by_machine.get(getattr(m, "id", None), {})

        # Базовое имя: MachineName за год версии (текущий) или Machine.machine_name
        base_name = None
        if version_year_for_base is not None:
            current_name = machine_names.get(version_year_for_base)
            if current_name:
                base_name = current_name.strip()
        if not base_name and version_year_end is not None:
            current_name = machine_names.get(version_year_end)
            if current_name:
                base_name = current_name.strip()
        if not base_name and getattr(m, "machine_name", None):
            base_name = (m.machine_name or "").strip()

        display_name = base_name

        # Ищем отличающееся имя в плановом периоде (полностью копируем логику handle_machine_get):
        # перебираем ВСЕ годы с признаком "план" и берем первое отличающееся название.
        if base_name and machine_names:
            for y in sorted(machine_names.keys()):
                label = year_features.get(y)
                if not label or "план" not in str(label).strip().lower():
                    continue
                plan_name = machine_names.get(y)
                if not plan_name:
                    continue
                plan_name = plan_name.strip()
                if plan_name and plan_name.lower() != base_name.lower():
                    display_name = f"{base_name} ({plan_name})"
                    break

        # Сохраняем вычисленное имя на объекте агрегата (runtime-атрибут)
        setattr(m, "display_name", display_name)


def _apply_machine_gen_companies_for_version(machines, version_id):
    """
    Подставляет GenCompany в версии станции (по ref_uuid), как при сохранении machine_details.
    id_gen_company в Machine может ссылаться на id справочника другой версии БД.
    """
    if not machines:
        return

    from app.common.services.version_entity_resolve_services import (
        resolve_gen_company_id_for_version,
    )

    resolved_by_machine = {}
    resolved_ids = set()
    for m in machines:
        anchor_id = getattr(m, "id_gen_company", None)
        if not anchor_id:
            continue
        resolved_id = resolve_gen_company_id_for_version(anchor_id, version_id)
        if resolved_id:
            resolved_by_machine[m.id] = resolved_id
            resolved_ids.add(resolved_id)

    if not resolved_ids:
        return

    gen_companies = {
        gc.id: gc
        for gc in GenCompany.query.filter(GenCompany.id.in_(resolved_ids)).all()
    }
    for m in machines:
        resolved_id = resolved_by_machine.get(m.id)
        if resolved_id and resolved_id in gen_companies:
            m.gen_company = gen_companies[resolved_id]


def get_gen_company_choices_for_version(version_id):
    """Список (id, name) генкомпаний для указанной версии БД (для select на station_details)."""
    query = GenCompany.query.order_by((GenCompany.id != 0), GenCompany.name.asc())
    if version_id is None:
        query = query.filter(GenCompany.database_version_id.is_(None))
    else:
        query = query.filter(GenCompany.database_version_id == version_id)
    return [(0, "не указано")] + [(gc.id, gc.name) for gc in query.all()]


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
    quick_fix_seq,
)


def clear_station_aggregation_cache(reason: str | None = None) -> None:
    """Сбрасывает кэш агрегированных сумм после мутаций электростанции/агрегатов."""
    try:
        clear_aggregation_cache()
    except Exception as exc:
        suffix = f" ({reason})" if reason else ""
        print(f"[CACHE] Failed to clear aggregation cache{suffix}: {exc}")


def _build_station_note_search_condition(note_filter_value):
    note_pattern = f"%{note_filter_value}%"
    return or_(
        Station.note.ilike(note_pattern),
        Station.machines.any(Machine.note.ilike(note_pattern)),
        Station.machines.any(
            Machine.pgu_submachines.any(PGUMachine.note.ilike(note_pattern))
        ),
    )


def _station_union_energy_system_sql_filter(union_energy_system_filter):
    """
    ОЭС: как в get_filtered_station_ids — прямая привязка электростанции к РЭС
    и связь через субъект РФ (fallback логики Station.union_energy_system).
    """
    ues_ids = union_energy_system_filter
    if not isinstance(ues_ids, list):
        ues_ids = [ues_ids]
    return or_(
        Station.regional_energy_system_obj.has(
            RegionalEnergySystem.id_union_energy_system.in_(ues_ids)
        ),
        Station.regional_district.has(
            RegionalDistrict.regional_energy_systems.any(
                RegionalEnergySystem.id_union_energy_system.in_(ues_ids)
            )
        ),
    )


def get_stations_list(
    page=1,
    per_page=None,
    rounding_digits=None,
    start_year=None,
    end_year=None,
    return_ids_only=False,
    **filters,
):
    # Совместимость параметров: поддерживаем legacy-ключ station_fuel_type_filter
    if not filters.get("fuel_type_filter") and filters.get("station_fuel_type_filter"):
        filters["fuel_type_filter"] = filters.get("station_fuel_type_filter")

    current_year = get_current_year()
    external_code_check = bool(filters.get("external_code_check"))

    if external_code_check:
        station_ids_query = db.session.query(Station.id)
    else:
        # 1. Фильтрация агрегатов
        machine_query = db.session.query(Machine.id, Machine.id_station)
        
        # Фильтрация по версии БД
        machine_query = filter_by_db_version(machine_query, Machine)

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

        # Проверка топлива: показываем "проблемные" агрегаты:
        if filters.get("fuel_check"):
            from sqlalchemy import func
            from app.refdata.models.fuels.fuel_type_model import FuelType
            from app.common.services.database_version_filter import get_current_db_version_id
            from app.common.services.get_services.years.years_get_services import (
                get_filter_start_year,
                get_filter_end_year,
            )

            current_version_id = get_current_db_version_id()
            if current_version_id is not None:
                mf_version_cond = MachineFuel.database_version_id == current_version_id
            else:
                mf_version_cond = MachineFuel.database_version_id.is_(None)

            sy = int(start_year if start_year is not None else get_filter_start_year())
            ey = int(end_year if end_year is not None else get_filter_end_year())

            has_year_fuel = Machine.machine_fuels.any(
                and_(
                    mf_version_cond,
                    MachineFuel.year_number >= sy,
                    MachineFuel.year_number <= ey,
                    MachineFuel.fuel.has(
                        Fuel.fuel_type.has(func.lower(FuelType.name) != "не указано")
                    ),
                )
            )

            fuel_so_missing = or_(
                Machine.fuel_so.is_(None),
                func.trim(Machine.fuel_so) == "",
                func.lower(func.trim(Machine.fuel_so)) == "не указано",
            )

            has_match_with_year_fuel = Machine.machine_fuels.any(
                and_(
                    mf_version_cond,
                    MachineFuel.year_number >= sy,
                    MachineFuel.year_number <= ey,
                    MachineFuel.fuel.has(
                        Fuel.fuel_type.has(
                            and_(
                                func.lower(FuelType.name) != "не указано",
                                func.strpos(
                                    func.lower(func.coalesce(Machine.fuel_so, "")),
                                    func.lower(FuelType.name),
                                ) > 0,
                            )
                        )
                    ),
                )
            )

            machine_query = machine_query.filter(
                and_(
                    has_year_fuel,
                    or_(fuel_so_missing, ~has_match_with_year_fuel),
                )
            )

        from app.generation.services.station_services.filters_services import (
            build_date_commission_filter,
            build_date_exploitation_filter,
            build_date_decompressing_filter,
            build_date_modernization_filter,
            build_date_modernization_no_power_filter,
            build_relabing_outcome_filter,
            build_machine_note_search_condition,
        )
        for build_fn in (
            build_date_commission_filter,
            build_date_exploitation_filter,
            build_date_decompressing_filter,
            build_date_modernization_filter,
            build_date_modernization_no_power_filter,
            build_relabing_outcome_filter,
        ):
            cond = build_fn(Machine, filters)
            if cond is not None:
                machine_query = machine_query.filter(cond)

        if filters.get("machines_without_equipment_group"):
            machine_query = machine_query.filter(Machine.id_equipment_group.is_(None))

        note_machine_cond = build_machine_note_search_condition(
            Machine, PGUMachine, filters.get("note_filter")
        )
        if note_machine_cond is not None:
            machine_query = machine_query.filter(note_machine_cond)

        machine_subquery = machine_query.subquery()
        station_ids_query = db.session.query(machine_subquery.c.id_station).distinct()
        station_ids_query = station_ids_query.join(Station, Station.id == machine_subquery.c.id_station)
        station_ids_query = filter_by_db_version(station_ids_query, Station)

    # 3. Фильтры по электростанции

    if filters.get("station_type_filter"):
        # Тип электростанции хранится в Station.id_station_type
        station_ids_query = station_ids_query.filter(
            Station.id_station_type.in_(filters["station_type_filter"])
        )

    from app.generation.services.station_services.filters_services import apply_station_sign_sql_filter
    station_ids_query = apply_station_sign_sql_filter(station_ids_query, filters)

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

    if filters.get("note_filter"):
        station_ids_query = station_ids_query.filter(
            _build_station_note_search_condition(filters["note_filter"])
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
            Station.id_regional_energy_system.in_(filters["regional_energy_system_filter"])
        )

    if filters.get("union_energy_system_filter"):
        station_ids_query = station_ids_query.filter(
            _station_union_energy_system_sql_filter(
                filters["union_energy_system_filter"]
            )
        )

    if filters.get("energy_system_type_filter"):
        condition = _station_energy_system_type_sql_filter(filters["energy_system_type_filter"])
        station_ids_query = station_ids_query.filter(condition)

    # 4. Подсчет и пагинация (сортировка не нужна, т.к. будет в Python)
    if external_code_check:
        from app.generation.services.station_services.external_code_check_services import (
            dedupe_station_ids_from_rows,
        )
        from app.common.services.database_version_filter import get_current_db_version_id

        station_rows = station_ids_query.with_entities(
            Station.id,
            Station.external_code,
            Station.database_version_id,
            Station.id_regional_district,
            Station.id_regional_energy_system,
        ).all()
        station_ids_in_rows = list({row[0] for row in station_rows})
        machine_counts = {}
        if station_ids_in_rows:
            from sqlalchemy import func

            machine_counts = dict(
                db.session.query(Machine.id_station, func.count(Machine.id))
                .filter(Machine.id_station.in_(station_ids_in_rows))
                .group_by(Machine.id_station)
                .all()
            )
        all_station_ids = dedupe_station_ids_from_rows(
            station_rows,
            get_current_db_version_id(),
            machine_counts=machine_counts,
        )
        raw_station_ids = all_station_ids
    else:
        raw_station_ids = [row[0] for row in station_ids_query.all()]

    # 4a. При наличии фильтров по датам — добавляем электростанции, где PGUMachine совпадает по датам
    date_filters_present = any([
        filters.get("date_commission_filter"),
        filters.get("date_exploitation_filter"),
        filters.get("date_decompressing_expected_filter"),
        filters.get("date_modernization_expected_filter"),
        filters.get("date_modernization_no_power_expected_filter"),
    ])
    if date_filters_present and not external_code_check:
        from app.generation.services.station_services.filters_services import (
            build_date_filters_for_pgu,
        )
        # Строим запрос: Station.id где PGUMachine совпадает по датам
        pgu_station_query = (
            db.session.query(Station.id)
            .join(Machine, Machine.id_station == Station.id)
            .join(PGUMachine, PGUMachine.id_parent_machine == Machine.id)
        )
        pgu_station_query = filter_by_db_version(pgu_station_query, PGUMachine)
        pgu_station_query = filter_by_db_version(pgu_station_query, Station)
        for cond in build_date_filters_for_pgu(PGUMachine, filters):
            pgu_station_query = pgu_station_query.filter(cond)
        # Для фильтра "агрегаты без группы" — только PGUMachine, у которых родительская Machine без id_equipment_group
        if filters.get("machines_without_equipment_group"):
            pgu_station_query = pgu_station_query.filter(Machine.id_equipment_group.is_(None))
        # Применяем те же фильтры по электростанции
        if filters.get("station_type_filter"):
            pgu_station_query = pgu_station_query.filter(
                Station.id_station_type.in_(filters["station_type_filter"])
            )
        pgu_station_query = apply_station_sign_sql_filter(pgu_station_query, filters)
        if filters.get("station_name_filter"):
            pgu_station_query = pgu_station_query.filter(
                Station.name.ilike(f"%{filters['station_name_filter']}%")
            )
        if filters.get("gen_company_filter"):
            gen_company_ids = db.session.query(GenCompany.id).filter(
                GenCompany.name.ilike(f"%{filters['gen_company_filter']}%")
            ).all()
            ids = [g[0] for g in gen_company_ids]
            pgu_station_query = pgu_station_query.filter(
                Station.machines.any(Machine.id_gen_company.in_(ids))
            )
        if filters.get("note_filter"):
            pgu_station_query = pgu_station_query.filter(
                _build_station_note_search_condition(filters["note_filter"])
            )
        if filters.get("condition_type_filter"):
            pgu_station_query = pgu_station_query.filter(
                Station.machines.any(Machine.id_condition_type == filters["condition_type_filter"])
            )
        if filters.get("regional_district_filter"):
            pgu_station_query = pgu_station_query.filter(
                Station.id_regional_district.in_(filters["regional_district_filter"])
            )
        if filters.get("federal_district_filter"):
            pgu_station_query = pgu_station_query.filter(
                Station.regional_district.has(
                    RegionalDistrict.federal_district.has(
                        FederalDistrict.id.in_(filters["federal_district_filter"])
                    )
                )
            )
        if filters.get("regional_energy_system_filter"):
            pgu_station_query = pgu_station_query.filter(
                Station.id_regional_energy_system.in_(filters["regional_energy_system_filter"])
            )
        if filters.get("union_energy_system_filter"):
            pgu_station_query = pgu_station_query.filter(
                _station_union_energy_system_sql_filter(
                    filters["union_energy_system_filter"]
                )
            )
        if filters.get("energy_system_type_filter"):
            condition = _station_energy_system_type_sql_filter(filters["energy_system_type_filter"])
            pgu_station_query = pgu_station_query.filter(condition)
        pgu_station_ids = [row[0] for row in pgu_station_query.distinct().all()]
        raw_station_ids = list(set(raw_station_ids) | set(pgu_station_ids))

    # Если ищем по названию электростанции или station.note, добавляем электростанции без агрегатов,
    # но только когда нет машинных фильтров (иначе они не могут быть выполнены).
    machine_filters_present = any(
        [
            filters.get("tes_type_filter"),
            filters.get("tes_machine_type_filter"),
            filters.get("fuel_type_filter"),
            filters.get("fuel_check"),
            filters.get("machines_without_equipment_group"),
            filters.get("date_commission_filter"),
            filters.get("date_exploitation_filter"),
            filters.get("date_decompressing_expected_filter"),
            filters.get("date_modernization_expected_filter"),
            filters.get("date_modernization_no_power_expected_filter"),
            filters.get("relabing_outcome_filter"),
            filters.get("gen_company_filter"),
            filters.get("condition_type_filter"),
        ]
    )
    extra_station_ids = []
    if (
        not external_code_check
        and (filters.get("station_name_filter") or filters.get("note_filter"))
        and not machine_filters_present
    ):
        station_query = filter_by_db_version(Station.query, Station)
        if filters.get("station_name_filter"):
            station_query = station_query.filter(
                Station.name.ilike(f"%{filters['station_name_filter']}%")
            )
        if filters.get("note_filter"):
            station_query = station_query.filter(
                Station.note.ilike(f"%{filters['note_filter']}%")
            )
        if filters.get("station_type_filter"):
            station_query = station_query.filter(
                Station.id_station_type.in_(filters["station_type_filter"])
            )
        station_query = apply_station_sign_sql_filter(station_query, filters)
        if filters.get("regional_district_filter"):
            station_query = station_query.filter(
                Station.id_regional_district.in_(filters["regional_district_filter"])
            )
        if filters.get("federal_district_filter"):
            station_query = station_query.filter(
                Station.regional_district.has(
                    RegionalDistrict.federal_district.has(
                        FederalDistrict.id.in_(filters["federal_district_filter"])
                    )
                )
            )
        if filters.get("regional_energy_system_filter"):
            station_query = station_query.filter(
                Station.id_regional_energy_system.in_(
                    filters["regional_energy_system_filter"]
                )
            )
        if filters.get("union_energy_system_filter"):
            station_query = station_query.filter(
                _station_union_energy_system_sql_filter(
                    filters["union_energy_system_filter"]
                )
            )
        if filters.get("energy_system_type_filter"):
            condition = _station_energy_system_type_sql_filter(filters["energy_system_type_filter"])
            station_query = station_query.filter(condition)
        extra_station_ids = [row[0] for row in station_query.with_entities(Station.id).all()]

    all_station_ids = list(set(raw_station_ids).union(set(extra_station_ids)))

    if filters.get("all_db_versions") and not external_code_check:
        from app.generation.services.station_services.external_code_check_services import (
            dedupe_station_ids_by_external_code,
        )
        from app.common.services.database_version_filter import get_current_db_version_id

        all_station_ids = dedupe_station_ids_by_external_code(
            all_station_ids,
            get_current_db_version_id(),
        )
    
    # Проверка на дубликаты в raw_station_ids (могут появиться из-за JOIN'ов)
    raw_unique = set(raw_station_ids)
    duplicates_count = len(raw_station_ids) - len(raw_unique)
    if duplicates_count > 0:
        logger.debug(
            "[SQL DUPLICATES] Обнаружено %d дубликатов в raw_station_ids (до: %d, после: %d)",
            duplicates_count, len(raw_station_ids), len(raw_unique)
        )
    
    total_count = len(all_station_ids)
    
    if total_count == 0:
        return {"stations": [], "total_count": 0}

    if return_ids_only:
        return {"station_ids": all_station_ids, "total_count": total_count}

    per_page_int = None if isinstance(per_page, str) and per_page.lower() == "all" else int(per_page or 10)
    
    # Пытаемся получить отсортированный список из кэша
    from app.generation.services.station_services.aggregation_cache import (
        get_cached_sorted_stations, cache_sorted_stations,
        get_cached_page_position, cache_page_position
    )
    
    cached_sorted_ids = None if external_code_check else get_cached_sorted_stations(filters)
    sorted_station_ids = None
    effective_total_pages = None
    rd_name_map = None  # Ленивая инициализация справочника субъектов для пагинации
    
    # Получаем кэшированную позицию и информацию о предыдущей странице
    if page > 1 and not external_code_check:
        cached_start_position, prev_page_last_station_info = get_cached_page_position(filters, page)
        print(f"[CACHE CHECK] Page {page}: cached_start_position={cached_start_position}, prev_info={prev_page_last_station_info}")
    else:
        cached_start_position, prev_page_last_station_info = None, None
    
    if cached_sorted_ids is not None:
        sorted_station_ids = cached_sorted_ids
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
                if rd_name_map is None:
                    rd_name_map = _build_rd_name_map(sorted_station_ids)
                offset_in_sorted_list = compute_page_start_index(sorted_station_ids, per_page_int, page, rd_name_map)
            # Берем страницу с запасом для корректировки границ субъектов
            station_ids_for_page = cached_sorted_ids[offset_in_sorted_list:offset_in_sorted_list + per_page_int + 100]
        else:
            offset_in_sorted_list = 0
            station_ids_for_page = cached_sorted_ids
        
        # Загружаем только электростанции для этой страницы
        if external_code_check:
            stations = Station.query.options(
                selectinload(Station.regional_district)
                    .selectinload(RegionalDistrict.regional_energy_systems)
                    .joinedload(RegionalEnergySystem.union_energy_system)
                    .joinedload(UnionEnergySystem.energy_system_type),
                selectinload(Station.regional_district).joinedload(RegionalDistrict.federal_district),
                joinedload(Station.energy_unit),
                joinedload(Station.regional_energy_system_obj)
                    .joinedload(RegionalEnergySystem.union_energy_system)
                    .joinedload(UnionEnergySystem.energy_system_type),
                joinedload(Station.station_type),
            ).filter(Station.id.in_(station_ids_for_page)).all()
        else:
            stations = Station.query.options(
                selectinload(Station.regional_district).selectinload(RegionalDistrict.regional_energy_systems).joinedload(RegionalEnergySystem.union_energy_system).joinedload(UnionEnergySystem.energy_system_type),
                selectinload(Station.regional_district).joinedload(RegionalDistrict.federal_district),
                joinedload(Station.energy_unit),
                selectinload(Station.machines)
                    .selectinload(Machine.machine_powers),
                selectinload(Station.machines)
                    .selectinload(Machine.machine_fuels),
                selectinload(Station.machines)
                    .selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
                selectinload(Station.machines).joinedload(Machine.equipment_group),
            ).filter(Station.id.in_(station_ids_for_page)).all()
        
        # Сортируем этот небольшой набор
        # (порядок в SQL может отличаться от кэшированного)
        def get_sorting_key_from_cache(station):
            # Находим позицию электростанции в кэшированном списке
            try:
                return cached_sorted_ids.index(station.id)
            except ValueError:
                return float('inf')
        
        stations = sorted(stations, key=get_sorting_key_from_cache)
        use_cached_sort = True
    else:
        # Кэша нет - загружаем все электростанции
        station_ids = all_station_ids
        
        if not station_ids:
            return {"stations": [], "total_count": 0}
        
        # ⚡ ОПТИМИЗАЦИЯ: Загружаем только минимум данных для сортировки
        sort_options = [
            selectinload(Station.regional_district)
                .selectinload(RegionalDistrict.regional_energy_systems)
                .joinedload(RegionalEnergySystem.union_energy_system)
                .joinedload(UnionEnergySystem.energy_system_type),
            joinedload(Station.energy_unit),
            joinedload(Station.station_type),
        ]
        if external_code_check:
            sort_options.extend([
                selectinload(Station.regional_district).joinedload(RegionalDistrict.federal_district),
                joinedload(Station.regional_energy_system_obj)
                    .joinedload(RegionalEnergySystem.union_energy_system)
                    .joinedload(UnionEnergySystem.energy_system_type),
            ])
        else:
            sort_options.append(
                selectinload(Station.machines).joinedload(Machine.equipment_group)
            )
        stations = Station.query.options(*sort_options).filter(Station.id.in_(station_ids)).all()
        
        use_cached_sort = False
    
    # Сортировка в Python по полной территориальной иерархии.
    # На самом нижнем уровне: по типам станций (фиксированный порядок) и по названию электростанции.
    def get_sorting_key(station):
        """
        Возвращает кортеж для сортировки по полной территориальной иерархии:
        (energy_system_type_id, union_energy_system_order, regional_energy_system_id,
         regional_district_name, energy_unit_id, station_type_rank, station_name, station_id)
        Это сохраняет текущую территориальную группировку, но меняет порядок на нижнем уровне.
        """
        # Определяем тип электростанции
        station_type_name = ""
        if getattr(station, "station_type", None) is not None and getattr(station.station_type, "name", None):
            station_type_name = station.station_type.name.strip()

        def _station_type_rank(name: str) -> int:
            """
            Фиксированный порядок типов: АЭС, ГЭС, ГАЭС, ТЭС, ВЭС, СЭС.
            Если в справочнике тип называется иначе, пытаемся найти вхождение аббревиатуры.
            """
            s = (name or "").strip().upper()
            # Важно: "ГАЭС" проверяем раньше "ГЭС"
            ordered = ["АЭС", "ГАЭС", "ГЭС", "ТЭС", "ВЭС", "СЭС"]
            direct = {abbr: idx for idx, abbr in enumerate(ordered)}
            if s in direct:
                return direct[s]
            for idx, abbr in enumerate(ordered):
                if abbr in s:
                    return idx
            return 999

        station_type_rank = _station_type_rank(station_type_name)

        gi = get_station_list_group_info(station)
        if gi["is_decentralized_zone"]:
            regional_district_name = (station.regional_district.name or "").lower() if station.regional_district else ""
            station_name = (station.name or "").strip().lower()
            sort_prefix = ()
            if external_code_check:
                has_territory = bool(station.regional_district or station.id_regional_energy_system)
                sort_prefix = ((0 if has_territory else 1),)
            return sort_prefix + (
                1,
                gi["energy_system_type_id"] or 10**9,
                0,
                gi["regional_energy_system_id"] or 0,
                regional_district_name,
                station.id_energy_unit or 0,
                station_type_rank,
                station_name,
                station.id,
            )

        # Получаем иерархию через связи (как было)
        energy_system_type_id = 0
        # Для корректной сортировки по ОЭС используем display_order; None уходит в конец
        union_energy_system_order = float('inf')
        regional_energy_system_id = 0
        regional_district_name = ""
        energy_unit_id = station.id_energy_unit or 0

        # 1) Приоритет: прямая связь электростанции с РЭС (Station.id_regional_energy_system)
        if station.id_regional_energy_system and station.regional_energy_system_obj:
            res = station.regional_energy_system_obj
            regional_energy_system_id = res.id
            if res.union_energy_system:
                # display_order: чем меньше, тем раньше
                union_energy_system_order = (
                    res.union_energy_system.display_order
                    if res.union_energy_system.display_order is not None else float('inf')
                )
                if res.union_energy_system.energy_system_type:
                    energy_system_type_id = res.union_energy_system.energy_system_type.id

        # 2) Fallback: через субъект РФ (старое поведение)
        if regional_energy_system_id == 0 and station.regional_district:
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
        elif station.regional_district:
            regional_district_name = (station.regional_district.name or "").lower()

        # Нижний уровень: по алфавиту названия электростанции
        station_name = (station.name or "").strip().lower()

        sort_prefix = ()
        if external_code_check:
            has_territory = bool(station.regional_district or station.id_regional_energy_system)
            sort_prefix = ((0 if has_territory else 1),)

        return sort_prefix + (
            0,
            energy_system_type_id,
            union_energy_system_order,
            regional_energy_system_id,
            regional_district_name,
            energy_unit_id,
            station_type_rank,
            station_name,
            station.id,
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
                print(f"[WARNING] Дубликат электростанции обнаружен при загрузке: ID={station.id}, name={station.name}")
        
        stations = unique_stations_list
        
        # Сортировка после уникализации
        stations = sorted(stations, key=get_sorting_key)
        
        # Сохраняем отсортированный список ID в кэш
        sorted_station_ids = [s.id for s in stations]
        if not external_code_check:
            cache_sorted_stations(filters, sorted_station_ids)
    else:
        # Кэш уже использован, stations уже отсортированы по кэшированному порядку
        pass

    if per_page_int is not None and sorted_station_ids:
        if external_code_check:
            try:
                effective_total_pages = compute_effective_total_pages(sorted_station_ids, per_page_int)
            except Exception as exc:
                print(f"[PAGINATION] external_code_check effective_total_pages failed: {exc}")
                effective_total_pages = max(1, (len(sorted_station_ids) + per_page_int - 1) // per_page_int)
        else:
            try:
                effective_total_pages = compute_effective_total_pages(sorted_station_ids, per_page_int)
            except Exception as exc:
                print(f"[PAGINATION] Failed to compute effective_total_pages: {exc}")
                effective_total_pages = None
    
    # Сохраняем информацию о следующей электростанции ДО применения пагинации
    next_station_info = None
    prev_page_last_info = None

    # Применяем пагинацию с учетом границ субъектов РФ
    if per_page_int is not None and not use_cached_sort:
        if external_code_check:
            if rd_name_map is None and sorted_station_ids:
                rd_name_map = _build_rd_name_map(sorted_station_ids)
            start_idx = compute_page_start_index(
                sorted_station_ids or [s.id for s in stations],
                per_page_int,
                page,
                rd_name_map,
            )
            end_idx = min(start_idx + per_page_int, len(stations))

            if end_idx < len(stations):
                current_rd_name = (
                    (stations[end_idx - 1].regional_district.name or "").lower()
                    if stations[end_idx - 1].regional_district
                    else ""
                )
                while end_idx < len(stations):
                    next_rd_name = (
                        (stations[end_idx].regional_district.name or "").lower()
                        if stations[end_idx].regional_district
                        else ""
                    )
                    if next_rd_name == current_rd_name:
                        end_idx += 1
                    else:
                        break

            if page > 1 and start_idx > 0:
                from app.generation.services.station_services.external_code_check_services import (
                    station_to_hierarchy_info,
                )
                prev_page_last_info = station_to_hierarchy_info(stations[start_idx - 1])

            stations = stations[start_idx:end_idx]
            print(
                f"[PAGINATION] external_code_check Page {page}: "
                f"range [{start_idx}:{end_idx}], showing {len(stations)} stations"
            )
        else:
            # Для НЕ кэшированного списка (все электростанции загружены)
            # Используем реальную позицию из кэша (если есть) или стандартный offset
            if cached_start_position is not None:
                start_idx = cached_start_position
                print(f"[PAGE POSITION CACHE] Используется закэшированная позиция: {start_idx}")
            else:
                if rd_name_map is None and sorted_station_ids:
                    rd_name_map = _build_rd_name_map(sorted_station_ids)
                start_idx = compute_page_start_index(sorted_station_ids or [s.id for s in stations], per_page_int, page, rd_name_map)
            
            end_idx = min(start_idx + per_page_int, len(stations))
            
            # НЕ корректируем начало! Это создает перекрытия страниц
            # Только корректируем конец: двигаемся вперед до конца субъекта
            if end_idx < len(stations):
                while end_idx < len(stations):
                    prev_tier = get_station_list_group_info(stations[end_idx - 1])["sort_tier"]
                    next_tier = get_station_list_group_info(stations[end_idx])["sort_tier"]
                    if next_tier != prev_tier:
                        break
                    current_rd_name = (stations[end_idx - 1].regional_district.name or "").lower() if stations[end_idx - 1].regional_district else ""
                    next_rd_name = (stations[end_idx].regional_district.name or "").lower() if stations[end_idx].regional_district else ""
                    if next_rd_name == current_rd_name:
                        end_idx += 1
                    else:
                        break
            
            # Получаем информацию о следующей электростанции (если она есть)
            if end_idx < len(stations):
                next_station_info = _pagination_station_group_info(stations[end_idx])
            
            stations = stations[start_idx:end_idx]
            
            # Получаем информацию о последней электростанции страницы для кэша
            if stations:
                last_station_info_for_cache = _pagination_station_group_info(stations[-1])
            else:
                last_station_info_for_cache = None
            
            # Сохраняем реальную конечную позицию этой страницы в кэш
            cache_page_position(filters, page, end_idx, last_station_info_for_cache)
            
            print(f"[PAGINATION] Page {page}: start={start_idx}, per_page={per_page_int}, range [{start_idx}:{end_idx}], showing {len(stations)} stations, next_station: {next_station_info}")
    elif per_page_int is not None and use_cached_sort and not external_code_check:
        # Для кэшированного списка (загружены только электростанции страницы)
        # Берем с начала буфера
        start_idx = 0  
        # Определяем, сколько станций уже было показано (из кэша позиций)
        end_idx = min(per_page_int, len(stations))
        
        # Корректируем конец: двигаемся вперед до конца субъекта (в пределах одного tier)
        if end_idx < len(stations):
            while end_idx < len(stations):
                prev_tier = get_station_list_group_info(stations[end_idx - 1])["sort_tier"]
                next_tier = get_station_list_group_info(stations[end_idx])["sort_tier"]
                if next_tier != prev_tier:
                    break
                current_rd_name = (stations[end_idx - 1].regional_district.name or "").lower() if stations[end_idx - 1].regional_district else ""
                next_rd_name = (stations[end_idx].regional_district.name or "").lower() if stations[end_idx].regional_district else ""
                if next_rd_name == current_rd_name:
                    end_idx += 1
                else:
                    break
        
        # Получаем информацию о следующей электростанции (если она есть)
        if end_idx < len(stations):
            next_station_info = _pagination_station_group_info(stations[end_idx])
        
        stations = stations[start_idx:end_idx]
        
        # Получаем информацию о последней электростанции страницы для кэша
        if stations:
            last_station_info_for_cache = _pagination_station_group_info(stations[-1])
        else:
            last_station_info_for_cache = None
        
        # Сохраняем реальную конечную позицию этой страницы в кэш
        # Это позиция в кэшированном sorted list, откуда начнется следующая страница
        real_end_position = offset_in_sorted_list + end_idx
        cache_page_position(filters, page, real_end_position, last_station_info_for_cache)
        
        print(f"[PAGINATION CACHED] Page {page}: offset_in_sorted_list={offset_in_sorted_list}, per_page={per_page_int}, range [{start_idx}:{end_idx}], showing {len(stations)} stations, next_station: {next_station_info}, real_end_pos: {real_end_position}")

    # 7. Загрузка отфильтрованных агрегатов (только для финального списка станций)
    if not external_code_check:
        final_station_ids = [s.id for s in stations]
        base_filtered_machine_ids = db.session.query(machine_subquery.c.id).filter(
            machine_subquery.c.id_station.in_(final_station_ids)
        )

        filtered_machines_query = Machine.query.options(
            selectinload(Machine.machine_fuels),
            selectinload(Machine.machine_powers),
            selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
            joinedload(Machine.equipment_group),
        ).filter(Machine.id.in_(base_filtered_machine_ids))

        # Если станция попала в выборку только за счет совпадения дочернего PGUMachine по датам,
        # подгружаем и родительскую Machine, чтобы строка ПГУ отрисовалась в station_list.
        if any(
            [
                filters.get("date_commission_filter"),
                filters.get("date_exploitation_filter"),
                filters.get("date_decompressing_expected_filter"),
                filters.get("date_modernization_expected_filter"),
                filters.get("date_modernization_no_power_expected_filter"),
                filters.get("relabing_outcome_filter"),
            ]
        ):
            from app.generation.services.station_services.filters_services import (
                build_date_commission_filter,
                build_date_exploitation_filter,
                build_date_decompressing_filter,
                build_date_modernization_filter,
                build_date_modernization_no_power_filter,
                build_relabing_outcome_filter,
                get_pgu_date_cond_for_filter,
            )

            date_filter_pairs = [
                (build_date_commission_filter, "date_commission_filter"),
                (build_date_exploitation_filter, "date_exploitation_filter"),
                (build_date_decompressing_filter, "date_decompressing_expected_filter"),
                (build_date_modernization_filter, "date_modernization_expected_filter"),
                (build_date_modernization_no_power_filter, "date_modernization_no_power_expected_filter"),
            ]
            date_and_parts = []
            for build_fn, key in date_filter_pairs:
                if not filters.get(key):
                    continue
                machine_cond = build_fn(Machine, filters)
                pgu_cond = get_pgu_date_cond_for_filter(PGUMachine, filters, key)
                if machine_cond is not None and pgu_cond is not None:
                    date_and_parts.append(or_(machine_cond, Machine.pgu_submachines.any(pgu_cond)))
                elif machine_cond is not None:
                    date_and_parts.append(machine_cond)
                elif pgu_cond is not None:
                    date_and_parts.append(Machine.pgu_submachines.any(pgu_cond))

            rel_cond = build_relabing_outcome_filter(Machine, filters)
            if rel_cond is not None:
                date_and_parts.append(rel_cond)

            if date_and_parts:
                extra_pgu_parent_machine_ids = (
                    db.session.query(Machine.id)
                    .filter(Machine.id_station.in_(final_station_ids))
                    .filter(and_(*date_and_parts))
                )
                filtered_machines_query = Machine.query.options(
                    selectinload(Machine.machine_fuels),
                    selectinload(Machine.machine_powers),
                    selectinload(Machine.machine_tes_types).selectinload(MachineTesType.tes_type),
                    joinedload(Machine.equipment_group),
                ).filter(
                    or_(
                        Machine.id.in_(base_filtered_machine_ids),
                        Machine.id.in_(extra_pgu_parent_machine_ids),
                    )
                )

        filtered_machines = filtered_machines_query.all()

        # Применяем логику отображаемого названия агрегата (как в карточке агрегата)
        _apply_machine_display_names(filtered_machines)

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
        "effective_total_pages": effective_total_pages,
        "prev_page_last_info": prev_page_last_info,
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

    from app.generation.services.station_services.filters_services import (
        build_date_commission_filter,
        build_date_exploitation_filter,
        build_date_decompressing_filter,
        build_date_modernization_filter,
        build_date_modernization_no_power_filter,
        build_relabing_outcome_filter,
    )
    for build_fn in (
        build_date_commission_filter,
        build_date_exploitation_filter,
        build_date_decompressing_filter,
        build_date_modernization_filter,
        build_date_modernization_no_power_filter,
        build_relabing_outcome_filter,
    ):
        cond = build_fn(Machine, filters)
        if cond is not None:
            machine_query = machine_query.filter(cond)

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

    print("Все электростанции с ПГУ:", sorted(set(pgu_station_ids)))

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
        condition = _station_energy_system_type_sql_filter(filters["energy_system_type_filter"])
        station_query = station_query.filter(condition)

    # Загружаем электростанции без сортировки (сортировка будет в Python)
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
            print(f"[WARNING] Дубликат электростанции обнаружен при загрузке (with PGU): ID={station.id}, name={station.name}")
    
    stations = unique_stations_list
    
    # Сортировка в Python по полной территориальной иерархии
    def get_sorting_key(station):
        """
        Возвращает кортеж для сортировки по полной территориальной иерархии:
        (energy_system_type_id, union_energy_system_id, regional_energy_system_id, 
         regional_district_id, energy_unit_id, min_station_type_id, station_id)
        Это гарантирует, что все электростанции одного субъекта будут отображаться вместе.
        Использует прямую связь id_regional_energy_system для определения РЭС.
        """
        # Определяем тип электростанции
        min_type = station.id_station_type if station.id_station_type is not None else float('inf')
        
        # Получаем иерархию через связи
        energy_system_type_id = 0
        union_energy_system_id = 0
        regional_energy_system_id = 0
        regional_district_id = station.id_regional_district or 0
        energy_unit_id = station.id_energy_unit or 0
        
        # 1) Приоритет: прямая связь электростанции с РЭС (Station.id_regional_energy_system)
        if station.id_regional_energy_system and station.regional_energy_system_obj:
            res = station.regional_energy_system_obj
            regional_energy_system_id = res.id
            if res.union_energy_system:
                union_energy_system_id = res.union_energy_system.id
                if res.union_energy_system.energy_system_type:
                    energy_system_type_id = res.union_energy_system.energy_system_type.id
        
        # 2) Fallback: через субъект РФ (старое поведение)
        if regional_energy_system_id == 0 and station.regional_district and station.regional_district.regional_energy_systems:
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

    # Применяем логику отображаемого названия агрегата (как в карточке агрегата)
    _apply_machine_display_names(filtered_machines)

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
        stations_on_page: электростанции на текущей странице
        prev_page_last_station_info: информация о последней электростанции предыдущей страницы
    
    Returns:
        dict с информацией о том, какие заголовки показывать
    """
    if not stations_on_page:
        return {}
    
    first_station = stations_on_page[0]
    
    # Определяем, какие группы показать для первой электростанции
    show_headers = {
        'energy_system_types': set(),
        'union_energy_systems': set(),
        'regional_energy_systems': set(),
        'regional_districts': set(),
        'energy_units': set(),
    }
    
    first_gi = get_station_list_group_info(first_station)
    est_id = first_gi.get("energy_system_type_id")
    ues_id = first_gi.get("union_energy_system_id")
    res_id = first_gi.get("regional_energy_system_id")
    rd_id = first_gi.get("regional_district_id")
    eu_id = first_gi.get("energy_unit_id") or 0
    first_is_dz = first_gi.get("is_decentralized_zone")
    
    # Если нет информации о предыдущей странице - показываем все заголовки
    if prev_page_last_station_info is None:
        if est_id is not None:
            show_headers['energy_system_types'].add(est_id)
        if not first_is_dz and ues_id is not None:
            show_headers['union_energy_systems'].add(ues_id)
        if not first_is_dz and res_id is not None:
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
        if not first_is_dz and ues_id != prev_ues and ues_id is not None:
            show_headers['union_energy_systems'].add(ues_id)
        if not first_is_dz and res_id != prev_res and res_id is not None:
            show_headers['regional_energy_systems'].add(res_id)
        if rd_id != prev_rd and rd_id is not None:
            show_headers['regional_districts'].add(rd_id)
        if eu_id != prev_eu and eu_id is not None and eu_id != 0:
            show_headers['energy_units'].add(eu_id)
    
    # Проверяем остальные электростанции на странице - добавляем заголовки при смене группы
    prev_est = est_id
    prev_ues = ues_id
    prev_res = res_id
    prev_rd = rd_id
    prev_eu = eu_id
    
    for station in stations_on_page[1:]:
        gi = get_station_list_group_info(station)
        curr_est_id = gi.get("energy_system_type_id")
        curr_ues_id = gi.get("union_energy_system_id")
        curr_res_id = gi.get("regional_energy_system_id")
        curr_rd_id = gi.get("regional_district_id")
        curr_eu_id = gi.get("energy_unit_id") or 0
        curr_is_dz = gi.get("is_decentralized_zone")

        if curr_est_id != prev_est and curr_est_id is not None:
            show_headers['energy_system_types'].add(curr_est_id)
        if not curr_is_dz and curr_ues_id != prev_ues and curr_ues_id is not None:
            show_headers['union_energy_systems'].add(curr_ues_id)
        if not curr_is_dz and curr_res_id != prev_res and curr_res_id is not None:
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
    РЭС/субъекты — общие справочники, не фильтруются по версии.
    """
    from collections import defaultdict
    res_to_rd_count = defaultdict(int)

    # Запрашиваем все РЭС с их субъектами (справочники общие для версий)
    res_list = db.session.query(RegionalEnergySystem).options(
        joinedload(RegionalEnergySystem.regional_districts)
    ).all()
    
    for res in res_list:
        res_to_rd_count[res.id] = len(res.regional_districts)
    
    return res_to_rd_count


def get_regional_districts_with_stations_per_res(filters=None):
    """
    Возвращает словарь {res_id: количество субъектов РФ с станциями в этой РЭС}.
    Учитывает фильтры - только субъекты, у которых есть электростанции после фильтрации.
    Учитывает текущую версию БД для согласованности со списком станций и агрегацией.
    """
    from collections import defaultdict

    # Получаем электростанции с учетом фильтров и версии БД
    query = db.session.query(
        Station.id_regional_district,
        Station.id_regional_energy_system.label('res_id')
    ).filter(
        Station.id_regional_energy_system.isnot(None)
    )
    query = filter_by_db_version(query, Station)
    query = query.distinct()
    
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
            query = query.filter(Station.id_regional_energy_system.in_(filters["regional_energy_system_filter"]))
        
        if filters.get("union_energy_system_filter"):
            query = query.filter(
                Station.regional_energy_system_obj.has(
                    RegionalEnergySystem.id_union_energy_system.in_(filters["union_energy_system_filter"])
                )
            )
        
        if filters.get("energy_system_type_filter"):
            condition = _station_energy_system_type_sql_filter(filters["energy_system_type_filter"])
            query = query.filter(condition)
    
    rows = query.all()
    
    res_to_rd_count = defaultdict(int)
    for rd_id, res_id in rows:
        if rd_id and res_id:
            res_to_rd_count[res_id] += 1
    
    return dict(res_to_rd_count)


def determine_totals_to_show(stations_on_page, total_count, page, per_page, filters, next_station_info=None, force_full_aggregates=False):
    """
    Определяет, какие агрегированные итоги нужно показать на текущей странице.
    Итог показывается если группа меняется внутри страницы или завершается на этой странице.
    Итоги по субъектам РФ показываются только если в РЭС более одного субъекта.
    
    Args:
        next_station_info: информация о следующей электростанции после текущей страницы (из отсортированного списка)
    """
    # Получаем маппинг: сколько субъектов в каждой РЭС (нужен во всех режимах)
    res_to_rd_count = get_regional_districts_count_per_res()
    # Получаем реальное количество субъектов со станциями в каждой РЭС (с учетом фильтров)
    res_to_rd_with_stations_global = get_regional_districts_with_stations_per_res(filters)
    
    if not stations_on_page or per_page is None:
        """
        Режим per_page='all':
        - Показываем итоги по всем уровням (ОЭС, РЭС, типы энергосистем, энергоузлы, Россия),
          а по субъектам РФ — только если в РЭС >1 субъекта по БД и >1 субъекта имеют электростанции.
        """
        from app.extensions import db  # локальный импорт, чтобы избежать циклических зависимостей
        from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem

        # Создаем маппинг rd_to_res для всех станций (через субъект или прямую РЭС)
        rd_to_res = {}
        all_rd_ids = set()

        # Наборы для всех уровней агрегации
        energy_unit_ids = set()
        regional_energy_system_ids = set()
        union_energy_system_ids = set()
        energy_system_type_ids = set()
        has_decentralized_zone = False
        decentralized_zone_est_id = get_decentralized_zone_energy_system_type_id()

        for station in stations_on_page:
            if is_decentralized_zone_station(station):
                has_decentralized_zone = True
                if station.id_energy_unit:
                    energy_unit_ids.add(station.id_energy_unit)
                if station.id_regional_district:
                    all_rd_ids.add(station.id_regional_district)
                    if decentralized_zone_est_id and station.id_regional_energy_system:
                        rd_to_res[station.id_regional_district] = station.id_regional_energy_system
                continue

            # Энергоузел
            if station.id_energy_unit:
                energy_unit_ids.add(station.id_energy_unit)

            # Субъект РФ
            if station.id_regional_district:
                all_rd_ids.add(station.id_regional_district)

            # Определяем РЭС с приоритетом прямой связи электростанции (id_regional_energy_system),
            # затем — через субъект РФ (как ранее)
            selected_res = None
            if getattr(station, "id_regional_energy_system", None):
                # Пытаемся использовать уже загруженный объект, чтобы не делать лишний запрос
                selected_res = getattr(station, "regional_energy_system_obj", None)
                if selected_res is None:
                    selected_res = db.session.get(RegionalEnergySystem, station.id_regional_energy_system)
            else:
                rd = station.regional_district
                if rd and rd.regional_energy_systems:
                    selected_res = rd.regional_energy_systems[0]
            
            # Для субъектов всегда фиксируем их РЭС (независимо от того, прямая связь или через субъект)
            if selected_res and station.id_regional_district:
                rd_to_res[station.id_regional_district] = selected_res.id

            if selected_res:
                regional_energy_system_ids.add(selected_res.id)

                ues = selected_res.union_energy_system
                if ues:
                    union_energy_system_ids.add(ues.id)
                    if ues.energy_system_type:
                        energy_system_type_ids.add(ues.energy_system_type.id)

        # Определяем, какие regional_districts показывать
        # Показываем только если в РЭС >1 субъекта по БД И >1 субъекта имеют электростанции
        allowed_rd_ids = {}
        for rd_id in all_rd_ids:
            res_id = rd_to_res.get(rd_id)
            if res_id:
                total_rd_in_res = res_to_rd_count.get(res_id, 0)
                rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)

                if total_rd_in_res > 1 and rd_with_stations_count > 1:
                    allowed_rd_ids[rd_id] = True

        return {
            'show_all': True,
            # Энергоузлы: показываем для всех, которые присутствуют в выборке
            'energy_units': {eu_id: True for eu_id in energy_unit_ids},
            # Субъекты РФ с особым правилом по РЭС
            'regional_districts': allowed_rd_ids,
            # Региональные энергосистемы (РЭС) из текущей выборки
            'regional_energy_systems': {res_id: True for res_id in regional_energy_system_ids},
            # Объединенные энергосистемы (ОЭС)
            'union_energy_systems': {ues_id: True for ues_id in union_energy_system_ids},
            # Типы энергосистем (без децентрализованной зоны)
            'energy_system_types': {est_id: True for est_id in energy_system_type_ids},
            # Итог по России (без децентрализованной зоны — см. aggregate_all_at_once)
            'total': True,
            'decentralized_zone': has_decentralized_zone,
            'decentralized_zone_est_id': decentralized_zone_est_id if has_decentralized_zone else None,
        }
    
    # Проверяем, есть ли еще электростанции после текущей страницы
    has_more_stations = bool(next_station_info)
    
    show_totals = {
        'energy_units': {},
        'regional_districts': {},
        'regional_energy_systems': {},
        'union_energy_systems': {},
        'energy_system_types': {},
        'total': False,
        'aggregate_full_dataset': False,
        'decentralized_zone': False,
        'decentralized_zone_est_id': None,
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
        if is_decentralized_zone_station(station):
            if station.id_energy_unit:
                groups_on_page['energy_units'].add(station.id_energy_unit)
            if station.id_regional_district:
                groups_on_page['regional_districts'].add(station.id_regional_district)
                if station.id_regional_energy_system:
                    rd_to_res[station.id_regional_district] = station.id_regional_energy_system
            continue

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
    last_gi = get_station_list_group_info(last_station)
    last_energy_unit_id = last_station.id_energy_unit
    last_regional_district_id = last_station.id_regional_district
    last_regional_energy_system_id = last_gi.get("regional_energy_system_id")
    last_union_energy_system_id = last_gi.get("union_energy_system_id")
    last_energy_system_type_id = last_gi.get("energy_system_type_id")
    
    if not has_more_stations:
        # Последняя страница - показываем итоги для всех групп на странице
        for eu_id in groups_on_page['energy_units']:
            show_totals['energy_units'][eu_id] = True
        for rd_id in groups_on_page['regional_districts']:
            # Показываем итог по субъекту только если:
            # 1. В РЭС более одного субъекта (по БД)
            # 2. И на странице электростанции есть у более чем одного субъекта этой РЭС
            res_id = rd_to_res.get(rd_id)
            if res_id:
                total_rd_in_res = res_to_rd_count.get(res_id, 0)
                rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                
                if total_rd_in_res > 1 and rd_with_stations_count > 1:
                    show_totals['regional_districts'][rd_id] = True
        for res_id in groups_on_page['regional_energy_systems']:
            show_totals['regional_energy_systems'][res_id] = True
        for ues_id in groups_on_page['union_energy_systems']:
            show_totals['union_energy_systems'][ues_id] = True
        for est_id in groups_on_page['energy_system_types']:
            show_totals['energy_system_types'][est_id] = True
        show_totals['total'] = True
        show_totals['aggregate_full_dataset'] = True
    else:
        # Используем переданную информацию о следующей электростанции
        next_station = next_station_info
        
        if next_station:
            # Находим точки смены групп на странице (группы, которые завершились внутри страницы)
            # Для этого проходим по всем станциям и отслеживаем изменения
            
            # Energy Units - находим завершившиеся на странице
            prev_eu = None
            for station in stations_on_page:
                curr_eu = station.id_energy_unit
                if prev_eu is not None and prev_eu != curr_eu and prev_eu in groups_on_page['energy_units']:
                    show_totals['energy_units'][prev_eu] = True
                prev_eu = curr_eu
            # Проверяем последний energy unit - завершается ли на следующей странице?
            if last_energy_unit_id and next_station.get('energy_unit_id') != last_energy_unit_id:
                show_totals['energy_units'][last_energy_unit_id] = True
            
            # Regional Districts - находим завершившиеся на странице
            prev_rd = None
            for station in stations_on_page:
                curr_rd = station.id_regional_district
                if prev_rd is not None and prev_rd != curr_rd and prev_rd in groups_on_page['regional_districts']:
                    # Показываем итог по субъекту только если:
                    # 1. В РЭС более одного субъекта (по БД)
                    # 2. И на странице электростанции есть у более чем одного субъекта этой РЭС
                    res_id = rd_to_res.get(prev_rd)
                    if res_id:
                        total_rd_in_res = res_to_rd_count.get(res_id, 0)
                        rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                        
                        if total_rd_in_res > 1 and rd_with_stations_count > 1:
                            show_totals['regional_districts'][prev_rd] = True
                prev_rd = curr_rd
            # Проверяем последний regional district
            if last_regional_district_id and next_station.get('regional_district_id') != last_regional_district_id:
                # Показываем итог по субъекту только если:
                # 1. В РЭС более одного субъекта (по БД)
                # 2. И на странице электростанции есть у более чем одного субъекта этой РЭС
                res_id = rd_to_res.get(last_regional_district_id)
                if res_id:
                    total_rd_in_res = res_to_rd_count.get(res_id, 0)
                    rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                    if total_rd_in_res > 1 and rd_with_stations_count > 1:
                        show_totals['regional_districts'][last_regional_district_id] = True
            
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
                prev_res = curr_res
            # Проверяем последнюю regional energy system
            if last_regional_energy_system_id and next_station.get('regional_energy_system_id') != last_regional_energy_system_id:
                show_totals['regional_energy_systems'][last_regional_energy_system_id] = True
            
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
                prev_ues = curr_ues
            # Проверяем последнюю union energy system
            if last_union_energy_system_id and next_station.get('union_energy_system_id') != last_union_energy_system_id:
                show_totals['union_energy_systems'][last_union_energy_system_id] = True
            
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
                prev_est = curr_est
            # Проверяем последний energy system type
            if last_energy_system_type_id and next_station.get('energy_system_type_id') != last_energy_system_type_id:
                show_totals['energy_system_types'][last_energy_system_type_id] = True
        else:
            for eu_id in groups_on_page['energy_units']:
                show_totals['energy_units'][eu_id] = True
            for rd_id in groups_on_page['regional_districts']:
                # Показываем итог по субъекту только если:
                # 1. В РЭС более одного субъекта (по БД)
                # 2. И на странице электростанции есть у более чем одного субъекта этой РЭС
                res_id = rd_to_res.get(rd_id)
                if res_id:
                    total_rd_in_res = res_to_rd_count.get(res_id, 0)
                    rd_with_stations_count = res_to_rd_with_stations_global.get(res_id, 0)
                    if total_rd_in_res > 1 and rd_with_stations_count > 1:
                        show_totals['regional_districts'][rd_id] = True
            for res_id in groups_on_page['regional_energy_systems']:
                show_totals['regional_energy_systems'][res_id] = True
            for ues_id in groups_on_page['union_energy_systems']:
                show_totals['union_energy_systems'][ues_id] = True
            for est_id in groups_on_page['energy_system_types']:
                show_totals['energy_system_types'][est_id] = True

    dz_est_id = get_decentralized_zone_energy_system_type_id()
    has_dz_on_page = any(is_decentralized_zone_station(s) for s in stations_on_page)
    has_regular_stations_on_page = any(
        not is_decentralized_zone_station(s) for s in stations_on_page
    )
    next_is_dz = bool(
        next_station_info
        and (
            next_station_info.get('is_decentralized_zone')
            or (
                dz_est_id is not None
                and str(next_station_info.get('energy_system_type_id')) == str(dz_est_id)
            )
        )
    )
    first_station_is_dz = is_decentralized_zone_station(stations_on_page[0])
    prev_station_is_dz = False
    if first_station_is_dz and page > 1:
        try:
            from app.generation.services.station_services.aggregation_cache import get_cached_page_position

            _, prev_page_last_info = get_cached_page_position(filters, page)
            prev_station_is_dz = bool(
                prev_page_last_info
                and (
                    prev_page_last_info.get('is_decentralized_zone')
                    or (
                        dz_est_id is not None
                        and str(prev_page_last_info.get('energy_system_type_id')) == str(dz_est_id)
                    )
                )
            )
        except Exception:
            prev_station_is_dz = False
    show_russia_before_dz = bool(
        has_dz_on_page
        and (
            has_regular_stations_on_page
            or not first_station_is_dz
            or not prev_station_is_dz
        )
    )

    # При явном запросе «Показать суммы по регионам» (show_totals=1)
    # агрегируем полный набор, но строку «Россия, всего» показываем только один раз:
    # перед блоком децентрализованной зоны либо в самом конце, если DZ в выборке нет.
    if force_full_aggregates:
        show_totals['aggregate_full_dataset'] = True
        show_totals['total'] = (
            show_russia_before_dz
            or (not has_more_stations and not has_dz_on_page)
        )

    if has_dz_on_page:
        show_totals['decentralized_zone_est_id'] = dz_est_id
        if not has_more_stations or (last_gi.get('is_decentralized_zone') and not next_is_dz):
            show_totals['decentralized_zone'] = True

    return show_totals


def get_next_station_info(current_page, per_page, filters):
    """Получает информацию о первой электростанции после текущей страницы."""
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
        
        from app.generation.services.station_services.filters_services import (
            build_date_commission_filter,
            build_date_exploitation_filter,
            build_date_decompressing_filter,
            build_date_modernization_filter,
            build_date_modernization_no_power_filter,
            build_relabing_outcome_filter,
            build_machine_note_search_condition,
        )
        for build_fn in (
            build_date_commission_filter,
            build_date_exploitation_filter,
            build_date_decompressing_filter,
            build_date_modernization_filter,
            build_date_modernization_no_power_filter,
            build_relabing_outcome_filter,
        ):
            cond = build_fn(Machine, filters)
            if cond is not None:
                machine_query = machine_query.filter(cond)

        note_machine_cond = build_machine_note_search_condition(
            Machine, PGUMachine, filters.get("note_filter")
        )
        if note_machine_cond is not None:
            machine_query = machine_query.filter(note_machine_cond)
        
        # 2. Subquery с подходящими агрегатами
        machine_subquery = machine_query.subquery()
        station_ids_query = db.session.query(machine_subquery.c.id_station).distinct()
        station_ids_query = station_ids_query.join(Station, Station.id == machine_subquery.c.id_station)
        
        # 3. Применяем фильтры по электростанции (как в get_stations_list)
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

        if filters.get("note_filter"):
            station_ids_query = station_ids_query.filter(
                _build_station_note_search_condition(filters["note_filter"])
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
                Station.id_regional_energy_system.in_(filters["regional_energy_system_filter"])
            )
        
        if filters.get("union_energy_system_filter"):
            station_ids_query = station_ids_query.filter(
                Station.regional_energy_system_obj.has(
                    RegionalEnergySystem.id_union_energy_system.in_(
                        filters["union_energy_system_filter"]
                    )
                )
            )
        
        if filters.get("energy_system_type_filter"):
            condition = _station_energy_system_type_sql_filter(filters["energy_system_type_filter"])
            station_ids_query = station_ids_query.filter(condition)
        
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


def _build_rd_name_map(sorted_station_ids):
    if not sorted_station_ids:
        return {}

    station_rd_rows = (
        db.session.query(Station.id, RegionalDistrict.name)
        .outerjoin(RegionalDistrict, Station.id_regional_district == RegionalDistrict.id)
        .filter(Station.id.in_(sorted_station_ids))
        .all()
    )

    rd_name_map = {row[0]: (row[1] or "").lower() for row in station_rd_rows}

    for sid in sorted_station_ids:
        rd_name_map.setdefault(sid, "")

    return rd_name_map


def compute_effective_total_pages(sorted_station_ids, per_page_int, rd_name_map=None):
    """
    Рассчитывает фактическое количество страниц с учетом правила
    «не разрывать субъект РФ»: если последняя запись страницы относится к субъекту,
    продолжаем выводить его электростанции на той же странице.
    """
    if per_page_int is None or per_page_int <= 0:
        return 1

    if not sorted_station_ids:
        return 1

    if rd_name_map is None:
        rd_name_map = _build_rd_name_map(sorted_station_ids)

    idx = 0
    total_count = len(sorted_station_ids)
    total_pages = 0
    while idx < total_count:
        total_pages += 1
        count = 0
        current_rd_name = None
        while idx < total_count:
            station_id = sorted_station_ids[idx]
            rd_name = rd_name_map.get(station_id, "")

            if count >= per_page_int and current_rd_name is not None and rd_name != current_rd_name:
                break

            idx += 1
            count += 1
            current_rd_name = rd_name

    return total_pages if total_pages > 0 else 1


def compute_page_start_index(sorted_station_ids, per_page_int, target_page, rd_name_map=None):
    if per_page_int is None or per_page_int <= 0 or target_page <= 1:
        return 0

    if not sorted_station_ids:
        return 0

    if rd_name_map is None:
        rd_name_map = _build_rd_name_map(sorted_station_ids)

    idx = 0
    current_page = 1
    total = len(sorted_station_ids)

    while current_page < target_page and idx < total:
        count = 0
        current_rd_name = None
        while idx < total:
            station_id = sorted_station_ids[idx]
            rd_name = rd_name_map.get(station_id, "")

            if count >= per_page_int and current_rd_name is not None and rd_name != current_rd_name:
                break

            current_rd_name = rd_name
            idx += 1
            count += 1

        current_page += 1

    return idx


def get_filtered_station_ids(filters):
    """
    Возвращает список ID станций, удовлетворяющих текущим фильтрам.
    Используется для пересчета агрегатов на последней странице, чтобы учесть всю выборку.
    """
    filters = filters or {}
    current_year = get_current_year()

    # 1. Фильтрация агрегатов (машин)
    machine_query = db.session.query(Machine.id, Machine.id_station)
    machine_query = filter_by_db_version(machine_query, Machine)

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

    from app.generation.services.station_services.filters_services import (
        build_date_commission_filter,
        build_date_exploitation_filter,
        build_date_decompressing_filter,
        build_date_modernization_filter,
        build_date_modernization_no_power_filter,
        build_relabing_outcome_filter,
        build_machine_note_search_condition,
    )
    for build_fn in (
        build_date_commission_filter,
        build_date_exploitation_filter,
        build_date_decompressing_filter,
        build_date_modernization_filter,
        build_date_modernization_no_power_filter,
        build_relabing_outcome_filter,
    ):
        cond = build_fn(Machine, filters)
        if cond is not None:
            machine_query = machine_query.filter(cond)

    note_machine_cond = build_machine_note_search_condition(
        Machine, PGUMachine, filters.get("note_filter")
    )
    if note_machine_cond is not None:
        machine_query = machine_query.filter(note_machine_cond)

    machine_subquery = machine_query.subquery()

    # 2. Фильтры по станциям
    station_ids_query = db.session.query(machine_subquery.c.id_station).distinct()
    station_ids_query = station_ids_query.join(Station, Station.id == machine_subquery.c.id_station)
    station_ids_query = filter_by_db_version(station_ids_query, Station)

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
        if ids:
            station_ids_query = station_ids_query.filter(
                Station.machines.any(Machine.id_gen_company.in_(ids))
            )

    if filters.get("note_filter"):
        station_ids_query = station_ids_query.filter(
            _build_station_note_search_condition(filters["note_filter"])
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
                RegionalDistrict.id_federal_district.in_(filters["federal_district_filter"])
            )
        )

    if filters.get("regional_energy_system_filter"):
        station_ids_query = station_ids_query.filter(
            Station.id_regional_energy_system.in_(filters["regional_energy_system_filter"])
        )

    if filters.get("union_energy_system_filter"):
        station_ids_query = station_ids_query.filter(
            Station.regional_energy_system_obj.has(
                RegionalEnergySystem.id_union_energy_system.in_(filters["union_energy_system_filter"])
            )
        )

    if filters.get("energy_system_type_filter"):
        condition = _station_energy_system_type_sql_filter(filters["energy_system_type_filter"])
        station_ids_query = station_ids_query.filter(condition)

    raw_ids = [row[0] for row in station_ids_query.all()]

    machine_filters_present = any(
        [
            filters.get("tes_type_filter"),
            filters.get("tes_machine_type_filter"),
            filters.get("fuel_type_filter"),
            filters.get("fuel_check"),
            filters.get("date_commission_filter"),
            filters.get("date_exploitation_filter"),
            filters.get("date_decompressing_expected_filter"),
            filters.get("date_modernization_expected_filter"),
            filters.get("date_modernization_no_power_expected_filter"),
            filters.get("relabing_outcome_filter"),
            filters.get("gen_company_filter"),
            filters.get("condition_type_filter"),
        ]
    )
    extra_station_ids = []
    if (filters.get("station_name_filter") or filters.get("note_filter")) and not machine_filters_present:
        station_query = filter_by_db_version(Station.query, Station)
        if filters.get("station_name_filter"):
            station_query = station_query.filter(
                Station.name.ilike(f"%{filters['station_name_filter']}%")
            )
        if filters.get("note_filter"):
            station_query = station_query.filter(
                Station.note.ilike(f"%{filters['note_filter']}%")
            )
        if filters.get("station_type_filter"):
            station_query = station_query.filter(
                Station.id_station_type.in_(filters["station_type_filter"])
            )
        if filters.get("regional_district_filter"):
            station_query = station_query.filter(
                Station.id_regional_district.in_(filters["regional_district_filter"])
            )
        if filters.get("federal_district_filter"):
            station_query = station_query.filter(
                Station.regional_district.has(
                    RegionalDistrict.id_federal_district.in_(filters["federal_district_filter"])
                )
            )
        if filters.get("regional_energy_system_filter"):
            station_query = station_query.filter(
                Station.id_regional_energy_system.in_(filters["regional_energy_system_filter"])
            )
        if filters.get("union_energy_system_filter"):
            station_query = station_query.filter(
                Station.regional_energy_system_obj.has(
                    RegionalEnergySystem.id_union_energy_system.in_(filters["union_energy_system_filter"])
                )
            )
        if filters.get("energy_system_type_filter"):
            condition = _station_energy_system_type_sql_filter(filters["energy_system_type_filter"])
            station_query = station_query.filter(condition)
        extra_station_ids = [row[0] for row in station_query.with_entities(Station.id).all()]

    unique_ids = sorted({sid for sid in raw_ids + extra_station_ids if sid is not None})
    print(f"[AGG DEBUG] get_filtered_station_ids -> {len(unique_ids)} stations (raw={len(raw_ids)}, extra={len(extra_station_ids)}) при фильтрах {filters}")
    return unique_ids


def get_station_ids_for_aggregation(stations_on_page, should_show_totals, filters):
    """
    Получает все station_ids для групп, которые завершаются на текущей странице.
    Нужно для вычисления агрегированных сумм только по завершенным группам.
    Применяет территориальные фильтры для корректного расчета агрегатов.
    """
    if should_show_totals.get('show_all'):
        # Для per_page='all' возвращаем ID текущих станций
        return [s.id for s in stations_on_page]
    
    if should_show_totals.get('aggregate_full_dataset'):
        # Последняя страница: агрегаты должны учитывать все электростанции текущей выборки
        print("[AGG DEBUG] aggregate_full_dataset=True -> запрашиваем все электростанции по фильтрам")
        return get_filtered_station_ids(filters)
    
    # Для корректных агрегатов нужно оперировать только станциями, прошедшими все фильтры
    filtered_station_ids_full = get_filtered_station_ids(filters)

    if should_show_totals.get('aggregate_full_dataset'):
        return filtered_station_ids_full

    if not filtered_station_ids_full:
        return [s.id for s in stations_on_page]

    filtered_station_ids_full = list(dict.fromkeys(filtered_station_ids_full))

    station_query = Station.query.options(
        joinedload(Station.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
            .joinedload(RegionalEnergySystem.union_energy_system)
            .joinedload(UnionEnergySystem.energy_system_type),
        joinedload(Station.energy_unit),
    ).filter(Station.id.in_(filtered_station_ids_full))

    station_query = filter_by_db_version(station_query, Station)
    filtered_stations = station_query.all()

    grouped_station_ids = {
        'energy_units': defaultdict(set),
        'regional_districts': defaultdict(set),
        'regional_energy_systems': defaultdict(set),
        'union_energy_systems': defaultdict(set),
        'energy_system_types': defaultdict(set),
    }

    for station in filtered_stations:
        sid = station.id
        if not sid:
            continue

        if station.id_energy_unit:
            grouped_station_ids['energy_units'][station.id_energy_unit].add(sid)

        rd = station.regional_district
        if rd:
            grouped_station_ids['regional_districts'][rd.id].add(sid)

            selected_res = None
            if rd.regional_energy_systems:
                for res_candidate in rd.regional_energy_systems:
                    if res_candidate:
                        selected_res = res_candidate
                        if res_candidate.union_energy_system:
                            break

            if selected_res:
                grouped_station_ids['regional_energy_systems'][selected_res.id].add(sid)
                ues = selected_res.union_energy_system
                if ues:
                    grouped_station_ids['union_energy_systems'][ues.id].add(sid)
                    if ues.energy_system_type:
                        grouped_station_ids['energy_system_types'][ues.energy_system_type.id].add(sid)

    station_ids = set()

    if should_show_totals.get('total'):
        station_ids.update(filtered_station_ids_full)

    for level in ['energy_units', 'regional_districts', 'regional_energy_systems', 'union_energy_systems', 'energy_system_types']:
        totals_map = (should_show_totals.get(level) or {})
        for group_id, should_show in totals_map.items():
            if should_show:
                station_ids.update(grouped_station_ids[level].get(group_id, set()))

    if station_ids:
        unique_est = {
            est_id: len(grouped_station_ids['energy_system_types'].get(est_id, set()))
            for est_id in should_show_totals.get('energy_system_types', {}).keys()
        }
        print(f"[AGG DEBUG] level_counts energy_system_types={unique_est}")

    # Если после отбора станций нет, возвращаем хотя бы текущие электростанции
    if not station_ids:
        station_ids = {s.id for s in stations_on_page}

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

    # Загружаем отфильтрованные электростанции
    station_data = get_stations_list(
        page=page,
        per_page=per_page,
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        **filters
    )
    stations = station_data["stations"]
    total_count = station_data["total_count"]
    next_station_info = station_data.get("next_station_info")
    total_pages_default = 1 if show_all else max(1, (total_count + per_page_int - 1) // per_page_int)
    total_pages = station_data.get("effective_total_pages") or total_pages_default

    print(f"[DEBUG] get_station_list_data: получено {len(stations)} станций из {total_count} общих")
    print(f"[DEBUG] get_station_list_data: первые 5 станций: {[s.id for s in stations[:5]]}")

    # Получаем агрегаты с рассчитанными rowspan (только если не per_page=all для ускорения)
    station_ids = [s.id for s in stations]
    is_external_code_check = bool(filters.get("external_code_check"))

    if is_external_code_check:
        from app.generation.services.station_services.external_code_check_services import (
            attach_machines_for_external_code_check,
            build_external_code_check_display_order,
            build_external_code_check_hierarchy,
            determine_external_code_check_headers,
        )

        from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
            get_union_energy_system_list_full,
        )

        station_totals = attach_machines_for_external_code_check(stations)
        hierarchy_data = build_external_code_check_hierarchy(stations, include_names=True)
        prev_page_last_info = station_data.get("prev_page_last_info")
        regional_districts_count_per_res = get_regional_districts_count_per_res()
        grouped_stations = hierarchy_data.get("grouped_stations", {})
        res_names = hierarchy_data.get("regional_energy_system_name", {})
        rd_names = hierarchy_data.get("regional_district_name", {})
        ues_order_index = {
            ues.id: idx for idx, ues in enumerate(get_union_energy_system_list_full())
        }
        grouped_display_order = build_external_code_check_display_order(
            grouped_stations,
            ues_order_index,
            res_names,
            rd_names,
        )

        return {
            "stations": stations,
            "stations_grouped": grouped_stations,
            "station_ids": station_ids,
            "total_count": total_count,
            "total_pages": total_pages,
            "station_totals": station_totals,
            "show_p_ogr": show_p_ogr,
            "show_p_rasp": show_p_rasp,
            "page": page,
            "per_page": per_page,
            "should_show_totals": {
                "energy_units": {},
                "regional_districts": {},
                "regional_energy_systems": {},
                "union_energy_systems": {},
                "energy_system_types": {},
                "total": False,
            },
            "show_headers": determine_external_code_check_headers(
                stations,
                prev_page_last_info,
                regional_districts_count_per_res,
            ),
            "hierarchy_data": hierarchy_data,
            "grouped_display_order": grouped_display_order,
            "regional_districts_count_per_res": regional_districts_count_per_res,
            "station_equipment_group_name_map": {},
        }

    if not show_all:
        machines, station_totals = fetch_machines_with_rowspans(
            station_ids,
            show_p_ogr=show_p_ogr,
            show_p_rasp=show_p_rasp,
            filters=filters,
            start_year=start_year,
            end_year=end_year,
        )
        
        # Привязываем машины обратно к станциям
        station_machines_map = defaultdict(list)
        for m in machines:
            station_machines_map[m.id_station].append(m)

        # Expire до присвоения: иначе замена station.machines помечает «удаленные» Machine как dirty
        # (id_station=None), и при concurrent import -> StaleDataError (version mismatch)
        for station in stations:
            db.session.expire(station, ["machines"])
        for station in stations:
            station.machines = station_machines_map.get(station.id, [])

        # Отображаемое название: как на machine_details — MachineName за год версии, иначе machine_name; при отличии в плане — "<текущ.> (<план>)"
        _apply_machine_display_names(machines)
            
        # Обеспечиваем, что station_totals содержит данные для всех станций
        for station in stations:
            if station.id not in station_totals:
                station_totals[station.id] = {
                    'total_rows': 1,  # только заголовок
                    'machine_count': 0,
                    'total_pgu_count': 0,
                    'summary_rows': 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                }
        
        # Проставляем вычисленные totals прямо в объекты Station (нужно для корректных rowspan/data-атрибутов в шаблонах/JS)
        for station in stations:
            totals = station_totals.get(station.id) or {}
            station.total_rows = totals.get('total_rows', 1)
            station.machine_count = totals.get('machine_count', 0)
            station.total_pgu_count = totals.get('total_pgu_count', 0)
            
        # 🧩 Назначение мощностей агрегатам
        for station in stations:
            for machine in station.machines:
                assign_machine_powers_by_year(machine, start_year, end_year, rounding_digits)
    else:
        # Для per_page=all считаем rowspan и итоги так же, как в постраничном режиме
        machines, station_totals = fetch_machines_with_rowspans(
            station_ids,
            show_p_ogr=show_p_ogr,
            show_p_rasp=show_p_rasp,
            filters=filters,
            start_year=start_year,
            end_year=end_year,
        )
        # Привязываем машины обратно к станциям
        station_machines_map = defaultdict(list)
        for m in machines:
            station_machines_map[m.id_station].append(m)
        for station in stations:
            db.session.expire(station, ["machines"])
        for station in stations:
            station.machines = station_machines_map.get(station.id, [])

        # Отображаемое название: как на machine_details — MachineName за год версии, иначе machine_name; при отличии в плане — "<текущ.> (<план>)"
        _apply_machine_display_names(machines)
            
        # Обеспечиваем, что station_totals содержит данные для всех станций
        for station in stations:
            if station.id not in station_totals:
                station_totals[station.id] = {
                    'total_rows': 1,  # только заголовок
                    'machine_count': 0,
                    'total_pgu_count': 0,
                    'summary_rows': 1 + (1 if show_p_ogr else 0) + (1 if show_p_rasp else 0)
                }
        
        # Проставляем вычисленные totals прямо в объекты Station (нужно для корректных rowspan/data-атрибутов в шаблонах/JS)
        for station in stations:
            totals = station_totals.get(station.id) or {}
            station.total_rows = totals.get('total_rows', 1)
            station.machine_count = totals.get('machine_count', 0)
            station.total_pgu_count = totals.get('total_pgu_count', 0)
                
        # Назначаем мощности агрегатам
        for station in stations:
            for machine in station.machines:
                assign_machine_powers_by_year(machine, start_year, end_year, rounding_digits)

    def _build_equipment_group_sort_key(station):
        machines_with_group = [
            m for m in (station.machines or []) if m.id_equipment_group is not None
        ]
        if not machines_with_group:
            return ""
        machines_with_group.sort(key=lambda m: m.id_equipment_group)
        key_parts = []
        current_group = None
        current_list = []

        def _append_key(group_id, group_list):
            key_parts.append(f"group:{group_id or 0}:{station.id}")

        for machine in machines_with_group:
            if current_group is None or machine.id_equipment_group != current_group:
                if current_list:
                    _append_key(current_group, current_list)
                current_group = machine.id_equipment_group
                current_list = [machine]
            else:
                current_list.append(machine)
        if current_list:
            _append_key(current_group, current_list)

        return "|".join(key_parts)

    for station in stations:
        station.equipment_group_sort_key = _build_equipment_group_sort_key(station)

    # Перерасчет мощностей электростанции
    recalculate_station_powers_by_filtered_machines(
        stations, start_year, end_year, rounding_digits
    )

    # Агрегация по иерархии
    print(f"[DEBUG] get_station_list_data: вызываем build_hierarchy_structure с {len(stations)} станциями")
    hierarchy_data = build_hierarchy_structure(stations, include_names=True)
    print(f"[DEBUG] get_station_list_data: build_hierarchy_structure вернул {len(hierarchy_data.get('grouped_stations', {}))} групп")

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
            filters, next_station_info, force_full_aggregates=show_totals
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
        print(f"[AGG DEBUG] should_show_totals keys: {list(should_show_totals.keys())}")
        print(f"[AGG DEBUG] should_show_totals summary: total={should_show_totals.get('total')}, show_all={should_show_totals.get('show_all')}, aggregate_full_dataset={should_show_totals.get('aggregate_full_dataset')}")
        aggregation_station_ids = get_station_ids_for_aggregation(stations, should_show_totals, filters)
        print(f"[AGG DEBUG] aggregation_station_ids count={len(aggregation_station_ids)}, page_station_count={len(stations)}")
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
        
        # Получаем информацию о последней электростанции предыдущей страницы из кэша
        from app.generation.services.station_services.aggregation_cache import get_cached_page_position
        _, prev_page_last_info = get_cached_page_position(filters, page) if page > 1 else (None, None)
        show_headers = determine_first_headers(stations, prev_page_last_info)
        print(f"[HEADERS] Page {page}: show_headers = {show_headers}")
        print(f"[HEADERS] prev_page_last_info = {prev_page_last_info}")
        
        # Не загружаем данные для агрегаций
        aggregation_station_ids = []
        rows = []

    from app.fuel.services.stations.stations_equipment_groups_services import (
        get_station_equipment_group_name_map,
    )
    station_equipment_group_name_map = get_station_equipment_group_name_map(station_ids)

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
        "hierarchy_data": hierarchy_data,
        "station_equipment_group_name_map": station_equipment_group_name_map,
    }

    # Выполняем агрегации если включено отображение сумм или режим "Все электростанции"
    if show_totals or show_all:
        # Выполняем все агрегации за один проход по данным
        all_aggregations = aggregate_all_at_once(rows)
        if should_show_totals.get('aggregate_full_dataset'):
            sample_year = start_year
            energy_unit_ids = list(should_show_totals.get('energy_units', {}).keys())
            rd_ids = list(should_show_totals.get('regional_districts', {}).keys())
            res_ids = list(should_show_totals.get('regional_energy_systems', {}).keys())
            ues_ids = list(should_show_totals.get('union_energy_systems', {}).keys())
            est_ids = list(should_show_totals.get('energy_system_types', {}).keys())
            if energy_unit_ids:
                eu_id = energy_unit_ids[-1]
                eu_p = all_aggregations["aggregate_power_by_energy_units"]["aggregated"]["p_ust"].get(eu_id, {}).get(sample_year)
                print(f"[AGG DEBUG] energy_unit {eu_id} sample_year {sample_year} p_ust={eu_p}")
            if rd_ids:
                rd_id = rd_ids[-1]
                rd_p = all_aggregations["aggregate_power_by_regional_districts"]["aggregated"]["p_ust"].get(rd_id, {}).get(sample_year)
                print(f"[AGG DEBUG] regional_district {rd_id} sample_year {sample_year} p_ust={rd_p}")
            if res_ids:
                res_id = res_ids[-1]
                res_p = all_aggregations["aggregate_power_by_regional_energy_systems"]["aggregated"]["p_ust"].get(res_id, {}).get(sample_year)
                print(f"[AGG DEBUG] regional_energy_system {res_id} sample_year {sample_year} p_ust={res_p}")
            if ues_ids:
                ues_id = ues_ids[-1]
                ues_p = all_aggregations["aggregate_power_by_union_energy_systems"]["aggregated"]["p_ust"].get(ues_id, {}).get(sample_year)
                print(f"[AGG DEBUG] union_energy_system {ues_id} sample_year {sample_year} p_ust={ues_p}")
            if est_ids:
                est_id = est_ids[-1]
                est_p = all_aggregations["aggregate_power_by_energy_system_types"]["aggregated"]["p_ust"].get(est_id, {}).get(sample_year)
                print(f"[AGG DEBUG] energy_system_type {est_id} sample_year {sample_year} p_ust={est_p}")
        result.update(all_aggregations)

    return result


def get_filtered_station_count(filters):
    """
    Быстрый подсчет количества станций по текущим фильтрам.
    Используется для ранней проверки объема данных при экспорте.
    """
    filters = (filters or {}).copy()
    filters.pop("page", None)
    start_year = filters.pop("start_year", None)
    end_year = filters.pop("end_year", None)

    station_data = get_stations_list(
        page=1,
        per_page=1,
        start_year=start_year,
        end_year=end_year,
        **filters,
    )
    return station_data.get("total_count", 0)


def get_station_list_template_context(form, data, rounding_digits, filters, show_all=False, hierarchy_data=None):
    import time
    start_time = time.time()

    # Порядок ОЭС/ЕЭС ниже — из справочника (union_energy_system_list); hierarchy_data только для совместимости вызовов.
    _ = hierarchy_data

    year_features = get_year_feature_dict()
    _years_from_db = [y.number for y in get_year_list_full()]
    filter_year_list = (
        _years_from_db
        if _years_from_db
        else list(range(get_filter_start_year(), get_filter_end_year() + 1))
    )

    # Получаем энергосистемы заново, чтобы избежать DetachedInstanceError
    from app.refdata.models.energy_systems.energy_system_type_model import EnergySystemType
    from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
    from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
    from app.refdata.models.territories.federal_district_model import FederalDistrict
    from app.refdata.models.territories.regional_district_model import RegionalDistrict
    from app.refdata.models.gen_companies.gen_company_model import GenCompany
    from app.common.services.database_version_services import get_current_version
    from app.common.services.database_version_filter import filter_by_db_version
    from app.extensions import db
    
    # Очищаем LRU кэши для энергосистем (только те, которые имеют кэш)
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import get_energy_system_type_list_full, get_energy_system_type_map
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import get_union_energy_system_list_full, get_union_energy_systems_map, get_ues_to_res_ids_map
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import get_regional_energy_system_list_full, get_regional_energy_systems_map
    from app.common.services.get_services.territories.federal_district_get_services import get_federal_district_list_full, get_fd_to_rd_ids_map
    from app.common.services.get_services.territories.regional_district_get_services import get_regional_district_list_full, get_regional_districts_map
    from app.common.services.get_services.gen_companies.gen_company_get_services import get_gen_company_list_full
    
    # Очищаем только функции с LRU кэшем
    cache_functions = [
        get_energy_system_type_list_full,
        get_energy_system_type_map,
        get_union_energy_system_list_full,
        get_union_energy_systems_map,
        get_regional_energy_system_list_full,
        get_regional_energy_systems_map,
        get_federal_district_list_full,
        get_regional_district_list_full,
        get_regional_districts_map,
        get_ues_to_res_ids_map,
        get_fd_to_rd_ids_map,
        get_gen_company_list_full,
    ]
    
    for func in cache_functions:
        if hasattr(func, 'cache_clear') and not filters.get("external_code_check"):
            func.cache_clear()
    
    current_version = get_current_version()
    
    # Загружаем энергосистемы заново (с фильтрацией по версии БД через кэшированные функции)
    energy_system_type_objects = get_energy_system_type_list_full()
    energy_system_type_list = [{"id": est.id, "name": est.name} for est in energy_system_type_objects]
    energy_system_type_names = dict(get_energy_system_type_map())
    hierarchy_from_data = data.get("hierarchy_data") or {}
    est_names_from_hierarchy = hierarchy_from_data.get("energy_system_type_name") or {}
    if est_names_from_hierarchy:
        energy_system_type_names.update(est_names_from_hierarchy)

    # Загружаем остальные справочники заново (с фильтрацией по версии БД через кэшированные функции)
    union_energy_system_objects = get_union_energy_system_list_full()
    union_energy_system_list = [{"id": ues.id, "name": ues.name} for ues in union_energy_system_objects]
    union_energy_system_names = get_union_energy_systems_map()
    
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import get_regional_energy_system_list_full
    regional_energy_system_objects = get_regional_energy_system_list_full()
    regional_energy_system_list = [{"id": res.id, "name": res.name} for res in regional_energy_system_objects]
    regional_energy_system_names = get_regional_energy_systems_map()
    regional_energy_system_mapping = get_ues_to_res_ids_map()
    ues_to_res_mapping = regional_energy_system_mapping  # это get_ues_to_res_ids_map()

    from app.common.services.get_services.territories.federal_district_get_services import get_federal_district_list_full
    federal_district_objects = get_federal_district_list_full()
    federal_district_list = [{"id": fd.id, "name": fd.name} for fd in federal_district_objects]
    federal_district_names = {fd.id: fd.name for fd in federal_district_objects}
    
    from app.common.services.get_services.territories.regional_district_get_services import (
        get_regional_district_list_full, get_regional_districts_map,
        get_rd_to_fd_id_map, get_rd_to_res_ids_map, get_rd_to_ues_ids_map, get_rd_to_est_ids_map
    )
    from app.common.services.get_services.territories.federal_district_get_services import (
        get_fd_to_rd_ids_map, get_fd_to_res_ids_map, get_fd_to_ues_ids_map, get_fd_to_est_ids_map
    )
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_est_to_ues_ids_map, get_est_to_res_ids_map, get_est_to_rd_ids_map, get_est_to_fd_ids_map
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_ues_to_est_id_map, get_ues_to_rd_ids_map, get_ues_to_fd_ids_map
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_res_to_ues_id_map, get_res_to_est_id_map, get_res_to_rd_ids_map, get_res_to_fd_ids_map
    )
    
    regional_district_tuples = get_regional_district_list_full()
    # get_regional_district_list_full() возвращает список кортежей (id, name)
    regional_district_list = [{"id": rd_id, "name": rd_name} for rd_id, rd_name in regional_district_tuples]
    regional_district_names = get_regional_districts_map()
    regional_district_mapping = get_fd_to_rd_ids_map()
    
    # Получаем все маппинги для JavaScript фильтрации
    est_to_ues_mapping = get_est_to_ues_ids_map()
    est_to_res_mapping = get_est_to_res_ids_map()
    est_to_rd_mapping = get_est_to_rd_ids_map()
    est_to_fd_mapping = get_est_to_fd_ids_map()
    ues_to_est_mapping = get_ues_to_est_id_map()
    ues_to_res_mapping = regional_energy_system_mapping  # это get_ues_to_res_ids_map()
    ues_to_rd_mapping = get_ues_to_rd_ids_map()
    ues_to_fd_mapping = get_ues_to_fd_ids_map()
    res_to_est_mapping = get_res_to_est_id_map()
    res_to_ues_mapping_one = get_res_to_ues_id_map()
    res_to_rd_mapping = get_res_to_rd_ids_map()
    res_to_fd_mapping = get_res_to_fd_ids_map()
    rd_to_fd_mapping_one = _enrich_rd_to_fd_mapping_from_stations(
        get_rd_to_fd_id_map(),
        data.get("stations"),
    )
    rd_to_res_mapping = get_rd_to_res_ids_map()
    rd_to_ues_mapping = get_rd_to_ues_ids_map()
    rd_to_est_mapping = get_rd_to_est_ids_map()
    fd_to_rd_mapping = regional_district_mapping  # это get_fd_to_rd_ids_map()
    fd_to_res_mapping = get_fd_to_res_ids_map()
    fd_to_ues_mapping = get_fd_to_ues_ids_map()
    fd_to_est_mapping = get_fd_to_est_ids_map()

    # Порядок ОЭС как в справочнике (порядковый номер / display_order — см. get_union_energy_system_list_full).
    # По нему же упорядочиваются типы ЕЭС: сначала тот тип, у которого минимальный индекс ОЭС среди фактических данных.
    ues_order_index = {ues["id"]: idx for idx, ues in enumerate(union_energy_system_list)}

    def _min_ues_index(es_group: dict) -> int:
        indices = [ues_order_index.get(ues_id, 10**9) for ues_id in es_group.keys()]
        return min(indices) if indices else 10**9

    # Проверяем наличие stations_grouped в data
    stations_grouped_raw = data.get("stations_grouped", {})
    stations_grouped = _normalize_stations_grouped_for_template(stations_grouped_raw)
    dz_est_id = get_decentralized_zone_energy_system_type_id()
    if stations_grouped:
        normal_est_ids = [
            est_id for est_id in stations_grouped.keys()
            if str(est_id) != str(dz_est_id)
        ]
        sorted_energy_system_type_ids = sorted(
            normal_est_ids,
            key=lambda est_id: _min_ues_index(stations_grouped[est_id])
        )
        decentralized_zone_est_id = dz_est_id if dz_est_id in stations_grouped else None
        if decentralized_zone_est_id is None and dz_est_id is not None:
            decentralized_zone_est_id = dz_est_id if str(dz_est_id) in stations_grouped else None
    else:
        sorted_energy_system_type_ids = []
        decentralized_zone_est_id = None

    decentralized_zone_rd_groups = _extract_decentralized_zone_rd_groups(
        stations_grouped,
        decentralized_zone_est_id,
    )

    # Получаем энергоузлы заново, чтобы избежать DetachedInstanceError
    from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
    from app.common.services.database_version_services import get_current_version
    from app.extensions import db
    
    # Очищаем LRU кэш отфильтрованного списка энергоузлов (полный список без @lru_cache — см. energy_unit_get_services)
    from app.common.services.get_services.energy_systems.energy_unit_get_services import get_energy_unit_list
    get_energy_unit_list.cache_clear()
    
    current_version = get_current_version()
    query = EnergyUnit.query
    query = filter_by_db_version(query, EnergyUnit)
    
    energy_units = query.order_by(
        (EnergyUnit.id != 0),
        EnergyUnit.id.asc()
    ).all()
    
    # Словарь имен энергоузлов сразу с ключами-числами и строками,
    # т.к. в шаблонах и агрегаторах eu_id может приходить как int или str.
    energy_unit_names = {}
    for eu in energy_units:
        energy_unit_names[eu.id] = eu.name
        energy_unit_names[str(eu.id)] = eu.name
    
    # Получаем типы станций заново, чтобы избежать DetachedInstanceError
    from app.refdata.models.refdata_for_stations.station.station_type_model import StationType
    
    station_type_query = StationType.query
    station_type_query = filter_by_db_version(station_type_query, StationType)
    station_type_names = station_type_query.order_by(
        StationType.display_order.asc().nullslast(),
        StationType.name.asc(),
        StationType.id.asc(),
    ).all()
    station_type_list = {st.id: st.name for st in station_type_names}

    # Получаем остальные справочники заново, чтобы избежать DetachedInstanceError
    from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType
    from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType
    from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import PGUTesMachineType
    from app.refdata.models.fuels.fuel_type_model import FuelType
    
    # Очищаем LRU кэши для всех справочников
    from app.common.services.get_services.stations.station_type_get_services import get_station_type_list_full
    from app.common.services.get_services.stations.tes_type_get_services import get_tes_type_list_full
    from app.common.services.get_services.stations.tes_machine_type_get_services import get_tes_machine_type_list_full
    from app.common.services.get_services.stations.pgu_tes_machine_type_get_services import get_pgu_tes_machine_type_list_full
    from app.common.services.get_services.fuels.fuel_type_get_services import get_fuel_type_list_full
    
    get_station_type_list_full.cache_clear()
    get_tes_type_list_full.cache_clear()
    get_tes_machine_type_list_full.cache_clear()
    get_pgu_tes_machine_type_list_full.cache_clear()
    get_fuel_type_list_full.cache_clear()
    
    # Типы ТЭС
    tes_type_query = TesType.query
    tes_type_query = filter_by_db_version(tes_type_query, TesType)
    tes_type_names = tes_type_query.order_by(
        TesType.display_order.asc().nullslast(),
        TesType.name.asc(),
        TesType.id.asc(),
    ).all()
    tes_type_list = {tt.id: tt.name for tt in tes_type_names}

    # Типы машин ТЭС
    tes_machine_type_query = TesMachineType.query
    tes_machine_type_query = filter_by_db_version(tes_machine_type_query, TesMachineType)
    tes_machine_type_names = tes_machine_type_query.order_by(
        TesMachineType.display_order.asc().nullslast(),
        TesMachineType.name.asc(),
        TesMachineType.id.asc(),
    ).all()
    tes_machine_type_list = {tmt.id: tmt.name for tmt in tes_machine_type_names}

    # Типы машин ПГУ-ТЭС
    pgu_tes_machine_type_query = PGUTesMachineType.query
    pgu_tes_machine_type_query = filter_by_db_version(pgu_tes_machine_type_query, PGUTesMachineType)
    pgu_tes_machine_type_names = pgu_tes_machine_type_query.order_by(PGUTesMachineType.id.asc()).all()
    pgu_tes_machine_type_list = {pt.id: pt.name for pt in pgu_tes_machine_type_names}

    # Типы топлива (сортировка по display_order для агрегатов/экспорта)
    from app.common.services.sorting_services import sort_fuel_type_objects

    fuel_type_query = FuelType.query
    fuel_type_query = filter_by_db_version(fuel_type_query, FuelType)
    fuel_type_names = sort_fuel_type_objects(fuel_type_query.all())
    fuel_type_list = {ft.id: ft.name for ft in fuel_type_names}

    machine_tes_types_map = get_current_machine_tes_types_map()

    from app.generation.forms.machine_forms import MACHINE_RELABING_OUTCOME_CHOICES
    from app.generation.services.station_services.filters_services import get_station_sign_filter_choices

    relabing_outcome_filter_choices = []
    for val, lab in MACHINE_RELABING_OUTCOME_CHOICES:
        if val == "":
            relabing_outcome_filter_choices.append(("", "не указано"))
        else:
            relabing_outcome_filter_choices.append((val, lab))

    station_sign_filter_choices = get_station_sign_filter_choices()

    context = {
            "form": form,
            "stations": data.get("stations", []),
            "show_headers": data.get("show_headers"),
            "show_all": show_all,
            "stations_grouped": stations_grouped,
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
            "filter_year_list": filter_year_list,
            "should_show_totals": data.get("should_show_totals", {}),
            "energy_system_type_list": energy_system_type_list,
            "energy_system_type_names": energy_system_type_names,
            "union_energy_system_list": union_energy_system_list,
            "union_energy_system_names": union_energy_system_names,
            "regional_energy_system_list": regional_energy_system_list,
            "regional_energy_system_names": regional_energy_system_names,
            "regional_energy_system_mapping": regional_energy_system_mapping,
            "federal_district_list": federal_district_list,
            "federal_district_names": federal_district_names,
            "regional_district_list": regional_district_list,
            "regional_district_names": regional_district_names,
            "regional_district_mapping": regional_district_mapping,
            # Маппинги для JavaScript фильтрации
            "est_to_ues_mapping": est_to_ues_mapping,
            "est_to_res_mapping": est_to_res_mapping,
            "est_to_rd_mapping": est_to_rd_mapping,
            "est_to_fd_mapping": est_to_fd_mapping,
            "ues_to_est_mapping": ues_to_est_mapping,
            "ues_to_res_mapping": ues_to_res_mapping,
            "ues_to_rd_mapping": ues_to_rd_mapping,
            "ues_to_fd_mapping": ues_to_fd_mapping,
            "res_to_est_mapping": res_to_est_mapping,
            "res_to_ues_mapping_one": res_to_ues_mapping_one,
            "res_to_rd_mapping": res_to_rd_mapping,
            "res_to_fd_mapping": res_to_fd_mapping,
            "rd_to_fd_mapping_one": rd_to_fd_mapping_one,
            "rd_to_res_mapping": rd_to_res_mapping,
            "rd_to_ues_mapping": rd_to_ues_mapping,
            "rd_to_est_mapping": rd_to_est_mapping,
            "fd_to_rd_mapping": fd_to_rd_mapping,
            "fd_to_res_mapping": fd_to_res_mapping,
            "fd_to_ues_mapping": fd_to_ues_mapping,
            "fd_to_est_mapping": fd_to_est_mapping,
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
            "note_filter": filters.get("note_filter"),
            "equipment_group_name_filter": filters.get("equipment_group_name_filter"),
            "station_type_filter": filters.get("station_type_filter"),
            "station_sign_filter": filters.get("station_sign_filter") or [],
            "station_sign_filter_choices": station_sign_filter_choices,
            "tes_type_filter": filters.get("tes_type_filter"),
            "tes_machine_type_filter": filters.get("tes_machine_type_filter"),
            "pgu_tes_machine_type_filter": filters.get("pgu_tes_machine_type_filter"),
            "energy_system_type_filter": filters.get("energy_system_type_filter"),
            "union_energy_system_filter": filters.get("union_energy_system_filter"),
            "regional_energy_system_filter": filters.get("regional_energy_system_filter"),
            "federal_district_filter": filters.get("federal_district_filter"),
            "regional_district_filter": filters.get("regional_district_filter"),
            "fuel_type_filter": filters.get("fuel_type_filter"),
            "relabing_outcome_filter_choices": relabing_outcome_filter_choices,
            "year_features": year_features,
            "machine_tes_types_map": machine_tes_types_map,
            "energy_unit_names": energy_unit_names,
            "sorted_energy_system_type_ids": sorted_energy_system_type_ids,
            "decentralized_zone_est_id": decentralized_zone_est_id,
            "decentralized_zone_rd_groups": decentralized_zone_rd_groups,
            "decentralized_zone_synthetic_ues_id": DECENTRALIZED_ZONE_SYNTHETIC_UES_ID,
            "decentralized_zone_synthetic_res_id": DECENTRALIZED_ZONE_SYNTHETIC_RES_ID,
            "grouped_display_order": data.get("grouped_display_order", {}),
            "regional_districts_count_per_res": data.get("regional_districts_count_per_res", {}),
            "station_equipment_group_name_map": data.get("station_equipment_group_name_map", {}),
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
        decentralized_zone_aggregates = build_decentralized_zone_aggregates(data)

        # Включаем агрегаты по уровням в context
        context.update(energy_unit_aggregates)
        context.update(regional_district_aggregates)
        context.update(regional_energy_system_aggregates)
        context.update(union_energy_system_aggregates)
        context.update(energy_system_type_aggregates)
        context.update(total_energy_system_type_aggregates)
        context.update(decentralized_zone_aggregates)

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
    current_version = get_current_version()

    query = (
        db.session.query(MachineTesType)
        .options(joinedload(MachineTesType.tes_type))
        .filter(MachineTesType.year_number == current_year)
    )
    
    if current_version:
        query = query.filter(MachineTesType.database_version_id == current_version)

    machine_tes_types = query.all()

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
            # Важно: считаем итоги из machine.powers_by_year (нормализовано до 1 записи на год),
            # иначе при дублях MachinePower за один год сумма "по станции" разойдётся с таблицей.
            mp_map = getattr(machine, "powers_by_year", None) or {}
            for year in range(start_year, end_year + 1):
                mp = mp_map.get(year) or {}
                p_ust = mp.get("p_ust")
                p_ogr = mp.get("p_ogr")
                p_rasp = mp.get("p_rasp")
                if p_ust is not None:
                    powers_by_year[year]["p_ust"] += Decimal(p_ust)
                if p_ogr is not None:
                    powers_by_year[year]["p_ogr"] += Decimal(p_ogr)
                if p_rasp is not None:
                    powers_by_year[year]["p_rasp"] += Decimal(p_rasp)

        # Округляем
        for year_data in powers_by_year.values():
            for k in year_data:
                year_data[k] = year_data[k]

        station.powers_by_year = powers_by_year


def assign_machine_powers_by_year(machine, start_year, end_year, rounding_digits):
    # Нормализуем мощности до 1 записи на год.
    # В БД могут встречаться дубли MachinePower на один год; для отображения и итогов
    # важно выбирать детерминированно одну запись (берём с максимальным id).
    by_year_best = {}
    for mp in getattr(machine, "machine_powers", []) or []:
        y = getattr(mp, "year_number", None)
        if y is None or not (start_year <= y <= end_year):
            continue
        mp_id = getattr(mp, "id", 0) or 0
        prev = by_year_best.get(y)
        prev_id = getattr(prev, "id", 0) or 0
        if prev is None or mp_id >= prev_id:
            by_year_best[y] = mp

    machine.powers_by_year = {}
    for y, mp in by_year_best.items():
        machine.powers_by_year[y] = {
            "p_ust": getattr(mp, "p_ust", None),
            "p_ogr": getattr(mp, "p_ogr", None),
            "p_rasp": getattr(mp, "p_rasp", None),
        }

        # fuel_type_by_year вычисляется автоматически через @property в модели Machine


@no_autoflush
def recalculate_station_power(station, start_year, end_year):
    """
    Высокопроизводительный пересчет мощностей электростанции.
    Использует прямой SQL-запрос вместо ORM для максимальной скорости.
    """
    from sqlalchemy import func
    
    # Используем SQL для подсчета суммарных мощностей всех агрегатов электростанции
    # Это намного быстрее, чем перебор через ORM
    power_sums = (
        db.session.query(
            MachinePower.year_number,
            func.coalesce(func.sum(MachinePower.p_ust), 0).label('p_ust'),
            func.coalesce(func.sum(MachinePower.p_ogr), 0).label('p_ogr'),
            func.coalesce(func.sum(MachinePower.p_rasp), 0).label('p_rasp'),
        )
        .join(Machine, MachinePower.id_machine == Machine.id)
        .filter(Machine.id_station == station.id)
        .filter(MachinePower.year_number.between(start_year, end_year))
        .group_by(MachinePower.year_number)
        .all()
    )
    
    # Преобразуем результат в словарь для быстрого доступа
    power_by_year = {
        row.year_number: {
            "p_ust": Decimal(str(row.p_ust or "0")),
            "p_ogr": Decimal(str(row.p_ogr or "0")),
            "p_rasp": Decimal(str(row.p_rasp or "0")),
        }
        for row in power_sums
    }
    
    # Добавляем нулевые значения для годов без данных
    for year in range(start_year, end_year + 1):
        if year not in power_by_year:
            power_by_year[year] = {
                "p_ust": Decimal("0"),
                "p_ogr": Decimal("0"),
                "p_rasp": Decimal("0"),
            }

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
            set_db_version_on_create(sp)
            powers_to_create.append(sp)

    # Коммитим только если есть изменения
    if powers_to_update or powers_to_create:
        if powers_to_create:
            # Чиним sequence через отдельное соединение, чтобы возможная ошибка
            # не оставляла ORM-сессию в aborted state перед основным commit().
            try:
                quick_fix_seq(SCHEMA_GENERATION, "gs_gen_station_powers", "id")
            except Exception:
                # Если БД не PostgreSQL или нет последовательности — тихо пропускаем
                pass
        db.session.add_all(powers_to_create)
        _commit_with_retry()
        clear_station_aggregation_cache("после изменения мощностей")  # Очищаем кэш после изменения мощностей


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

    def _select_total_values(values_dict):
        """
        В агрегатах по России ключом верхнего уровня является ID версии БД.
        Для шаблонов нужно получить словарь {year: value} (или аналогичные вложенные структуры).
        Берем текущую версию, а при ее отсутствии — первый доступный ключ.
        """
        current_version_id = get_current_db_version_id()
        if isinstance(values_dict, dict):
            if current_version_id in values_dict:
                return values_dict[current_version_id]
            # Если по какой-то причине нет текущей версии, берем первый попавшийся словарь
            for _, nested in values_dict.items():
                return nested
        return {}

    def _select_nested_total_values(values_dict):
        """
        Для структур вида {db_version: {inner_key: {...}}} выбираем словарь по текущей версии.
        """
        current_version_id = get_current_db_version_id()
        if isinstance(values_dict, dict):
            if current_version_id in values_dict:
                return values_dict[current_version_id]
            for _, nested in values_dict.items():
                return nested
        return {}

    return {
        # Итоги по России (общие итоги - это уже aggregate_power_by_total_energy_system_types)
        "total_energy_system_types_yearly_p_ust": _select_total_values(
            data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_ust"]
        ),
        "total_energy_system_types_yearly_p_ogr": _select_total_values(
            data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_ogr"]
        ),
        "total_energy_system_types_yearly_p_rasp": _select_total_values(
            data["aggregate_power_by_total_energy_system_types"]["aggregated"]["p_rasp"]
        ),

        # По типам станций
        "total_energy_system_types_by_station_types_yearly_p_ust": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_station_types"]["aggregated"]["p_ust"]
        ),
        "total_energy_system_types_by_station_types_yearly_p_ogr": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_station_types"]["aggregated"]["p_ogr"]
        ),
        "total_energy_system_types_by_station_types_yearly_p_rasp": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_station_types"]["aggregated"]["p_rasp"]
        ),

        # По типам станций и топливу
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_ust": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_ust"]
        ),
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_ogr": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_ogr"]
        ),
        "total_energy_system_types_by_station_types_with_fuel_yearly_p_rasp": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_station_types_with_fuel"]["aggregated"]["p_rasp"]
        ),

        # По типам ТЭС
        "total_energy_system_types_by_tes_types_yearly_p_ust": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_types"]["aggregated"]["p_ust"]
        ),
        "total_energy_system_types_by_tes_types_yearly_p_ogr": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_types"]["aggregated"]["p_ogr"]
        ),
        "total_energy_system_types_by_tes_types_yearly_p_rasp": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_types"]["aggregated"]["p_rasp"]
        ),

        # По типам ТЭС и топливу
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_ust": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_ust"]
        ),
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_ogr": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_ogr"]
        ),
        "total_energy_system_types_by_tes_types_with_fuel_yearly_p_rasp": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_types_with_fuel"]["aggregated"]["p_rasp"]
        ),

        # По типам машин ТЭС
        "total_energy_system_types_by_tes_machine_types_yearly_p_ust": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_machine_types"]["aggregated"]["p_ust"]
        ),
        "total_energy_system_types_by_tes_machine_types_yearly_p_ogr": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_machine_types"]["aggregated"]["p_ogr"]
        ),
        "total_energy_system_types_by_tes_machine_types_yearly_p_rasp": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_machine_types"]["aggregated"]["p_rasp"]
        ),

        # По типам машин ТЭС и топливу
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ust": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"]
        ),
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_ogr": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_ogr"]
        ),
        "total_energy_system_types_by_tes_machine_types_with_fuel_yearly_p_rasp": _select_nested_total_values(
            data["aggregate_total_energy_system_types_by_tes_machine_types_with_fuel"]["aggregated"]["p_rasp"]
        ),
    }


def build_synchronous_area_aggregates(data):
    """
    Итоги по синхронным зонам (Synchronous Areas) для шаблонов станций.

    В optimized_aggregation уже формируются агрегаты:
      - aggregate_power_by_synchronous_areas
      - aggregate_synchronous_areas_by_station_types
      - aggregate_synchronous_areas_by_station_types_with_fuel
      - aggregate_synchronous_areas_by_tes_types
      - aggregate_synchronous_areas_by_tes_types_with_fuel
      - aggregate_synchronous_areas_by_tes_machine_types
      - aggregate_synchronous_areas_by_tes_machine_types_with_fuel

    Здесь лишь приводим их к именам, которые ожидают шаблоны.
    """
    return {
        # Основная агрегация
        "synchronous_areas_yearly_p_ust": data["aggregate_power_by_synchronous_areas"]["aggregated"]["p_ust"],
        "synchronous_areas_yearly_p_ogr": data["aggregate_power_by_synchronous_areas"]["aggregated"]["p_ogr"],
        "synchronous_areas_yearly_p_rasp": data["aggregate_power_by_synchronous_areas"]["aggregated"]["p_rasp"],

        # По типам станций
        "synchronous_areas_by_station_types_yearly_p_ust": data["aggregate_synchronous_areas_by_station_types"]["aggregated"]["p_ust"],
        "synchronous_areas_by_station_types_yearly_p_ogr": data["aggregate_synchronous_areas_by_station_types"]["aggregated"]["p_ogr"],
        "synchronous_areas_by_station_types_yearly_p_rasp": data["aggregate_synchronous_areas_by_station_types"]["aggregated"]["p_rasp"],

        # По типам станций и топливу
        "synchronous_areas_by_station_types_with_fuel_yearly_p_ust": data["aggregate_synchronous_areas_by_station_types_with_fuel"]["aggregated"]["p_ust"],
        "synchronous_areas_by_station_types_with_fuel_yearly_p_ogr": data["aggregate_synchronous_areas_by_station_types_with_fuel"]["aggregated"]["p_ogr"],
        "synchronous_areas_by_station_types_with_fuel_yearly_p_rasp": data["aggregate_synchronous_areas_by_station_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам ТЭС
        "synchronous_areas_by_tes_types_yearly_p_ust": data["aggregate_synchronous_areas_by_tes_types"]["aggregated"]["p_ust"],
        "synchronous_areas_by_tes_types_yearly_p_ogr": data["aggregate_synchronous_areas_by_tes_types"]["aggregated"]["p_ogr"],
        "synchronous_areas_by_tes_types_yearly_p_rasp": data["aggregate_synchronous_areas_by_tes_types"]["aggregated"]["p_rasp"],

        # По типам ТЭС и топливу
        "synchronous_areas_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_synchronous_areas_by_tes_types_with_fuel"]["aggregated"]["p_ust"],
        "synchronous_areas_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_synchronous_areas_by_tes_types_with_fuel"]["aggregated"]["p_ogr"],
        "synchronous_areas_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_synchronous_areas_by_tes_types_with_fuel"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС
        "synchronous_areas_by_tes_machine_types_yearly_p_ust": data["aggregate_synchronous_areas_by_tes_machine_types"]["aggregated"]["p_ust"],
        "synchronous_areas_by_tes_machine_types_yearly_p_ogr": data["aggregate_synchronous_areas_by_tes_machine_types"]["aggregated"]["p_ogr"],
        "synchronous_areas_by_tes_machine_types_yearly_p_rasp": data["aggregate_synchronous_areas_by_tes_machine_types"]["aggregated"]["p_rasp"],

        # По типам машин ТЭС и топливу
        "synchronous_areas_by_tes_machine_types_with_fuel_yearly_p_ust": data["aggregate_synchronous_areas_by_tes_machine_types_with_fuel"]["aggregated"]["p_ust"],
        "synchronous_areas_by_tes_machine_types_with_fuel_yearly_p_ogr": data["aggregate_synchronous_areas_by_tes_machine_types_with_fuel"]["aggregated"]["p_ogr"],
        "synchronous_areas_by_tes_machine_types_with_fuel_yearly_p_rasp": data["aggregate_synchronous_areas_by_tes_machine_types_with_fuel"]["aggregated"]["p_rasp"],
    }


def build_federal_district_aggregates(data):
    """
    Итоги по федеральным округам (ФО) для totals_summary.

    Сейчас используем только суммарные значения (без детализаций).
    """
    return {
        "federal_districts_yearly_p_ust": data["aggregate_power_by_federal_districts"]["aggregated"]["p_ust"],
        "federal_districts_yearly_p_ogr": data["aggregate_power_by_federal_districts"]["aggregated"]["p_ogr"],
        "federal_districts_yearly_p_rasp": data["aggregate_power_by_federal_districts"]["aggregated"]["p_rasp"],

        "federal_districts_by_station_types_yearly_p_ust": data["aggregate_federal_districts_by_station_types"]["aggregated"]["p_ust"],
        "federal_districts_by_station_types_yearly_p_ogr": data["aggregate_federal_districts_by_station_types"]["aggregated"]["p_ogr"],
        "federal_districts_by_station_types_yearly_p_rasp": data["aggregate_federal_districts_by_station_types"]["aggregated"]["p_rasp"],

        "federal_districts_by_tes_types_yearly_p_ust": data["aggregate_federal_districts_by_tes_types"]["aggregated"]["p_ust"],
        "federal_districts_by_tes_types_yearly_p_ogr": data["aggregate_federal_districts_by_tes_types"]["aggregated"]["p_ogr"],
        "federal_districts_by_tes_types_yearly_p_rasp": data["aggregate_federal_districts_by_tes_types"]["aggregated"]["p_rasp"],

        "federal_districts_by_tes_types_with_fuel_yearly_p_ust": data["aggregate_federal_districts_by_tes_types_with_fuel"]["aggregated"]["p_ust"],
        "federal_districts_by_tes_types_with_fuel_yearly_p_ogr": data["aggregate_federal_districts_by_tes_types_with_fuel"]["aggregated"]["p_ogr"],
        "federal_districts_by_tes_types_with_fuel_yearly_p_rasp": data["aggregate_federal_districts_by_tes_types_with_fuel"]["aggregated"]["p_rasp"],

        "federal_districts_by_tes_machine_types_yearly_p_ust": data["aggregate_federal_districts_by_tes_machine_types"]["aggregated"]["p_ust"],
        "federal_districts_by_tes_machine_types_yearly_p_ogr": data["aggregate_federal_districts_by_tes_machine_types"]["aggregated"]["p_ogr"],
        "federal_districts_by_tes_machine_types_yearly_p_rasp": data["aggregate_federal_districts_by_tes_machine_types"]["aggregated"]["p_rasp"],

        "federal_districts_by_tes_machine_types_with_fuel_yearly_p_ust": data[
            "aggregate_federal_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_ust"],
        "federal_districts_by_tes_machine_types_with_fuel_yearly_p_ogr": data[
            "aggregate_federal_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_ogr"],
        "federal_districts_by_tes_machine_types_with_fuel_yearly_p_rasp": data[
            "aggregate_federal_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_rasp"],
    }


def build_decentralized_zone_aggregates(data):
    """Отдельные итоги по децентрализованной зоне: всего, по ФО и по субъектам РФ."""
    return {
        "decentralized_zone_yearly_p_ust": data["aggregate_decentralized_zone"]["aggregated"]["p_ust"],
        "decentralized_zone_yearly_p_ogr": data["aggregate_decentralized_zone"]["aggregated"]["p_ogr"],
        "decentralized_zone_yearly_p_rasp": data["aggregate_decentralized_zone"]["aggregated"]["p_rasp"],
        "decentralized_zone_by_regional_districts_yearly_p_ust": data[
            "aggregate_decentralized_zone_by_regional_districts"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_by_regional_districts_yearly_p_ogr": data[
            "aggregate_decentralized_zone_by_regional_districts"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_by_regional_districts_yearly_p_rasp": data[
            "aggregate_decentralized_zone_by_regional_districts"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_by_federal_districts_yearly_p_ust": data[
            "aggregate_decentralized_zone_by_federal_districts"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_by_federal_districts_yearly_p_ogr": data[
            "aggregate_decentralized_zone_by_federal_districts"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_by_federal_districts_yearly_p_rasp": data[
            "aggregate_decentralized_zone_by_federal_districts"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_by_station_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_by_station_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_by_station_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_by_station_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_by_station_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_by_station_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_by_tes_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_by_tes_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_by_tes_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_by_tes_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_by_tes_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_by_tes_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_by_tes_types_with_fuel_yearly_p_ust": data[
            "aggregate_decentralized_zone_by_tes_types_with_fuel"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_by_tes_types_with_fuel_yearly_p_ogr": data[
            "aggregate_decentralized_zone_by_tes_types_with_fuel"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_by_tes_types_with_fuel_yearly_p_rasp": data[
            "aggregate_decentralized_zone_by_tes_types_with_fuel"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_by_tes_machine_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_by_tes_machine_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_by_tes_machine_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_by_tes_machine_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_by_tes_machine_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_by_tes_machine_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_by_tes_machine_types_with_fuel_yearly_p_ust": data[
            "aggregate_decentralized_zone_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_by_tes_machine_types_with_fuel_yearly_p_ogr": data[
            "aggregate_decentralized_zone_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_by_tes_machine_types_with_fuel_yearly_p_rasp": data[
            "aggregate_decentralized_zone_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_regional_districts_by_station_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_regional_districts_by_station_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_regional_districts_by_station_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_regional_districts_by_station_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_regional_districts_by_station_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_regional_districts_by_station_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_regional_districts_by_tes_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_regional_districts_by_tes_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_regional_districts_by_tes_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_regional_districts_by_tes_types_with_fuel_yearly_p_ust": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_types_with_fuel"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_regional_districts_by_tes_types_with_fuel_yearly_p_ogr": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_types_with_fuel"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_regional_districts_by_tes_types_with_fuel_yearly_p_rasp": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_types_with_fuel"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_regional_districts_by_tes_machine_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_machine_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_regional_districts_by_tes_machine_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_machine_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_regional_districts_by_tes_machine_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_machine_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_regional_districts_by_tes_machine_types_with_fuel_yearly_p_ust": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_regional_districts_by_tes_machine_types_with_fuel_yearly_p_ogr": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_regional_districts_by_tes_machine_types_with_fuel_yearly_p_rasp": data[
            "aggregate_decentralized_zone_regional_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_federal_districts_by_station_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_federal_districts_by_station_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_federal_districts_by_station_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_federal_districts_by_station_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_federal_districts_by_station_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_federal_districts_by_station_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_federal_districts_by_tes_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_federal_districts_by_tes_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_federal_districts_by_tes_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_federal_districts_by_tes_types_with_fuel_yearly_p_ust": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_types_with_fuel"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_federal_districts_by_tes_types_with_fuel_yearly_p_ogr": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_types_with_fuel"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_federal_districts_by_tes_types_with_fuel_yearly_p_rasp": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_types_with_fuel"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_federal_districts_by_tes_machine_types_yearly_p_ust": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_machine_types"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_federal_districts_by_tes_machine_types_yearly_p_ogr": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_machine_types"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_federal_districts_by_tes_machine_types_yearly_p_rasp": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_machine_types"
        ]["aggregated"]["p_rasp"],
        "decentralized_zone_federal_districts_by_tes_machine_types_with_fuel_yearly_p_ust": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_ust"],
        "decentralized_zone_federal_districts_by_tes_machine_types_with_fuel_yearly_p_ogr": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_ogr"],
        "decentralized_zone_federal_districts_by_tes_machine_types_with_fuel_yearly_p_rasp": data[
            "aggregate_decentralized_zone_federal_districts_by_tes_machine_types_with_fuel"
        ]["aggregated"]["p_rasp"],
    }


# -------------------------------
# Мутации по станциям/агрегатам
# -------------------------------

def add_station_service(
    user,
    name: str,
    id_regional_district: int,
    id_station_type=None,
    id_regional_energy_system=None,
    force_create: bool = False,
) -> Station:
    name = (name or "").strip()
    if not name:
        raise ValueError("Не указано название электростанции")

    current_version_id = get_current_db_version_id()
    if not force_create:
        station_query = Station.query.filter(
            Station.name == name,
            Station.id_regional_district == id_regional_district,
        )
        if current_version_id is None:
            station_query = station_query.filter(Station.database_version_id.is_(None))
        else:
            station_query = station_query.filter(Station.database_version_id == current_version_id)
        existing_station = station_query.first()
        if existing_station:
            raise ValueError("STATION_DUPLICATE")


    # SelectField часто возвращает строку; "0"/"" трактуем как "не указано"
    station_type_id = None
    if id_station_type not in (None, "", 0, "0"):
        station_type_id = int(id_station_type)
    
    max_attempts = 2
    for attempt in range(max_attempts):
        try:
            station = Station(
                name=name,
                id_regional_district=id_regional_district,
                id_station_type=station_type_id,
                id_regional_energy_system=id_regional_energy_system,
            )
            # Автоматически связываем с текущей версией БД
            set_db_version_on_create(station)
            db.session.add(station)
            _commit_with_retry()
            clear_station_aggregation_cache("после добавления электростанции")  # Очищаем кэш после добавления электростанции
            rd = db.session.query(RegionalDistrict).get(id_regional_district)
            rd_name = rd.name if rd else "не указано"
            log_to_db(user, f"Создана новая станция: {station.name}", entity_type="station", entity_id=station.id, details=f"Субъект РФ: {rd_name}")
            return station
        except IntegrityError as e:
            db.session.rollback()
            # Проверяем, является ли это ошибкой UniqueViolation на первичном ключе
            if isinstance(e.orig, psycopg2.errors.UniqueViolation) and attempt == 0:
                error_msg = str(e.orig)
                # Проверяем, что это ошибка именно на первичном ключе stations
                if "stations_pkey" in error_msg:
                    # Исправляем последовательность и повторяем попытку
                    quick_fix_seq(SCHEMA_GENERATION, "gs_gen_stations", "id")
                    continue
            raise
        except Exception:
            db.session.rollback()
            raise


_EXCLUDED_DISTRICT_IDS_CACHE: dict[object, set[int]] = {}


def _norm_text_value(value: str | None) -> str:
    return (value or "").strip().lower()


def _get_excluded_district_ids(database_version_id: int | None) -> set[int]:
    cache_key = database_version_id if database_version_id is not None else "none"
    cached = _EXCLUDED_DISTRICT_IDS_CACHE.get(cache_key)
    if cached is not None:
        return set(cached)

    excluded_ids = set(STATION_UNIQUE_EXCLUDED_DISTRICT_IDS)
    if STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS:
        version_id = database_version_id or get_current_db_version_id()
        query = db.session.query(RegionalDistrict.id)
        if version_id is not None:
            query = query.filter(RegionalDistrict.database_version_id == version_id)
        filters = []
        uuids = [uid.strip() for uid in STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS if uid.strip()]
        if uuids:
            filters.append(RegionalDistrict.ref_uuid.in_(uuids))

        if filters:
            excluded_ids.update({row[0] for row in query.filter(or_(*filters)).all()})

    _EXCLUDED_DISTRICT_IDS_CACHE[cache_key] = set(excluded_ids)
    return excluded_ids


def _is_excluded_district(district_id: int | None, database_version_id: int | None) -> bool:
    if not district_id:
        return False
    excluded_ids = _get_excluded_district_ids(database_version_id)
    if district_id in excluded_ids:
        return True

    # Дополнительная проверка: сверяем по UUID конкретного id без фильтра по версии
    if STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS:
        rd = db.session.get(RegionalDistrict, district_id)
        if rd and rd.ref_uuid and rd.ref_uuid in STATION_UNIQUE_EXCLUDED_DISTRICT_UUIDS:
            excluded_ids.add(district_id)
            _EXCLUDED_DISTRICT_IDS_CACHE[database_version_id if database_version_id is not None else "none"] = set(excluded_ids)
            return True
    return False


def _station_external_code_conflict_id(station: Station, new_code: str) -> int | None:
    query = db.session.query(Station.id).filter(
        Station.external_code == new_code,
        Station.id != station.id,
    )
    version_id = getattr(station, "database_version_id", None)
    if version_id is None:
        query = query.filter(Station.database_version_id.is_(None))
    else:
        query = query.filter(Station.database_version_id == version_id)
    return query.scalar()


def update_station_from_form_service(
    user,
    station: Station,
    form,
    regional_district_list,
    *,
    can_edit_generation: bool = True,
    can_edit_fuel: bool = True,
    can_edit_fuel_dz: bool = False,
) -> list:
    changes = []
    try:
        def _norm_text(v) -> str:
            """Нормализует текст для сравнения: None/пусто/пробелы -> ''."""
            if v is None:
                return ""
            try:
                return str(v).strip()
            except Exception:
                return ""

        def _is_unspecified_text(v) -> bool:
            """Считает 'не указано' и пустые значения эквивалентом None."""
            s = _norm_text(v).lower()
            return s in {"", "не указано", "не указан", "не указана", "—", "-"}

        def _normalize_angle_quotes(value: str | None) -> str | None:
            """Normalize «» pairs to opening/closing order."""
            if value is None:
                return None
            text = str(value)
            if "«" not in text and "»" not in text:
                return text
            normalized = []
            inside = False
            for ch in text:
                if ch in {"«", "»"}:
                    normalized.append("»" if inside else "«")
                    inside = not inside
                else:
                    normalized.append(ch)
            return "".join(normalized)

        if not can_edit_generation and not can_edit_fuel and not can_edit_fuel_dz:
            return changes

        can_edit_core = can_edit_generation or can_edit_fuel_dz

        if current_user.is_authenticated and getattr(current_user, "is_admin", False):
            old_code = (getattr(station, "external_code", None) or "").strip()
            new_code = (getattr(form, "external_code", None).data or "").strip()
            if not new_code:
                raise ValueError("external_code не может быть пустым.")
            if old_code != new_code:
                conflict_id = _station_external_code_conflict_id(station, new_code)
                if conflict_id is not None:
                    raise ValueError(
                        f"Код {new_code!r} уже используется электростанцией id={conflict_id} "
                        f"в версии БД {getattr(station, 'database_version_id', None)}"
                    )
                changes.append(f"external_code: {old_code or 'не указано'} → {new_code}")
                station.external_code = new_code

        # Название + субъект РФ: проверка уникальности до присваивания
        new_name = _normalize_angle_quotes(form.name.data) if can_edit_core else station.name
        new_district_id = (
            form.id_regional_district.data if can_edit_core else station.id_regional_district
        )
        if can_edit_core and (
            station.name != new_name or station.id_regional_district != new_district_id
        ):
            if not _is_excluded_district(new_district_id, station.database_version_id):
                with db.session.no_autoflush:
                    conflict = (
                        db.session.query(Station.id)
                        .filter(
                            Station.name == new_name,
                            Station.id_regional_district == new_district_id,
                            Station.database_version_id == station.database_version_id,
                            Station.id != station.id,
                        )
                        .first()
                    )
                if conflict:
                    raise ValueError(
                        "Станция с таким названием уже существует в выбранном субъекте РФ и версии БД."
                    )

        if can_edit_core and station.name != new_name:
            changes.append(f"Название: {station.name} → {new_name}")
            station.name = new_name

        if can_edit_core:
            # Состояние
            new_condition_type_id = int(form.id_condition_type.data)
            new_condition_type = db.session.query(ConditionType).filter_by(id=new_condition_type_id).first()
            if new_condition_type:
                old_value = station.condition_type.name if station.condition_type else "не указано"
                new_value = new_condition_type.name
                if old_value != new_value:
                    changes.append(f"Состояние: {old_value} → {new_value}")
                station.id_condition_type = new_condition_type.id

            # Группа электростанции
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

        if can_edit_fuel:
            # Признак электростанции
            new_station_sign_raw = getattr(form, "station_sign", None)
            new_station_sign_value = (
                new_station_sign_raw.data if new_station_sign_raw is not None else None
            )
            if _is_unspecified_text(new_station_sign_value):
                new_station_sign = None
            elif _norm_text(new_station_sign_value) == STATION_SIGN_ESPP:
                new_station_sign = STATION_SIGN_ESPP
            else:
                new_station_sign = None
            old_station_sign_display = station.station_sign_display
            new_station_sign_display = (
                STATION_SIGN_ESPP if new_station_sign == STATION_SIGN_ESPP else STATION_SIGN_UNSPECIFIED
            )
            if station.station_sign != new_station_sign:
                changes.append(
                    f"Признак электростанции: {old_station_sign_display} → {new_station_sign_display}"
                )
                station.station_sign = new_station_sign

        if can_edit_core:
            # Субъект РФ
            if station.id_regional_district != new_district_id:
                old_value = station.regional_district.name if station.regional_district else "не указано"
                new_value = next(
                    (d[1] if isinstance(d, tuple) else d["name"]
                     for d in regional_district_list
                     if (d[0] if isinstance(d, tuple) else d["id"]) == new_district_id),
                    "не указано",
                )
                changes.append(f"Субъект РФ: {old_value} → {new_value}")
                station.id_regional_district = new_district_id

                # Обновление федерального округа (как производного от субъекта)
                new_regional_district_obj = (
                    db.session.query(RegionalDistrict)
                    .options(
                        joinedload(RegionalDistrict.federal_district),
                        joinedload(RegionalDistrict.regional_energy_systems),
                    )
                    .filter_by(id=new_district_id)
                    .first()
                )
                if new_regional_district_obj:
                    old_federal_district = (
                        station.regional_district.federal_district.name
                        if station.regional_district and station.regional_district.federal_district
                        else "не указано"
                    )
                    new_federal_district = (
                        new_regional_district_obj.federal_district.name
                        if new_regional_district_obj.federal_district
                        else "не указано"
                    )
                    if old_federal_district != new_federal_district:
                        changes.append(f"Федеральный округ: {old_federal_district} → {new_federal_district}")

                    station.regional_district = new_regional_district_obj

                    if can_edit_generation:
                        # Проверка соответствия Субъекта РФ и Региональной энергосистемы
                        res_id_to_check = form.id_regional_energy_system.data
                        if res_id_to_check == 0:
                            res_id_to_check = station.id_regional_energy_system

                        if res_id_to_check:
                            res_ids_for_district = {res.id for res in new_regional_district_obj.regional_energy_systems}
                            if res_id_to_check not in res_ids_for_district:
                                res_obj = db.session.get(RegionalEnergySystem, res_id_to_check)
                                res_name = res_obj.name if res_obj else "не указано"
                                raise ValueError(
                                    f"Субъект РФ '{new_value}' не входит в указанную региональную энергосистему '{res_name}'. "
                                    f"Пожалуйста, выберите соответствующую региональную энергосистему или измените субъект РФ."
                                )

            # Местоположение
            new_location_raw = getattr(form, "location", None).data if getattr(form, "location", None) is not None else None
            new_location = _norm_text(new_location_raw) or None
            old_location = _norm_text(getattr(station, "location", None)) or None
            if old_location != new_location:
                changes.append(f"Местоположение: {old_location or 'не указано'} → {new_location or 'не указано'}")
                station.location = new_location

        if can_edit_generation:
            # Тип  электростанции
            if form.id_station_type.data and int(form.id_station_type.data) != 0:
                new_station_type_id = int(form.id_station_type.data)
                new_station_type = db.session.query(StationType).filter_by(id=new_station_type_id).first()
                if new_station_type:
                    old_value = station.station_type.name if station.station_type else "не указано"
                    new_value = new_station_type.name
                    if old_value != new_value:
                        changes.append(f"Тип  электростанции: {old_value} → {new_value}")
                    station.id_station_type = new_station_type.id
            else:
                if station.id_station_type is not None:
                    old_value = station.station_type.name if station.station_type else "не указано"
                    changes.append(f"Тип  электростанции: {old_value} → не указано")
                    station.id_station_type = None

            # Региональная энергосистема (прямая связь через id_regional_energy_system)
            new_res_id = form.id_regional_energy_system.data
            if new_res_id == 0:
                new_res_id = None
            if station.id_regional_energy_system != new_res_id:
                from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
                old_res_obj = (
                    db.session.get(RegionalEnergySystem, station.id_regional_energy_system)
                    if station.id_regional_energy_system
                    else None
                )
                new_res_obj = db.session.get(RegionalEnergySystem, new_res_id) if new_res_id else None
                old_res_name = old_res_obj.name if old_res_obj else "не указано"
                new_res_name = new_res_obj.name if new_res_obj else "не указано"
                changes.append(f"Региональная энергосистема: {old_res_name} → {new_res_name}")
                station.id_regional_energy_system = new_res_id

            # Энергоузел
            from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit

            new_energy_unit_id = None
            try:
                if getattr(form, "id_energy_unit", None) is not None and form.id_energy_unit.data not in (None, "", 0, "0"):
                    new_energy_unit_id = int(form.id_energy_unit.data)
            except Exception:
                new_energy_unit_id = None
            if new_energy_unit_id == 0:
                new_energy_unit_id = None

            new_energy_unit_obj = db.session.get(EnergyUnit, new_energy_unit_id) if new_energy_unit_id is not None else None
            station_version_id = getattr(station, "database_version_id", None)
            energy_unit_version_id = getattr(new_energy_unit_obj, "database_version_id", None) if new_energy_unit_obj else None
            try:
                from flask import current_app
                current_app.logger.debug(
                    "[ENERGY_UNIT_SAVE] station_id=%s station_version_id=%s form_energy_unit=%s loaded_energy_unit=%s loaded_version_id=%s",
                    getattr(station, "id", None),
                    station_version_id,
                    new_energy_unit_id,
                    getattr(new_energy_unit_obj, "id", None),
                    energy_unit_version_id,
                )
            except Exception:
                pass
            if new_energy_unit_id is not None and new_energy_unit_obj is None:
                raise ValueError("Выбранный энергоузел не найден. Обновите страницу и попробуйте снова.")
            if new_energy_unit_obj is not None:
                if station_version_id != energy_unit_version_id:
                    raise ValueError(
                        "Выбранный энергоузел относится к другой версии БД. "
                        "Выберите энергоузел из текущей версии электростанции."
                    )
            if new_energy_unit_obj is not None and _is_unspecified_text(getattr(new_energy_unit_obj, "name", None)):
                new_energy_unit_id = None
                new_energy_unit_obj = None

            old_energy_unit_id_raw = getattr(station, "id_energy_unit", None)
            old_energy_unit_id = old_energy_unit_id_raw
            if old_energy_unit_id == 0:
                old_energy_unit_id = None
            old_energy_unit_obj = getattr(station, "energy_unit", None) or (db.session.get(EnergyUnit, old_energy_unit_id) if old_energy_unit_id is not None else None)
            if old_energy_unit_obj is not None and _is_unspecified_text(getattr(old_energy_unit_obj, "name", None)):
                old_energy_unit_id = None
                old_energy_unit_obj = None

            if old_energy_unit_id != new_energy_unit_id:
                old_value = (getattr(old_energy_unit_obj, "name", None) or "не указано") if old_energy_unit_obj else "не указано"
                new_value = (getattr(new_energy_unit_obj, "name", None) or "не указано") if new_energy_unit_obj else "не указано"
                changes.append(f"Энергоузел: {old_value} → {new_value}")
                station.id_energy_unit = new_energy_unit_id
            else:
                if old_energy_unit_id is None and old_energy_unit_id_raw not in (None, 0, "0"):
                    station.id_energy_unit = None

        _commit_with_retry()
        clear_station_aggregation_cache("после обновления электростанции")  # Очищаем кэш после обновления электростанции

        if changes:
            rd_name = station.regional_district.name if station.regional_district else "не указано"
            log_to_db(user, f"Изменения в  электростанции {station.name} ({rd_name})", details="; ".join(changes), entity_type="station", entity_id=station.id)

        return changes
    except Exception:
        db.session.rollback()
        raise


def station_annual_energy_generation_query(
    station_id: int,
    start_year: int,
    end_year: int,
    station_version_id: int | None,
):
    """Записи выработки с периодом «год» (month_number = 0) для таблицы на карточке станции."""
    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.energy_balance.models.station_energy_generation_model import (
        STATION_ENERGY_GENERATION_PERIOD_YEAR,
        StationEnergyGeneration,
    )

    q = StationEnergyGeneration.query.filter(
        StationEnergyGeneration.id_station == station_id,
        StationEnergyGeneration.year_number >= start_year,
        StationEnergyGeneration.year_number <= end_year,
        StationEnergyGeneration.month_number == STATION_ENERGY_GENERATION_PERIOD_YEAR,
    )
    return filter_by_explicit_db_version(q, StationEnergyGeneration, station_version_id)


def station_annual_energy_by_year(
    station_id: int,
    start_year: int,
    end_year: int,
    station_version_id: int | None,
) -> dict[int, object]:
    return {
        row.year_number: row.electricity_generation
        for row in station_annual_energy_generation_query(
            station_id, start_year, end_year, station_version_id
        ).all()
    }


def save_station_energy_generation_service(
    user,
    station: Station,
    station_version_id: int | None,
    start_year: int,
    end_year: int,
    form_data,
) -> list:
    """
    Сохраняет выработку электроэнергии электростанцией по годам (млн кВт·ч).
    Возвращает список строк изменений для логирования (пустой, если сохранять нечего).
    """
    from app.energy_balance.models.station_energy_generation_model import (
        STATION_ENERGY_GENERATION_PERIOD_YEAR,
        StationEnergyGeneration,
    )
    from app.generation.services.machine_services.machine_services import to_decimal, is_same_decimal

    changes: list[str] = []

    def _log_num(v) -> str:
        if v is None:
            return "не указано"
        try:
            return str(v).replace(".", ",").rstrip("0").rstrip(",") or "0"
        except Exception:
            return str(v).replace(".", ",")

    def _field_changed(raw_value, orig_value) -> bool:
        if orig_value in (None, "", "—", "-"):
            return raw_value not in (None, "", "—", "-")
        return not is_same_decimal(to_decimal(raw_value), to_decimal(orig_value))

    try:
        by_year = {
            r.year_number: r
            for r in station_annual_energy_generation_query(
                station.id, start_year, end_year, station_version_id
            ).all()
        }

        for year in range(start_year, end_year + 1):
            field = f"st_gen_{year}"
            raw = form_data.get(field)
            orig_raw = form_data.get(f"{field}_orig")

            if not _field_changed(raw, orig_raw):
                continue

            new_val = to_decimal(raw)
            rec = by_year.get(year)
            old_val = rec.electricity_generation if rec else None

            if new_val is None:
                if rec is None or old_val is None:
                    continue
                rec.electricity_generation = None
                db.session.add(rec)
                changes.append(f"{year} г.: {_log_num(old_val)} → не указано")
                continue

            if rec is not None and old_val is not None and is_same_decimal(to_decimal(old_val), new_val):
                continue

            if rec is None:
                rec = StationEnergyGeneration(
                    id_station=station.id,
                    year_number=year,
                    month_number=STATION_ENERGY_GENERATION_PERIOD_YEAR,
                    electricity_generation=new_val,
                )
                set_db_version_on_create(rec)
                if station_version_id is not None:
                    rec.database_version_id = station_version_id
                db.session.add(rec)
                by_year[year] = rec
                changes.append(f"{year} г.: не указано → {_log_num(new_val)}")
            else:
                rec.electricity_generation = new_val
                db.session.add(rec)
                changes.append(f"{year} г.: {_log_num(old_val)} → {_log_num(new_val)}")

        if not changes:
            return []

        try:
            quick_fix_seq(SCHEMA_ENERGY_BALANCE, "gs_bem_station_energy_generations", "id")
        except Exception:
            pass
        _commit_with_retry()

        rd_name = station.regional_district.name if station.regional_district else "не указано"
        log_to_db(
            user,
            f"Изменения в электростанции {station.name} ({rd_name}), выработка электроэнергии (млн кВт·ч)",
            details="; ".join(changes),
            entity_type="station",
            entity_id=station.id,
        )
        return changes
    except Exception:
        db.session.rollback()
        raise


def save_station_gaes_charge_consumption_service(
    user,
    station: Station,
    station_version_id: int | None,
    start_year: int,
    end_year: int,
    form_data,
) -> list:
    """
    Потребление электрической энергии ГАЭС на заряд по годам (млн кВт·ч).
    """
    from app.common.services.database_version_filter import filter_by_explicit_db_version
    from app.generation.models.station.station_gaes_charge_consumption_model import (
        StationGaesChargeConsumption,
    )
    from app.generation.services.machine_services.machine_services import to_decimal, is_same_decimal

    changes: list[str] = []

    def _log_num(v) -> str:
        if v is None:
            return "не указано"
        try:
            return str(v).replace(".", ",").rstrip("0").rstrip(",") or "0"
        except Exception:
            return str(v).replace(".", ",")

    def _field_changed(raw_value, orig_value) -> bool:
        if orig_value in (None, "", "—", "-"):
            return raw_value not in (None, "", "—", "-")
        return not is_same_decimal(to_decimal(raw_value), to_decimal(orig_value))

    try:
        q = StationGaesChargeConsumption.query.filter(
            StationGaesChargeConsumption.id_station == station.id,
            StationGaesChargeConsumption.year_number >= start_year,
            StationGaesChargeConsumption.year_number <= end_year,
        )
        q = filter_by_explicit_db_version(q, StationGaesChargeConsumption, station_version_id)
        by_year = {r.year_number: r for r in q.all()}

        for year in range(start_year, end_year + 1):
            field = f"st_gaes_charge_{year}"
            raw = form_data.get(field)
            orig_raw = form_data.get(f"{field}_orig")

            if not _field_changed(raw, orig_raw):
                continue

            new_val = to_decimal(raw)
            rec = by_year.get(year)
            old_val = rec.charge_consumption if rec else None

            if new_val is None:
                if rec is None or old_val is None:
                    continue
                rec.charge_consumption = None
                db.session.add(rec)
                changes.append(f"{year} г.: {_log_num(old_val)} → не указано")
                continue

            if rec is not None and old_val is not None and is_same_decimal(to_decimal(old_val), new_val):
                continue

            if rec is None:
                rec = StationGaesChargeConsumption(
                    id_station=station.id,
                    year_number=year,
                    charge_consumption=new_val,
                )
                set_db_version_on_create(rec)
                if station_version_id is not None:
                    rec.database_version_id = station_version_id
                db.session.add(rec)
                by_year[year] = rec
                changes.append(f"{year} г.: не указано → {_log_num(new_val)}")
            else:
                rec.charge_consumption = new_val
                db.session.add(rec)
                changes.append(f"{year} г.: {_log_num(old_val)} → {_log_num(new_val)}")

        if not changes:
            return []

        try:
            quick_fix_seq(SCHEMA_GENERATION, "gs_gen_station_gaes_charge_consumptions", "id")
        except Exception:
            pass
        _commit_with_retry()

        from app.energy_consumption.services.energy_consumption_summary_services import (
            clear_gaes_charge_summary_cache,
        )

        clear_gaes_charge_summary_cache()

        rd_name = station.regional_district.name if station.regional_district else "не указано"
        log_to_db(
            user,
            f"Изменения в электростанции {station.name} ({rd_name}), потребление электроэнергии ГАЭС на заряд (млн кВт·ч)",
            details="; ".join(changes),
            entity_type="station",
            entity_id=station.id,
        )
        from app.energy_consumption.services.energy_consumption_summary_logging import (
            log_gaes_charge_from_station_details,
        )

        log_gaes_charge_from_station_details(
            user,
            station_id=station.id,
            station_name=station.name or "Без названия",
            change_lines=changes,
            database_version_id=station_version_id,
        )
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
            # Полагаться на каскадные связи ORM: дети удаляются автоматически
            changes.append(f"Агрегат {machine.machine_number or '—'} удален")
            db.session.delete(machine)

        for station_id in affected_station_ids:
            remaining_machines = Machine.query.filter_by(id_station=station_id).count()
            if remaining_machines == 0:
                powers_to_delete = StationPower.query.filter_by(id_station=station_id).all()
                for sp in powers_to_delete:
                    db.session.delete(sp)
                changes.append(f"Мощности электростанции ID={station_id} удалены, так как все агрегаты были удалены")

        _commit_with_retry()
        clear_station_aggregation_cache("после удаления агрегатов")  # Очищаем кэш после удаления агрегатов

        if changes:
            log_to_db(user, f"Агрегаты удалены на электростанции {station.name}", details="; ".join(changes), entity_type="station", entity_id=station.id)

        return changes
    except Exception:
        db.session.rollback()
        raise


def update_machines_from_form_service(user, station: Station, form_machines, form_data) -> list:
    import time
    start_time = time.perf_counter()
    
    changes = []
    conflicts = []  # Список конфликтов версий
    
    try:
        if not form_machines.validate():
            return changes

        def _norm_text(v) -> str:
            """Нормализует текст для сравнения: None/пусто/пробелы -> ''."""
            if v is None:
                return ""
            try:
                return str(v).strip()
            except Exception:
                return ""

        # ОПТИМИЗАЦИЯ 1: Предварительно загружаем все GenCompany одним запросом
        # Собираем все уникальные id_gen_company из формы
        gen_company_ids = set()
        for machine in station.machines:
            gen_company_key = f"id_gen_company_{machine.id}"
            try:
                gen_company_id = form_data.get(gen_company_key, type=int) if hasattr(form_data, 'get') else None
                if gen_company_id is None:
                    gen_company_id = int(form_data.get(gen_company_key)) if gen_company_key in form_data else None
                if gen_company_id:
                    gen_company_ids.add(gen_company_id)
            except (ValueError, TypeError):
                pass
        
        # Загружаем все GenCompany одним запросом (batch loading)
        gen_companies_map = {}
        if gen_company_ids:
            gen_companies = db.session.query(GenCompany).filter(GenCompany.id.in_(gen_company_ids)).all()
            gen_companies_map = {gc.id: gc for gc in gen_companies}
            print(f"[OPTIMIZATION] Предзагружено {len(gen_companies_map)} GenCompany одним запросом")

        # ОПТИМИЗАЦИЯ 3: Отключаем autoflush для ускорения массовых изменений
        with db.session.no_autoflush:
            for machine in station.machines:
                fuel_so_key = f"fuel_so_{machine.id}"
                gen_company_key = f"id_gen_company_{machine.id}"
                new_note_key = f"note_{machine.id}"
                version_key = f"machine_version_{machine.id}"

                # Проверка версии для предотвращения concurrent updates
                form_version = None
                if hasattr(form_data, 'get'):
                    form_version = form_data.get(version_key, type=int)
                else:
                    try:
                        form_version = int(form_data.get(version_key)) if version_key in form_data else None
                    except (ValueError, TypeError):
                        form_version = None
                
                if form_version and hasattr(machine, 'version') and machine.version != form_version:
                    conflicts.append(f"Агрегат №{machine.machine_number} (ожидаемая версия: {form_version}, текущая: {machine.version})")
                    log_to_db(
                        user, 
                        f"Конфликт версий при обновлении агрегата №{machine.machine_number} на электростанции {station.name}",
                        details=f"Ожидаемая: {form_version}, текущая: {machine.version}",
                        entity_type="machine",
                        entity_id=machine.id
                    )
                    continue  # Пропускаем этот агрегат
                
                new_fuel_so = (form_data.get(fuel_so_key, "") or "").strip()
                new_gen_company_id = form_data.get(gen_company_key, type=int) if hasattr(form_data, 'get') else None
                if new_gen_company_id is None:
                    try:
                        new_gen_company_id = int(form_data.get(gen_company_key)) if gen_company_key in form_data else None
                    except Exception:
                        new_gen_company_id = None
                new_note = (form_data.get(new_note_key, "") or "").strip()
                
                # Флаг для отслеживания изменений в этом агрегате
                machine_changed = False

                old_fuel_so_norm = _norm_text(getattr(machine, "fuel_so", None))
                new_fuel_so_norm = _norm_text(new_fuel_so)
                # Не логируем "None → ''" и подобные псевдо-изменения
                if old_fuel_so_norm != new_fuel_so_norm:
                    changes.append(
                        f"Агрегат {machine.machine_number}: Топливо {old_fuel_so_norm or 'не указано'} → {new_fuel_so_norm or 'не указано'}"
                    )
                    machine.fuel_so = new_fuel_so
                    machine_changed = True

                old_note_norm = _norm_text(getattr(machine, "note", None))
                new_note_norm = _norm_text(new_note)
                if old_note_norm != new_note_norm:
                    changes.append(
                        f"Агрегат {machine.machine_number}: Примечание {old_note_norm or 'не указано'} → {new_note_norm or 'не указано'}"
                    )
                    machine.note = new_note
                    machine_changed = True

                # ОПТИМИЗАЦИЯ 2: Используем предзагруженный словарь GenCompany
                if new_gen_company_id:
                    new_gen_company = gen_companies_map.get(new_gen_company_id)
                    if new_gen_company:
                        old_gen_company_name = machine.gen_company.name if machine.gen_company else "не указано"
                        if machine.gen_company is None or machine.gen_company.id != new_gen_company_id:
                            changes.append(f"Агрегат {machine.machine_number}: Собственник {old_gen_company_name} → {new_gen_company.name}")
                            machine.gen_company = new_gen_company
                            machine_changed = True
                
                # Обновляем версию агрегата для защиты от concurrent updates
                if machine_changed:
                    from sqlalchemy.sql import func
                    from sqlalchemy.orm.attributes import flag_modified
                    machine.updated_at = func.now()
                    flag_modified(machine, 'updated_at')

        # Если были конфликты версий, показываем ошибку
        if conflicts:
            from flask import flash
            flash(
                f"Обнаружены конфликты версий для агрегатов: {', '.join(conflicts)}. "
                "Данные были изменены другим пользователем. Пожалуйста, обновите страницу.",
                "danger"
            )
            # Не сохраняем изменения при наличии конфликтов
            db.session.rollback()
            return []
        
        _commit_with_retry()
        clear_station_aggregation_cache("после обновления агрегатов")  # Очищаем кэш после обновления агрегатов

        if changes:
            log_to_db(user, f"Обновлены Агрегаты  электростанции {station.name}", details="; ".join(changes), entity_type="station", entity_id=station.id)
        
        # Логируем время выполнения
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        print(f"[PERFORMANCE] update_machines_from_form_service завершена за {elapsed_ms}мс (агрегатов: {len(station.machines)}, изменений: {len(changes)})")
        
        return changes
    except Exception:
        db.session.rollback()
        raise