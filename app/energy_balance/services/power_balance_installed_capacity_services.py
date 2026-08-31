# -*- coding: utf-8 -*-
"""Мощности списка станций для балансов: p_ust по типам, ограничения и вводы Q4.

Типы — справочник station_type (порядок display_order): «не указано» не берём,
ВЭС и СЭС суммируем в одну строку. Территория — ОЭС или синхронная зона листа.
Ограничения мощности — сумма Рогр (или Руст−Ррасп) по всем станциям территории.
Вводы после максимума — Руст агрегатов с «Ввод 4 квартала» в ожидаемом году ввода.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from app.common.services.get_services.energy_systems.synchronous_area_get_services import (
    get_synchronous_area_list_full,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_list_full,
)
from app.common.services.get_services.stations.station_type_get_services import (
    get_station_type_list_full,
)

DEFAULT_STATION_TYPE_GROUPS: tuple[dict[str, Any], ...] = (
    {"key": "installed_aes", "label": "АЭС", "type_ids": (), "is_ses_ves": False},
    {"key": "installed_ges", "label": "ГЭС", "type_ids": (), "is_ses_ves": False},
    {"key": "installed_gaes", "label": "ГАЭС", "type_ids": (), "is_ses_ves": False},
    {"key": "installed_tes", "label": "ТЭС", "type_ids": (), "is_ses_ves": False},
    {"key": "installed_snee", "label": "СНЭЭ", "type_ids": (), "is_ses_ves": False},
    {"key": "installed_ses_ves", "label": "СЭС, ВЭС", "type_ids": (), "is_ses_ves": True},
)

# Листы, которые читают p_ust напрямую (как фильтр ОЭС / СЗ на station_list).
# ЕЭС России и 1-я СЗ считаются формулами макета по этим листам.
SHEET_TERRITORY = {
    "severo-zapad": {"kind": "ues", "needles": ("северо-запад",), "exclude": ()},
    "centr": {"kind": "ues", "needles": ("центр",), "exclude": ("северо",)},
    "srednyaya-volga": {"kind": "ues", "needles": ("волг",), "exclude": ()},
    "yug": {"kind": "ues", "needles": ("юг",), "exclude": ()},
    "ural": {"kind": "ues", "needles": ("урал",), "exclude": ()},
    "sibir": {"kind": "ues", "needles": ("сибир",), "exclude": ()},
    "vostok": {"kind": "ues", "needles": ("восток",), "exclude": ()},
    "2-sz-ees-vostok": {"kind": "ues", "needles": ("восток",), "exclude": ()},
    "kaliningradskaya-sz-ees": {"kind": "sa", "needles": ("калининград",), "exclude": ()},
}


def _norm(text: str | None) -> str:
    return (text or "").casefold().replace("ё", "е").strip()


def _is_unspecified_name(name: str | None) -> bool:
    n = _norm(name)
    return (not n) or ("не указано" in n) or n in {"не указан", "не указана"}


def _is_ves_or_ses_name(name: str | None) -> bool:
    n = _norm(name)
    if not n:
        return False
    return "вэс" in n or "сэс" in n


def _stable_type_key(name: str, type_id: int | None) -> str:
    n = _norm(name)
    if "гаэс" in n:
        return "installed_gaes"
    if "гэс" in n:
        return "installed_ges"
    if "аэс" in n:
        return "installed_aes"
    if "тэс" in n:
        return "installed_tes"
    if "снээ" in n:
        return "installed_snee"
    if type_id is None:
        return "installed_type_unknown"
    return f"installed_type_{int(type_id)}"


def _groups_from_station_types(station_types: list[Any]) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    ses_ves_ids: list[int] = []
    ses_ves_at: int | None = None
    for station_type in station_types:
        type_id = getattr(station_type, "id", None)
        name = getattr(station_type, "name", None)
        if type_id is None or int(type_id) <= 0 or _is_unspecified_name(name):
            continue
        if _is_ves_or_ses_name(name):
            if ses_ves_at is None:
                ses_ves_at = len(groups)
            ses_ves_ids.append(int(type_id))
            continue
        groups.append(
            {
                "key": _stable_type_key(str(name), int(type_id)),
                "label": str(name).strip(),
                "type_ids": (int(type_id),),
                "is_ses_ves": False,
            }
        )
    if ses_ves_ids:
        insert_at = 0 if ses_ves_at is None else ses_ves_at
        groups.insert(
            insert_at,
            {
                "key": "installed_ses_ves",
                "label": "СЭС, ВЭС",
                "type_ids": tuple(ses_ves_ids),
                "is_ses_ves": True,
            },
        )
    return groups


def get_power_balance_station_type_groups() -> list[dict[str, Any]]:
    station_types: list[Any] = []
    try:
        station_types = list(get_station_type_list_full() or [])
    except Exception:
        station_types = []
    groups = _groups_from_station_types(station_types)
    if groups:
        return groups
    return [dict(group) for group in DEFAULT_STATION_TYPE_GROUPS]


def installed_type_keys(groups: list[dict[str, Any]] | None = None) -> tuple[str, ...]:
    items = groups if groups is not None else get_power_balance_station_type_groups()
    return tuple(group["key"] for group in items)


def _object_haystack(obj: Any) -> str:
    parts = [
        getattr(obj, "name", None),
        getattr(obj, "name_full", None),
        getattr(obj, "number", None),
    ]
    return _norm(" ".join(str(part) for part in parts if part))


def _match_named_object(
    objects: list[Any],
    *,
    needles: tuple[str, ...],
    exclude: tuple[str, ...] = (),
) -> Any | None:
    needles_n = tuple(_norm(item) for item in needles if item)
    exclude_n = tuple(_norm(item) for item in exclude if item)
    matched: list[Any] = []
    for obj in objects:
        obj_id = getattr(obj, "id", None)
        if obj_id is None or int(obj_id) <= 0:
            continue
        hay = _object_haystack(obj)
        if _is_unspecified_name(hay):
            continue
        if any(item in hay for item in exclude_n):
            continue
        if needles_n and all(item in hay for item in needles_n):
            matched.append(obj)
    if not matched:
        return None
    if len(matched) == 1:
        return matched[0]

    def _score(obj: Any) -> tuple[int, int]:
        hay = _object_haystack(obj)
        starts = 0 if hay.startswith("оэс") or hay.startswith("1") or hay.startswith("2") else 1
        return (starts, len(hay))

    return sorted(matched, key=_score)[0]


def resolve_sheet_territory(slug: str) -> dict[str, Any] | None:
    spec = SHEET_TERRITORY.get(slug)
    if spec is None:
        return None
    kind = spec["kind"]
    needles = tuple(spec.get("needles") or ())
    exclude = tuple(spec.get("exclude") or ())
    if kind == "ues":
        try:
            objects = list(get_union_energy_system_list_full() or [])
        except Exception:
            objects = []
        matched = _match_named_object(objects, needles=needles, exclude=exclude)
        if matched is None:
            return None
        return {"kind": "ues", "id": int(matched.id), "name": matched.name}
    if kind == "sa":
        try:
            objects = list(get_synchronous_area_list_full() or [])
        except Exception:
            objects = []
        matched = _match_named_object(objects, needles=needles, exclude=exclude)
        if matched is None:
            return None
        return {"kind": "sa", "id": int(matched.id), "name": matched.name}
    return None


def _year_values_for_types(
    by_type: dict[Any, dict[int, Any]] | None,
    type_ids: tuple[int, ...],
    years: list[int],
) -> dict[int, Decimal]:
    by_type = by_type or {}
    result: dict[int, Decimal] = {}
    for year in years:
        total = Decimal("0")
        for type_id in type_ids:
            year_map = by_type.get(type_id) or {}
            raw = year_map.get(year)
            if raw is None:
                continue
            total += Decimal(str(raw))
        result[int(year)] = total
    return result


def _decimal_or_zero(raw: Any) -> Decimal:
    if raw is None:
        return Decimal("0")
    return Decimal(str(raw))


def _entity_year_map(
    by_entity: dict[Any, dict[int, Any]] | None,
    entity_id: int,
) -> dict[int, Any]:
    return (by_entity or {}).get(entity_id) or {}


def _constraints_year_values(
    p_ogr_map: dict[int, Any] | None,
    p_ust_map: dict[int, Any] | None,
    p_rasp_map: dict[int, Any] | None,
    years: list[int],
) -> dict[int, Decimal]:
    """Рогр; если пусто — Руст − Ррасп (как на списке станций)."""
    p_ogr_map = p_ogr_map or {}
    p_ust_map = p_ust_map or {}
    p_rasp_map = p_rasp_map or {}
    result: dict[int, Decimal] = {}
    for year in years:
        ogr = _decimal_or_zero(p_ogr_map.get(year))
        if ogr:
            result[int(year)] = ogr
            continue
        result[int(year)] = _decimal_or_zero(p_ust_map.get(year)) - _decimal_or_zero(
            p_rasp_map.get(year)
        )
    return result


def _aggregated_metric(aggregated: dict[str, Any], key: str, metric: str) -> dict[Any, Any]:
    return (aggregated.get(key) or {}).get("aggregated", {}).get(metric) or {}


def _year_values_filled(
    year_map: dict[int, Any] | None,
    years: list[int],
) -> dict[int, Decimal]:
    year_map = year_map or {}
    return {int(year): _decimal_or_zero(year_map.get(year)) for year in years}


def resolve_station_balance_territory(
    *,
    id_regional_energy_system: int | None,
    id_regional_district: int | None,
    res_to_ues: dict[int, int],
    district_to_ues: dict[int, int],
    district_to_sa: dict[int, int],
) -> tuple[int | None, int | None]:
    """ОЭС: прямая РЭС, иначе первая РЭС субъекта. СЗ — субъект РФ станции."""
    ues_id: int | None = None
    if id_regional_energy_system:
        ues_id = res_to_ues.get(int(id_regional_energy_system))
    if ues_id is None and id_regional_district:
        ues_id = district_to_ues.get(int(id_regional_district))
    sa_id = district_to_sa.get(int(id_regional_district)) if id_regional_district else None
    return ues_id, sa_id


def accumulate_q4_p_ust_by_territory(
    rows: list[Any],
    *,
    res_to_ues: dict[int, int],
    district_to_ues: dict[int, int],
    district_to_sa: dict[int, int],
) -> dict[str, dict[int, dict[int, Decimal]]]:
    """Сумма Руст агрегатов Q4 по ОЭС и СЗ; при дублях (machine, year) берём max id."""
    best_by_machine_year: dict[tuple[int, int], Any] = {}
    for row in rows or []:
        machine_id = getattr(row, "machine_id", None)
        if machine_id is None:
            machine_id = getattr(row, "id_machine", None)
        year = getattr(row, "year", None)
        if year is None:
            year = getattr(row, "year_number", None)
        if machine_id is None or year is None:
            continue
        key = (int(machine_id), int(year))
        prev = best_by_machine_year.get(key)
        row_id = int(getattr(row, "id", 0) or 0)
        prev_id = int(getattr(prev, "id", 0) or 0) if prev is not None else -1
        if prev is None or row_id >= prev_id:
            best_by_machine_year[key] = row

    ues: dict[int, dict[int, Decimal]] = {}
    sa: dict[int, dict[int, Decimal]] = {}
    res: dict[int, dict[int, Decimal]] = {}
    eu: dict[int, dict[int, Decimal]] = {}
    for row in best_by_machine_year.values():
        year = int(getattr(row, "year", None) or getattr(row, "year_number"))
        p_ust = _decimal_or_zero(getattr(row, "p_ust", None))
        if not p_ust:
            continue
        res_id = getattr(row, "id_regional_energy_system", None)
        district_id = getattr(row, "id_regional_district", None)
        ues_id, sa_id = resolve_station_balance_territory(
            id_regional_energy_system=int(res_id) if res_id else None,
            id_regional_district=int(district_id) if district_id else None,
            res_to_ues=res_to_ues,
            district_to_ues=district_to_ues,
            district_to_sa=district_to_sa,
        )
        if res_id:
            try:
                res_int = int(res_id)
            except (TypeError, ValueError):
                res_int = None
            if res_int:
                res.setdefault(res_int, {})
                res[res_int][year] = res[res_int].get(year, Decimal("0")) + p_ust
        eu_id = getattr(row, "id_energy_unit", None)
        if eu_id:
            try:
                eu_int = int(eu_id)
            except (TypeError, ValueError):
                eu_int = None
            if eu_int:
                eu.setdefault(eu_int, {})
                eu[eu_int][year] = eu[eu_int].get(year, Decimal("0")) + p_ust
        if ues_id is not None:
            ues.setdefault(ues_id, {})
            ues[ues_id][year] = ues[ues_id].get(year, Decimal("0")) + p_ust
        if sa_id is not None:
            sa.setdefault(sa_id, {})
            sa[sa_id][year] = sa[sa_id].get(year, Decimal("0")) + p_ust
    return {"ues": ues, "sa": sa, "res": res, "eu": eu}


def _q4_territory_lookups(
    res_ids: set[int],
    district_ids: set[int],
) -> tuple[dict[int, int], dict[int, int], dict[int, int]]:
    from app.refdata.models.energy_systems.regional_energy_system_model import (
        RegionalEnergySystem,
    )
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    res_to_ues: dict[int, int] = {}
    if res_ids:
        for res in RegionalEnergySystem.query.filter(RegionalEnergySystem.id.in_(res_ids)):
            ues_id = getattr(res, "id_union_energy_system", None)
            if ues_id:
                res_to_ues[int(res.id)] = int(ues_id)
    district_to_ues: dict[int, int] = {}
    district_to_sa: dict[int, int] = {}
    if district_ids:
        for district in RegionalDistrict.query.filter(RegionalDistrict.id.in_(district_ids)):
            sa_id = getattr(district, "id_synchronous_area", None)
            if sa_id:
                district_to_sa[int(district.id)] = int(sa_id)
            for res in district.regional_energy_systems or []:
                ues_id = getattr(res, "id_union_energy_system", None)
                if ues_id:
                    district_to_ues[int(district.id)] = int(ues_id)
                    break
    return res_to_ues, district_to_ues, district_to_sa


def _query_q4_commissioning_machine_powers(
    start_year: int,
    end_year: int,
    station_ids: list[int],
) -> list[Any]:
    from sqlalchemy import and_, literal, or_

    from app.common.services.database_version_filter import (
        filter_by_db_version,
        get_current_db_version_id,
    )
    from app.extensions import db
    from app.generation.models.machine.machine_model import Machine
    from app.generation.models.machine.machine_power_model import MachinePower
    from app.generation.models.station.station_model import Station

    current_version_id = get_current_db_version_id()

    def _version_cond(model_cls: Any):
        if not hasattr(model_cls, "database_version_id"):
            return literal(True)
        if current_version_id is None:
            return model_cls.database_version_id.is_(None)
        return model_cls.database_version_id == current_version_id

    def _version_cond_power(model_cls: Any):
        if not hasattr(model_cls, "database_version_id"):
            return literal(True)
        if current_version_id is None:
            return model_cls.database_version_id.is_(None)
        return or_(
            model_cls.database_version_id == current_version_id,
            model_cls.database_version_id.is_(None),
        )

    query = (
        db.session.query(
            MachinePower.id.label("id"),
            Machine.id.label("machine_id"),
            Station.id_regional_energy_system.label("id_regional_energy_system"),
            Station.id_regional_district.label("id_regional_district"),
            Station.id_energy_unit.label("id_energy_unit"),
            MachinePower.year_number.label("year"),
            MachinePower.p_ust.label("p_ust"),
        )
        .select_from(MachinePower)
        .join(Machine, and_(Machine.id == MachinePower.id_machine, _version_cond(Machine)))
        .join(Station, and_(Station.id == Machine.id_station, _version_cond(Station)))
        .filter(
            Station.id.in_(station_ids),
            Machine.is_archived.isnot(True),
            Machine.is_commissioning_q4.is_(True),
            Machine.date_exploitation_expected.isnot(None),
            MachinePower.year_number == Machine.date_exploitation_expected,
            MachinePower.year_number.between(start_year, end_year),
            _version_cond_power(MachinePower),
        )
    )
    query = filter_by_db_version(query, Station)
    return list(query.all())


def _load_q4_commissioning_p_ust_maps(
    years: list[int],
    station_ids: list[int],
) -> dict[str, dict[int, dict[int, Decimal]]]:
    """Руст агрегатов с «Ввод 4 квартала» в ожидаемом году ввода, по ОЭС и СЗ."""
    empty: dict[str, dict[int, dict[int, Decimal]]] = {"ues": {}, "sa": {}, "res": {}, "eu": {}}
    if not years or not station_ids:
        return empty
    try:
        rows = _query_q4_commissioning_machine_powers(min(years), max(years), station_ids)
    except Exception:
        return empty
    if not rows:
        return empty
    res_ids: set[int] = set()
    district_ids: set[int] = set()
    for row in rows:
        res_id = getattr(row, "id_regional_energy_system", None)
        district_id = getattr(row, "id_regional_district", None)
        if res_id:
            res_ids.add(int(res_id))
        if district_id:
            district_ids.add(int(district_id))
    try:
        res_to_ues, district_to_ues, district_to_sa = _q4_territory_lookups(
            res_ids, district_ids
        )
    except Exception:
        return empty
    return accumulate_q4_p_ust_by_territory(
        rows,
        res_to_ues=res_to_ues,
        district_to_ues=district_to_ues,
        district_to_sa=district_to_sa,
    )


def load_power_balance_installed_capacity_inputs(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """p_ust по типам, ограничения (Рогр) и вводы Q4 для листов с фильтром."""
    if not years:
        return {}
    groups = get_power_balance_station_type_groups()
    from app.generation.services.station_services.aggregation_station_services.aggregation_rows import (
        get_full_aggregation_rows,
    )
    from app.generation.services.station_services.aggregation_station_services.optimized_aggregation import (
        aggregate_all_at_once,
    )
    from app.generation.services.station_services.station_services import get_filtered_station_ids

    station_ids = get_filtered_station_ids({})
    if not station_ids:
        return {}
    start_year = min(years)
    end_year = max(years)
    aggregation_rows = get_full_aggregation_rows(start_year, end_year, station_ids)
    aggregated = aggregate_all_at_once(aggregation_rows)
    ues_by_type = _aggregated_metric(
        aggregated, "aggregate_union_energy_systems_by_station_types", "p_ust"
    )
    ues_by_type_rasp = _aggregated_metric(
        aggregated, "aggregate_union_energy_systems_by_station_types", "p_rasp"
    )
    sa_by_type = _aggregated_metric(
        aggregated, "aggregate_synchronous_areas_by_station_types", "p_ust"
    )
    sa_by_type_rasp = _aggregated_metric(
        aggregated, "aggregate_synchronous_areas_by_station_types", "p_rasp"
    )
    ues_p_ogr = _aggregated_metric(aggregated, "aggregate_power_by_union_energy_systems", "p_ogr")
    ues_p_ust = _aggregated_metric(aggregated, "aggregate_power_by_union_energy_systems", "p_ust")
    ues_p_rasp = _aggregated_metric(aggregated, "aggregate_power_by_union_energy_systems", "p_rasp")
    sa_p_ogr = _aggregated_metric(aggregated, "aggregate_power_by_synchronous_areas", "p_ogr")
    sa_p_ust = _aggregated_metric(aggregated, "aggregate_power_by_synchronous_areas", "p_ust")
    sa_p_rasp = _aggregated_metric(aggregated, "aggregate_power_by_synchronous_areas", "p_rasp")
    res_by_type = _aggregated_metric(
        aggregated, "aggregate_regional_energy_systems_by_station_types", "p_ust"
    )
    res_by_type_rasp = _aggregated_metric(
        aggregated, "aggregate_regional_energy_systems_by_station_types", "p_rasp"
    )
    res_p_ogr = _aggregated_metric(aggregated, "aggregate_power_by_regional_energy_systems", "p_ogr")
    res_p_ust = _aggregated_metric(aggregated, "aggregate_power_by_regional_energy_systems", "p_ust")
    res_p_rasp = _aggregated_metric(aggregated, "aggregate_power_by_regional_energy_systems", "p_rasp")
    eu_by_type = _aggregated_metric(
        aggregated, "aggregate_energy_units_by_station_types", "p_ust"
    )
    eu_by_type_rasp = _aggregated_metric(
        aggregated, "aggregate_energy_units_by_station_types", "p_rasp"
    )
    eu_p_ogr = _aggregated_metric(aggregated, "aggregate_power_by_energy_units", "p_ogr")
    eu_p_ust = _aggregated_metric(aggregated, "aggregate_power_by_energy_units", "p_ust")
    eu_p_rasp = _aggregated_metric(aggregated, "aggregate_power_by_energy_units", "p_rasp")
    q4_maps = _load_q4_commissioning_p_ust_maps(years, station_ids)

    if sheets:
        sheet_specs: list[tuple[str, dict[str, Any] | None]] = []
        for sheet in sheets:
            if (
                sheet.get("skip_table")
                or sheet.get("skip_direct_capacity")
                or sheet.get("layout") in {"ees_rossii", "sz1"}
            ):
                continue
            sheet_specs.append((sheet["slug"], sheet.get("territory")))
    else:
        sheet_specs = [(slug, None) for slug in SHEET_TERRITORY]

    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for slug, territory in sheet_specs:
        resolved = territory if territory and territory.get("id") is not None else resolve_sheet_territory(slug)
        if resolved is None:
            continue
        try:
            entity_id = int(resolved["id"])
        except (TypeError, ValueError, KeyError):
            continue
        kind = resolved.get("kind") or (SHEET_TERRITORY.get(slug) or {}).get("kind")
        if kind == "ues":
            by_type = ues_by_type.get(entity_id) or {}
            by_type_rasp = ues_by_type_rasp.get(entity_id) or {}
            ogr_map = _entity_year_map(ues_p_ogr, entity_id)
            ust_map = _entity_year_map(ues_p_ust, entity_id)
            rasp_map = _entity_year_map(ues_p_rasp, entity_id)
            q4_map = _entity_year_map(q4_maps.get("ues"), entity_id)
        elif kind == "sa":
            by_type = sa_by_type.get(entity_id) or {}
            by_type_rasp = sa_by_type_rasp.get(entity_id) or {}
            ogr_map = _entity_year_map(sa_p_ogr, entity_id)
            ust_map = _entity_year_map(sa_p_ust, entity_id)
            rasp_map = _entity_year_map(sa_p_rasp, entity_id)
            q4_map = _entity_year_map(q4_maps.get("sa"), entity_id)
        elif kind == "res":
            by_type = res_by_type.get(entity_id) or {}
            by_type_rasp = res_by_type_rasp.get(entity_id) or {}
            ogr_map = _entity_year_map(res_p_ogr, entity_id)
            ust_map = _entity_year_map(res_p_ust, entity_id)
            rasp_map = _entity_year_map(res_p_rasp, entity_id)
            q4_map = _entity_year_map(q4_maps.get("res"), entity_id)
        elif kind == "eu":
            by_type = eu_by_type.get(entity_id) or {}
            by_type_rasp = eu_by_type_rasp.get(entity_id) or {}
            ogr_map = _entity_year_map(eu_p_ogr, entity_id)
            ust_map = _entity_year_map(eu_p_ust, entity_id)
            rasp_map = _entity_year_map(eu_p_rasp, entity_id)
            q4_map = _entity_year_map(q4_maps.get("eu"), entity_id)
        else:
            continue
        sheet_inputs: dict[str, dict[int, Decimal]] = {}
        for group in groups:
            type_ids = tuple(group.get("type_ids") or ())
            sheet_inputs[group["key"]] = _year_values_for_types(by_type, type_ids, years)
            sheet_inputs[available_row_key(group["key"])] = _year_values_for_types(
                by_type_rasp, type_ids, years
            )
        sheet_inputs["constraints"] = _constraints_year_values(
            ogr_map, ust_map, rasp_map, years
        )
        sheet_inputs["commissioning_after_max"] = _year_values_filled(q4_map, years)
        inputs[slug] = sheet_inputs
    return inputs


def available_row_key(installed_key: str) -> str:
    text = str(installed_key or "")
    if text.startswith("installed_"):
        return "available_" + text[len("installed_") :]
    return f"available_{text}"


def station_capacity_row_key(station_id: int) -> str:
    return f"installed_station_{int(station_id)}"


def machine_capacity_row_key(machine_id: int) -> str:
    return f"installed_machine_{int(machine_id)}"


def _name_already_shows_machine_number(name: str, number: str) -> bool:
    if not name or not number:
        return False
    escaped = re.escape(number)
    if re.match(rf"^{escaped}(?:\s|$)", name):
        return True
    return bool(re.search(rf"№\s*{escaped}(?:\D|$)", name))


def _machine_capacity_label(machine_number: Any, machine_name: Any) -> str:
    number = " ".join(str(machine_number or "").split())
    name = " ".join(str(machine_name or "").split())
    if number and name:
        if _name_already_shows_machine_number(name, number):
            return name
        return f"{number} {name}"
    return name or number or "Агрегат"


def _machine_sort_tuple(machine_number: Any) -> tuple[int, str]:
    text = str(machine_number or "").strip()
    digits = ""
    for char in text:
        if char.isdigit():
            digits += char
        elif digits:
            break
    return (int(digits) if digits else 10**9, text)


# Токены энергорайонов ТИТЭС Востока: при общей РЭС (Чукотка) режем станции по имени.
_EU_SPLIT_SPECS: tuple[tuple[str, ...], ...] = (
    ("чаун", "билибин"),
    ("анад",),
    ("камчат",),
    ("магадан",),
    ("сахалин",),
)


def _tokens_for_eu_name(name: str | None) -> tuple[str, ...]:
    n = _norm(name)
    if not n:
        return ()
    for spec in _EU_SPLIT_SPECS:
        if all(token in n for token in spec):
            return spec
    return ()


def _station_name_matches_tokens(station_name: str | None, tokens: tuple[str, ...]) -> bool:
    if not tokens:
        return False
    n = _norm(station_name)
    return any(token in n for token in tokens)


def assign_station_ids_for_shared_res_eu(
    stations: list[tuple[int, str]],
    current_eu_id: int,
    eu_id_to_name: dict[int, str],
) -> list[int]:
    """Станции общей РЭС: в энергорайон по токенам имени, без совпадений — в «остаток»."""
    token_by_eu = {
        int(eu_id): _tokens_for_eu_name(name) for eu_id, name in (eu_id_to_name or {}).items()
    }
    token_items = [(eu_id, tokens) for eu_id, tokens in token_by_eu.items() if tokens]
    if len(token_items) <= 1:
        return [int(station_id) for station_id, _name in stations]
    remainder_id = max(token_items, key=lambda item: (len(item[1]), -item[0]))[0]
    result: list[int] = []
    for station_id, station_name in stations:
        matched = [
            eu_id
            for eu_id, tokens in token_items
            if _station_name_matches_tokens(station_name, tokens)
        ]
        if current_eu_id in matched:
            result.append(int(station_id))
        elif not matched and current_eu_id == remainder_id:
            result.append(int(station_id))
    return result


def _station_ids_for_energy_unit_via_res(eu_id: int, eu_name: str) -> list[int]:
    """Станции энергорайона: прямого id_energy_unit нет — берём РЭС, Чукотку режем по имени."""
    from app.common.services.database_version_filter import filter_by_db_version
    from app.extensions import db
    from app.generation.models.station.station_model import Station
    from app.refdata.models.energy_systems.energy_unit_model import EnergyUnit

    eu = EnergyUnit.query.get(eu_id)
    res_id = getattr(eu, "id_regional_energy_system", None) if eu is not None else None
    if not res_id:
        return []
    res_id = int(res_id)
    query = (
        db.session.query(Station.id, Station.name)
        .filter(Station.id_regional_energy_system == res_id)
    )
    query = filter_by_db_version(query, Station)
    stations = [
        (int(row[0]), str(row[1] or ""))
        for row in query.all()
        if row[0] is not None
    ]
    if not stations:
        return []
    sibling_names: dict[int, str] = {}
    try:
        siblings = EnergyUnit.query.filter(EnergyUnit.id_regional_energy_system == res_id).all()
    except Exception:
        siblings = []
    for sibling in siblings:
        sibling_id = getattr(sibling, "id", None)
        if sibling_id is None:
            continue
        sibling_names[int(sibling_id)] = str(getattr(sibling, "name", None) or "")
    sibling_names.setdefault(int(eu_id), eu_name)
    if len(sibling_names) <= 1:
        return [station_id for station_id, _name in stations]
    return assign_station_ids_for_shared_res_eu(stations, int(eu_id), sibling_names)


def _station_ids_for_capacity_territory(territory: dict[str, Any] | None) -> list[int]:
    if not territory or territory.get("id") is None:
        return []
    kind = str(territory.get("kind") or "")
    try:
        entity_id = int(territory["id"])
    except (TypeError, ValueError, KeyError):
        return []
    from app.common.services.database_version_filter import filter_by_db_version
    from app.extensions import db
    from app.generation.models.station.station_model import Station
    from app.generation.services.station_services.station_services import (
        _station_energy_unit_sql_filter,
        _station_union_energy_system_sql_filter,
    )

    query = db.session.query(Station.id)
    query = filter_by_db_version(query, Station)
    if kind == "ues":
        query = query.filter(_station_union_energy_system_sql_filter([entity_id]))
        return [int(row[0]) for row in query.all() if row[0] is not None]
    if kind == "eu":
        cond = _station_energy_unit_sql_filter([entity_id])
        ids: list[int] = []
        if cond is not None:
            ids = [int(row[0]) for row in query.filter(cond).all() if row[0] is not None]
        if ids:
            return ids
        return _station_ids_for_energy_unit_via_res(entity_id, str(territory.get("name") or ""))
    return []


def _query_station_machine_powers(
    start_year: int,
    end_year: int,
    station_ids: list[int],
) -> list[Any]:
    from sqlalchemy import and_, func, literal, or_

    from app.common.services.database_version_filter import (
        filter_by_db_version,
        get_current_db_version_id,
    )
    from app.extensions import db
    from app.generation.models.machine.machine_model import Machine
    from app.generation.models.machine.machine_power_model import MachinePower
    from app.generation.models.station.station_model import Station

    current_version_id = get_current_db_version_id()

    def _version_cond(model_cls: Any):
        if not hasattr(model_cls, "database_version_id"):
            return literal(True)
        if current_version_id is None:
            return model_cls.database_version_id.is_(None)
        return model_cls.database_version_id == current_version_id

    def _version_cond_power(model_cls: Any):
        if not hasattr(model_cls, "database_version_id"):
            return literal(True)
        if current_version_id is None:
            return model_cls.database_version_id.is_(None)
        return or_(
            model_cls.database_version_id == current_version_id,
            model_cls.database_version_id.is_(None),
        )

    query = (
        db.session.query(
            Station.id.label("station_id"),
            Station.name.label("station_name"),
            Machine.id.label("machine_id"),
            Machine.machine_number.label("machine_number"),
            Machine.machine_name.label("machine_name"),
            MachinePower.year_number.label("year"),
            func.sum(MachinePower.p_ust).label("p_ust"),
            func.sum(MachinePower.p_rasp).label("p_rasp"),
        )
        .select_from(Machine)
        .join(Station, and_(Station.id == Machine.id_station, _version_cond(Station)))
        .outerjoin(
            MachinePower,
            and_(
                MachinePower.id_machine == Machine.id,
                MachinePower.year_number.between(start_year, end_year),
                _version_cond_power(MachinePower),
            ),
        )
        .filter(
            Station.id.in_(station_ids),
            Machine.is_archived.isnot(True),
            _version_cond(Machine),
        )
        .group_by(
            Station.id,
            Station.name,
            Machine.id,
            Machine.machine_number,
            Machine.machine_name,
            MachinePower.year_number,
        )
    )
    query = filter_by_db_version(query, Station)
    return list(query.all())


def _build_station_capacity_items(
    rows: list[Any],
    years: list[int],
) -> list[dict[str, Any]]:
    stations: dict[int, dict[str, Any]] = {}
    for row in rows or []:
        station_id = getattr(row, "station_id", None)
        machine_id = getattr(row, "machine_id", None)
        if station_id is None or machine_id is None:
            continue
        station_id = int(station_id)
        machine_id = int(machine_id)
        station = stations.get(station_id)
        if station is None:
            station = {
                "id": station_id,
                "key": station_capacity_row_key(station_id),
                "label": str(getattr(row, "station_name", None) or "").strip()
                or f"Станция {station_id}",
                "year_values": {int(year): Decimal("0") for year in years},
                "rasp_year_values": {int(year): Decimal("0") for year in years},
                "machines": {},
            }
            stations[station_id] = station
        machines = station["machines"]
        machine = machines.get(machine_id)
        if machine is None:
            machine = {
                "id": machine_id,
                "key": machine_capacity_row_key(machine_id),
                "label": _machine_capacity_label(
                    getattr(row, "machine_number", None),
                    getattr(row, "machine_name", None),
                ),
                "number": str(getattr(row, "machine_number", None) or ""),
                "year_values": {int(year): Decimal("0") for year in years},
                "rasp_year_values": {int(year): Decimal("0") for year in years},
            }
            machines[machine_id] = machine
        year = getattr(row, "year", None)
        if year is None:
            continue
        year_int = int(year)
        if year_int not in machine["year_values"]:
            continue
        amount = _decimal_or_zero(getattr(row, "p_ust", None))
        machine["year_values"][year_int] += amount
        station["year_values"][year_int] += amount
        rasp = _decimal_or_zero(getattr(row, "p_rasp", None))
        machine["rasp_year_values"][year_int] += rasp
        station["rasp_year_values"][year_int] += rasp

    items: list[dict[str, Any]] = []
    for station in stations.values():
        machine_items = list((station.get("machines") or {}).values())
        machine_items.sort(
            key=lambda item: (
                _machine_sort_tuple(item.get("number")),
                _norm(item.get("label")),
                int(item.get("id") or 0),
            )
        )
        station["machines"] = [{k: v for k, v in item.items() if k != "number"} for item in machine_items]
        items.append(station)
    items.sort(key=lambda item: (_norm(item.get("label")), int(item.get("id") or 0)))
    return items


def load_power_balance_station_capacity_breakdown(
    years: list[int],
    sheets: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Станции и агрегаты с p_ust для листов ТИТЭС (вместо разбивки по типам)."""
    if not years or not sheets:
        return {}
    targets = [
        sheet
        for sheet in sheets
        if sheet.get("station_capacity_breakdown")
        and not sheet.get("skip_table")
        and not sheet.get("skip_direct_capacity")
    ]
    if not targets:
        return {}
    start_year = min(years)
    end_year = max(years)
    result: dict[str, dict[str, Any]] = {}
    for sheet in targets:
        slug = str(sheet.get("slug") or "").strip()
        if not slug:
            continue
        territory = sheet.get("territory") or {}
        try:
            station_ids = _station_ids_for_capacity_territory(territory)
        except Exception:
            station_ids = []
        if not station_ids:
            result[slug] = {"stations": []}
            continue
        try:
            rows = _query_station_machine_powers(start_year, end_year, station_ids)
        except Exception:
            result[slug] = {"stations": []}
            continue
        result[slug] = {"stations": _build_station_capacity_items(rows, years)}
    return result


def _add_station_metric_inputs(
    sheet_inputs: dict[str, dict[int, Decimal]],
    station: dict[str, Any],
    *,
    year_field: str,
    key_mapper=None,
) -> None:
    mapper = key_mapper or (lambda key: key)

    def _put(item: dict[str, Any]) -> None:
        year_map = item.get(year_field) or {}
        if not year_map:
            return
        sheet_inputs[mapper(item["key"])] = {
            int(year): _decimal_or_zero(value) for year, value in year_map.items()
        }

    machines = station.get("machines") or []
    if machines:
        for machine in machines:
            _put(machine)
    else:
        _put(station)


def station_capacity_breakdown_to_inputs(
    breakdown: dict[str, dict[str, Any]] | None,
) -> dict[str, dict[str, dict[int, Decimal]]]:
    """Значения агрегатов (и станций без агрегатов) для подстановки в таблицу."""
    inputs: dict[str, dict[str, dict[int, Decimal]]] = {}
    for slug, payload in (breakdown or {}).items():
        sheet_inputs: dict[str, dict[int, Decimal]] = {}
        for station in payload.get("stations") or []:
            _add_station_metric_inputs(sheet_inputs, station, year_field="year_values")
            _add_station_metric_inputs(
                sheet_inputs,
                station,
                year_field="rasp_year_values",
                key_mapper=available_row_key,
            )
        if sheet_inputs:
            inputs[slug] = sheet_inputs
    return inputs
