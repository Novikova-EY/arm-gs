# -*- coding: utf-8 -*-
"""
Пагинация иерархий страниц топлива (ЕЭС → ОЭС → РЭС → станция → группа оборудования).

Как на station_list при show_totals=1: soft-лимит per_page по группам оборудования,
страница удлиняется до конца текущего РЭС (не рвём субъект / строки «…, всего»
и составные кластеры родитель+дети внутри РЭС).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.services.equipment_groups.composite_station_semantics import (
    fuel_param_row_participates,
)
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    should_suppress_fuel_params_station_summary_row,
)
from app.fuel.services.equipment_groups.equipment_group_extra_fuel_params_services import (
    sum_extra_fuel_attrs_for_rows,
)
from app.fuel.services.stations.stations_equipment_groups_services import (
    get_standalone_equipment_group_ids,
)


def _rows_from_group_block(gb: dict) -> list:
    return gb.get("rows") or []


def _rows_for_summary(rows: list) -> list:
    """Как в hierarchy: при наличии ved — только ved>0; иначе legacy все строки."""
    has_any_ved = any(
        param is not None and getattr(param, "ved", None) is not None
        for _eg, param in rows
    )
    if not has_any_ved:
        return rows
    return [(eg, param) for eg, param in rows if fuel_param_row_participates(param)]


def _compute_summary_for_attrs(
    rows: list,
    summary_attr_names: list[str],
    children_by_parent: dict | None = None,
) -> dict:
    return sum_extra_fuel_attrs_for_rows(
        _rows_for_summary(rows), summary_attr_names, children_by_parent
    )


def _station_block_key(station_block: dict | None) -> tuple:
    """
    Ключ бакета станции при сборке страницы.

    Нужен cluster_key: иначе два разных кластера с одним station_id/name
    (например lone comp=1 и соседняя EG на той же Station) сливаются и
    выводятся дважды — по разу на каждый исходный station_block.
    """
    sb = station_block or {}
    return (
        sb.get("station_id"),
        sb.get("station_name"),
        sb.get("cluster_key"),
    )


def _station_block_out_from(
    *,
    station_id,
    station_name,
    group_blocks: list,
    is_virtual: bool,
    standalone_eg_ids: set,
    summary_attr_names: list[str],
    children_by_parent: dict | None,
    source_station_block: dict | None = None,
) -> dict:
    station_rows: list = []
    for gb in group_blocks:
        station_rows.extend(_rows_from_group_block(gb))
    src = source_station_block or {}
    suppress = src.get("suppress_station_summary")
    if suppress is None:
        suppress = should_suppress_fuel_params_station_summary_row(
            station_id,
            station_name,
            group_blocks,
            standalone_eg_ids,
        )
    return {
        "station_id": station_id,
        "station_name": station_name,
        "group_blocks": group_blocks,
        "station_summary": _compute_summary_for_attrs(
            station_rows,
            summary_attr_names,
            children_by_parent,
        ),
        "station_summary_by_year": src.get("station_summary_by_year") or {},
        "is_virtual": is_virtual,
        "suppress_station_summary": suppress,
        "has_composite_structure": src.get("has_composite_structure", False),
        "composite_parent_eg_id": src.get("composite_parent_eg_id"),
        "params_detail_level_by_year": src.get("params_detail_level_by_year") or {},
        "cluster_key": src.get("cluster_key"),
        "cluster_kind": src.get("cluster_kind"),
        "treat_as_composite": src.get("treat_as_composite", False),
    }


def count_fuel_eg_groups_in_hierarchy(hierarchy_flat: list | None) -> int:
    """Число блоков групп оборудования в иерархии (как на странице — по group_blocks)."""
    n = 0
    for est_block in hierarchy_flat or []:
        for ues_block in est_block.get("ues_list", []):
            for res_block in ues_block.get("res_list", []):
                for station_block in res_block.get("station_blocks", []):
                    n += len(station_block.get("group_blocks") or [])
    return n


def fuel_eg_station_hierarchy_nonempty(hierarchy_flat: list | None) -> bool:
    return count_fuel_eg_groups_in_hierarchy(hierarchy_flat) > 0


def _flatten_fuel_eg_hierarchy(hierarchy_flat: list | None) -> list[dict[str, Any]]:
    """Плоский список group_block в порядке отображения + ключ границы РЭС."""
    flat_items: list[dict[str, Any]] = []
    for est_block in hierarchy_flat or []:
        est_id = est_block.get("est_id")
        est_name = est_block.get("est_name")
        for ues_block in est_block.get("ues_list", []):
            ues_id = ues_block.get("ues_id")
            ues_name = ues_block.get("ues_name")
            for res_block in ues_block.get("res_list", []):
                res_id = res_block.get("res_id")
                res_name = res_block.get("res_name")
                for station_block in res_block.get("station_blocks", []):
                    st_id = station_block.get("station_id")
                    st_name = station_block.get("station_name")
                    is_virtual = station_block.get("is_virtual", False)
                    cluster_key = station_block.get("cluster_key")
                    for gb in station_block.get("group_blocks", []):
                        flat_items.append(
                            {
                                "est_id": est_id,
                                "est_name": est_name,
                                "ues_id": ues_id,
                                "ues_name": ues_name,
                                "res_id": res_id,
                                "res_name": res_name,
                                "station_id": st_id,
                                "station_name": st_name,
                                "cluster_key": cluster_key,
                                "is_virtual": is_virtual,
                                "group_block": gb,
                            }
                        )
    return flat_items


def _fuel_res_boundary_key(item: dict[str, Any]) -> tuple:
    """
    Граница soft-пагинации — РЭС внутри ОЭС/ЕЭС
    (аналог субъекта РФ на station_list).
    """
    return (item.get("est_id"), item.get("ues_id"), item.get("res_id"))


def compute_fuel_eg_page_start_index(
    flat_items: list[dict[str, Any]],
    per_page_int: int,
    target_page: int,
) -> int:
    """
    Индекс начала страницы target_page при правиле «не рвать РЭС»
    (как compute_page_start_index в station_services).
    """
    if per_page_int is None or per_page_int <= 0 or target_page <= 1:
        return 0
    if not flat_items:
        return 0

    idx = 0
    current_page = 1
    total = len(flat_items)

    while current_page < target_page and idx < total:
        count = 0
        current_key = None
        while idx < total:
            key = _fuel_res_boundary_key(flat_items[idx])
            if (
                count >= per_page_int
                and current_key is not None
                and key != current_key
            ):
                break
            current_key = key
            idx += 1
            count += 1
        current_page += 1

    return idx


def compute_fuel_eg_effective_total_pages(
    flat_items: list[dict[str, Any]],
    per_page_int: int,
) -> int:
    """Фактическое число страниц с учётом удлинения до конца РЭС."""
    if per_page_int is None or per_page_int <= 0:
        return 1
    if not flat_items:
        return 1

    idx = 0
    total_count = len(flat_items)
    total_pages = 0
    while idx < total_count:
        total_pages += 1
        count = 0
        current_key = None
        while idx < total_count:
            key = _fuel_res_boundary_key(flat_items[idx])
            if (
                count >= per_page_int
                and current_key is not None
                and key != current_key
            ):
                break
            idx += 1
            count += 1
            current_key = key

    return total_pages if total_pages > 0 else 1


def slice_fuel_eg_page_range(
    flat_items: list[dict[str, Any]],
    per_page_int: int,
    page: int,
) -> tuple[int, int, int, int]:
    """
    Возвращает (start_idx, end_idx, total_pages, current_page)
    для soft-пагинации по РЭС.
    """
    total_count = len(flat_items)
    if not flat_items:
        return 0, 0, 1, 1

    total_pages = compute_fuel_eg_effective_total_pages(flat_items, per_page_int)
    requested_page = max(int(page or 1), 1)
    current_page = min(requested_page, total_pages)
    start_idx = compute_fuel_eg_page_start_index(
        flat_items, per_page_int, current_page
    )

    idx = start_idx
    count = 0
    current_key = None
    while idx < total_count:
        key = _fuel_res_boundary_key(flat_items[idx])
        if (
            count >= per_page_int
            and current_key is not None
            and key != current_key
        ):
            break
        current_key = key
        idx += 1
        count += 1

    return start_idx, idx, total_pages, current_page


def paginate_fuel_eg_station_hierarchy(
    hierarchy_flat: list | None,
    page: int,
    per_page: int | str | None,
    summary_attr_names: list[str],
    children_by_parent: dict | None = None,
) -> tuple[list, int, int, int]:
    """
    Возвращает:
      - иерархию для текущей страницы;
      - общее число групп оборудования (по всем страницам);
      - число страниц (с учётом soft-границ РЭС);
      - номер текущей страницы.

    children_by_parent — опционально: для страниц, где родительские столбцы
    считаются суммой листовых полей (доп. топливные параметры).
    """
    flat_items = _flatten_fuel_eg_hierarchy(hierarchy_flat)
    total_count = len(flat_items)
    if not flat_items:
        return [], 0, 1, 1

    if isinstance(per_page, str) and per_page.lower() == "all":
        return hierarchy_flat or [], total_count, 1, 1

    try:
        per_page_int = int(per_page)
    except (TypeError, ValueError):
        per_page_int = None

    if per_page_int is None or per_page_int <= 0:
        return hierarchy_flat or [], total_count, 1, 1

    _vid = get_current_db_version_id()
    _standalone_eg_ids = get_standalone_equipment_group_ids(
        version_id=_vid,
        strict_version=_vid is not None,
    )

    start_idx, end_idx, total_pages, current_page = slice_fuel_eg_page_range(
        flat_items, per_page_int, page
    )
    page_items = flat_items[start_idx:end_idx]

    # est_id -> ues_id -> res_id -> (station_id, station_name, cluster_key) -> [group_block, ...]
    grouped: dict = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )

    for item in page_items:
        st_key = (
            item["station_id"],
            item["station_name"],
            item.get("cluster_key"),
        )
        grouped[item["est_id"]][item["ues_id"]][item["res_id"]][st_key].append(
            item["group_block"]
        )

    paged_hierarchy: list = []
    for est_block in hierarchy_flat or []:
        est_id = est_block.get("est_id")
        if est_id not in grouped:
            continue
        ues_list_out: list = []
        for ues_block in est_block.get("ues_list", []):
            ues_id = ues_block.get("ues_id")
            if ues_id not in grouped[est_id]:
                continue
            res_list_out: list = []
            for res_block in ues_block.get("res_list", []):
                res_id = res_block.get("res_id")
                by_station = grouped[est_id][ues_id].get(res_id)
                if not by_station:
                    continue

                station_blocks_out: list = []
                seen: set = set()
                for station_block in res_block.get("station_blocks", []):
                    st_key = _station_block_key(station_block)
                    if st_key in seen:
                        continue
                    gbs = by_station.get(st_key)
                    if not gbs:
                        continue
                    seen.add(st_key)
                    # Soft-граница РЭС: на странице либо весь РЭС, либо ничего
                    # из него — берём исходный порядок group_blocks станции.
                    src_gbs = station_block.get("group_blocks") or []
                    if len(gbs) == len(src_gbs) and src_gbs:
                        gbs = src_gbs
                    station_blocks_out.append(
                        _station_block_out_from(
                            station_id=station_block.get("station_id"),
                            station_name=station_block.get("station_name"),
                            group_blocks=gbs,
                            is_virtual=station_block.get("is_virtual", False),
                            standalone_eg_ids=_standalone_eg_ids,
                            summary_attr_names=summary_attr_names,
                            children_by_parent=children_by_parent,
                            source_station_block=station_block,
                        )
                    )

                for st_key, gbs in by_station.items():
                    if st_key in seen:
                        continue
                    station_blocks_out.append(
                        _station_block_out_from(
                            station_id=st_key[0],
                            station_name=st_key[1],
                            group_blocks=gbs,
                            is_virtual=False,
                            standalone_eg_ids=_standalone_eg_ids,
                            summary_attr_names=summary_attr_names,
                            children_by_parent=children_by_parent,
                            source_station_block={
                                "cluster_key": st_key[2] if len(st_key) > 2 else None,
                            },
                        )
                    )

                all_res_rows: list = []
                for sb in station_blocks_out:
                    for gb in sb.get("group_blocks", []):
                        all_res_rows.extend(_rows_from_group_block(gb))

                # Полный РЭС на странице — сохраняем исходный res_summary,
                # если он уже посчитан на полной иерархии.
                src_res_summary = res_block.get("res_summary")
                if (
                    src_res_summary is not None
                    and len(station_blocks_out)
                    == len(res_block.get("station_blocks") or [])
                ):
                    res_summary = src_res_summary
                else:
                    res_summary = _compute_summary_for_attrs(
                        all_res_rows,
                        summary_attr_names,
                        children_by_parent,
                    )

                res_list_out.append(
                    {
                        "res_id": res_id,
                        "res_name": res_block.get("res_name"),
                        "group_blocks": [
                            gb
                            for sb in station_blocks_out
                            for gb in sb["group_blocks"]
                        ],
                        "station_blocks": station_blocks_out,
                        "res_summary": res_summary,
                    }
                )

            if res_list_out:
                ues_list_out.append(
                    {
                        "ues_id": ues_id,
                        "ues_name": ues_block.get("ues_name"),
                        "res_list": res_list_out,
                    }
                )

        if ues_list_out:
            paged_hierarchy.append(
                {
                    "est_id": est_id,
                    "est_name": est_block.get("est_name"),
                    "ues_list": ues_list_out,
                }
            )

    return paged_hierarchy, total_count, total_pages, current_page
