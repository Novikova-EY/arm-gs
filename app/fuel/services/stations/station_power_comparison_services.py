"""Build a year-specific comparison of generation and fuel power records."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from app.common.services.database_version_filter import (
    apply_version_filter,
    get_current_db_version_id,
)
from app.common.services.help_services import format_decimal_trim_for_display
from app.common.services.get_services.years.years_get_services import get_current_year
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_ved_participates,
)
from app.fuel.services.equipment_groups.composite_hierarchy_enrich_services import (
    resolve_composite_parents_by_numb,
    territorial_ids_for_equipment_group,
)
from app.fuel.models.fue_equipment_group_fuel_param_model import EquipmentGroupFuelParam
from app.fuel.models.fue_equipment_group_model import EquipmentGroup
from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation
from app.fuel.models.fue_machine_fuel_param_model import MachineFuelParam
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.station.station_model import Station
from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.energy_systems.union_energy_system_model import UnionEnergySystem
from app.refdata.models.territories.regional_district_model import RegionalDistrict
from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
    EquipmentGroupType,
)

_ZERO = Decimal("0")


def _versioned_rows(model, version_id, *options):
    """Use current-version rows, falling back to legacy rows only if needed."""
    query = model.query.options(*options)
    if version_id is None:
        return query.filter(model.database_version_id.is_(None)).all()

    rows = query.filter(model.database_version_id == version_id).all()
    if rows:
        return rows
    return query.filter(model.database_version_id.is_(None)).all()


def _power(value):
    return value if value is not None else _ZERO


def _add_fuel_totals(target, row):
    """Как в итогах топлива: NUST/NR участвуют при ved>0 независимо от типа группы."""
    if not fuel_param_ved_participates(row.get("ved")):
        return
    _add_totals(target, nust=row.get("nust"), nr=row.get("nr"))


def _add_generation_totals(target, row):
    if not _is_boiler_group_type(row):
        _add_totals(target, p_ust=row.get("p_ust"), p_rasp=row.get("p_rasp"))


def _add_totals(target, p_ust=None, p_rasp=None, nust=None, nr=None):
    target["p_ust"] += _power(p_ust)
    target["p_rasp"] += _power(p_rasp)
    target["nust"] += _power(nust)
    target["nr"] += _power(nr)


def _new_totals():
    return {"p_ust": _ZERO, "p_rasp": _ZERO, "nust": _ZERO, "nr": _ZERO}


def _station_path(station):
    """Названия не входят в ключ: name и name_full могут различаться."""
    from app.fuel.services.stations.stations_equipment_groups_services import (
        _hierarchy_key_from_station,
    )

    return _hierarchy_key_from_station(station)[:3]


def _equipment_group_path(group, parent_by_numb=None):
    path = territorial_ids_for_equipment_group(group, parent_by_numb)
    return None if path == (-1, -1, -1) else path


def _name(group):
    return (getattr(group, "name", None) or getattr(group, "name_ext", None) or "").strip()



def _hierarchy_sort_key(item):
    """Order of /fuel/stations_equipment_groups: named entries, then «Не указано»."""
    key, node = item
    return (
        1 if key in (None, -1) else 0,
        (node["name"] or "").strip().lower(),
        key if key is not None else -1,
    )

def _empty_group_node(name, key):
    return {"name": name, "key": key, "totals": _new_totals(), "children": {}}


def _ved0_parts_check(parent_row, child_rows, *, show_p_rasp=False):
    """Сравнивает строку-оболочку ved=0 с суммой прямых дочерних групп."""
    if not child_rows:
        return None
    parts = _new_totals()
    for row in child_rows:
        if row.get("has_param"):
            _add_fuel_totals(parts, row)
    return {
        "parts_nust": parts["nust"],
        "parts_nr": parts["nr"],
        "nust_mismatch": _power(parent_row.get("nust")) != parts["nust"],
        "nr_mismatch": show_p_rasp and _power(parent_row.get("nr")) != parts["nr"],
    }


def _without_ved0_rows(rows):
    """Прячет строки-оболочки ved=0, пока не включён переключатель VED=0."""
    return [row for row in rows if row.get("ved") != 0]


def _is_boiler_group_type(row):
    return any(
        group_type.strip().casefold() == "котельная"
        for group_type in (row.get("group_type") or "").split(";")
    )


def _without_boiler_rows(rows):
    return [row for row in rows if not _is_boiler_group_type(row)]


def _mark_equipment_group_rowspans(rows):
    """Помечает строки агрегатов, чтобы название группы выводилось один раз."""
    grouped = {}
    for index, row in enumerate(rows):
        group_id = row.get("equipment_group_id")
        key = ("group", group_id) if group_id is not None else ("row", index)
        grouped.setdefault(key, []).append(row)

    ordered_groups = sorted(
        grouped.values(),
        key=lambda group: (
            group[0].get("machine_sort_key", ()),
            group[0].get("machine_id") or 0,
        ),
    )
    result = []
    for group in ordered_groups:
        group[0]["equipment_group_cell_first"] = True
        group[0]["equipment_group_cell_rowspan"] = len(group)
        for row in group[1:]:
            row["equipment_group_cell_first"] = False
        result.extend(group)
    return result


def _comparison_row_groups(rows):
    leading_rows = []
    rows = list(rows)
    while rows and rows[0].get("kind") in {
        "unassigned", "unassigned_station", "unclassified"
    }:
        leading_rows.append(rows.pop(0))

    groups = []
    current_group = []
    for row in rows:
        if row.get("kind") == "numb" and current_group:
            groups.append(current_group)
            current_group = []
        current_group.append(row)
    if current_group:
        groups.append(current_group)
    if leading_rows:
        if groups:
            groups[0] = leading_rows + groups[0]
        else:
            groups.append(leading_rows)
    return groups


def _paginate_comparison_items(items, page, page_size=50):
    pages = []
    page_items = []
    row_count = 0
    for item in items:
        if row_count >= page_size:
            pages.append(page_items)
            page_items = []
            row_count = 0
        page_items.append(item)
        row_count += len(item["rows"])
    if page_items or not pages:
        pages.append(page_items)

    try:
        requested_page = int(page)
    except (TypeError, ValueError):
        requested_page = 1
    current_page = max(1, min(requested_page, len(pages)))
    return current_page, len(pages), pages[current_page - 1]


def _equipment_group_key(row):
    group_id = row.get("equipment_group_id", row.get("group_id"))
    if group_id is not None:
        return ("id", group_id)
    name = (row.get("group_name") or "").strip()
    group_type = (row.get("group_type") or "").strip()
    if name and name != "—":
        return ("name", name.casefold(), group_type.casefold())
    if group_type and group_type != "—":
        return ("type", group_type.casefold())
    return None


def _collapse_single_equipment_group(
    station_row, *, show_p_rasp=False, show_ved0=False, rounding_digits=0
):
    """Собирает мощности всех агрегатов единственной группы в одну строку."""
    generation_rows = station_row["generation_rows"]
    if not generation_rows or any(_is_boiler_group_type(row) for row in generation_rows):
        return None

    group_keys = {_equipment_group_key(row) for row in generation_rows}
    if len(group_keys) != 1 or None in group_keys:
        return None

    fuel_rows = station_row["fuel_rows"]
    if not show_ved0:
        fuel_rows = _without_ved0_rows(fuel_rows)
    equipment_group_id = generation_rows[0].get("equipment_group_id")
    source_rows = generation_rows + fuel_rows
    numb_values = {row.get("numb") for row in source_rows}
    if len(numb_values) > 1:
        return None
    numb = next(iter(numb_values), None)
    if equipment_group_id is not None and any(
        row.get("group_id") != equipment_group_id for row in fuel_rows
    ):
        return None
    if equipment_group_id is None and numb is None and len({row.get("group_id") for row in fuel_rows}) > 1:
        return None

    totals = _new_totals()
    for row in generation_rows:
        _add_generation_totals(totals, row)
    comparable_fuel_rows = [
        row for row in fuel_rows
        if fuel_param_ved_participates(row.get("ved"))
    ]
    for row in comparable_fuel_rows:
        _add_fuel_totals(totals, row)

    machine_numbers = list(dict.fromkeys(
        row["machine_number"]
        for row in generation_rows
        if row.get("machine_number") and row["machine_number"] != "—"
    ))
    machine_types = list(dict.fromkeys(
        row["machine_type"]
        for row in generation_rows
        if row.get("machine_type") and row["machine_type"] != "—"
    ))
    group_types = list(dict.fromkeys(
        row["group_type"]
        for row in generation_rows
        if row.get("group_type") and row["group_type"] != "—"
    ))
    ved_values = list(dict.fromkeys(row["ved"] for row in fuel_rows))
    has_param = bool(fuel_rows) and all(row["has_param"] for row in fuel_rows)
    ved = ved_values[0] if len(ved_values) == 1 else None
    ved_display = ", ".join(
        "NULL" if value is None else str(value) for value in ved_values
    )
    ved_warning = any(value is None or value <= 0 for value in ved_values)
    has_numb_comparison = numb is not None and (
        not fuel_rows or bool(comparable_fuel_rows)
    )
    archived = any(row["is_archived"] for row in generation_rows)
    has_power_row = all(row["has_power_row"] for row in generation_rows)

    return {
        "kind": "station_group",
        "label": station_row["name"],
        "station_id": station_row["station"].id,
        "equipment_group_id": equipment_group_id,
        "stations": [{"id": station_row["station"].id, "name": station_row["name"]}],
        "machines": [
            {
                "id": row["machine_id"],
                "station_id": row.get("station_id", station_row["station"].id),
                "name": row["machine_type"],
            }
            for row in generation_rows
        ],
        "group_name": generation_rows[0]["group_name"],
        "group_type": "; ".join(group_types) or "—",
        "machine_number": ", ".join(machine_numbers) or "—",
        "machine_type": "; ".join(machine_types) or "—",
        "numb": numb,
        **totals,
        "p_ust_mismatch": has_numb_comparison and not _totals_match(
            totals["p_ust"], totals["nust"], rounding_digits
        ),
        "p_rasp_mismatch": show_p_rasp and has_numb_comparison and not _totals_match(
            totals["p_rasp"], totals["nr"], rounding_digits
        ),
        "has_numb_comparison": has_numb_comparison,
        "has_param": has_param,
        "ved": ved,
        "ved_display": ved_display,
        "ved_warning": ved_warning,
        "has_power_row": has_power_row,
        "is_archived": archived,
        "title": (
            f"Станция «{station_row['name']}»; группа «{generation_rows[0]['group_name']}»; "
            f"агрегатов: {len(generation_rows)}; ID агрегатов: "
            + ", ".join(str(row["machine_id"]) for row in generation_rows)
        ),
    }


def _collapse_shared_equipment_group(
    group_id, station_rows, fuel_rows, *, show_p_rasp=False, show_ved0=False,
    rounding_digits=0,
):
    """Собирает агрегаты одной группы с разных станций в общую строку."""
    member_rows = [
        station_row for station_row in station_rows
        if any(
            row.get("equipment_group_id") == group_id
            for row in station_row["generation_rows"]
        )
    ]
    if len(member_rows) < 2:
        return None

    generation_rows = [
        row
        for station_row in member_rows
        for row in station_row["generation_rows"]
        if row.get("equipment_group_id") == group_id
    ]
    first_station = member_rows[0]
    station_names = [row["name"] for row in member_rows]
    merged_station = {
        "name": " / ".join(station_names),
        "station": first_station["station"],
        "generation_rows": generation_rows,
        "fuel_rows": fuel_rows,
    }
    result = _collapse_single_equipment_group(
        merged_station,
        show_p_rasp=show_p_rasp,
        show_ved0=show_ved0,
        rounding_digits=rounding_digits,
    )
    if result is None:
        return None

    result["stations"] = [
        {"id": row["station"].id, "name": row["name"]}
        for row in member_rows
    ]
    result["machines"] = [
        {
            "id": row["machine_id"],
            "station_id": row["station_id"],
            "name": row["machine_type"],
        }
        for row in generation_rows
    ]
    result["label"] = " / ".join(station_names)
    result["title"] = (
        f"Станции: {', '.join(station_names)}; группа «{result['group_name']}»; "
        f"агрегатов: {len(generation_rows)}; ID агрегатов: "
        + ", ".join(str(row["machine_id"]) for row in generation_rows)
    )
    return result


def _rounded_for_comparison(value, rounding_digits):
    """Значение или его округлённый показ, чтобы сравнение шло по видимым числам."""
    return format_decimal_trim_for_display(value, digits=rounding_digits)


def _totals_match(left, right, rounding_digits):
    return _rounded_for_comparison(left, rounding_digits) == _rounded_for_comparison(
        right, rounding_digits
    )


def _station_comparison_rows(
    station_row, *, show_p_rasp=False, show_ved0=False, show_boilers=False,
    rounding_digits=0,
):

    generation_rows = station_row["generation_rows"]
    fuel_rows = station_row["fuel_rows"]
    visible_totals = _new_totals()
    for row in generation_rows:
        _add_generation_totals(visible_totals, row)
    for row in fuel_rows:
        _add_fuel_totals(visible_totals, row)
    if not show_boilers:
        generation_rows = _without_boiler_rows(generation_rows)
        fuel_rows = _without_boiler_rows(fuel_rows)
    if not show_ved0:
        fuel_rows = _without_ved0_rows(fuel_rows)
    if not generation_rows and not fuel_rows:
        return []

    station_row = {
        **station_row,
        "generation_rows": generation_rows,
        "fuel_rows": fuel_rows,
        "totals": visible_totals,
    }
    generation_by_group = defaultdict(list)
    for index, row in enumerate(station_row["generation_rows"]):
        key = _equipment_group_key(row)
        if key is None:
            key = ("machine", row.get("machine_id", index))
        generation_by_group[key].append(row)

    fuel_by_group = defaultdict(list)
    for index, row in enumerate(station_row["fuel_rows"]):
        key = _equipment_group_key(row)
        if key is None:
            key = ("fuel", row.get("fuel_param_id", index))
        fuel_by_group[key].append(row)

    group_keys = set(generation_by_group) | set(fuel_by_group)
    station_header = {
        "kind": "station",
        "label": station_row["name"],
        "station_id": station_row["station"].id,
        "has_records": True,
        **station_row["totals"],
    }
    if len(group_keys) <= 1:
        collapsed = _collapse_single_equipment_group(
            station_row,
            show_p_rasp=show_p_rasp,
            show_ved0=show_ved0,
            rounding_digits=rounding_digits,
        )
        if collapsed is not None:
            return [collapsed]
        detail_rows = _rows_with_numb_subtotals(
            station_row["generation_rows"],
            station_row["fuel_rows"],
            show_p_rasp=show_p_rasp,
            show_ved0=show_ved0,
            show_boilers=show_boilers,
            rounding_digits=rounding_digits,
        )
        if not detail_rows:
            return []
        return [station_header] + detail_rows

    rows = [station_header]
    generation_keys = set(generation_by_group)
    parent_numbs = {
        row.get("numb") for row in station_row["fuel_rows"]
        if row.get("ved") == 0 and row.get("numb") is not None
    }
    ordered_generation_keys = sorted(
        generation_keys,
        key=lambda key: (
            generation_by_group[key][0].get("machine_sort_key", ()),
            generation_by_group[key][0].get("machine_id") or 0,
        ),
    )
    for key in ordered_generation_keys:
        generation_rows = generation_by_group[key]
        group_row = {
            **station_row,
            "generation_rows": generation_rows,
            "fuel_rows": fuel_by_group.get(key, []),
        }
        collapsed = _collapse_single_equipment_group(
            group_row,
            show_p_rasp=show_p_rasp,
            show_ved0=show_ved0,
            rounding_digits=rounding_digits,
        )
        is_composite_child = any(
            row.get("equipment_group_main") in parent_numbs
            for row in generation_rows
        )
        if collapsed is not None:
            collapsed["show_station_label"] = False
            if is_composite_child:
                collapsed["tree_prefix"] = "└"
            rows.append(collapsed)
            continue

        detail_rows = _rows_with_numb_subtotals(
            generation_rows,
            fuel_by_group.get(key, []),
            show_p_rasp=show_p_rasp,
            show_ved0=show_ved0,
            show_boilers=show_boilers,
            rounding_digits=rounding_digits,
        )
        if is_composite_child:
            for detail_row in detail_rows:
                if detail_row.get("kind") in ("generation", "generation_orphan", "fuel"):
                    detail_row["tree_prefix"] = "└"
        rows.extend(detail_rows)

    fuel_only_keys = set(fuel_by_group) - generation_keys
    for key in sorted(
        fuel_only_keys,
        key=lambda item: (
            fuel_by_group[item][0].get("numb") is None,
            fuel_by_group[item][0].get("numb") or 0,
            fuel_by_group[item][0].get("group_id") or 0,
        ),
    ):
        detail_rows = _rows_with_numb_subtotals(
            [], fuel_by_group[key], show_p_rasp=show_p_rasp,
            show_ved0=show_ved0,
            show_boilers=show_boilers,
            rounding_digits=rounding_digits,
        )
        for detail_row in detail_rows:
            if (
                detail_row.get("kind") == "fuel"
                and detail_row.get("equipment_group_main") in parent_numbs
            ):
                detail_row["tree_prefix"] = "└"
        rows.extend(detail_rows)
    return rows


def _rows_with_numb_subtotals(
    generation_rows,
    fuel_rows,
    *,
    separate_fuel_groups=False,
    show_p_rasp=False,
    show_ved0=False,
    show_boilers=False,
    rounding_digits=0,
):
    """Добавляет по каждому numb итог генерации и топливных параметров."""
    if not show_boilers:
        generation_rows = _without_boiler_rows(generation_rows)
        fuel_rows = _without_boiler_rows(fuel_rows)
    if not show_ved0:
        fuel_rows = _without_ved0_rows(fuel_rows)
    groups = {}

    unnumbered_generation = []
    unnumbered_fuel = []
    ved0_fuel_rows = []
    ved0_numbs = {row.get("numb") for row in fuel_rows if row.get("ved") == 0}

    for row in generation_rows:
        numb = row.get("numb")
        if numb is None:
            unnumbered_generation.append(row)
            continue
        group = groups.setdefault(numb, {"generation": [], "fuel": []})
        group["generation"].append(row)

    for row in fuel_rows:
        numb = row.get("numb")
        if row.get("ved") == 0:
            ved0_fuel_rows.append(row)
            continue
        if numb is None:
            unnumbered_fuel.append(row)
            continue
        key = (numb, row.get("group_id")) if separate_fuel_groups else numb
        group = groups.setdefault(key, {"generation": [], "fuel": []})
        group["fuel"].append(row)

    group_counts_by_numb = {}
    for key in groups:
        numb = key[0] if isinstance(key, tuple) else key
        group_counts_by_numb[numb] = group_counts_by_numb.get(numb, 0) + 1

    result = []
    for key in sorted(groups, key=lambda value: (value[0] if isinstance(value, tuple) else value)):
        group = groups[key]
        numb = key[0] if isinstance(key, tuple) else key
        totals = _new_totals()
        for row in group["generation"]:
            _add_generation_totals(totals, row)
        for row in group["fuel"]:
            _add_fuel_totals(totals, row)
        ignore_comparison = numb in ved0_numbs and not group["fuel"]
        subtotal = {
            "kind": "numb",
            "numb": numb,
            **totals,
            "p_ust_mismatch": not ignore_comparison and not _totals_match(
                totals["p_ust"], totals["nust"], rounding_digits
            ),
            "p_rasp_mismatch": show_p_rasp and not ignore_comparison
            and not _totals_match(totals["p_rasp"], totals["nr"], rounding_digits),
        }
        source_rows = group["generation"] + group["fuel"]
        boiler_group = bool(source_rows) and all(
            _is_boiler_group_type(row) for row in source_rows
        )
        redundant_fuel_subtotal = (
            not group["generation"]
            and len(group["fuel"]) == 1
            and group_counts_by_numb[numb] == 1
        )
        generation_rows_marked = _mark_equipment_group_rowspans(group["generation"])
        if not ignore_comparison and not boiler_group and not redundant_fuel_subtotal:
            result.append(subtotal)
        result.extend(generation_rows_marked)
        result.extend(group["fuel"])

    result.extend(_mark_equipment_group_rowspans(unnumbered_generation))
    result.extend(unnumbered_fuel)
    if show_ved0:
        result.extend(ved0_fuel_rows)
    return result


def _tpp_station_ids(version_id):
    """Stations shown on /fuel/stations_equipment_groups (StationType 'ТЭС')."""
    from app.refdata.models.refdata_for_stations.station.station_type_model import (
        StationType,
    )

    station_type = (
        apply_version_filter(StationType.query, StationType)
        .filter(func.lower(StationType.name) == "тэс")
        .first()
    )
    if station_type is None:
        station_type = (
            apply_version_filter(StationType.query, StationType)
            .filter(StationType.name.ilike("%тэс%"))
            .order_by(StationType.id)
            .first()
        )
    if station_type is None:
        return set()

    query = Station.query.filter(Station.id_station_type == station_type.id)
    if version_id is None:
        query = query.filter(Station.database_version_id.is_(None))
    else:
        current = query.filter(Station.database_version_id == version_id).all()
        if current:
            return {station.id for station in current}
        query = query.filter(Station.database_version_id.is_(None))
    return {station.id for station in query.all()}


def build_station_power_comparison(
    selected_year=None, page=1, show_p_rasp=False, show_ved0=False,
    show_boilers=False, rounding_digits=0, *, paginate=True,
):
    """Return all current-version machine and fuel power rows for one year.

    Only TPP stations are shown, ordered by type of energy system, ОЭС, РЭС and
    station like /fuel/stations_equipment_groups. Machine records without a
    power row remain visible with empty power cells. Fuel rows with no unique
    station link are retained once in an unassigned bucket, never copied onto
    multiple stations.

    Столбец Ррасп и его сравнение с NR включаются только при
    show_p_rasp=True. Строки ved=0 отображаются только при show_ved0=True;
    котельные группы — только при show_boilers=True. Итоги топлива включают
    все строки ved>0 по территории группы, как на /fuel/totals_summary.
    Котельные агрегаты генерации исключены из Руст/Ррасп.
    rounding_digits задаёт
    только показ чисел: сравнение Руст с NUST идёт по округлённым значениям,
    которые видит пользователь. paginate=False возвращает все строки для Excel.
    """
    version_id = get_current_db_version_id()
    from app.common.services.get_services.energy_systems.energy_system_type_get_services import (
        get_energy_system_type_map,
    )
    from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
        get_regional_energy_systems_map,
    )
    from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
        get_union_energy_system_display_order_map,
        get_union_energy_systems_map,
        union_energy_system_hierarchy_sort_key,
    )
    from app.fuel.services.stations.stations_equipment_groups_services import (
        _machine_number_sort_key,
    )

    est_names = get_energy_system_type_map()
    ues_names = get_union_energy_systems_map()
    res_names = get_regional_energy_systems_map()
    est_names[-1] = est_names.get(-1) or "Не указано"
    ues_names[-1] = ues_names.get(-1) or "Не указано"
    res_names[-1] = res_names.get(-1) or "Не указано"
    ues_display_orders = get_union_energy_system_display_order_map()
    tpp_station_ids = _tpp_station_ids(version_id)
    all_stations = _versioned_rows(
        Station,
        version_id,
        joinedload(Station.regional_energy_system_obj).joinedload(
            RegionalEnergySystem.union_energy_system
        ).joinedload(UnionEnergySystem.energy_system_type),
        joinedload(Station.regional_district).selectinload(
            RegionalDistrict.regional_energy_systems
        ).joinedload(RegionalEnergySystem.union_energy_system).joinedload(
            UnionEnergySystem.energy_system_type
        ),
    )
    all_stations_by_id = {station.id: station for station in all_stations}
    stations = [station for station in all_stations if station.id in tpp_station_ids]
    machines = [
        machine
        for machine in _versioned_rows(
            Machine,
            version_id,
            joinedload(Machine.equipment_group),
        )
        if machine.id_station in tpp_station_ids
    ]
    machine_ids = {machine.id for machine in machines}
    powers = [
        power
        for power in _versioned_rows(MachinePower, version_id)
        if power.id_machine in machine_ids
    ]
    groups = _versioned_rows(
        EquipmentGroup,
        version_id,
        joinedload(EquipmentGroup.regional_energy_system)
        .joinedload(RegionalEnergySystem.union_energy_system)
        .joinedload(UnionEnergySystem.energy_system_type),
    )
    equipment_group_types_by_id = {
        group_type.id: group_type.name
        for group_type in _versioned_rows(EquipmentGroupType, version_id)
    }
    fuel_params = _versioned_rows(EquipmentGroupFuelParam, version_id)
    set_stations = _versioned_rows(EquipmentGroupSetStation, version_id)
    machine_fuel_params = [
        param
        for param in _versioned_rows(MachineFuelParam, version_id)
        if param.machine_id in machine_ids
    ]
    groups_by_id = {group.id: group for group in groups}

    # A group can be linked to several station/type pairs. Keep its fuel row
    # singular and only assign it to a station if there is exactly one target.
    set_station_by_id = {row.id: row for row in set_stations}
    group_links = defaultdict(list)
    for link in EquipmentGroupSet.query.all():
        set_station = set_station_by_id.get(link.equipment_group_set_station_id)
        if set_station is not None and link.equipment_group_id in groups_by_id:
            group_links[link.equipment_group_id].append(set_station)

    group_station_ids = {}
    group_all_station_ids = {}
    group_station_type_ids = {}
    for group_id, links in group_links.items():
        all_station_ids = {link.station_id for link in links if link.station_id is not None}
        station_ids = {station_id for station_id in all_station_ids if station_id in tpp_station_ids}
        group_all_station_ids[group_id] = all_station_ids
        group_station_ids[group_id] = station_ids
        group_station_type_ids[group_id] = {
            (link.station_id, link.equipment_group_type_id)
            for link in links
            if link.station_id in tpp_station_ids
        }

    tpp_group_ids = {
        group_id
        for group_id, station_ids in group_all_station_ids.items()
        if station_ids & tpp_station_ids
    }
    comparison_group_ids = set(groups_by_id)
    tpp_groups_by_id = {
        group_id: groups_by_id[group_id]
        for group_id in tpp_group_ids
        if group_id in groups_by_id
    }
    comparison_groups_by_id = {
        group_id: groups_by_id[group_id]
        for group_id in comparison_group_ids
        if group_id in groups_by_id
    }
    fuel_params = [
        param for param in fuel_params if param.equipment_group_id in comparison_group_ids
    ]
    parent_by_numb = resolve_composite_parents_by_numb(
        [(group, None) for group in groups], database_version_id=version_id,
    )

    available_years = sorted(
        {
            row.year_number
            for row in [*powers, *fuel_params]
            if row.year_number is not None
        },
        reverse=True,
    )
    has_yearless_rows = any(row.year_number is None for row in [*powers, *fuel_params])
    year_choices = [{"value": year, "label": str(year)} for year in available_years]
    if has_yearless_rows:
        year_choices.append({"value": "", "label": "Без года"})

    current_year = get_current_year()
    if selected_year is None:
        selected_year = current_year if current_year in available_years else None
        if selected_year is None and available_years:
            prior_years = [year for year in available_years if current_year and year <= current_year]
            selected_year = prior_years[0] if prior_years else available_years[0]
        if selected_year is None and has_yearless_rows:
            selected_year = ""
    elif selected_year != "" and selected_year not in available_years:
        selected_year = current_year if current_year in available_years else (available_years[0] if available_years else "")
    elif selected_year is None:
        selected_year = ""

    def in_selected_year(row):
        return row.year_number is None if selected_year == "" else row.year_number == selected_year

    selected_powers = [row for row in powers if in_selected_year(row)]
    power_by_machine = {row.id_machine: row for row in selected_powers if row.id_machine is not None}

    stations_by_id = {station.id: station for station in stations}
    machine_by_id = {machine.id: machine for machine in machines}
    machine_fuel_group_by_machine = {
        row.machine_id: row.equipment_group_id
        for row in machine_fuel_params
        if row.equipment_group_id in tpp_group_ids
    }

    # Resolve a readable Fuel EquipmentGroup name for each generation machine.
    groups_by_station_type = defaultdict(list)
    for group_id, type_links in group_station_type_ids.items():
        for station_id, group_type_id in type_links:
            if station_id in stations_by_id and group_id in tpp_groups_by_id:
                groups_by_station_type[(station_id, group_type_id)].append(tpp_groups_by_id[group_id])

    station_data = {}
    hierarchy = {}
    for station in stations:
        path = _station_path(station)
        station_data[station.id] = {
            "name": station.name,
            "station": station,
            "path": path,
            "totals": _new_totals(),
            "generation_rows": [],
            "fuel_rows": [],
        }
        est_node = hierarchy.setdefault(path[0], _empty_group_node(est_names.get(path[0], "Не указано"), path[0]))
        ues_node = est_node["children"].setdefault(path[1], _empty_group_node(ues_names.get(path[1], "Не указано"), path[1]))
        ues_node["children"].setdefault(path[2], _empty_group_node(res_names.get(path[2], "Не указано"), path[2]))

    generation_count = 0
    unassigned_totals = _new_totals()
    unmapped_totals = _new_totals()
    unassigned_generation_rows = []
    # Include every current Machine, including archived machines and machines
    # without a power row for the selected year.
    for machine in machines:
        station_id = machine.id_station if machine.id_station in station_data else None
        power = power_by_machine.get(machine.id)
        explicit_group_id = machine_fuel_group_by_machine.get(machine.id)
        equipment_group = tpp_groups_by_id.get(explicit_group_id)
        if equipment_group is None and machine.id_equipment_group is not None and station_id is not None:
            candidates = groups_by_station_type.get((station_id, machine.id_equipment_group), [])
            if len(candidates) == 1:
                equipment_group = candidates[0]
        row = {
            "kind": "generation",
            "machine_id": machine.id,
            "station_id": station_id,
            "group_name": _name(equipment_group) or "—",
            "equipment_group_id": equipment_group.id if equipment_group else None,
            "equipment_group_main": getattr(equipment_group, "main", None),
            "group_type": getattr(machine.equipment_group, "name", None) or "—",
            "machine_number": machine.machine_number or "—",
            "machine_sort_key": _machine_number_sort_key(machine),
            "machine_type": machine.machine_name or "—",
            "numb": equipment_group.numb if equipment_group else None,
            "p_ust": power.p_ust if power else None,
            "p_rasp": power.p_rasp if power else None,
            "has_power_row": power is not None,
            "is_archived": bool(machine.is_archived),
            "title": (
                f"Агрегат ID {machine.id}; запись мощности ID {power.id}; год {selected_year}"
                if power
                else f"Агрегат ID {machine.id}; за {selected_year or 'год не указан'} записи мощности нет"
            ),
        }
        if station_id is None:
            row["station_name"] = "Без станции / нет связи"
            row["path"] = None
            _add_generation_totals(unassigned_totals, row)
            _add_generation_totals(unmapped_totals, row)
            unassigned_generation_rows.append(row)
        else:
            station_row = station_data[station_id]
            row["path"] = station_row["path"]
            station_row["generation_rows"].append(row)
            _add_generation_totals(station_row["totals"], row)
        generation_count += 1

    # Power rows with no current-version Machine are still displayed and totaled.
    orphan_power_rows = [row for row in selected_powers if row.id_machine not in machine_by_id]
    for power in orphan_power_rows:
        row = {
            "kind": "generation_orphan",
            "machine_id": None,
            "group_name": "—",
            "group_type": "—",
            "machine_number": "—",
            "numb": None,
            "machine_type": f"Запись мощности без агрегата (ID {power.id_machine or 'NULL'})",
            "p_ust": power.p_ust,
            "p_rasp": power.p_rasp,
            "has_power_row": True,
            "is_archived": False,
            "title": f"MachinePower ID {power.id}; ID агрегата отсутствует в текущей версии",
        }
        row["path"] = None
        unassigned_generation_rows.append(row)
        _add_totals(unassigned_totals, power.p_ust, power.p_rasp)
        _add_totals(unmapped_totals, power.p_ust, power.p_rasp)
        generation_count += 1

    fuel_count = 0
    unresolved_fuel_rows = []
    fuel_by_group_id = defaultdict(list)
    for param in fuel_params:
        if in_selected_year(param):
            fuel_by_group_id[param.equipment_group_id].append(param)

    fuel_group_row_count = 0
    fuel_group_without_param_count = 0
    unclassified_fuel_rows = []
    unclassified_fuel_totals = _new_totals()
    for group_id in sorted(set(comparison_groups_by_id) | set(fuel_by_group_id)):
        params = fuel_by_group_id.get(group_id) or [None]
        group = comparison_groups_by_id.get(group_id)
        target_station_ids = group_station_ids.get(group_id, set())
        all_station_ids = group_all_station_ids.get(group_id, set())
        target_station_id = (
            next(iter(target_station_ids))
            if len(all_station_ids) == 1 and len(target_station_ids) == 1
            else None
        )
        fuel_path = _equipment_group_path(group, parent_by_numb)
        if target_station_id is not None and station_data[target_station_id]["path"] != fuel_path:
            target_station_id = None
        for param in params:
            has_param = param is not None
            ambiguous_names = sorted(
                (
                    all_stations_by_id[station_id].name
                    + (" (не ТЭС)" if station_id not in tpp_station_ids else "")
                )
                if station_id in all_stations_by_id
                else f"ID станции {station_id} (нет в текущей версии)"
                for station_id in all_station_ids
            )
            type_ids = {
                link.equipment_group_type_id
                for link in group_links.get(group_id, [])
                if link.equipment_group_type_id is not None
                and (target_station_id is None or link.station_id == target_station_id)
            }
            group_type = "; ".join(sorted({
                equipment_group_types_by_id[type_id]
                for type_id in type_ids
                if type_id in equipment_group_types_by_id
            })) or "—"
            row = {
                "kind": "fuel",
                "fuel_param_id": param.id if has_param else None,
                "group_id": group_id,
                "group_name": _name(group) or "—",
                "group_type": group_type,
                "equipment_group_main": getattr(group, "main", None),
                "numb": group.numb if group else None,
                "nust": param.nust if has_param else None,
                "nr": param.nr if has_param else None,
                "ved": param.ved if has_param else None,
                "year": param.year_number if has_param else selected_year,
                "has_param": has_param,
                "station_name": (
                    stations_by_id[target_station_id].name
                    if target_station_id is not None
                    else (
                        "Несколько станций: " + ", ".join(ambiguous_names)
                        if all_station_ids
                        else "Без связи со станцией — тип ТЭС не подтверждён"
                    )
                ),
                "ambiguous_stations": ambiguous_names if len(all_station_ids) > 1 else [],
                "ambiguous_station_links": [
                    {"id": station_id, "name": all_stations_by_id[station_id].name}
                    for station_id in sorted(all_station_ids)
                    if station_id in all_stations_by_id
                ] if len(all_station_ids) > 1 else [],
                "tpp_linked": bool(all_station_ids & tpp_station_ids),
                "title": (
                    f"EquipmentGroupFuelParam ID {param.id}; группа ID {group_id}; год {param.year_number}; "
                    f"ved={param.ved if param.ved is not None else 'NULL'}; группа «{_name(group) or 'без названия'}»"
                    + (f"; связи со станциями: {', '.join(ambiguous_names)}" if len(all_station_ids) > 1 else "")
                    if has_param
                    else f"Группа топлива ID {group_id}; numb={group.numb if group else 'NULL'}; за {selected_year or 'год не указан'} записи NUST/NR нет"
                ),
            }
            if target_station_id is not None:
                station_row = station_data[target_station_id]
                row["station_id"] = target_station_id
                station_row["fuel_rows"].append(row)
                _add_fuel_totals(station_row["totals"], row)
            else:
                row["path"] = fuel_path
                unresolved_fuel_rows.append(row)
                _add_fuel_totals(unassigned_totals, row)
                if fuel_path is None:
                    _add_fuel_totals(unmapped_totals, row)
                    if not row["tpp_linked"]:
                        unclassified_fuel_rows.append(row)
                        _add_fuel_totals(unclassified_fuel_totals, row)
            fuel_group_row_count += 1
            if has_param:
                fuel_count += 1
            else:
                fuel_group_without_param_count += 1

    # Annotate parent rows ved=0 by comparing them only with linked child groups.
    for station_row in station_data.values():
        station_id = station_row["station"].id
        for parent_row in station_row["fuel_rows"]:
            if parent_row["ved"] != 0 or parent_row["numb"] is None:
                continue
            expected_child_ids = {
                group.id
                for group in groups
                if group.main == parent_row["numb"]
                and station_id in group_station_ids.get(group.id, set())
            }
            if not expected_child_ids:
                continue
            children = [
                row for row in station_row["fuel_rows"]
                if row["group_id"] in expected_child_ids
            ]
            if {row["group_id"] for row in children} != expected_child_ids:
                continue
            parent_row["ved0_check"] = _ved0_parts_check(
                parent_row, children, show_p_rasp=show_p_rasp
            )

    # Record totals and detail rows at the first identifiable regional level.
    for station_row in station_data.values():
        est_key, ues_key, res_key = station_row["path"]
        est_node = hierarchy[est_key]
        ues_node = est_node["children"][ues_key]
        res_node = ues_node["children"][res_key]
        _add_totals(est_node["totals"], **station_row["totals"])
        _add_totals(ues_node["totals"], **station_row["totals"])
        _add_totals(res_node["totals"], **station_row["totals"])
        station_row["generation_rows"].sort(
            key=lambda row: (row["machine_sort_key"], row["machine_id"] or 0)
        )
        station_row["fuel_rows"].sort(key=lambda row: (row["numb"] is None, row["numb"] or 0, row["group_id"] or 0))

    # Place unassigned fuel rows under their own region when its metadata permits;
    # rows without a complete path remain visible in the global unassigned block.
    fuel_rows_by_path = defaultdict(list)
    for row in unresolved_fuel_rows:
        if row["path"] is not None:
            path = row["path"]
            est_node = hierarchy.setdefault(path[0], _empty_group_node(est_names.get(path[0], "Не указано"), path[0]))
            ues_node = est_node["children"].setdefault(path[1], _empty_group_node(ues_names.get(path[1], "Не указано"), path[1]))
            res_node = ues_node["children"].setdefault(path[2], _empty_group_node(res_names.get(path[2], "Не указано"), path[2]))
            _add_fuel_totals(est_node["totals"], row)
            _add_fuel_totals(ues_node["totals"], row)
            _add_fuel_totals(res_node["totals"], row)
            fuel_rows_by_path[path].append(row)
            row["assigned_by_region"] = True
        else:
            row["assigned_by_region"] = False

    shared_rows_by_path = defaultdict(list)
    shared_station_ids = set()
    shared_fuel_group_ids = set()
    station_count_with_records = sum(
        bool(row["generation_rows"] or row["fuel_rows"])
        for row in station_data.values()
    )
    generation_without_power_count = sum(
        not row["has_power_row"]
        for station_row in station_data.values()
        for row in station_row["generation_rows"]
    ) + sum(not row["has_power_row"] for row in unassigned_generation_rows)
    group_machine_station_ids = defaultdict(set)
    for station_id, station_row in station_data.items():
        for row in station_row["generation_rows"]:
            group_id = row.get("equipment_group_id")
            if group_id is not None:
                group_machine_station_ids[group_id].add(station_id)

    for group_id, member_station_ids in group_machine_station_ids.items():
        if len(member_station_ids) < 2:
            continue
        member_rows = [station_data[station_id] for station_id in sorted(
            member_station_ids,
            key=lambda station_id: (
                station_data[station_id]["name"].casefold(), station_id
            ),
        )]
        if not show_boilers and all(
            _is_boiler_group_type(row)
            for station_row in member_rows
            for row in station_row["generation_rows"]
            if row.get("equipment_group_id") == group_id
        ):
            continue
        shared_fuel_rows = [
            row for row in unresolved_fuel_rows
            if row["group_id"] == group_id
            and row["path"] == member_rows[0]["path"]
        ]
        joined_row = _collapse_shared_equipment_group(
            group_id,
            member_rows,
            shared_fuel_rows,
            show_p_rasp=show_p_rasp,
            show_ved0=show_ved0,
            rounding_digits=rounding_digits,
        )
        if joined_row is None:
            continue

        anchor_path = member_rows[0]["path"]
        shared_rows_by_path[anchor_path].append(joined_row)
        shared_station_ids.update(member_station_ids)
        shared_fuel_group_ids.add(group_id)
        for station_row in member_rows:
            station_row["generation_rows"] = [
                row for row in station_row["generation_rows"]
                if row.get("equipment_group_id") != group_id
            ]

    # All-data totals stay available for the audit counters; the summary row
    # itself is not rendered.
    russia_totals = _new_totals()
    for row in station_data.values():
        _add_totals(russia_totals, **row["totals"])
    _add_totals(russia_totals, **unassigned_totals)

    def _ues_sort_key(item):
        key, _node = item
        return union_energy_system_hierarchy_sort_key(
            key if key is not None else -1,
            ues_names,
            ues_display_orders,
        )

    comparison_items = []
    for est_key, est_node in sorted(hierarchy.items(), key=_hierarchy_sort_key):
        for ues_key, ues_node in sorted(est_node["children"].items(), key=_ues_sort_key):
            for res_key, res_node in sorted(ues_node["children"].items(), key=_hierarchy_sort_key):
                regional_path = (est_key, ues_key, res_key)
                regional_items_start = len(comparison_items)
                for shared_row in shared_rows_by_path.get(regional_path, []):
                    comparison_items.append({"path": regional_path, "rows": [shared_row]})

                station_rows = [
                    row for row in station_data.values()
                    if row["path"] == regional_path
                ]
                station_rows.sort(key=lambda row: (row["name"].casefold(), row["station"].id))
                for station_row in station_rows:
                    station_id = station_row["station"].id
                    if (
                        station_id in shared_station_ids
                        and not station_row["generation_rows"]
                        and not station_row["fuel_rows"]
                    ):
                        continue
                    station_rows_for_display = _station_comparison_rows(
                        station_row,
                        show_p_rasp=show_p_rasp,
                        show_ved0=show_ved0,
                        show_boilers=show_boilers,
                        rounding_digits=rounding_digits,
                    )
                    if station_rows_for_display:
                        comparison_items.append({
                            "path": regional_path,
                            "rows": station_rows_for_display,
                        })

                regional_fuel_rows = [
                    row for row in fuel_rows_by_path.get(regional_path, [])
                    if row["group_id"] not in shared_fuel_group_ids
                    and (show_ved0 or row.get("ved") != 0)
                    and (show_boilers or not _is_boiler_group_type(row))
                ]
                if regional_fuel_rows:
                    regional_fuel_totals = _new_totals()
                    for row in regional_fuel_rows:
                        _add_fuel_totals(regional_fuel_totals, row)
                    regional_rows = [{
                        "kind": "unassigned_station",
                        "label": "Топливные группы по территории (без однозначной связи с ТЭС в этой РЭС)",
                        **regional_fuel_totals,
                    }]
                    regional_rows.extend(_rows_with_numb_subtotals(
                        [],
                        regional_fuel_rows,
                        separate_fuel_groups=True,
                        show_p_rasp=show_p_rasp,
                        show_ved0=show_ved0,
                        show_boilers=show_boilers,
                        rounding_digits=rounding_digits,
                    ))
                    for row_group in _comparison_row_groups(regional_rows):
                        comparison_items.append({"path": regional_path, "rows": row_group})
                if len(comparison_items) == regional_items_start and any(res_node["totals"].values()):
                    comparison_items.append({"path": regional_path, "rows": []})

    unassigned_display_generation_rows = (
        unassigned_generation_rows
        if show_boilers
        else _without_boiler_rows(unassigned_generation_rows)
    )
    unassigned_display_fuel_rows = [
        row for row in unresolved_fuel_rows
        if row["tpp_linked"]
        and not row["assigned_by_region"]
        and row["group_id"] not in shared_fuel_group_ids
        and (show_ved0 or row.get("ved") != 0)
        and (show_boilers or not _is_boiler_group_type(row))
    ]
    if unassigned_display_generation_rows or unassigned_display_fuel_rows:
        global_rows = [{
            "kind": "unassigned",
            "label": "Не распределено по РЭС / ОЭС / типу энергосистемы",
            **unmapped_totals,
        }]
        global_rows.extend(_rows_with_numb_subtotals(
            unassigned_display_generation_rows,
            unassigned_display_fuel_rows,
            separate_fuel_groups=True,
            show_p_rasp=show_p_rasp,
            show_ved0=show_ved0,
            show_boilers=show_boilers,
            rounding_digits=rounding_digits,
        ))
        comparison_items.extend(
            {"path": None, "rows": row_group}
            for row_group in _comparison_row_groups(global_rows)
        )

    unclassified_display_rows = [
        row for row in unclassified_fuel_rows
        if (show_ved0 or row.get("ved") != 0)
        and (show_boilers or not _is_boiler_group_type(row))
    ]
    if unclassified_display_rows:
        global_rows = [{
            "kind": "unclassified",
            "label": "Топливные группы без связи с ТЭС и без определённой территории",
            **unclassified_fuel_totals,
        }]
        global_rows.extend(_rows_with_numb_subtotals(
            [],
            unclassified_display_rows,
            separate_fuel_groups=True,
            show_p_rasp=show_p_rasp,
            show_ved0=show_ved0,
            show_boilers=show_boilers,
            rounding_digits=rounding_digits,
        ))
        comparison_items.extend(
            {"path": None, "rows": row_group}
            for row_group in _comparison_row_groups(global_rows)
        )

    if paginate:
        current_page, total_pages, page_items = _paginate_comparison_items(
            comparison_items, page
        )
    else:
        current_page, total_pages, page_items = 1, 1, comparison_items

    def display_totals(totals):
        """Итоги уровня с признаком расхождения Руст и NUST."""
        return {
            **totals,
            "p_ust_mismatch": not _totals_match(
                totals["p_ust"], totals["nust"], rounding_digits
            ),
            "p_rasp_mismatch": show_p_rasp and not _totals_match(
                totals["p_rasp"], totals["nr"], rounding_digits
            ),
            "has_numb_comparison": True,
        }

    display_rows = []
    current_est_key = current_ues_key = current_res_key = None
    for item in page_items:
        if item["path"] is None:
            current_est_key = current_ues_key = current_res_key = None
            display_rows.extend(item["rows"])
            continue
        est_key, ues_key, res_key = item["path"]
        if est_key != current_est_key:
            est_node = hierarchy[est_key]
            display_rows.append({
                "kind": "system",
                "label": est_node["name"],
                **display_totals(est_node["totals"]),
            })
            current_est_key = est_key
            current_ues_key = current_res_key = None
        if ues_key != current_ues_key:
            ues_node = hierarchy[est_key]["children"][ues_key]
            display_rows.append({
                "kind": "ues",
                "key": ues_key,
                "label": ues_node["name"],
                **display_totals(ues_node["totals"]),
            })
            current_ues_key = ues_key
            current_res_key = None
        if res_key != current_res_key:
            res_node = hierarchy[est_key]["children"][ues_key]["children"][res_key]
            display_rows.append({
                "kind": "res",
                "label": res_node["name"],
                **display_totals(res_node["totals"]),
            })
            current_res_key = res_key
        display_rows.extend(item["rows"])

    return {
        "selected_year": selected_year,
        "show_p_rasp": bool(show_p_rasp),
        "show_ved0": bool(show_ved0),
        "show_boilers": bool(show_boilers),
        "rounding_digits": rounding_digits,
        "year_choices": year_choices,
        "display_rows": display_rows,
        "pagination": {
            "current_page": current_page,
            "total_pages": total_pages,
            "total_count": sum(len(item["rows"]) for item in comparison_items),
            "total_count_label": "строк",
            "page_size": 50,
        } if total_pages > 1 else None,
        "generation_record_count": generation_count,
        "generation_without_power_count": generation_without_power_count,
        "fuel_record_count": fuel_count,
        "fuel_group_row_count": fuel_group_row_count,
        "fuel_group_without_param_count": fuel_group_without_param_count,
        "station_count": len(station_data),
        "station_with_records_count": station_count_with_records,
        "unassigned_generation_count": len(unassigned_generation_rows),
        "unassigned_fuel_count": sum(row["tpp_linked"] for row in unresolved_fuel_rows),
        "unclassified_fuel_count": len(unclassified_fuel_rows),
        "unclassified_fuel_totals": unclassified_fuel_totals,
    }
