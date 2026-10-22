# -*- coding: utf-8 -*-
"""Сборка JSON-наборов generation_stations (станция×год) и generation_machines (агрегат×год)."""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Iterable

from sqlalchemy import func
from sqlalchemy.orm import joinedload

from app.api.services.exchange_common_services import (
    clip_years,
    dataset_envelope,
    exchange_years_bounds,
    load_exchange_years,
    resolve_database_version,
    version_filter as _version_filter,
)
from app.energy_balance.models.station_energy_generation_model import (
    STATION_ENERGY_GENERATION_PERIOD_YEAR,
    StationEnergyGeneration,
)
from app.extensions import db
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.generation.services.station_services.station_power_aggregation import (
    is_machine_archived,
    load_stations_powers_by_year,
    machine_not_archived_clause,
)
from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.fuels.fuel_model import Fuel
from app.refdata.models.fuels.fuel_type_model import FuelType
from app.refdata.models.territories.regional_district_model import RegionalDistrict

DATASET_GENERATION_STATIONS = "generation_stations"
DATASET_GENERATION_OBJECTS = DATASET_GENERATION_STATIONS  # совместимость импорта
DATASET_GENERATION_MACHINES = "generation_machines"

KEY_STATION_CODE = "external_code"
KEY_STATION_NAME = "Название станции"
KEY_STATION_TYPE = "Тип станции"
KEY_YEAR = "Год"
KEY_SUBJECT = "Субъект станции"
KEY_ZONE = "Зона станции"
KEY_OES = "ОЭС"
KEY_ENERGY_ZONE = "Номер энергозоны (код для оптимизации)"
KEY_CAPACITY = "Установленная мощность, МВт"
KEY_GENERATION = "Производство электроэнергии в году, МВт*ч"
KEY_PLANNED = "Станция является планируемой"

KEY_MACHINE_CODE = "external_code"
KEY_STATION_CODE_ON_MACHINE = "station_external_code"
KEY_MACHINE_NAME = "Название агрегата"
KEY_MACHINE_NUMBER = "Станционный номер"
KEY_MACHINE_STATION_TYPE = "Тип станции агрегата"
KEY_MACHINE_CAPACITY = "Установленная мощность агрегата, МВт"
KEY_FUEL = "Тип топлива"
KEY_MACHINE_SUBJECT = "Субъект агрегата"
KEY_MACHINE_ZONE = "Зона агрегата"
KEY_MACHINE_GENERATION = "Производство агрегатом электроэнергии в году, МВт*ч"
KEY_MACHINE_TYPE = "Тип агрегата"
KEY_MACHINE_PLANNED = "Блок является планируемым"
KEY_ASH = "твердые частицы (зола), млн т"
KEY_SO2 = "диоксид серы (SO2), млн т"
KEY_NOX = "оксиды азота (NOx), млн т"
KEY_CO2 = "диоксид углерода (CO2), млн т"
KEY_DECOMMISSION = "Год вывода из эксплуатации"
KEY_COMMISSION_FACT_DATE = "Дата ввода блока (фактическая)"
KEY_DECOMMISSION_DATE = "Дата вывода блока"
KEY_MODERNIZATION_DATE = "Дата модернизации блока"
KEY_MODERNIZATION_ADVISABLE = "Модернизация целесообразна"
MISSING_DATE = "-"
GENERATION_MACHINES_COMMENT = (
    "Поля «твердые частицы (зола), млн т», «диоксид серы (SO2), млн т», "
    "«оксиды азота (NOx), млн т», «диоксид углерода (CO2), млн т» пока всегда 0: "
    "данных по выбросам в разрезе агрегата нет.\n\n"
    "Поле «Производство агрегатом электроэнергии в году, МВт*ч» всегда 0: "
    "выработки по агрегату в АРМ нет, есть только по станции в целом (generation_stations).\n\n"
    "Поле «Модернизация целесообразна» всегда false: такого признака в АРМ нет; "
    "на карточке агрегата есть «Ожидаемый год модернизации с изменением мощности» "
    "и «Ожидаемый год модернизации без изменения мощности» "
    "(в JSON – «Дата модернизации блока»).\n\n"
    "Поле station_external_code добавлено для связи со станцией "
    "(тот же код, что external_code в generation_stations).\n\n"
    "Поле «Станционный номер» – «Номер агрегата» с карточки агрегата.\n\n"
    "14.10.2026 - добавлено поле \"Станционный номер\""
)


def json_number(value: Any) -> int | float | None:
    """Decimal/число в JSON: целое без точки, иначе float; пустое – None."""
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


def _quantize_number(value: Any, quant: str) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(
            Decimal(str(value)).quantize(Decimal(quant), rounding=ROUND_HALF_UP)
        )
    except Exception:
        return 0.0


def generation_mwh(value: Any) -> float:
    """Выработка из БД (млн кВт·ч), в JSON – 3 знака после запятой."""
    return _quantize_number(value, "0.001")


def capacity_mw(value: Any) -> float:
    """Установленная мощность, МВт – 6 знаков после запятой (как в БД)."""
    return _quantize_number(value, "0.000001")


def energy_zone_number(raw: Any) -> int | None:
    """Номер энергозоны в JSON: целое; «не указано» и пустое – null."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.casefold() == "не указано":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def station_page_name(station: Any) -> str:
    """Название как на карточке станции: name, иначе name_combined / name_so."""
    for attr in ("name", "name_combined", "name_so"):
        val = (getattr(station, attr, None) or "").strip()
        if val:
            return val
    return ""


def station_page_subject(station: Any) -> str | None:
    """Субъект РФ – как поле «Субъект РФ» на карточке."""
    district = getattr(station, "regional_district", None)
    name = (getattr(district, "name", None) or "").strip() if district else ""
    if name:
        return name
    energy_unit = getattr(station, "energy_unit", None)
    eu_district = getattr(energy_unit, "regional_district", None) if energy_unit else None
    eu_name = (getattr(eu_district, "name", None) or "").strip() if eu_district else ""
    return eu_name or None


def _district_synchronous_area_full_name(district: Any) -> str | None:
    """Полное наименование синхронной зоны субъекта РФ (name_full, иначе name)."""
    sa = getattr(district, "synchronous_area", None) if district else None
    if sa is None:
        return None
    full = (getattr(sa, "name_full", None) or "").strip()
    if full:
        return full
    short = (getattr(sa, "name", None) or "").strip()
    return short or None


def station_page_zone(station: Any) -> str | None:
    """Зона станции – синхронная зона субъекта РФ с карточки станции."""
    district = getattr(station, "regional_district", None)
    name = _district_synchronous_area_full_name(district)
    if name:
        return name
    energy_unit = getattr(station, "energy_unit", None)
    eu_district = getattr(energy_unit, "regional_district", None) if energy_unit else None
    return _district_synchronous_area_full_name(eu_district)


def station_page_oes(station: Any) -> str | None:
    """ОЭС/ТИТЭС – как поле «ОЭС» на карточке станции (например «ТИТЭС Сибири»)."""
    # Station.union_energy_system – property; у SimpleNamespace в тестах может быть строка.
    direct = getattr(station, "union_energy_system", None)
    if isinstance(direct, str):
        text = direct.strip()
        return text or None
    res = getattr(station, "regional_energy_system_obj", None)
    ues = getattr(res, "union_energy_system", None) if res else None
    name = (getattr(ues, "name", None) or "").strip() if ues else ""
    if name:
        return name
    district = getattr(station, "regional_district", None)
    systems = getattr(district, "regional_energy_systems", None) if district else None
    if not systems:
        return None
    names = sorted(
        {
            (getattr(getattr(item, "union_energy_system", None), "name", None) or "").strip()
            for item in systems
            if getattr(item, "union_energy_system", None) is not None
        }
        - {""}
    )
    return ", ".join(names) if names else None


def _district_energy_zone_number(district: Any) -> Any:
    """Номер энергозоны субъекта РФ (справочник /refdata/regional_district)."""
    energy_zone = getattr(district, "energy_zone", None) if district else None
    if energy_zone is None:
        return None
    return getattr(energy_zone, "number", None)


def station_page_energy_zone(station: Any) -> Any:
    """Номер энергозоны – как у субъекта РФ на карточке станции."""
    district = getattr(station, "regional_district", None)
    number = _district_energy_zone_number(district)
    if number is not None and str(number).strip():
        return number
    energy_unit = getattr(station, "energy_unit", None)
    eu_district = getattr(energy_unit, "regional_district", None) if energy_unit else None
    return _district_energy_zone_number(eu_district)


def station_is_planned_for_year(capacity_by_year: dict[int, Any], year: int) -> bool:
    """
    True, если сумма Руст неархивных агрегатов в году = 0,
    а в каком-либо более позднем году эта сумма > 0.
    """
    now = json_number(capacity_by_year.get(int(year))) or 0
    if now != 0:
        return False
    return any(
        (json_number(cap) or 0) > 0
        for later_year, cap in capacity_by_year.items()
        if int(later_year) > int(year)
    )


def station_is_planned(condition_name: str | None) -> bool:
    """Устарело: раньше по condition_type; оставлено для совместимости тестов/импорта."""
    return (condition_name or "").strip().casefold().startswith("планир")


def json_date_or_dash(raw: Any) -> str:
    """Дата как в макете: строка дд.мм.гггг или «-»."""
    if raw is None:
        return MISSING_DATE
    text = str(raw).strip()
    return text if text else MISSING_DATE


def json_year_as_date(raw: Any) -> str:
    """Год → 01.01.ГГГГ; уже дата – как есть; пусто – «-»."""
    if raw is None or raw == "":
        return MISSING_DATE
    if isinstance(raw, int):
        return f"01.01.{raw}"
    text = str(raw).strip()
    if not text:
        return MISSING_DATE
    if text.isdigit() and len(text) == 4:
        return f"01.01.{text}"
    return text


def machine_page_number(machine: Any) -> str | None:
    """Станционный номер – «Номер агрегата» с карточки; пусто – None."""
    number = getattr(machine, "machine_number", None)
    if number is None:
        return None
    text = str(number).strip()
    return text or None


def machine_page_name(machine: Any) -> str:
    """Название как на карточке агрегата: machine_name."""
    name = (getattr(machine, "machine_name", None) or "").strip()
    if name:
        return name
    number = getattr(machine, "machine_number", None)
    station = getattr(machine, "machine_station", None)
    station_name = station_page_name(station) if station else ""
    parts: list[str] = []
    if number not in (None, ""):
        parts.append(str(number).strip())
    if station_name:
        parts.append(station_name)
    return ". ".join(p for p in parts if p)


def machine_modernization_date(machine: Any) -> str:
    for attr in (
        "date_modernization_power_change_expected",
        "date_modernization_no_power_change_expected",
        "year_modern",
    ):
        formatted = json_year_as_date(getattr(machine, attr, None))
        if formatted != MISSING_DATE:
            return formatted
    return MISSING_DATE


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


def build_station_year_row(
    *,
    external_code: str | None,
    name: str | None,
    station_type: str | None,
    year: int,
    subject: str | None,
    zone: str | None,
    oes: str | None,
    energy_zone: Any,
    capacity: Any,
    generation: Any,
    planned: bool,
    preserve_generation_precision: bool = False,
) -> dict[str, Any]:
    return {
        KEY_YEAR: int(year),
        KEY_ZONE: zone,
        KEY_OES: oes,
        KEY_STATION_CODE: external_code,
        KEY_SUBJECT: subject,
        KEY_STATION_TYPE: station_type,
        KEY_STATION_NAME: name,
        KEY_CAPACITY: json_number(capacity_mw(capacity)) or 0,
        KEY_PLANNED: bool(planned),
        KEY_ENERGY_ZONE: energy_zone_number(energy_zone),
        KEY_GENERATION: (
            generation if generation is not None else Decimal("0")
        )
        if preserve_generation_precision
        else json_number(generation_mwh(generation)) or 0,
    }


def build_machine_year_row(
    *,
    name: str | None,
    number: str | None,
    station_type: str | None,
    capacity: Any,
    fuel: str | None,
    year: int,
    subject: str | None,
    zone: str | None,
    machine_type: str | None,
    planned: bool,
    decommission: int | None,
    energy_zone: Any,
    commission_fact_date: str | None,
    decommission_date: str | None,
    modernization_date: str | None,
    external_code: str | None,
    station_external_code: str | None,
) -> dict[str, Any]:
    return {
        KEY_MACHINE_NAME: name,
        KEY_MACHINE_NUMBER: number,
        KEY_MACHINE_STATION_TYPE: station_type,
        KEY_MACHINE_CAPACITY: capacity_mw(capacity),
        KEY_FUEL: fuel or "",
        KEY_YEAR: int(year),
        KEY_MACHINE_SUBJECT: subject,
        KEY_MACHINE_ZONE: zone,
        KEY_MACHINE_GENERATION: 0.0,
        KEY_MACHINE_TYPE: machine_type,
        KEY_MACHINE_PLANNED: bool(planned),
        KEY_ASH: 0.0,
        KEY_SO2: 0.0,
        KEY_NOX: 0.0,
        KEY_CO2: 0.0,
        KEY_DECOMMISSION: decommission,
        KEY_ENERGY_ZONE: energy_zone_number(energy_zone),
        KEY_COMMISSION_FACT_DATE: json_date_or_dash(commission_fact_date),
        KEY_DECOMMISSION_DATE: json_date_or_dash(decommission_date),
        KEY_MODERNIZATION_DATE: json_date_or_dash(modernization_date),
        KEY_MODERNIZATION_ADVISABLE: False,
        KEY_MACHINE_CODE: external_code,
        KEY_STATION_CODE_ON_MACHINE: station_external_code,
    }


def _load_stations(version_id: int | None) -> list[Station]:
    return (
        db.session.query(Station)
        .options(
            joinedload(Station.station_type),
            joinedload(Station.condition_type),
            joinedload(Station.regional_district).joinedload(RegionalDistrict.synchronous_area),
            joinedload(Station.regional_district).joinedload(RegionalDistrict.energy_zone),
            joinedload(Station.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
            .joinedload(RegionalEnergySystem.union_energy_system)
            .joinedload(UnionEnergySystem.energy_system_type),
            joinedload(Station.regional_energy_system_obj)
            .joinedload(RegionalEnergySystem.union_energy_system)
            .joinedload(UnionEnergySystem.energy_system_type),
            joinedload(Station.energy_unit)
            .joinedload(EnergyUnit.regional_district)
            .joinedload(RegionalDistrict.synchronous_area),
            joinedload(Station.energy_unit)
            .joinedload(EnergyUnit.regional_district)
            .joinedload(RegionalDistrict.energy_zone),
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
    """Сумма p_ust неархивных агрегатов по станции и году – как на карточке станции."""
    nested = load_stations_powers_by_year(station_ids, years, version_id)
    result: dict[tuple[int, int], Decimal] = {}
    for station_id, by_year in nested.items():
        for year_number, values in by_year.items():
            result[(int(station_id), int(year_number))] = values.get(
                "p_ust", Decimal("0")
            )
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


def _capacity_by_station(
    capacity_map: dict[tuple[int, int], Decimal],
) -> dict[int, dict[int, Decimal]]:
    by_station: dict[int, dict[int, Decimal]] = {}
    for (station_id, year), capacity in capacity_map.items():
        by_station.setdefault(int(station_id), {})[int(year)] = capacity
    return by_station


def build_generation_objects_rows(
    stations: Iterable[Station],
    years: list[int],
    capacity_map: dict[tuple[int, int], Decimal],
    generation_map: dict[tuple[int, int], Decimal],
    *,
    preserve_generation_precision: bool = False,
) -> list[dict[str, Any]]:
    """Станция × год. Планируемая: Руст года = 0, а в будущем году Руст > 0.

    Строка собирается с карточки электростанции: название, тип, субъект РФ;
    зона и номер энергозоны – по субъекту РФ карточки. Станции без названия
    на карточке в набор не входят.
    """
    caps_by_station = _capacity_by_station(capacity_map)
    rows: list[dict[str, Any]] = []
    for station in stations:
        name = station_page_name(station)
        if not name:
            continue
        station_type = getattr(getattr(station, "station_type", None), "name", None)
        subject = station_page_subject(station)
        zone = station_page_zone(station)
        oes = station_page_oes(station)
        energy_zone = station_page_energy_zone(station)
        station_caps = caps_by_station.get(int(station.id), {})
        for year in years:
            capacity = station_caps.get(int(year))
            generation = generation_map.get((station.id, year))
            cap_n = json_number(capacity) or 0
            gen_n = json_number(generation) or 0
            planned = station_is_planned_for_year(station_caps, year)
            if cap_n == 0 and gen_n == 0 and not planned:
                continue
            rows.append(
                build_station_year_row(
                    external_code=station.external_code,
                    name=name,
                    station_type=station_type,
                    year=year,
                    subject=subject,
                    zone=zone,
                    oes=oes,
                    energy_zone=energy_zone,
                    capacity=capacity,
                    generation=generation,
                    planned=planned,
                    preserve_generation_precision=preserve_generation_precision,
                )
            )
    return rows


def load_generation_objects_dataset(
    *,
    version_id: int | None = None,
    year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    preserve_generation_precision: bool = False,
) -> dict[str, Any]:
    resolved_id, version_number = resolve_database_version(version_id)
    all_years = load_exchange_years(resolved_id)
    years = clip_years(
        all_years,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
    stations = _load_stations(resolved_id)
    station_ids = [s.id for s in stations]
    rows = build_generation_objects_rows(
        stations,
        years,
        _load_station_capacity_map(station_ids, all_years, resolved_id),
        _load_station_generation_map(station_ids, years, resolved_id),
        preserve_generation_precision=preserve_generation_precision,
    )
    return dataset_envelope(
        DATASET_GENERATION_STATIONS,
        database_version=resolved_id,
        version_number=version_number,
        rows=rows,
    )


load_generation_stations_dataset = load_generation_objects_dataset


def _load_machines(version_id: int | None) -> list[Machine]:
    station = joinedload(Machine.machine_station)
    return (
        db.session.query(Machine)
        .options(
            station.joinedload(Station.station_type),
            station.joinedload(Station.regional_district).joinedload(
                RegionalDistrict.synchronous_area
            ),
            station.joinedload(Station.regional_district).joinedload(
                RegionalDistrict.energy_zone
            ),
            station.joinedload(Station.regional_district)
            .joinedload(RegionalDistrict.regional_energy_systems)
            .joinedload(RegionalEnergySystem.union_energy_system)
            .joinedload(UnionEnergySystem.energy_system_type),
            station.joinedload(Station.regional_energy_system_obj)
            .joinedload(RegionalEnergySystem.union_energy_system)
            .joinedload(UnionEnergySystem.energy_system_type),
            station.joinedload(Station.energy_unit)
            .joinedload(EnergyUnit.regional_district)
            .joinedload(RegionalDistrict.synchronous_area),
            station.joinedload(Station.energy_unit)
            .joinedload(EnergyUnit.regional_district)
            .joinedload(RegionalDistrict.energy_zone),
            joinedload(Machine.tes_machine_type),
            joinedload(Machine.machine_type),
        )
        .filter(_version_filter(Machine, version_id))
        .filter(machine_not_archived_clause())
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
    """Агрегат × год. Планируемый: Руст года = 0, а в будущем году Руст > 0."""
    caps_by_machine = _capacity_by_station(capacity_map)
    rows: list[dict[str, Any]] = []
    for machine in machines:
        if is_machine_archived(machine):
            continue
        station = getattr(machine, "machine_station", None)
        machine_caps = caps_by_machine.get(int(machine.id), {})
        machine_type = block_type_name(
            getattr(getattr(machine, "tes_machine_type", None), "name", None),
            getattr(getattr(machine, "machine_type", None), "name", None),
        )
        out_year = decommission_year(
            machine.date_decompressing_expected,
            machine.date_decompressing_fact,
        )
        station_type = getattr(getattr(station, "station_type", None), "name", None) if station else None
        for year in years:
            capacity = machine_caps.get(int(year))
            cap_n = json_number(capacity) or 0
            planned = station_is_planned_for_year(machine_caps, year)
            if cap_n == 0 and not planned:
                continue
            rows.append(
                build_machine_year_row(
                    name=machine_page_name(machine),
                    number=machine_page_number(machine),
                    station_type=station_type,
                    capacity=capacity,
                    fuel=fuel_map.get((machine.id, year)),
                    year=year,
                    subject=station_page_subject(station) if station else None,
                    zone=station_page_zone(station) if station else None,
                    machine_type=machine_type,
                    planned=planned,
                    decommission=out_year,
                    energy_zone=station_page_energy_zone(station) if station else None,
                    commission_fact_date=getattr(machine, "date_commission_fact", None),
                    decommission_date=getattr(machine, "date_decompressing_fact", None),
                    modernization_date=machine_modernization_date(machine),
                    external_code=machine.external_code,
                    station_external_code=(
                        getattr(station, "external_code", None) if station else None
                    ),
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
    all_years = load_exchange_years(resolved_id)
    years = clip_years(
        all_years,
        year=year,
        start_year=start_year,
        end_year=end_year,
    )
    machines = _load_machines(resolved_id)
    machine_ids = [m.id for m in machines]
    rows = build_generation_machines_rows(
        machines,
        years,
        _load_machine_capacity_map(machine_ids, all_years, resolved_id),
        _load_machine_fuel_map(machine_ids, years, resolved_id),
    )
    return dataset_envelope(
        DATASET_GENERATION_MACHINES,
        database_version=resolved_id,
        version_number=version_number,
        comment=GENERATION_MACHINES_COMMENT,
        rows=rows,
    )


def list_exchange_datasets() -> dict[str, Any]:
    """Совместимость: канон – app.api.services.exchange_api_services."""
    from app.api.services.exchange_api_services import (
        list_exchange_datasets as _list,
    )

    return _list()
