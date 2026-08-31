# -*- coding: utf-8 -*-
"""Сборка JSON-наборов generation_objects (станция×год) и generation_machines (агрегат×год)."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.common.models.database_version_model import DatabaseVersion
from app.common.services.database_version_filter import get_current_db_version_id
from app.energy_balance.models.station_energy_generation_model import (
    STATION_ENERGY_GENERATION_PERIOD_YEAR,
    StationEnergyGeneration,
)
from app.extensions import db
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.station_power_aggregation import (
    is_machine_archived,
    machine_not_archived_clause,
)
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.years.year_feature_model import YearFeature
from app.refdata.models.years.year_model import Year
from app.refdata.services.year_management_services import get_current_year_info

DATASET_GENERATION_OBJECTS = "generation_objects"
DATASET_GENERATION_MACHINES = "generation_machines"
FACT_YEARS_LIMIT = 5

KEY_STATION_CODE = "external_code"
KEY_STATION_NAME = "Название объекта"
KEY_STATION_TYPE = "Тип станции"
KEY_YEAR = "Год"
KEY_SUBJECT = "Субъект"
KEY_ZONE = "Зона"
KEY_ENERGY_ZONE = "Номер энергозоны (код для оптимизации)"
KEY_CAPACITY = "Установленная мощность, МВт"
KEY_GENERATION = "Производство электроэнергии в году, МВт*ч"
KEY_PLANNED = "Станция является планируемой"

KEY_STATION_CODE_ON_MACHINE = "station_external_code"
KEY_MACHINE_CODE = "external_code"
KEY_MACHINE_NUMBER = "Номер агрегата"
KEY_MACHINE_NAME = "Название агрегата"
KEY_BLOCK_TYPE = "Тип блока"
KEY_FUEL = "Тип топлива"
KEY_EQUIPMENT_GROUP_TYPE = "Тип группы оборудования"
KEY_EQUIPMENT_GROUP_NAME = "Группа оборудования"
KEY_EQUIPMENT_GROUP_CODE = "equipment_group_external_code"
KEY_COMMISSION = "Год ввода в эксплуатацию"
KEY_DECOMMISSION = "Год вывода из эксплуатации"
KEY_ARCHIVED = "Архивный"


def json_number(value: Any) -> int | float | None:
    """Decimal/число в JSON: целое без точки, иначе float; пустое — None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    try:
        dec = value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception:
        return None
    if dec == dec.to_integral_value():
        return int(dec)
    return float(dec)


def generation_mwh(value: Any) -> float:
    """Выработка из БД (млн кВт·ч), в JSON — 3 знака после запятой."""
    if value is None or value == "":
        return 0.0
    try:
        return float(Decimal(str(value)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))
    except Exception:
        return 0.0


def energy_zone_number(raw: Any) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def station_is_planned(condition_name: str | None) -> bool:
    """Устарело: раньше по condition_type; оставлено для совместимости тестов/импорта."""
    return (condition_name or "").strip().casefold().startswith("планир")


def _commission_fact_empty(raw: Any) -> bool:
    return raw is None or str(raw).strip() == ""


def machine_matches_planned_rules(machine: Any, *, current_year: int) -> bool:
    """Ожидаемый год ввода ≥ текущего и фактическая дата ввода в работу пуста."""
    expected = getattr(machine, "date_exploitation_expected", None)
    if expected is None:
        return False
    try:
        expected_year = int(expected)
    except (TypeError, ValueError):
        return False
    if expected_year < int(current_year):
        return False
    return _commission_fact_empty(getattr(machine, "date_commission_fact", None))


def station_is_planned_by_machines(
    machines: Iterable[Any],
    *,
    current_year: int,
) -> bool:
    """
    True, если у станции есть неархивные агрегаты и у каждого из них:
    date_exploitation_expected ≥ текущий год и date_commission_fact пуста.
    Архивные не учитываем. Без активных агрегатов → False.
    """
    if current_year is None or int(current_year) <= 0:
        return False
    active = [m for m in (machines or []) if not is_machine_archived(m)]
    if not active:
        return False
    return all(
        machine_matches_planned_rules(m, current_year=int(current_year)) for m in active
    )


def year_from_fact_date(raw: Any) -> int | None:
    """Год из фактической даты; 01.01.YYYY → YYYY-1, как на карточке агрегата."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    token = text.split(",")[0].strip()
    parts = token.replace("/", ".").replace("-", ".").split(".")
    try:
        if len(parts) == 3 and all(parts):
            if len(parts[0]) == 4:
                year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
            else:
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            if month == 1 and day == 1:
                return year - 1
            return year
        if len(token) == 4 and token.isdigit():
            return int(token)
    except (TypeError, ValueError):
        return None
    return None


def commission_year(
    date_exploitation: int | None,
    date_exploitation_expected: int | None,
) -> int | None:
    if date_exploitation is not None:
        return int(date_exploitation)
    if date_exploitation_expected is not None:
        return int(date_exploitation_expected)
    return None


def decommission_year(
    date_decompressing_expected: int | None,
    date_decompressing_fact: Any = None,
) -> int | None:
    fact_year = year_from_fact_date(date_decompressing_fact)
    if fact_year is not None:
        return fact_year
    if date_decompressing_expected is not None:
        return int(date_decompressing_expected)
    return None


def block_type_name(tes_type_name: str | None, machine_type_name: str | None) -> str | None:
    tes = (tes_type_name or "").strip()
    if tes:
        return tes
    generic = (machine_type_name or "").strip()
    return generic or None


def fuel_type_name(fuel_type: str | None, fuel_name: str | None) -> str | None:
    typed = (fuel_type or "").strip()
    if typed:
        return typed
    named = (fuel_name or "").strip()
    return named or None


def select_exchange_years(year_rows: Iterable[tuple[Any, Any]]) -> list[int]:
    """5 последних фактических + текущий (оценка) + все плановые; иначе все годы."""
    fact: list[int] = []
    current: list[int] = []
    plan: list[int] = []
    all_years: list[int] = []
    seen: set[int] = set()
    for number, feature_name in year_rows:
        if number is None:
            continue
        year = int(number)
        if year not in seen:
            all_years.append(year)
            seen.add(year)
        label = (feature_name or "").strip().casefold()
        if "факт" in label:
            fact.append(year)
        elif "текущ" in label:
            current.append(year)
        elif "план" in label:
            plan.append(year)
    if not fact and not current and not plan:
        return sorted(all_years)
    fact_keep = sorted(set(fact))[-FACT_YEARS_LIMIT:]
    return sorted(set(fact_keep) | set(current) | set(plan))


def clip_years(
    years: Iterable[int],
    *,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> list[int]:
    selected = sorted({int(y) for y in years})
    if year is not None:
        return [int(year)]
    if start_year is not None:
        selected = [y for y in selected if y >= int(start_year)]
    if end_year is not None:
        selected = [y for y in selected if y <= int(end_year)]
    return selected


def dataset_envelope(
    dataset: str,
    *,
    database_version: int | None,
    rows: list[dict[str, Any]],
    comment: str = "",
    version_number: str | None = None,
) -> dict[str, Any]:
    """Оболочка набора: срез всегда привязан к версии БД АРМ.

    ``database_version`` — PK ``gs_sys.gs_database_versions.id`` (числовой id версии).
    ``version_number`` — человекочитаемый номер (например «ГС 2023-2042 (утвержденная)»).
    ``version`` — то же значение, что ``database_version``; это не ISO-дата.
    """
    label = version_number
    if label is None and database_version is not None:
        row = db.session.get(DatabaseVersion, int(database_version))
        label = row.version_number if row is not None else None
    return {
        "dataset": dataset,
        "database_version": database_version,
        "version_number": label or "",
        "version": database_version,
        "comment": comment,
        "rows": rows,
    }


def build_station_year_row(
    *,
    external_code: str | None,
    name: str | None,
    station_type: str | None,
    year: int,
    subject: str | None,
    zone: str | None,
    energy_zone: Any,
    capacity: Any,
    generation: Any,
    planned: bool,
) -> dict[str, Any]:
    return {
        KEY_STATION_CODE: external_code,
        KEY_STATION_NAME: name,
        KEY_STATION_TYPE: station_type,
        KEY_YEAR: int(year),
        KEY_SUBJECT: subject,
        KEY_ZONE: zone,
        KEY_ENERGY_ZONE: energy_zone_number(energy_zone),
        KEY_CAPACITY: json_number(capacity) or 0,
        KEY_GENERATION: generation_mwh(generation),
        KEY_PLANNED: bool(planned),
    }


def build_machine_year_row(
    *,
    station_external_code: str | None,
    external_code: str | None,
    year: int,
    machine_number: str | None,
    machine_name: str | None,
    block_type: str | None,
    capacity: Any,
    fuel: str | None,
    equipment_group_type: str | None,
    equipment_group_name: str | None,
    equipment_group_external_code: str | None,
    commission: int | None,
    decommission: int | None,
    archived: bool,
) -> dict[str, Any]:
    return {
        KEY_STATION_CODE_ON_MACHINE: station_external_code,
        KEY_MACHINE_CODE: external_code,
        KEY_YEAR: int(year),
        KEY_MACHINE_NUMBER: machine_number,
        KEY_MACHINE_NAME: machine_name,
        KEY_BLOCK_TYPE: block_type,
        KEY_CAPACITY: json_number(capacity) or 0,
        KEY_FUEL: fuel or "",
        KEY_EQUIPMENT_GROUP_TYPE: equipment_group_type or "",
        KEY_EQUIPMENT_GROUP_NAME: equipment_group_name or "",
        KEY_EQUIPMENT_GROUP_CODE: equipment_group_external_code or "",
        KEY_COMMISSION: commission,
        KEY_DECOMMISSION: decommission,
        KEY_ARCHIVED: bool(archived),
    }


def _version_filter(model, version_id: int | None):
    if version_id is None:
        return model.database_version_id.is_(None)
    return model.database_version_id == int(version_id)


def resolve_database_version(version_id: int | None) -> tuple[int | None, str | None]:
    vid = int(version_id) if version_id is not None else get_current_db_version_id()
    if vid is None:
        return None, None
    row = db.session.get(DatabaseVersion, vid)
    if row is None:
        return None, None
    return row.id, row.version_number


def load_exchange_years(version_id: int | None) -> list[int]:
    query = (
        db.session.query(Year.number, YearFeature.name)
        .outerjoin(YearFeature, Year.id_year_feature == YearFeature.id)
        .filter(_version_filter(Year, version_id))
        .order_by(Year.number.asc())
    )
    return select_exchange_years(query.all())


def _load_stations(version_id: int | None) -> list[Station]:
    return (
        db.session.query(Station)
        .options(
            joinedload(Station.station_type),
            joinedload(Station.condition_type),
            joinedload(Station.regional_district).joinedload(RegionalDistrict.synchronous_area),
            joinedload(Station.regional_district).joinedload(RegionalDistrict.energy_zone),
        )
        .filter(_version_filter(Station, version_id))
        .order_by(Station.name.asc(), Station.id.asc())
        .all()
    )


def _load_station_capacity_map(
    station_ids: list[int],
    years: list[int],
    version_id: int | None,
) -> dict[tuple[int, int], Decimal]:
    if not station_ids or not years:
        return {}
    query = (
        db.session.query(
            Machine.id_station,
            MachinePower.year_number,
            func.coalesce(func.sum(MachinePower.p_ust), 0).label("p_ust"),
        )
        .join(Machine, MachinePower.id_machine == Machine.id)
        .filter(Machine.id_station.in_(station_ids))
        .filter(machine_not_archived_clause())
        .filter(MachinePower.year_number.in_(years))
        .filter(_version_filter(Machine, version_id))
        .filter(_version_filter(MachinePower, version_id))
        .group_by(Machine.id_station, MachinePower.year_number)
    )
    result: dict[tuple[int, int], Decimal] = {}
    for station_id, year_number, p_ust in query.all():
        result[(int(station_id), int(year_number))] = Decimal(str(p_ust or 0))
    return result


def _load_station_generation_map(
    station_ids: list[int],
    years: list[int],
    version_id: int | None,
) -> dict[tuple[int, int], Decimal]:
    if not station_ids or not years:
        return {}
    query = (
        db.session.query(
            StationEnergyGeneration.id_station,
            StationEnergyGeneration.year_number,
            StationEnergyGeneration.electricity_generation,
        )
        .filter(StationEnergyGeneration.id_station.in_(station_ids))
        .filter(StationEnergyGeneration.year_number.in_(years))
        .filter(
            StationEnergyGeneration.month_number == STATION_ENERGY_GENERATION_PERIOD_YEAR
        )
        .filter(_version_filter(StationEnergyGeneration, version_id))
    )
    result: dict[tuple[int, int], Decimal] = {}
    for station_id, year_number, value in query.all():
        if station_id is None or year_number is None:
            continue
        result[(int(station_id), int(year_number))] = Decimal(str(value or 0))
    return result


def _load_station_planned_map(
    station_ids: list[int],
    version_id: int | None,
    current_year: int,
) -> dict[int, bool]:
    """station_id → «все неархивные агрегаты планируемые»."""
    result = {int(sid): False for sid in station_ids}
    if not station_ids or current_year <= 0:
        return result
    rows = (
        db.session.query(
            Machine.id_station,
            Machine.date_exploitation_expected,
            Machine.date_commission_fact,
            Machine.is_archived,
        )
        .filter(Machine.id_station.in_(station_ids))
        .filter(_version_filter(Machine, version_id))
        .all()
    )
    by_station: dict[int, list[Any]] = {int(sid): [] for sid in station_ids}
    for station_id, expected, fact, archived in rows:
        if station_id is None:
            continue
        sid = int(station_id)
        by_station.setdefault(sid, []).append(
            type(
                "_M",
                (),
                {
                    "date_exploitation_expected": expected,
                    "date_commission_fact": fact,
                    "is_archived": archived,
                },
            )()
        )
    for sid, machines in by_station.items():
        result[sid] = station_is_planned_by_machines(
            machines, current_year=current_year
        )
    return result


def build_generation_objects_rows(
    stations: Iterable[Station],
    years: list[int],
    capacity_map: dict[tuple[int, int], Decimal],
    generation_map: dict[tuple[int, int], Decimal],
    planned_by_station: dict[int, bool] | None = None,
) -> list[dict[str, Any]]:
    """Станция × год; без мощности и выработки в году — строку не отдаём."""
    planned_map = planned_by_station or {}
    rows: list[dict[str, Any]] = []
    for station in stations:
        district = getattr(station, "regional_district", None)
        zone = getattr(district, "synchronous_area", None) if district else None
        energy_zone = getattr(district, "energy_zone", None) if district else None
        planned = bool(planned_map.get(int(station.id), False))
        for year in years:
            capacity = capacity_map.get((station.id, year))
            generation = generation_map.get((station.id, year))
            cap_n = json_number(capacity) or 0
            gen_n = json_number(generation) or 0
            if cap_n == 0 and gen_n == 0:
                continue
            rows.append(
                build_station_year_row(
                    external_code=station.external_code,
                    name=station.name,
                    station_type=getattr(getattr(station, "station_type", None), "name", None),
                    year=year,
                    subject=getattr(district, "name", None) if district else None,
                    zone=getattr(zone, "name", None) if zone else None,
                    energy_zone=getattr(energy_zone, "number", None) if energy_zone else None,
                    capacity=capacity,
                    generation=generation,
                    planned=planned,
                )
            )
    return rows


def load_generation_objects_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    resolved_id, version_number = resolve_database_version(version_id)
    years = clip_years(
        load_exchange_years(resolved_id),
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
    stations = _load_stations(resolved_id)
    station_ids = [s.id for s in stations]
    try:
        current_year = int(
            (get_current_year_info(resolved_id) or {}).get("current_year") or 0
        )
    except (TypeError, ValueError):
        current_year = 0
    rows = build_generation_objects_rows(
        stations,
        years,
        _load_station_capacity_map(station_ids, years, resolved_id),
        _load_station_generation_map(station_ids, years, resolved_id),
        planned_by_station=_load_station_planned_map(
            station_ids, resolved_id, current_year
        ),
    )
    return dataset_envelope(
        DATASET_GENERATION_OBJECTS,
        database_version=resolved_id,
        version_number=version_number,
        rows=rows,
    )


def _load_machines(version_id: int | None) -> list[Machine]:
    return (
        db.session.query(Machine)
        .options(
            joinedload(Machine.machine_station),
            joinedload(Machine.tes_machine_type),
            joinedload(Machine.machine_type),
            joinedload(Machine.equipment_group),
            joinedload(Machine.machine_fuel_param).joinedload(MachineFuelParam.equipment_group),
        )
        .filter(_version_filter(Machine, version_id))
        .order_by(Machine.id_station.asc(), Machine.machine_number.asc(), Machine.id.asc())
        .all()
    )


def _load_machine_capacity_map(
    machine_ids: list[int],
    years: list[int],
    version_id: int | None,
) -> dict[tuple[int, int], Decimal]:
    if not machine_ids or not years:
        return {}
    query = (
        db.session.query(
            MachinePower.id_machine,
            MachinePower.year_number,
            func.coalesce(func.sum(MachinePower.p_ust), 0).label("p_ust"),
        )
        .filter(MachinePower.id_machine.in_(machine_ids))
        .filter(MachinePower.year_number.in_(years))
        .filter(_version_filter(MachinePower, version_id))
        .group_by(MachinePower.id_machine, MachinePower.year_number)
    )
    result: dict[tuple[int, int], Decimal] = {}
    for machine_id, year_number, p_ust in query.all():
        result[(int(machine_id), int(year_number))] = Decimal(str(p_ust or 0))
    return result


def _load_machine_fuel_map(
    machine_ids: list[int],
    years: list[int],
    version_id: int | None,
) -> dict[tuple[int, int], str]:
    if not machine_ids or not years:
        return {}
    query = (
        db.session.query(
            MachineFuel.id_machine,
            MachineFuel.year_number,
            FuelType.name,
            Fuel.name,
        )
        .outerjoin(Fuel, Fuel.id == MachineFuel.id_fuel)
        .outerjoin(FuelType, FuelType.id == Fuel.id_fuel_type)
        .filter(MachineFuel.id_machine.in_(machine_ids))
        .filter(MachineFuel.year_number.in_(years))
        .filter(_version_filter(MachineFuel, version_id))
    )
    result: dict[tuple[int, int], str] = {}
    for machine_id, year_number, type_name, fuel_name in query.all():
        label = fuel_type_name(type_name, fuel_name)
        if label:
            result[(int(machine_id), int(year_number))] = label
    return result


def build_generation_machines_rows(
    machines: Iterable[Machine],
    years: list[int],
    capacity_map: dict[tuple[int, int], Decimal],
    fuel_map: dict[tuple[int, int], str],
) -> list[dict[str, Any]]:
    """Агрегат × год; без Руст в году — строку не отдаём."""
    rows: list[dict[str, Any]] = []
    for machine in machines:
        station = getattr(machine, "machine_station", None)
        block_type = block_type_name(
            getattr(getattr(machine, "tes_machine_type", None), "name", None),
            getattr(getattr(machine, "machine_type", None), "name", None),
        )
        in_year = commission_year(machine.date_exploitation, machine.date_exploitation_expected)
        out_year = decommission_year(
            machine.date_decompressing_expected,
            machine.date_decompressing_fact,
        )
        archived = bool(getattr(machine, "is_archived", False))
        eg_type = getattr(getattr(machine, "equipment_group", None), "name", None)
        fuel_group = getattr(getattr(machine, "machine_fuel_param", None), "equipment_group", None)
        for year in years:
            capacity = capacity_map.get((machine.id, year))
            if (json_number(capacity) or 0) == 0:
                continue
            rows.append(
                build_machine_year_row(
                    station_external_code=getattr(station, "external_code", None) if station else None,
                    external_code=machine.external_code,
                    year=year,
                    machine_number=machine.machine_number,
                    machine_name=machine.machine_name,
                    block_type=block_type,
                    capacity=capacity,
                    fuel=fuel_map.get((machine.id, year)),
                    equipment_group_type=eg_type,
                    equipment_group_name=getattr(fuel_group, "name", None) if fuel_group else None,
                    equipment_group_external_code=(
                        getattr(fuel_group, "external_code", None) if fuel_group else None
                    ),
                    commission=in_year,
                    decommission=out_year,
                    archived=archived,
                )
            )
    return rows


def load_generation_machines_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
) -> dict[str, Any]:
    resolved_id, version_number = resolve_database_version(version_id)
    years = clip_years(
        load_exchange_years(resolved_id),
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
    machines = _load_machines(resolved_id)
    machine_ids = [m.id for m in machines]
    rows = build_generation_machines_rows(
        machines,
        years,
        _load_machine_capacity_map(machine_ids, years, resolved_id),
        _load_machine_fuel_map(machine_ids, years, resolved_id),
    )
    return dataset_envelope(
        DATASET_GENERATION_MACHINES,
        database_version=resolved_id,
        version_number=version_number,
        rows=rows,
    )


def list_exchange_datasets() -> dict[str, Any]:
    """Совместимость: канон — app.api.services.exchange_api_services."""
    from app.api.services.exchange_api_services import (
        list_exchange_datasets as _list,
    )

    return _list()
