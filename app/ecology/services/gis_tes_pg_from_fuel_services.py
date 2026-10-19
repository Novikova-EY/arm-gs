# -*- coding: utf-8 -*-
"""Страницы анализа ПГ: состав групп из модуля «Топливо», данные ТЭП + PGParamCalc."""
from __future__ import annotations

from typing import Any

from app.ecology.services.ecology_decimal_helpers import decimal_or_none
from app.ecology.services.ecology_text_helpers import text_contains
from app.ecology.services.gis_tes_fuel_comparison_constants import (
    ANALYSIS_SHEET_SLUGS,
    BEZ_KOT_SHEET_SLUGS,
    PG_ANALYSIS_SHEET_SLUGS,
    STATION_AFFILIATION_SHEET_SLUGS,
    STATION_GENERATION_COLUMN_KEYS,
    STATION_GENERATION_SHEET_SLUGS,
    UNSPECIFIED_LEVEL_NAME,
    VSE_SHEET_SLUGS,
    ZV_ANALYSIS_SHEET_SLUGS,
)
from app.fuel.services.equipment_groups.composite_station_semantics import (
    is_composite_child_group,
    is_composite_parent_group,
    is_main_empty,
)

# Сводная строка составной станции не складывает идентификацию строки и
# станционные столбцы «Генерации» (у всех групп станции они одинаковые).
COMPOSITE_IDENTITY_COLUMN_KEYS = frozenset({"NAME", "Stancia", "numb1120", "Year"})
COMPOSITE_SHARED_COLUMN_KEYS = STATION_GENERATION_COLUMN_KEYS


def _eg_display_numb(eg: Any, param: Any = None) -> int | None:
    for raw in (
        getattr(param, "numb1120", None) if param else None,
        getattr(eg, "numb", None),
    ):
        if raw is None or raw is False:
            continue
        try:
            return int(raw)
        except (TypeError, ValueError):
            continue
    return None


def _eg_display_name(eg: Any) -> str:
    return (
        (getattr(eg, "name", None) or getattr(eg, "name_ext", None) or "").strip()
        or UNSPECIFIED_LEVEL_NAME
    )


def _as_int_or_none(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _composite_parent_numb(group: dict[str, Any]) -> int | None:
    """NUMB головы составной станции, если группа — её подгруппа (MAIN > 0)."""
    numb = _as_int_or_none(group.get("numb"))
    eg = group.get("equipment_group")
    if numb is None or eg is None or not is_composite_child_group(eg):
        return None
    parent_numb = _as_int_or_none(getattr(eg, "main", None))
    if parent_numb is None or parent_numb <= 0 or parent_numb == numb:
        return None
    return parent_numb


def _equipment_groups_by_numb(
    numbs: set[int],
    version_id: int | None,
) -> dict[int, Any]:
    """EquipmentGroup по NUMB: текущая версия, для отсутствующих — любая."""
    if not numbs:
        return {}
    from app.extensions import db
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup

    out: dict[int, Any] = {}

    def _collect(query) -> None:
        for eg in query.all():
            numb = _as_int_or_none(getattr(eg, "numb", None))
            if numb is not None:
                out.setdefault(numb, eg)

    query = db.session.query(EquipmentGroup).filter(EquipmentGroup.numb.in_(list(numbs)))
    if version_id is not None:
        _collect(query.filter(EquipmentGroup.database_version_id == version_id))
    else:
        _collect(query)
    missing = [numb for numb in numbs if numb not in out]
    if missing:
        _collect(db.session.query(EquipmentGroup).filter(EquipmentGroup.numb.in_(missing)))
    return out


def _composite_member(eg: Any, numb: int | None, param: Any = None) -> dict[str, Any]:
    """Участник сводной строки: группа оборудования, её NUMB и её строка «Топлива»."""
    return {"numb": numb, "equipment_group": eg, "param": param}


def _boiler_equipment_groups(version_id: int | None = None) -> list[Any]:
    """
    Группы оборудования с типом «котельная».

    «Котельная» — это поле «Тип группы оборудования» (EquipmentGroupType.name
    за связью EquipmentGroupSetStation), а не название группы.
    """
    from sqlalchemy import func

    from app.extensions import db
    from app.fuel.models.fue_equipment_group_model import EquipmentGroup
    from app.fuel.models.fue_equipment_group_set_model import EquipmentGroupSet
    from app.fuel.models.fue_equipment_group_set_station_model import (
        EquipmentGroupSetStation,
    )
    from app.refdata.models.refdata_for_stations.technologies.equipment_group_model import (
        EquipmentGroupType,
    )

    q = (
        db.session.query(EquipmentGroup)
        .join(EquipmentGroupSet, EquipmentGroupSet.equipment_group_id == EquipmentGroup.id)
        .join(
            EquipmentGroupSetStation,
            EquipmentGroupSet.equipment_group_set_station_id == EquipmentGroupSetStation.id,
        )
        .join(
            EquipmentGroupType,
            EquipmentGroupSetStation.equipment_group_type_id == EquipmentGroupType.id,
        )
        .filter(func.lower(EquipmentGroupType.name).like("%котельн%"))
    )
    if version_id is not None:
        q = q.filter(EquipmentGroupSetStation.database_version_id == version_id)
        q = q.filter(EquipmentGroupType.database_version_id == version_id)
    return q.all()


def _eg_numbs(groups: list[Any]) -> set[int]:
    numbs: set[int] = set()
    for eg in groups:
        try:
            numbs.add(int(getattr(eg, "numb", None)))
        except (TypeError, ValueError):
            continue
    return numbs


def _boiler_numbs(version_id: int | None = None) -> set[int]:
    """NUMB1120 всех групп с типом группы «котельная»."""
    return _eg_numbs(_boiler_equipment_groups(version_id))


def _boiler_without_parent_group(eg: Any) -> bool:
    """Котельная вне состава станции: MAIN пуст / 0 (в т.ч. оболочка составной станции)."""
    return is_main_empty(getattr(eg, "main", None))


def _boiler_numbs_without_parent(version_id: int | None = None) -> set[int]:
    """NUMB1120 котельных, не входящих в состав другой группы оборудования."""
    return _eg_numbs(
        [
            eg
            for eg in _boiler_equipment_groups(version_id)
            if _boiler_without_parent_group(eg)
        ]
    )


def hidden_boiler_numbs_for_sheet(
    sheet_slug: str,
    version_id: int | None = None,
) -> set[int]:
    """
    NUMB1120 котельных, которые на вкладке не показываем.

    «С котельными» — все группы оборудования плюс котельные в составе станции
    (MAIN заполнен, т.е. котельная входит в другую группу оборудования);
    «Без котельных» — все группы оборудования, кроме котельных любого уровня.
    """
    slug = str(sheet_slug or "").strip()
    if slug in BEZ_KOT_SHEET_SLUGS:
        return _boiler_numbs(version_id)
    if slug in VSE_SHEET_SLUGS:
        return _boiler_numbs_without_parent(version_id)
    return set()


def _rows_without_boilers(
    rows: list[tuple[Any, Any]],
    boiler_numbs: set[int],
) -> list[tuple[Any, Any]]:
    """Убирает строки котельных с указанными NUMB1120."""
    return [
        (eg, param)
        for eg, param in rows
        if _eg_display_numb(eg, param) not in boiler_numbs
    ]


def _groups_without_boilers(
    groups: list[dict[str, Any]],
    boiler_numbs: set[int],
) -> list[dict[str, Any]]:
    """
    Убирает группы котельных с указанными NUMB1120.

    Иерархия Топливо возвращает блок станции с её EG, даже когда строки этой
    станции отфильтрованы, поэтому одного отбора строк недостаточно.
    """
    return [group for group in groups if group.get("numb") not in boiler_numbs]


def _group_numbs(group: dict[str, Any]) -> list[int]:
    """NUMB группы и её подгрупп (у сводной строки составной станции — все участники)."""
    return [
        numb
        for numb in (group.get("member_numbs") or [group.get("numb")])
        if isinstance(numb, int)
    ]


def _drop_groups_without_station(
    groups: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[int]]:
    """
    Убирает группы оборудования, не привязанные к станции «Генерации».

    Привязка на странице — это ссылка на карточку станции в столбце
    «Электростанция», поэтому группа без такой ссылки не нужна. У сводной строки
    составной станции достаточно привязки любой подгруппы.
    Второй элемент — NUMB убранных групп, чтобы убрать их и из фильтра numb1120.
    """
    from app.ecology.services.gis_tes_fuel_comparison_services import (
        load_generation_station_links_by_numb,
    )

    links_by_numb = load_generation_station_links_by_numb(
        {numb for group in groups for numb in _group_numbs(group)}
    )
    kept: list[dict[str, Any]] = []
    hidden: set[int] = set()
    for group in groups:
        numbs = _group_numbs(group)
        if any(links_by_numb.get(numb) for numb in numbs):
            kept.append(group)
        else:
            hidden.update(numbs)
    return kept, hidden


def _merged_composite_group(
    parent_numb: int,
    parent_eg: Any,
    parent_group: dict[str, Any] | None,
    child_groups: list[dict[str, Any]],
) -> dict[str, Any]:
    """Сводная строка составной станции: код головы, участники — она сама и подгруппы."""
    first = parent_group or child_groups[0]
    meta = dict(first.get("meta") or {})
    meta["station_name"] = _eg_display_name(parent_eg)
    members = [
        _composite_member(parent_eg, parent_numb, (parent_group or {}).get("sample_param"))
    ]
    members.extend(
        _composite_member(
            group.get("equipment_group"),
            group.get("numb"),
            group.get("sample_param"),
        )
        for group in child_groups
    )
    return {
        "id": parent_numb,
        "numb": parent_numb,
        "meta": meta,
        "rowspan": 0,
        "filled_by_year": {},
        "equipment_group": parent_eg,
        "sample_param": members[0]["param"],
        "is_composite_parent": True,
        "is_composite_child": False,
        "show_composite_cluster": False,
        "members": members,
        "member_numbs": [
            member["numb"] for member in members if isinstance(member["numb"], int)
        ],
        "rows": [],
    }


def merge_composite_groups(
    groups: list[dict[str, Any]],
    *,
    version_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Подгруппы составных станций складываются в одну строку головы (MAIN = NUMB головы).

    В «Код группы оборудования (numb1120)» попадает группа с признаком родителя,
    а показатели её подгрупп суммируются при заполнении строк (см. `_composite_filled_row`).
    Группы, у которых нет головы составной станции, возвращаются как есть.
    """
    listed = list(groups or [])
    children_by_parent: dict[int, list[dict[str, Any]]] = {}
    for group in listed:
        parent_numb = _composite_parent_numb(group)
        if parent_numb is not None:
            children_by_parent.setdefault(parent_numb, []).append(group)
    if not children_by_parent:
        return listed
    parents = _equipment_groups_by_numb(set(children_by_parent), version_id)
    group_by_numb = {
        group["numb"]: group for group in listed if isinstance(group.get("numb"), int)
    }
    merged_by_parent: dict[int, dict[str, Any]] = {}
    for parent_numb, child_groups in children_by_parent.items():
        parent_group = group_by_numb.get(parent_numb)
        parent_eg = parents.get(parent_numb) or (
            parent_group.get("equipment_group") if parent_group else None
        )
        # MAIN заполняется и у котельных в составе станции: сворачиваем только
        # подгруппы, у которых голова — действительно составная станция (COMP=1).
        if parent_eg is None or not is_composite_parent_group(parent_eg):
            continue
        merged_by_parent[parent_numb] = _merged_composite_group(
            parent_numb,
            parent_eg,
            parent_group,
            [group for group in child_groups if group is not parent_group],
        )
    if not merged_by_parent:
        return listed
    out: list[dict[str, Any]] = []
    emitted: set[int] = set()
    for group in listed:
        numb = group.get("numb")
        parent_numb = _composite_parent_numb(group)
        owner = parent_numb if parent_numb is not None else numb
        if owner in merged_by_parent:
            if owner not in emitted:
                out.append(merged_by_parent[owner])
                emitted.add(owner)
            continue
        out.append(group)
    return out


def numb_choices_with_parents(
    choices: list[Any],
    groups: list[dict[str, Any]],
) -> list[int]:
    """Значения фильтра numb1120: коды подгрупп заменяются кодом головы."""
    parent_by_child: dict[int, int] = {}
    for group in groups or []:
        parent_numb = _as_int_or_none(group.get("numb"))
        if parent_numb is None:
            continue
        for member_numb in group.get("member_numbs") or []:
            if member_numb != parent_numb:
                parent_by_child[member_numb] = parent_numb
    out: set[int] = set()
    for choice in choices or []:
        numb = _as_int_or_none(choice)
        if numb is not None:
            out.add(parent_by_child.get(numb, numb))
    return sorted(out)


def _territory_filters_to_fuel_filters(filters: dict[str, Any]) -> dict[str, Any]:
    """Фильтры страницы анализа → формат get_equipment_groups_with_fuel_params_data."""
    out: dict[str, Any] = {}
    for key in (
        "energy_system_type_filter",
        "union_energy_system_filter",
        "regional_energy_system_filter",
        "federal_district_filter",
        "regional_district_filter",
        "numb1120_filter",
    ):
        values = filters.get(key) or []
        if values:
            out[key] = list(values)
    station = (filters.get("station_name_filter") or "").strip()
    if station:
        out["equipment_group_name_filter"] = station
    return out


def _blank_filled(source_columns: list[dict[str, Any]]) -> list[Any]:
    return [None] * len(source_columns)


def _set_column_value(
    filled: list[Any],
    source_columns: list[dict[str, Any]],
    keys: set[str],
    value: Any,
) -> None:
    from app.ecology.services.gis_tes_fuel_comparison_services import _column_index

    idx = _column_index(source_columns, keys)
    if idx is None:
        return
    if len(filled) <= idx:
        filled.extend([None] * (idx - len(filled) + 1))
    filled[idx] = value


def _apply_group_identity(
    filled: list[Any],
    source_columns: list[dict[str, Any]],
    *,
    eg: Any,
    year: int,
    param: Any = None,
) -> list[Any]:
    out = list(filled)
    name = _eg_display_name(eg)
    numb = _eg_display_numb(eg, param)
    _set_column_value(out, source_columns, {"NAME", "Stancia"}, name)
    _set_column_value(out, source_columns, {"numb1120"}, numb)
    _set_column_value(out, source_columns, {"Year"}, year)
    return out


def _iter_fuel_group_blocks(fuel_hierarchy: list[dict[str, Any]]):
    for est_block in fuel_hierarchy or []:
        for ues_block in est_block.get("ues_list") or []:
            for res_block in ues_block.get("res_list") or []:
                station_blocks = res_block.get("station_blocks")
                if station_blocks:
                    for station_block in station_blocks:
                        for group_block in station_block.get("group_blocks") or []:
                            yield est_block, ues_block, res_block, station_block, group_block
                else:
                    for group_block in res_block.get("group_blocks") or []:
                        yield est_block, ues_block, res_block, None, group_block


def _unique_eg_rows(rows: list[tuple[Any, Any]]) -> list[tuple[Any, Any]]:
    seen: set[int] = set()
    out: list[tuple[Any, Any]] = []
    for eg, param in rows or []:
        eg_id = getattr(eg, "id", None) if eg is not None else None
        if eg_id is None or int(eg_id) in seen:
            continue
        seen.add(int(eg_id))
        out.append((eg, param))
    return out


def _text_contains_ci(needle: str, value: Any) -> bool:
    return text_contains(needle, value, reject_empty_needle=True)


def _eg_ids_matching_ved(
    eg_ids: set[int],
    allowed: set[int],
    start_year: int,
    end_year: int,
    version_id: int | None,
) -> set[int] | None:
    if not eg_ids or not allowed:
        return set()
    try:
        from sqlalchemy import or_

        from app.extensions import db
        from app.fuel.models.fue_equipment_group_fuel_param_model import (
            EquipmentGroupFuelParam,
        )

        query = db.session.query(EquipmentGroupFuelParam.equipment_group_id).filter(
            EquipmentGroupFuelParam.equipment_group_id.in_(list(eg_ids)),
            EquipmentGroupFuelParam.year_number >= int(start_year),
            EquipmentGroupFuelParam.year_number <= int(end_year),
            EquipmentGroupFuelParam.ved.in_(list(allowed)),
        )
        if version_id is not None:
            query = query.filter(
                or_(
                    EquipmentGroupFuelParam.database_version_id == version_id,
                    EquipmentGroupFuelParam.database_version_id.is_(None),
                )
            )
        return {int(row[0]) for row in query.distinct().all() if row[0] is not None}
    except Exception:
        return None


def _filter_listing_rows(
    rows: list[tuple[Any, Any]],
    territory_filters: dict[str, Any],
    *,
    start_year: int,
    end_year: int,
    version_id: int | None,
) -> list[tuple[Any, Any]]:
    from app.ecology.services.gis_tes_fuel_comparison_constants import (
        VED_FILTER_TO_VALUES,
    )

    out = list(rows or [])
    gen_q = (territory_filters.get("gen_company_filter") or "").strip()
    if gen_q:
        filtered = []
        for eg, param in out:
            gk = getattr(eg, "gen_company_external_mapping", None) if eg is not None else None
            name = getattr(gk, "external_name", None) if gk is not None else None
            if _text_contains_ci(gen_q, name):
                filtered.append((eg, param))
        out = filtered

    ved_group = str(territory_filters.get("ved_filter") or "").strip()
    allowed = set(VED_FILTER_TO_VALUES.get(ved_group, ()))
    if not allowed:
        return out
    eg_ids = {
        int(eg.id)
        for eg, _param in out
        if eg is not None and getattr(eg, "id", None) is not None
    }
    matching = _eg_ids_matching_ved(
        eg_ids, allowed, start_year, end_year, version_id
    )
    if matching is not None:
        return [
            (eg, param)
            for eg, param in out
            if eg is not None
            and getattr(eg, "id", None) is not None
            and int(eg.id) in matching
        ]
    filtered = []
    for eg, param in out:
        try:
            ved_value = int(getattr(param, "ved", None))
        except (TypeError, ValueError):
            continue
        if ved_value in allowed:
            filtered.append((eg, param))
    return filtered


def _fallback_fuel_dict(
    eg: Any,
    param: Any,
    est_block: dict[str, Any],
    ues_block: dict[str, Any],
    res_block: dict[str, Any],
) -> dict[str, Any]:
    district = getattr(eg, "regional_district", None)
    federal = getattr(district, "federal_district", None) if district else None
    sync_area = getattr(district, "synchronous_area", None) if district else None
    return {
        "energy_system_type_id": est_block.get("est_id"),
        "est_name": est_block.get("est_name"),
        "ues_id": ues_block.get("ues_id"),
        "ues": ues_block.get("ues_name"),
        "res_id": res_block.get("res_id"),
        "res_name": res_block.get("res_name"),
        "station_name": _eg_display_name(eg),
        "ved": getattr(param, "ved", None),
        "federal_district_id": getattr(federal, "id", None)
        or getattr(district, "id_federal_district", None),
        "federal_district": (getattr(federal, "name", None) or "").strip() or None,
        "synchronous_area_id": getattr(sync_area, "id", None)
        or getattr(district, "id_synchronous_area", None),
        "synchronous_area": (getattr(sync_area, "name", None) or "").strip() or None,
    }


def _sum_numeric_values(values: list[Any]) -> Any:
    """Сумма числовых ячеек подгрупп (Decimal); None, если слагаемых нет."""
    total = None
    for value in values:
        part = decimal_or_none(value)
        if part is None:
            continue
        total = part if total is None else total + part
    return total


def _composite_filled_row(
    parent_filled: list[Any],
    child_filled_rows: list[list[Any]],
    source_columns: list[dict[str, Any]],
) -> list[Any]:
    """
    Сводная строка составной станции: подпоказатели подгрупп складываются.

    Код/год/станционные столбцы («Генерация») остаются у головы (иначе — у первой
    подгруппы); числовые столбцы — сумма подгрупп, а если у подгрупп значения нет —
    значение головы (у оболочки составной станции своих параметров обычно нет).
    Расчётные столбцы (d_*/K_*/CO2/UD_*) пересчитываются позже по итогам.
    """
    from app.ecology.services.gis_tes_fuel_comparison_services import _is_blank

    width = len(source_columns)
    out = list(parent_filled) + [None] * max(0, width - len(parent_filled))
    for index, column in enumerate(source_columns):
        key = str(column.get("key") or "")
        if key in COMPOSITE_IDENTITY_COLUMN_KEYS:
            continue
        values = [row[index] if index < len(row) else None for row in child_filled_rows]
        if not column.get("numeric") or key in COMPOSITE_SHARED_COLUMN_KEYS:
            if _is_blank(out[index]):
                out[index] = next((value for value in values if not _is_blank(value)), None)
            continue
        total = _sum_numeric_values(values)
        if total is not None:
            out[index] = total
    return out


def _station_links_for_group(
    numb: int | None,
    members: list[dict[str, Any]],
    station_links_by_numb: dict[Any, Any],
) -> list[Any]:
    """Ссылки на карточку станции «Генерации»; для сводной строки — у любой подгруппы."""
    links = station_links_by_numb.get(numb)
    if links:
        return links
    for member in members:
        links = station_links_by_numb.get(member.get("numb"))
        if links:
            return links
    return []


def _list_pg_groups_from_fuel(
    sheet_slug: str,
    *,
    start_year: int,
    end_year: int,
    territory_filters: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[int]]:
    from app.common.services.database_version_filter import get_current_db_version_id
    from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
        build_equipment_group_fuel_params_hierarchy,
        collect_numb1120_filter_choices,
        get_equipment_groups_with_fuel_params_data,
        should_suppress_aggregate_rows_for_filters,
    )

    slug = str(sheet_slug or "").strip()
    if slug not in ANALYSIS_SHEET_SLUGS:
        return [], []

    fuel_filters = _territory_filters_to_fuel_filters(territory_filters)
    # Годы ячеек подставляются позже из оверлеев; здесь достаточно уникальных групп.
    fuel_data = get_equipment_groups_with_fuel_params_data(
        filters=fuel_filters,
        start_year=start_year,
        end_year=start_year,
        show_all=True,
        per_page="all",
        page=1,
    )
    rows = _unique_eg_rows(list(fuel_data.get("rows") or []))
    numb1120_filter_choices = list(fuel_data.get("numb1120_filter_choices") or [])
    if not numb1120_filter_choices:
        numb1120_filter_choices = collect_numb1120_filter_choices(rows)

    version_id = get_current_db_version_id()
    hidden_boiler_numbs = hidden_boiler_numbs_for_sheet(slug, version_id)
    rows = _rows_without_boilers(rows, hidden_boiler_numbs)
    numb1120_filter_choices = [
        numb for numb in numb1120_filter_choices if numb not in hidden_boiler_numbs
    ]
    rows = _filter_listing_rows(
        rows,
        territory_filters,
        start_year=start_year,
        end_year=end_year,
        version_id=version_id,
    )

    fuel_hierarchy = build_equipment_group_fuel_params_hierarchy(
        rows,
        use_equipment_group_hierarchy_only=False,
        suppress_aggregate_rows=should_suppress_aggregate_rows_for_filters(fuel_filters),
    )

    groups: list[dict[str, Any]] = []
    for est_block, ues_block, res_block, _station_block, group_block in _iter_fuel_group_blocks(
        fuel_hierarchy
    ):
        if group_block.get("is_composite_total_row"):
            continue
        eg = group_block.get("equipment_group")
        if eg is None:
            continue
        sample_param = None
        for _eg, param in group_block.get("rows") or []:
            sample_param = param
            break
        group_id = _eg_display_numb(eg, sample_param) or f"eg-{getattr(eg, 'id', None)}"
        groups.append(
            {
                "id": group_id,
                "numb": group_id if isinstance(group_id, int) else None,
                "meta": {
                    "est_id": est_block.get("est_id"),
                    "est_name": est_block.get("est_name"),
                    "ues_id": ues_block.get("ues_id"),
                    "ues_name": ues_block.get("ues_name"),
                    "res_id": res_block.get("res_id"),
                    "res_name": res_block.get("res_name"),
                    "station_name": _eg_display_name(eg),
                },
                "rowspan": 0,
                "filled_by_year": {},
                "equipment_group": eg,
                "sample_param": sample_param,
                "is_composite_parent": bool(group_block.get("is_composite_parent")),
                "is_composite_child": bool(group_block.get("is_composite_child")),
                "show_composite_cluster": bool(group_block.get("show_composite_cluster")),
                "rows": [],
            }
        )
    groups = _groups_without_boilers(groups, hidden_boiler_numbs)
    groups = merge_composite_groups(groups, version_id=version_id)
    if slug in VSE_SHEET_SLUGS:
        # «С котельными»: «Электростанция» у строки — станция «Генерации»,
        # поэтому группы без привязки к станции не показываем.
        groups, hidden_station_numbs = _drop_groups_without_station(groups)
        numb1120_filter_choices = [
            numb
            for numb in numb1120_filter_choices
            if numb not in hidden_station_numbs
        ]
    numb1120_filter_choices = numb_choices_with_parents(numb1120_filter_choices, groups)
    return groups, numb1120_filter_choices


def fill_pg_group_year_rows(
    groups: list[dict[str, Any]],
    *,
    sheet_slug: str,
    start_year: int,
    end_year: int,
    territory_filters: dict[str, Any],
    source_columns: list[dict[str, Any]],
    visible_columns: list[dict[str, Any]],
    digits: int,
    emission_digits: int | None = None,
    specific_digits: int | None = None,
) -> None:
    """Заполняет годовые строки только для переданных групп (обычно текущая страница)."""
    from app.ecology.services.analysis_pg_param_services import (
        seed_missing_analysis_pg_params_from_reports,
    )
    from app.ecology.services.analysis_zv_param_services import (
        seed_missing_analysis_zv_params_from_reports,
    )
    from app.ecology.services.gis_tes_fuel_comparison_services import (
        _compute_derived_columns,
        _display_is_nonzero,
        _format_value,
        _group_meta,
        _is_empty_numeric_row,
        apply_fuel_indicators,
        apply_pg_ecology_overlay,
        apply_station_affiliation_cells,
        apply_station_generation_overlay,
        apply_zv_ecology_overlay,
        cell_titles,
        column_rounding_digits,
        load_fuel_indicators_by_numb_year,
        load_pg_ecology_overlay_by_numb_year,
        load_station_affiliations_by_numb_year,
        load_station_generation_overlay,
        load_zv_ecology_overlay_by_numb_year,
        row_matches_territory_filters,
        station_generation_check_pairs,
        station_generation_mismatch,
    )

    slug = str(sheet_slug or "").strip()
    if slug not in ANALYSIS_SHEET_SLUGS or not groups:
        return
    years: list[int] = list(range(int(start_year), int(end_year) + 1))
    numbs: set[int] = set()
    for group in groups:
        for numb in group.get("member_numbs") or [group.get("numb")]:
            if isinstance(numb, int):
                numbs.add(numb)
    if slug in PG_ANALYSIS_SHEET_SLUGS:
        seed_missing_analysis_pg_params_from_reports(
            slug,
            station_numbs=numbs or None,
            years=years,
        )
    elif slug in ZV_ANALYSIS_SHEET_SLUGS:
        seed_missing_analysis_zv_params_from_reports(
            slug,
            station_numbs=numbs or None,
            years=years,
        )
    fuel_overlay = load_fuel_indicators_by_numb_year(numbs, years)
    pg_overlay = (
        load_pg_ecology_overlay_by_numb_year(slug, numbs, years)
        if slug in PG_ANALYSIS_SHEET_SLUGS
        else {}
    )
    zv_overlay = (
        load_zv_ecology_overlay_by_numb_year(slug, numbs, years)
        if slug in ZV_ANALYSIS_SHEET_SLUGS
        else {}
    )
    station_check_pairs = station_generation_check_pairs(visible_columns)
    station_generation_overlay = (
        load_station_generation_overlay(numbs, years)
        if slug in STATION_GENERATION_SHEET_SLUGS
        else {}
    )
    station_links_by_numb = station_generation_overlay.get("station_links_by_numb") or {}
    station_affiliations = (
        load_station_affiliations_by_numb_year(
            numbs, sorted({year for _numb, year in fuel_overlay})
        )
        if slug in STATION_AFFILIATION_SHEET_SLUGS
        else {}
    )

    def _member_year_row(
        member: dict[str, Any],
        year: int,
        blocks: tuple[dict[str, Any], dict[str, Any], dict[str, Any]],
    ) -> tuple[list[Any], dict[str, Any] | None]:
        """Строка группы-участника за год: идентификация + ТЭП + ПГ/ЗВ + принадлежность."""
        est_block, ues_block, res_block = blocks
        member_eg = member.get("equipment_group")
        member_param = member.get("param")
        member_numb = member.get("numb")
        filled = _blank_filled(source_columns)
        filled = _apply_group_identity(
            filled,
            source_columns,
            eg=member_eg,
            year=year,
            param=member_param,
        )
        filled = apply_fuel_indicators(filled, source_columns, fuel_overlay)
        if station_affiliations:
            filled = apply_station_affiliation_cells(
                filled, source_columns, station_affiliations
            )
        if pg_overlay:
            filled = apply_pg_ecology_overlay(filled, source_columns, pg_overlay)
        if zv_overlay:
            filled = apply_zv_ecology_overlay(filled, source_columns, zv_overlay)
        if station_generation_overlay:
            filled = apply_station_generation_overlay(
                filled, source_columns, station_generation_overlay
            )
        fuel = fuel_overlay.get((member_numb, year)) if member_numb is not None else None
        if fuel is None:
            fuel = _fallback_fuel_dict(member_eg, member_param, est_block, ues_block, res_block)
        return filled, fuel

    for group in groups:
        eg = group.get("equipment_group")
        if eg is None:
            continue
        sample_param = group.get("sample_param")
        numb = _eg_display_numb(eg, sample_param)
        members = group.get("members") or [_composite_member(eg, numb, sample_param)]
        group["station_links"] = _station_links_for_group(
            numb, members, station_links_by_numb
        )
        meta = group.get("meta") or {}
        blocks = (
            {
                "est_id": meta.get("est_id"),
                "est_name": meta.get("est_name"),
            },
            {
                "ues_id": meta.get("ues_id"),
                "ues_name": meta.get("ues_name"),
            },
            {
                "res_id": meta.get("res_id"),
                "res_name": meta.get("res_name"),
            },
        )
        year_items: list[dict[str, Any]] = []
        filled_by_year: dict[int, list[Any]] = {}
        for year in years:
            member_rows = [_member_year_row(member, year, blocks) for member in members]
            filled = (
                _composite_filled_row(
                    member_rows[0][0],
                    [row for row, _fuel in member_rows[1:]],
                    source_columns,
                )
                if len(member_rows) > 1
                else member_rows[0][0]
            )
            # Фильтры проверяем по каждой группе состава: у головы составной
            # станции своего ved может не быть (оболочка, ved=0).
            if not any(
                row_matches_territory_filters(
                    member_filled, source_columns, member_fuel, territory_filters
                )
                for member_filled, member_fuel in member_rows
            ):
                continue
            fuel = member_rows[0][1]
            filled = _compute_derived_columns(filled, source_columns)
            cells = [
                _format_value(
                    filled[column["source_index"]]
                    if column["source_index"] < len(filled)
                    else None,
                    column["numeric"],
                    column_rounding_digits(
                        column, digits, emission_digits, specific_digits
                    ),
                )
                for column in visible_columns
            ]
            titles = cell_titles(filled, visible_columns)
            cell_nonzero = [
                bool(column.get("diff_highlight")) and _display_is_nonzero(text)
                for column, text in zip(visible_columns, cells)
            ]
            cell_mismatch = station_generation_mismatch(
                cells, visible_columns, station_check_pairs
            )
            visible_filled = [
                filled[column["source_index"]]
                if column["source_index"] < len(filled)
                else None
                for column in visible_columns
            ]
            year_items.append(
                {
                    "key": f"{slug}-eg{getattr(eg, 'id', '')}-{year}",
                    "year": year,
                    "cells": cells,
                    "titles": titles,
                    "cell_nonzero": cell_nonzero,
                    "cell_mismatch": cell_mismatch,
                    "is_empty": _is_empty_numeric_row(visible_filled, visible_columns),
                    "fuel": fuel,
                    "filled": filled,
                }
            )
            filled_by_year[year] = filled

        if not year_items:
            group["rows"] = []
            group["rowspan"] = 0
            group["filled_by_year"] = {}
            continue
        year_items.sort(key=lambda item: (item["year"] is None, item["year"] or 0))
        meta_src = next(
            (
                item
                for item in year_items
                if (item.get("fuel") or {}).get("ues_id") is not None
            ),
            year_items[0],
        )
        filled_meta = _group_meta(
            meta_src.get("fuel"),
            meta_src.get("filled") or [],
            source_columns,
        )
        filled_meta["est_id"] = meta.get("est_id")
        filled_meta["est_name"] = meta.get("est_name") or filled_meta.get("est_name")
        filled_meta["ues_id"] = meta.get("ues_id")
        filled_meta["ues_name"] = meta.get("ues_name") or filled_meta.get("ues_name")
        filled_meta["res_id"] = meta.get("res_id")
        filled_meta["res_name"] = meta.get("res_name") or filled_meta.get("res_name")
        filled_meta["station_name"] = _eg_display_name(eg)
        group["meta"] = filled_meta
        group["rowspan"] = len(year_items)
        group["filled_by_year"] = filled_by_year
        group["rows"] = [
            {
                "key": item["key"],
                "year": item["year"],
                "cells": item["cells"],
                "titles": item["titles"],
                "cell_nonzero": item["cell_nonzero"],
                "cell_mismatch": item["cell_mismatch"],
                "is_empty": item["is_empty"],
                "is_group_first": loop_i == 0,
            }
            for loop_i, item in enumerate(year_items)
        ]


def collect_pg_groups_from_fuel(
    sheet_slug: str,
    *,
    start_year: int,
    end_year: int,
    territory_filters: dict[str, Any],
    source_columns: list[dict[str, Any]],
    visible_columns: list[dict[str, Any]],
    digits: int,
    hydrate: bool = True,
    emission_digits: int | None = None,
    specific_digits: int | None = None,
) -> tuple[list[dict[str, Any]], list[int]]:
    """
    Состав отображаемых групп — из модуля Топливо (как edit_data).
    К строкам подтягиваются ТЭП и параметры/отчёт ПГ либо отчётные ЗВ.

    hydrate=False — только состав/иерархия без расчёта ячеек (для пагинации).
    """
    groups, numb1120_filter_choices = _list_pg_groups_from_fuel(
        sheet_slug,
        start_year=start_year,
        end_year=end_year,
        territory_filters=territory_filters,
    )
    if hydrate:
        fill_pg_group_year_rows(
            groups,
            sheet_slug=sheet_slug,
            start_year=start_year,
            end_year=end_year,
            territory_filters=territory_filters,
            source_columns=source_columns,
            visible_columns=visible_columns,
            digits=digits,
            emission_digits=emission_digits,
            specific_digits=specific_digits,
        )
        groups = [group for group in groups if group.get("rows")]
    return groups, numb1120_filter_choices
