# -*- coding: utf-8 -*-
"""
Пагинация иерархий страниц топлива (ЕЭС → ОЭС → РЭС → станция → группа оборудования)
по числу групп оборудования, аналогично _paginate_equipment_group_hierarchy
в stations_equipment_groups_services.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.common.services.database_version_filter import get_current_db_version_id
from app.fuel.services.equipment_groups.equipment_group_fuel_params_services import (
    should_suppress_fuel_params_station_summary_row,
)
from app.fuel.services.stations.stations_equipment_groups_services import (
    get_standalone_equipment_group_ids,
)


def _rows_from_group_block(gb: dict) -> list:
    return gb.get("rows") or []


def _compute_summary_for_attrs(rows: list, summary_attr_names: list[str]) -> dict:
    summary: dict[str, Decimal] = {}
    for attr in summary_attr_names:
        total = Decimal(0)
        for _eg, param in rows:
            if param is None:
                continue
            val = getattr(param, attr, None)
            if val is not None:
                try:
                    total += Decimal(str(val))
                except (TypeError, ValueError):
                    pass
        summary[attr] = total
    return summary


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


def paginate_fuel_eg_station_hierarchy(
    hierarchy_flat: list | None,
    page: int,
    per_page: int | str | None,
    summary_attr_names: list[str],
) -> tuple[list, int, int, int]:
    """
    Возвращает:
      - иерархию для текущей страницы;
      - общее число групп оборудования (по всем страницам);
      - число страниц;
      - номер текущей страницы.
    """
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
                                "is_virtual": is_virtual,
                                "group_block": gb,
                            }
                        )

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

    requested_page = max(int(page or 1), 1)
    total_pages = max(1, (total_count + per_page_int - 1) // per_page_int)
    current_page = min(requested_page, total_pages)
    start_idx = (current_page - 1) * per_page_int
    end_idx = start_idx + per_page_int
    page_items = flat_items[start_idx:end_idx]

    # est_id -> ues_id -> res_id -> (station_id, station_name) -> [group_block, ...]
    grouped: dict = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    )

    for item in page_items:
        st_key = (item["station_id"], item["station_name"])
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
                    st_key = (
                        station_block.get("station_id"),
                        station_block.get("station_name"),
                    )
                    gbs = by_station.get(st_key)
                    if not gbs:
                        continue
                    seen.add(st_key)
                    station_rows: list = []
                    for gb in gbs:
                        station_rows.extend(_rows_from_group_block(gb))
                    station_blocks_out.append(
                        {
                            "station_id": station_block.get("station_id"),
                            "station_name": station_block.get("station_name"),
                            "group_blocks": gbs,
                            "station_summary": _compute_summary_for_attrs(
                                station_rows, summary_attr_names
                            ),
                            "is_virtual": station_block.get("is_virtual", False),
                            "suppress_station_summary": should_suppress_fuel_params_station_summary_row(
                                station_block.get("station_id"),
                                station_block.get("station_name"),
                                gbs,
                                _standalone_eg_ids,
                            ),
                        }
                    )

                for st_key, gbs in by_station.items():
                    if st_key in seen:
                        continue
                    station_rows = []
                    for gb in gbs:
                        station_rows.extend(_rows_from_group_block(gb))
                    station_blocks_out.append(
                        {
                            "station_id": st_key[0],
                            "station_name": st_key[1],
                            "group_blocks": gbs,
                            "station_summary": _compute_summary_for_attrs(
                                station_rows, summary_attr_names
                            ),
                            "is_virtual": False,
                            "suppress_station_summary": should_suppress_fuel_params_station_summary_row(
                                st_key[0],
                                st_key[1],
                                gbs,
                                _standalone_eg_ids,
                            ),
                        }
                    )

                all_res_rows: list = []
                for sb in station_blocks_out:
                    for gb in sb.get("group_blocks", []):
                        all_res_rows.extend(_rows_from_group_block(gb))

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
                        "res_summary": _compute_summary_for_attrs(
                            all_res_rows, summary_attr_names
                        ),
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
