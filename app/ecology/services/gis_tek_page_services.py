# -*- coding: utf-8 -*-
"""Сборка страниц отчетных данных ГИС ТЭК (ПГ / ЗВ)."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import selectinload

from app.common.services.database_version_filter import get_current_db_version_id
from app.ecology.services.ecology_decimal_helpers import decimal_or_none as _decimal_or_none
from app.ecology.services.ecology_request_helpers import parse_truthy_arg
from app.ecology.services.ecology_text_helpers import text_contains
from app.ecology.models.pg_report_gis_tek_model import PGReportGisTek
from app.ecology.models.zv_report_gis_tek_model import ZVReportGisTek
from app.ecology.services.gis_tek_constants import (
    PAGE_TITLES,
    REPORT_PG,
    REPORT_ZV,
    VALUE_COLUMN_GROUPS,
    VALUE_COLUMNS,
    ZV_DERIVED_ATTRS,
    ZV_EMISSIONS_BANNER_TITLE,
    ZV_GASEOUS_AND_LIQUID_FORMULA_KEY,
    ZV_GASEOUS_AND_LIQUID_PARTS,
    ZV_TOTAL_FORMULA_KEY,
    ZV_TOTAL_PARTS,
)
from app.energy_consumption.forms.energy_consumption_parameter_forms import EmptyCSRFForm
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import (
    EquipmentGroupSetStation,
)
from app.refdata.models.energy_systems.regional_energy_system_model import (
    RegionalEnergySystem,
)
from app.refdata.models.years.year_model import Year


REPORT_MODELS = {
    REPORT_PG: PGReportGisTek,
    REPORT_ZV: ZVReportGisTek,
}

UNKNOWN_UES = "Не указано"
UNKNOWN_RES = "Не указано"

IDENTITY_COLUMNS = [
    ("station_numb", "Код группы оборудования (numb)", False),
    ("gis_tek_station_name", "Электростанция (ГИС ТЭК)", False),
    ("generation_station_name", "Электростанция (Генерация)", False),
    ("equipment_group_name", "Группа оборудования (Топливо)", False),
    ("station_type", "Тип станции", False),
]


def can_edit_ecology(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "has_admin", False):
        return True
    names = [str(n or "") for n in (getattr(user, "role_names", None) or [])]
    return any("ecology" in n.lower() for n in names)


def _parse_year(raw, fallback: int | None) -> int | None:
    if raw is None or str(raw).strip() == "":
        return fallback
    try:
        return int(raw)
    except (TypeError, ValueError):
        return fallback


def _coerce_numb(raw) -> int | None:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _args_getlist(args, key: str) -> list:
    if args is None:
        return []
    if hasattr(args, "getlist"):
        return list(args.getlist(key) or [])
    getter = getattr(args, "get", None)
    val = getter(key) if callable(getter) else None
    if val is None and isinstance(args, dict):
        val = args.get(key)
    if val is None:
        return []
    if isinstance(val, (list, tuple, set)):
        return list(val)
    return [val]


def normalize_numb_filter(raw) -> list[int] | None:
    """Коды группы оборудования из фильтра шапки; None, если фильтр не задан."""
    if not raw:
        return None
    if not isinstance(raw, (list, tuple, set)):
        raw = [raw]
    out: list[int] = []
    seen: set[int] = set()
    for item in raw:
        n = _coerce_numb(item)
        if n is None or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out or None


def collect_numb_filter_choices(rows: list[dict]) -> list[int]:
    values: set[int] = set()
    for row in rows or []:
        n = _coerce_numb(row.get("station_numb"))
        if n is not None:
            values.add(n)
    return sorted(values)


def _parse_per_page(raw) -> int | str:
    if raw is None or str(raw).strip() == "":
        return 25
    if str(raw).strip().lower() == "all":
        return "all"
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 25
    if value in (10, 25, 50, 100):
        return value
    return 25


def parse_show_totals_arg(args) -> bool:
    return parse_truthy_arg(args, "show_totals", casefold=True)


def parse_show_empty_rows_arg(args) -> bool:
    """Кнопка «Пустые строки»: по умолчанию не нажата (скрывать)."""
    return parse_truthy_arg(args, "show_empty_rows", casefold=True)


def display_station_type(value) -> str:
    if value is None:
        return "—"
    s = str(value).strip()
    if not s or s == "0":
        return "—"
    return s


def equipment_group_title(group: EquipmentGroup | None) -> str:
    if group is None:
        return "—"
    name = (group.name or "").strip()
    return name if name else "—"


def linked_generation_stations(
    group: EquipmentGroup | None,
    version_id: int | None = None,
) -> list[dict]:
    """Станции модуля «Генерация», привязанные к группе оборудования."""
    if group is None:
        return []
    seen: set[int] = set()
    result: list[dict] = []
    for link in getattr(group, "equipment_group_links_v2", None) or []:
        set_station = getattr(link, "equipment_group_set_station", None)
        if set_station is None:
            continue
        ss_version = getattr(set_station, "database_version_id", None)
        if version_id is not None and ss_version is not None and ss_version != version_id:
            continue
        station = getattr(set_station, "station", None)
        if station is None:
            continue
        station_id = getattr(station, "id", None)
        if station_id is None or station_id in seen:
            continue
        seen.add(station_id)
        name = (getattr(station, "name", None) or "").strip()
        result.append({"id": station_id, "name": name or "—"})
    result.sort(key=lambda item: (str(item["name"]).casefold(), int(item["id"])))
    return result


def _gen_company_name(group: EquipmentGroup | None) -> str:
    mapping = getattr(group, "gen_company_external_mapping", None) if group is not None else None
    return (getattr(mapping, "external_name", None) or "").strip()


def _text_contains(needle: str, haystack) -> bool:
    return text_contains(
        needle,
        haystack,
        treat_em_dash_as_empty=True,
        reject_empty_needle=True,
    )


def apply_gis_tek_territory_filters(
    rows: list[dict],
    territory_filters: dict | None,
    *,
    matching_eg_ids: set[int] | None = None,
    matching_ved_eg_ids: set[int] | None = None,
) -> list[dict]:
    """Территориальные фильтры первой строки, как на /ecology/analysis/zv-vse/."""
    filters = territory_filters or {}
    out = list(rows or [])
    if matching_eg_ids is not None:
        wanted = {int(item) for item in matching_eg_ids}
        out = [
            row
            for row in out
            if row.get("equipment_group_id") is not None
            and int(row["equipment_group_id"]) in wanted
        ]

    station_q = str(filters.get("station_name_filter") or "").strip()
    if station_q:
        filtered = []
        for row in out:
            names = [
                row.get("gis_tek_station_name"),
                row.get("generation_station_name"),
                row.get("equipment_group_name"),
                row.get("station_numb"),
            ]
            for station in row.get("generation_stations") or []:
                if isinstance(station, dict):
                    names.append(station.get("name"))
            if any(_text_contains(station_q, name) for name in names):
                filtered.append(row)
        out = filtered

    gen_q = str(filters.get("gen_company_filter") or "").strip()
    if gen_q:
        out = [row for row in out if _text_contains(gen_q, row.get("gen_company_name"))]

    if matching_ved_eg_ids is not None:
        wanted_ved = {int(item) for item in matching_ved_eg_ids}
        out = [
            row
            for row in out
            if row.get("equipment_group_id") is not None
            and int(row["equipment_group_id"]) in wanted_ved
        ]
    return out


def _territory_id_filters_active(filters: dict | None) -> bool:
    from app.ecology.services.gis_tes_fuel_comparison_constants import TERRITORY_FILTER_KEYS

    selected = filters or {}
    return any(selected.get(key) for key in TERRITORY_FILTER_KEYS[:5])


def _matching_territory_equipment_group_ids(
    territory_filters: dict,
    version_id: int | None,
) -> set[int] | None:
    if not _territory_id_filters_active(territory_filters):
        return None
    from app.fuel.services.stations.stations_equipment_groups_services import (
        get_filtered_equipment_group_ids_all,
    )

    return get_filtered_equipment_group_ids_all(
        territory_filters,
        version_id=version_id,
        strict_version=True,
    )


def _matching_ved_equipment_group_ids(
    rows: list[dict],
    territory_filters: dict,
    year: int | None,
    version_id: int | None,
) -> set[int] | None:
    from app.ecology.services.gis_tes_fuel_comparison_constants import VED_FILTER_TO_VALUES
    from app.ecology.services.gis_tes_pg_from_fuel_services import _eg_ids_matching_ved

    ved_group = str(territory_filters.get("ved_filter") or "").strip()
    allowed = set(VED_FILTER_TO_VALUES.get(ved_group, ()))
    if not allowed or year is None:
        return None
    eg_ids = {
        int(row["equipment_group_id"])
        for row in rows or []
        if row.get("equipment_group_id") is not None
    }
    return _eg_ids_matching_ved(eg_ids, allowed, int(year), int(year), version_id)


def _parse_gis_tek_territory_filters(args) -> dict:
    from app.ecology.services.gis_tes_fuel_comparison_services import parse_territory_filters

    territory_filters = parse_territory_filters(args)
    if not str(territory_filters.get("station_name_filter") or "").strip():
        q_fallback = ""
        if args is not None:
            getter = getattr(args, "get", None)
            raw = getter("q") if callable(getter) else None
            q_fallback = str(raw or "").strip()
        if q_fallback:
            territory_filters["station_name_filter"] = q_fallback
    return territory_filters


def _ues_res_for_group(group: EquipmentGroup | None) -> tuple[str, str, int, int]:
    if group is None:
        return UNKNOWN_UES, UNKNOWN_RES, 10**9, 10**9
    res = getattr(group, "regional_energy_system", None)
    ues = getattr(res, "union_energy_system", None) if res else None
    ues_name = (getattr(ues, "name", None) or "").strip() or UNKNOWN_UES
    res_name = (getattr(res, "name", None) or "").strip() or UNKNOWN_RES
    ues_order = getattr(ues, "display_order", None)
    res_order = getattr(res, "display_order", None)
    ues_sort = ues_order if ues_order is not None else 10**8
    res_sort = res_order if res_order is not None else 10**8
    if ues_name == UNKNOWN_UES:
        ues_sort = 10**9
    if res_name == UNKNOWN_RES:
        res_sort = 10**9
    return ues_name, res_name, ues_sort, res_sort


def sum_gaseous_and_liquid(metrics: dict | None) -> Decimal | None:
    """Сумма SO2 + CO + NOx + углеводороды + ЛОС + прочие; None, если все слагаемые пустые."""
    return _sum_parts(metrics, ZV_GASEOUS_AND_LIQUID_PARTS)


def sum_zv_total(metrics: dict | None) -> Decimal | None:
    """Сумма твёрдых и газообразных/жидких веществ; None, если оба слагаемых пустые."""
    return _sum_parts(metrics, ZV_TOTAL_PARTS)


def _sum_parts(metrics: dict | None, attrs: tuple[str, ...]) -> Decimal | None:
    present: list[Decimal] = []
    source = metrics or {}
    for attr in attrs:
        part = _decimal_or_none(source.get(attr))
        if part is not None:
            present.append(part)
    if not present:
        return None
    return sum(present, Decimal("0"))


def apply_zv_derived_metrics(values: dict) -> dict:
    """Подставляет расчётные столбцы ЗВ (газообразные и жидкие, всего)."""
    values = dict(values or {})
    values["gaseous_and_liquid"] = sum_gaseous_and_liquid(values)
    values["total"] = sum_zv_total(values)
    return values


def _metrics_from_record(record, kind: str) -> dict:
    values = {attr: getattr(record, attr, None) for attr, _label in VALUE_COLUMNS[kind]}
    if kind == REPORT_ZV:
        values = apply_zv_derived_metrics(values)
    return values


def _empty_metrics(kind: str) -> dict:
    values = {attr: None for attr, _label in VALUE_COLUMNS[kind]}
    if kind == REPORT_ZV:
        values = apply_zv_derived_metrics(values)
    return values


def _row_from_group(group, report, kind: str, year: int | None) -> dict:
    """Строка страницы: группа из «Топливо», показатели — из отчёта ГИС ТЭК, если есть."""
    ues_name, res_name, ues_sort, res_sort = _ues_res_for_group(group)
    version_id = getattr(group, "database_version_id", None)
    if report is not None:
        version_id = getattr(report, "database_version_id", version_id)
    stations = linked_generation_stations(group, version_id)
    generation_station_name = ", ".join(s["name"] for s in stations) if stations else "—"
    numb = _coerce_numb(getattr(group, "numb", None))
    if report is not None:
        numb = _coerce_numb(getattr(report, "station_numb", None)) or numb
        values = _metrics_from_record(report, kind)
        gis_name = report.gis_tek_station_name or "—"
        station_type = display_station_type(report.station_type)
        rec_id = getattr(report, "id", None)
        year_number = getattr(report, "year_number", None) or year
    else:
        values = _empty_metrics(kind)
        gis_name = "—"
        station_type = "—"
        rec_id = None
        year_number = year
    return {
        "id": rec_id,
        "station_numb": numb,
        "gis_tek_station_name": gis_name,
        "generation_stations": stations,
        "generation_station_name": generation_station_name,
        "equipment_group_id": getattr(group, "id", None),
        "equipment_group_name": equipment_group_title(group),
        "station_type": station_type,
        "year_number": year_number,
        "metrics": values,
        "ues_name": ues_name,
        "res_name": res_name,
        "ues_sort": ues_sort,
        "res_sort": res_sort,
        "eg_sort": (numb if numb is not None else 10**9),
        "gen_company_name": _gen_company_name(group),
    }


def _row_dict(record, kind: str) -> dict:
    group = getattr(record, "equipment_group", None)
    return _row_from_group(group, record, kind, getattr(record, "year_number", None))


def _equipment_group_query(version_id: int | None):
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        restrict_equipment_group_query_to_current_version,
    )

    query = EquipmentGroup.query.options(
        selectinload(EquipmentGroup.regional_energy_system).selectinload(
            RegionalEnergySystem.union_energy_system
        ),
        selectinload(EquipmentGroup.equipment_group_links_v2)
        .selectinload(EquipmentGroupSet.equipment_group_set_station)
        .selectinload(EquipmentGroupSetStation.station),
        selectinload(EquipmentGroup.gen_company_external_mapping),
    )
    return restrict_equipment_group_query_to_current_version(query, version_id)


def build_rows_from_equipment_groups(
    groups: list,
    records: list,
    kind: str,
    year: int | None,
) -> list[dict]:
    """Все группы оборудования текущей версии + наложение строк отчёта ГИС ТЭК."""
    by_numb: dict[int, object] = {}
    unmatched: list = []
    for rec in records or []:
        numb = _coerce_numb(getattr(rec, "station_numb", None))
        if numb is None:
            unmatched.append(rec)
            continue
        by_numb[numb] = rec
    used: set[int] = set()
    rows: list[dict] = []
    for group in groups or []:
        numb = _coerce_numb(getattr(group, "numb", None))
        report = by_numb.get(numb) if numb is not None else None
        if numb is not None and report is not None:
            used.add(numb)
        rows.append(_row_from_group(group, report, kind, year))
    for numb, rec in by_numb.items():
        if numb not in used:
            rows.append(_row_dict(rec, kind))
    for rec in unmatched:
        rows.append(_row_dict(rec, kind))
    return rows


def _build_hierarchy(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple, dict] = {}
    for row in rows:
        ues_key = (row["ues_sort"], row["ues_name"])
        if ues_key not in grouped:
            grouped[ues_key] = {"ues_name": row["ues_name"], "ues_sort": row["ues_sort"], "res_map": {}}
        res_key = (row["res_sort"], row["res_name"])
        res_map = grouped[ues_key]["res_map"]
        if res_key not in res_map:
            res_map[res_key] = {"res_name": row["res_name"], "res_sort": row["res_sort"], "rows": []}
        res_map[res_key]["rows"].append(row)

    hierarchy = []
    for ues_key in sorted(grouped.keys(), key=lambda k: (k[0], k[1])):
        ues_block = grouped[ues_key]
        res_list = []
        for res_key in sorted(ues_block["res_map"].keys(), key=lambda k: (k[0], k[1])):
            block = ues_block["res_map"][res_key]
            block["rows"].sort(
                key=lambda r: (
                    r["eg_sort"],
                    str(r["gis_tek_station_name"] or ""),
                    r["year_number"] or 0,
                )
            )
            res_list.append({"res_name": block["res_name"], "rows": block["rows"], "summary": None})
        hierarchy.append({"ues_name": ues_block["ues_name"], "res_list": res_list, "summary": None})
    return hierarchy


def _row_identity(row: dict) -> tuple:
    return (
        row.get("equipment_group_id"),
        row.get("station_numb"),
        row.get("gis_tek_station_name"),
        row.get("year_number"),
        row.get("id"),
    )


def metrics_are_empty(metrics: dict | None, kind: str) -> bool:
    """True, если все показатели пустые или равны нулю."""
    has_attr = False
    source = metrics or {}
    for attr, _label in VALUE_COLUMNS[kind]:
        has_attr = True
        value = _decimal_or_none(source.get(attr))
        if value is not None and value != 0:
            return False
    return has_attr


def sum_row_metrics(rows: list[dict], kind: str) -> dict:
    """Сумма показателей по строкам; для ЗВ расчётные столбцы пересчитываются."""
    attrs = [attr for attr, _label in VALUE_COLUMNS[kind]]
    out = {attr: None for attr in attrs}
    for row in rows or []:
        metrics = row.get("metrics") or {}
        for attr in attrs:
            if kind == REPORT_ZV and attr in ZV_DERIVED_ATTRS:
                continue
            part = _decimal_or_none(metrics.get(attr))
            if part is None:
                continue
            out[attr] = (out[attr] or Decimal("0")) + part
    if kind == REPORT_ZV:
        return apply_zv_derived_metrics(out)
    return out


def _region_summary(label: str, source_rows: list[dict], kind: str) -> dict:
    metrics = sum_row_metrics(source_rows, kind)
    return {
        "label": label,
        "metrics": metrics,
        "is_empty": metrics_are_empty(metrics, kind),
    }


def attach_gis_tek_region_summaries(
    hierarchy: list[dict],
    all_rows: list[dict],
    display_rows: list[dict],
    page_rows: list[dict],
    kind: str,
) -> None:
    """Итоги РЭС/ОЭС, если на странице последняя строка региона."""
    page_ids = {_row_identity(row) for row in page_rows or []}

    def _last(pool: list[dict], pred) -> dict | None:
        found = None
        for row in pool or []:
            if pred(row):
                found = row
        return found

    for ues_block in hierarchy or []:
        ues_name = ues_block.get("ues_name")
        for res_block in ues_block.get("res_list") or []:
            res_name = res_block.get("res_name")
            last_res = _last(
                display_rows,
                lambda row, ues=ues_name, res=res_name: (
                    row.get("ues_name") == ues and row.get("res_name") == res
                ),
            )
            if last_res is None or _row_identity(last_res) not in page_ids:
                continue
            source = [
                row
                for row in all_rows or []
                if row.get("ues_name") == ues_name and row.get("res_name") == res_name
            ]
            res_block["summary"] = _region_summary(f"{res_name}, всего", source, kind)
        last_ues = _last(
            display_rows,
            lambda row, ues=ues_name: row.get("ues_name") == ues,
        )
        if last_ues is None or _row_identity(last_ues) not in page_ids:
            continue
        source = [row for row in all_rows or [] if row.get("ues_name") == ues_name]
        ues_block["summary"] = _region_summary(f"{ues_name}, всего", source, kind)


def _available_years(model, version_id: int | None) -> tuple[list[int], bool]:
    query = model.query.with_entities(model.year_number).distinct()
    if version_id is not None:
        query = query.filter(model.database_version_id == version_id)
    else:
        query = query.filter(model.database_version_id.is_(None))
    years = sorted({int(y) for (y,) in query.all() if y is not None})
    if years:
        return years, True
    year_q = Year.query.with_entities(Year.number)
    if version_id is not None:
        year_q = year_q.filter(Year.database_version_id == version_id)
    else:
        year_q = year_q.filter(Year.database_version_id.is_(None))
    return sorted({int(y) for (y,) in year_q.all() if y is not None}), False


def _available_station_types(model, version_id: int | None) -> list[str]:
    query = model.query.with_entities(model.station_type).distinct()
    if version_id is not None:
        query = query.filter(model.database_version_id == version_id)
    else:
        query = query.filter(model.database_version_id.is_(None))
    values = []
    for (raw,) in query.all():
        label = display_station_type(raw)
        if label != "—":
            values.append(label)
    return sorted(set(values), key=lambda s: s.lower())


def build_gis_tek_page_context(kind: str, args) -> dict:
    model = REPORT_MODELS[kind]
    version_id = get_current_db_version_id()
    years, years_from_data = _available_years(model, version_id)
    if years_from_data:
        default_year = years[-1]
    else:
        from config import START_YEAR
        default_year = START_YEAR if START_YEAR in years else (years[-1] if years else None)
    selected_year = _parse_year(args.get("year"), default_year)
    if selected_year is not None and years and selected_year not in years:
        selected_year = default_year

    per_page = _parse_per_page(args.get("per_page"))
    try:
        page = int(args.get("page") or 1)
    except (TypeError, ValueError):
        page = 1
    if page < 1:
        page = 1

    q = (args.get("q") or "").strip()
    station_type_filter = (args.get("station_type") or "").strip()
    numb1120_filter = normalize_numb_filter(_args_getlist(args, "numb1120_filter"))
    territory_filters = _parse_gis_tek_territory_filters(args)
    q = str(territory_filters.get("station_name_filter") or q or "").strip()
    show_totals = parse_show_totals_arg(args)
    show_empty_rows = parse_show_empty_rows_arg(args)

    query = model.query
    if version_id is not None:
        query = query.filter(model.database_version_id == version_id)
    else:
        query = query.filter(model.database_version_id.is_(None))
    if selected_year is not None:
        query = query.filter(model.year_number == selected_year)

    records = query.all()
    groups = _equipment_group_query(version_id).all()
    rows = build_rows_from_equipment_groups(groups, records, kind, selected_year)
    rows = apply_gis_tek_territory_filters(
        rows,
        territory_filters,
        matching_eg_ids=_matching_territory_equipment_group_ids(
            territory_filters, version_id
        ),
        matching_ved_eg_ids=_matching_ved_equipment_group_ids(
            rows, territory_filters, selected_year, version_id
        ),
    )
    if station_type_filter:
        rows = [row for row in rows if row["station_type"] == station_type_filter]
    numb1120_filter_choices = collect_numb_filter_choices(rows)
    if numb1120_filter:
        wanted = set(numb1120_filter)
        rows = [
            row
            for row in rows
            if _coerce_numb(row.get("station_numb")) in wanted
        ]
    rows.sort(
        key=lambda r: (
            r["ues_sort"],
            r["ues_name"],
            r["res_sort"],
            r["res_name"],
            r["eg_sort"],
            str(r["gis_tek_station_name"] or ""),
        )
    )
    for row in rows:
        row["is_empty"] = metrics_are_empty(row.get("metrics"), kind)
    display_rows = rows if show_empty_rows else [row for row in rows if not row["is_empty"]]

    total_count = len(display_rows)
    show_all = per_page == "all"
    if show_all:
        page_rows = display_rows
        total_pages = 1
        current_page = 1
        per_page_value = None
    else:
        per_page_int = int(per_page)
        total_pages = max(1, (total_count + per_page_int - 1) // per_page_int) if total_count else 1
        if page > total_pages:
            page = total_pages
        start = (page - 1) * per_page_int
        page_rows = display_rows[start : start + per_page_int]
        current_page = page
        per_page_value = per_page_int

    hierarchy = _build_hierarchy(page_rows)
    if show_totals:
        attach_gis_tek_region_summaries(hierarchy, rows, display_rows, page_rows, kind)

    value_columns = list(VALUE_COLUMNS[kind])
    value_column_groups = list(VALUE_COLUMN_GROUPS.get(kind) or [])
    value_column_banner = ZV_EMISSIONS_BANNER_TITLE if kind == REPORT_ZV else ""
    if value_column_banner and value_column_groups:
        header_rowspan = 3
        group_rowspan = 2
    elif value_column_groups:
        header_rowspan = 2
        group_rowspan = 2
    else:
        header_rowspan = 1
        group_rowspan = 1
    column_count = len(IDENTITY_COLUMNS) + len(value_columns)
    value_column_formulas: dict[str, str] = {}
    if kind == REPORT_ZV:
        from app.ecology.services.formula_text.operating_tes_formula_text_services import (
            ot_formula_text,
        )

        formula = str(ot_formula_text(ZV_GASEOUS_AND_LIQUID_FORMULA_KEY) or "").strip()
        if formula:
            value_column_formulas["gaseous_and_liquid"] = formula
        total_formula = str(ot_formula_text(ZV_TOTAL_FORMULA_KEY) or "").strip()
        if total_formula:
            value_column_formulas["total"] = total_formula

    has_active_filters = bool(
        q
        or station_type_filter
        or numb1120_filter
        or (territory_filters.get("gen_company_filter") or "").strip()
        or (territory_filters.get("ved_filter") or "").strip()
        or _territory_id_filters_active(territory_filters)
    )

    from app.ecology.services.gis_tes_fuel_comparison_services import (
        load_territorial_filter_context,
    )

    context = {
        "kind": kind,
        "page_title": PAGE_TITLES[kind],
        "hierarchy": hierarchy,
        "identity_columns": IDENTITY_COLUMNS,
        "value_columns": value_columns,
        "value_column_groups": value_column_groups,
        "value_column_banner": value_column_banner,
        "header_rowspan": header_rowspan,
        "group_rowspan": group_rowspan,
        "value_column_formulas": value_column_formulas,
        "column_count": column_count,
        "total_count": total_count,
        "current_page": current_page,
        "total_pages": total_pages,
        "per_page": per_page_value,
        "per_page_param": "all" if show_all else str(per_page_value or 25),
        "selected_year": selected_year,
        "filter_year_list": years,
        "station_types": _available_station_types(model, version_id),
        "station_type_filter": station_type_filter,
        "q": q,
        "numb1120_filter": numb1120_filter or [],
        "numb1120_filter_choices": numb1120_filter_choices,
        "has_active_filters": has_active_filters,
        "can_edit": False,
        "form": EmptyCSRFForm(),
        "rounding_digits": 1,
        "show_totals": show_totals,
        "show_empty_rows": show_empty_rows,
    }
    context.update(load_territorial_filter_context(territory_filters))
    return context
