# -*- coding: utf-8 -*-
"""Страница «Перетоки ЭЭ» — перетоки между энергосистемами."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.common.services.database_version_filter import filter_by_db_version
from app.common.services.get_services.energy_systems.energy_unit_get_services import (
    get_energy_unit_list,
)
from app.common.services.get_services.energy_systems.regional_energy_system_get_services import (
    get_regional_energy_systems_name_map,
)
from app.common.services.get_services.territories.regional_district_get_services import (
    get_regional_districts_map,
)
from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_display_order_map,
    get_union_energy_systems_map,
    union_energy_system_hierarchy_sort_key,
)
from app.energy_balance.services.energy_balance_year_filter_services import (
    get_ee_default_end_year,
    get_ee_default_start_year,
)
from app.common.services.help_services import format_decimal_for_display
from app.energy_balance.models.regional_energy_system_transfer_model import (
    EE_TRANSFER_PERIOD_YEAR,
    RegionalEnergySystemTransfer,
)
from app.energy_balance.services.energy_balance_cache import cached_load
from app.energy_balance.services.station_ee_generation_page_services import (
    EE_PERIOD_MODE_MONTHS,
    EE_PERIOD_MODE_YEARS,
    MONTH_COLUMNS,
    build_year_columns,
    resolve_single_year_filter,
)
from sqlalchemy.orm import joinedload

from app.refdata.models.energy_systems.regional_energy_system_model import RegionalEnergySystem
from app.refdata.models.territories.foreign_border_country_model import ForeignBorderCountry


def format_transfer_cell(value, rounding_digits: int) -> str:
    if value is None:
        return "—"
    try:
        if Decimal(str(value)) == 0:
            return "0"
    except Exception:
        pass
    return format_decimal_for_display(value, digits=rounding_digits)


def _add_period_sum(target: dict[int, Decimal], period_key: int, value) -> None:
    if value is None:
        return
    target[period_key] = target.get(period_key, Decimal(0)) + Decimal(str(value))


def _parse_int_list(values) -> list[int]:
    result: list[int] = []
    for raw in values or []:
        try:
            result.append(int(raw))
        except (TypeError, ValueError):
            continue
    return result


def _from_group_key(*, from_res_id: int | None, from_rd_id: int | None) -> str:
    if from_res_id is not None:
        return f"res:{from_res_id}"
    if from_rd_id is not None:
        return f"rd:{from_rd_id}"
    return "unknown"


def _load_res_territory_maps_uncached() -> dict[str, Any]:
    """Один проход по справочникам РЭС/субъектов для всех карт фильтрации."""
    from app.refdata.models.territories.regional_district_model import RegionalDistrict

    res_rd_map: dict[int, set[int]] = defaultdict(set)
    rd_res_map: dict[int, set[int]] = defaultdict(set)
    res_ues_map: dict[int, int | None] = {}
    res_est_map: dict[int, int | None] = {}

    rd_fd_single: dict[int, int | None] = {}
    for rd in RegionalDistrict.query.all():
        rd_fd_single[rd.id] = rd.id_federal_district

    for res in RegionalEnergySystem.query.options(
        joinedload(RegionalEnergySystem.union_energy_system)
    ).all():
        for rd in res.regional_districts or []:
            if rd.id is not None:
                res_rd_map[res.id].add(rd.id)
                rd_res_map[rd.id].add(res.id)
        res_ues_map[res.id] = res.id_union_energy_system
        ues = res.union_energy_system
        res_est_map[res.id] = ues.id_energy_system_type if ues else None

    res_fd_map: dict[int, set[int]] = defaultdict(set)
    for res_id, rd_ids in res_rd_map.items():
        for rd_id in rd_ids:
            fd_id = rd_fd_single.get(rd_id)
            if fd_id is not None:
                res_fd_map[res_id].add(fd_id)

    rd_fd_map: dict[int, set[int]] = defaultdict(set)
    for rd_id, res_ids in rd_res_map.items():
        for res_id in res_ids:
            rd_fd_map[rd_id].update(res_fd_map.get(res_id, set()))

    return {
        "res_rd_map": dict(res_rd_map),
        "rd_res_map": dict(rd_res_map),
        "res_fd_map": dict(res_fd_map),
        "rd_fd_map": dict(rd_fd_map),
        "res_ues_map": res_ues_map,
        "res_est_map": res_est_map,
    }


def _get_res_territory_maps() -> dict[str, Any]:
    return cached_load("res_territory_maps", (), _load_res_territory_maps_uncached)


def _transfer_matches_filters(
    row: dict[str, Any],
    filters: dict,
    res_rd_map: dict[int, set[int]],
    res_fd_map: dict[int, set[int]],
    res_ues_map: dict[int, int | None],
    res_est_map: dict[int, int | None],
    rd_res_map: dict[int, set[int]],
    rd_fd_map: dict[int, set[int]],
) -> bool:
    est_filter = _parse_int_list(filters.get("energy_system_type_filter"))
    ues_filter = _parse_int_list(filters.get("union_energy_system_filter"))
    res_filter = _parse_int_list(filters.get("regional_energy_system_filter"))
    fd_filter = _parse_int_list(filters.get("federal_district_filter"))
    rd_filter = _parse_int_list(filters.get("regional_district_filter"))

    from_res_id = row.get("from_res_id")
    from_rd_id = row.get("from_rd_id")
    to_res_id = row.get("to_res_id")
    to_country_id = row.get("to_country_id")
    to_rd_id = row.get("to_rd_id")
    to_eu_id = row.get("to_eu_id")

    linked_res_ids: set[int] = set()
    if from_res_id is not None:
        linked_res_ids.add(from_res_id)
    elif from_rd_id is not None:
        linked_res_ids.update(rd_res_map.get(from_rd_id, set()))

    source_ues_ids = {
        res_ues_map.get(res_id)
        for res_id in linked_res_ids
        if res_ues_map.get(res_id) is not None
    }
    source_est_ids = {
        res_est_map.get(res_id)
        for res_id in linked_res_ids
        if res_est_map.get(res_id) is not None
    }

    if ues_filter and not (source_ues_ids & set(ues_filter)):
        return False
    if est_filter and not (source_est_ids & set(est_filter)):
        return False
    if res_filter and not (linked_res_ids & set(res_filter)):
        return False
    if rd_filter:
        from_rd_ids: set[int] = set()
        if from_rd_id is not None:
            from_rd_ids.add(from_rd_id)
        if from_res_id is not None:
            from_rd_ids.update(res_rd_map.get(from_res_id, set()))
        if not (from_rd_ids & set(rd_filter)):
            return False
    if fd_filter:
        from_fd_ids: set[int] = set()
        if from_res_id is not None:
            from_fd_ids.update(res_fd_map.get(from_res_id, set()))
        if from_rd_id is not None:
            from_fd_ids.update(rd_fd_map.get(from_rd_id, set()))
        if not (from_fd_ids & set(fd_filter)):
            return False

    to_res_filter = _parse_int_list(filters.get("transfer_to_res_filter"))
    to_country_filter = _parse_int_list(filters.get("transfer_to_country_filter"))
    to_rd_filter = _parse_int_list(filters.get("transfer_to_rd_filter"))
    to_eu_filter = _parse_int_list(filters.get("transfer_to_energy_unit_filter"))
    if to_res_filter or to_country_filter or to_rd_filter or to_eu_filter:
        matches_res = bool(to_res_filter) and to_res_id is not None and to_res_id in to_res_filter
        matches_country = (
            bool(to_country_filter)
            and to_country_id is not None
            and to_country_id in to_country_filter
        )
        matches_rd = bool(to_rd_filter) and to_rd_id is not None and to_rd_id in to_rd_filter
        matches_eu = bool(to_eu_filter) and to_eu_id is not None and to_eu_id in to_eu_filter
        if not (matches_res or matches_country or matches_rd or matches_eu):
            return False
    return True


def _load_energy_unit_list() -> list[dict[str, Any]]:
    return [{"id": item.id, "name": item.name} for item in get_energy_unit_list().all()]


def _load_regional_district_list() -> list[dict[str, Any]]:
    return [{"id": rd_id, "name": rd_name} for rd_id, rd_name in sorted(get_regional_districts_map().items(), key=lambda x: x[1])]


def _load_foreign_border_country_list() -> list[dict[str, Any]]:
    q = ForeignBorderCountry.query.filter(
        ForeignBorderCountry.id.isnot(None),
        ForeignBorderCountry.id > 0,
    )
    q = filter_by_db_version(q, ForeignBorderCountry)
    items = q.order_by(
        ForeignBorderCountry.display_order.asc().nullslast(),
        ForeignBorderCountry.name.asc(),
    ).all()
    return [{"id": item.id, "name": item.name} for item in items]


def _load_transfer_rows(
    *,
    period_mode: str,
    selected_year: int | None,
    start_year: int | None,
    end_year: int | None,
) -> list[RegionalEnergySystemTransfer]:
    q = RegionalEnergySystemTransfer.query.options(
        joinedload(RegionalEnergySystemTransfer.from_regional_energy_system),
        joinedload(RegionalEnergySystemTransfer.from_regional_district),
        joinedload(RegionalEnergySystemTransfer.to_regional_energy_system),
        joinedload(RegionalEnergySystemTransfer.to_foreign_border_country),
        joinedload(RegionalEnergySystemTransfer.to_regional_district),
        joinedload(RegionalEnergySystemTransfer.to_energy_unit),
        joinedload(RegionalEnergySystemTransfer.union_energy_system),
    )
    q = filter_by_db_version(q, RegionalEnergySystemTransfer)

    if period_mode == EE_PERIOD_MODE_MONTHS:
        if selected_year is not None:
            q = q.filter(RegionalEnergySystemTransfer.year_number == selected_year)
        q = q.filter(RegionalEnergySystemTransfer.month_number != EE_TRANSFER_PERIOD_YEAR)
    else:
        if start_year is not None:
            q = q.filter(RegionalEnergySystemTransfer.year_number >= start_year)
        if end_year is not None:
            q = q.filter(RegionalEnergySystemTransfer.year_number <= end_year)
        q = q.filter(RegionalEnergySystemTransfer.month_number == EE_TRANSFER_PERIOD_YEAR)

    return q.all()


def _infer_transfer_ues_id(
    rec: RegionalEnergySystemTransfer,
    *,
    res_ues_map: dict[int, int | None],
    rd_res_map: dict[int, set[int]],
) -> int | None:
    """Для сводных перетоков без ОЭС в файле — ОЭС по РЭС/субъекту источника."""
    if rec.id_union_energy_system is not None:
        return rec.id_union_energy_system
    from_res_id = rec.id_from_regional_energy_system
    if from_res_id is not None:
        return res_ues_map.get(from_res_id)
    from_rd_id = rec.id_from_regional_district
    if from_rd_id is not None:
        for res_id in rd_res_map.get(from_rd_id, set()):
            ues_id = res_ues_map.get(res_id)
            if ues_id is not None:
                return ues_id
    return None


def _build_transfer_pairs(
    db_rows: list[RegionalEnergySystemTransfer],
    period_columns: list[tuple[int, str]],
) -> list[dict[str, Any]]:
    """Собирает уникальные пары перетоков с периодами."""
    ues_names = dict(get_union_energy_systems_map())
    ues_names[-1] = "Не указано"
    res_names = dict(get_regional_energy_systems_name_map())
    rd_names = dict(get_regional_districts_map())
    eu_names = {item.id: item.name for item in get_energy_unit_list().all()}
    territory_maps = _get_res_territory_maps()
    res_ues_map = territory_maps["res_ues_map"]
    rd_res_map = territory_maps["rd_res_map"]
    res_est_map = territory_maps["res_est_map"]

    pair_key_to_row: dict[tuple, dict[str, Any]] = {}

    for rec in db_rows:
        resolved_ues_id = _infer_transfer_ues_id(
            rec,
            res_ues_map=res_ues_map,
            rd_res_map=rd_res_map,
        )
        ues_id = resolved_ues_id if resolved_ues_id is not None else -1
        pair_key = (
            ues_id,
            rec.id_from_regional_energy_system,
            rec.id_from_regional_district,
            rec.id_to_regional_energy_system,
            rec.id_to_foreign_border_country,
            rec.id_to_regional_district,
            rec.id_to_energy_unit,
        )
        if pair_key not in pair_key_to_row:
            est_id = -1
            ues = rec.union_energy_system
            if ues and ues.id_energy_system_type is not None:
                est_id = ues.id_energy_system_type
            elif rec.id_from_regional_energy_system is not None:
                est_id = res_est_map.get(rec.id_from_regional_energy_system, -1)
            if rec.id_from_regional_energy_system is not None:
                from_name = res_names.get(rec.id_from_regional_energy_system) or rec.from_display_name
            else:
                from_name = rd_names.get(rec.id_from_regional_district) or rec.from_display_name
            if rec.id_to_regional_energy_system is not None:
                to_name = res_names.get(rec.id_to_regional_energy_system) or rec.to_display_name
            elif rec.id_to_foreign_border_country is not None:
                to_name = rec.to_display_name
            elif rec.id_to_regional_district is not None:
                to_name = rd_names.get(rec.id_to_regional_district) or rec.to_display_name
            else:
                to_name = eu_names.get(rec.id_to_energy_unit) or rec.to_display_name
            pair_key_to_row[pair_key] = {
                "ues_id": ues_id,
                "ues_name": rec.source_oes_name or ues_names.get(ues_id, f"id={ues_id}"),
                "est_id": est_id,
                "from_name": from_name,
                "to_name": to_name,
                "from_res_id": rec.id_from_regional_energy_system,
                "from_rd_id": rec.id_from_regional_district,
                "from_group_key": _from_group_key(
                    from_res_id=rec.id_from_regional_energy_system,
                    from_rd_id=rec.id_from_regional_district,
                ),
                "to_res_id": rec.id_to_regional_energy_system,
                "to_country_id": rec.id_to_foreign_border_country,
                "to_rd_id": rec.id_to_regional_district,
                "to_eu_id": rec.id_to_energy_unit,
                "periods": {period_key: None for period_key, _ in period_columns},
            }

        period_key = (
            rec.month_number
            if rec.month_number != EE_TRANSFER_PERIOD_YEAR
            else rec.year_number
        )
        pair_key_to_row[pair_key]["periods"][period_key] = rec.transfer_value

    return list(pair_key_to_row.values())


def _get_all_transfer_pairs(
    *,
    period_mode: str,
    selected_year: int | None,
    start_year: int | None,
    end_year: int | None,
    period_columns: list[tuple[int, str]],
) -> list[dict[str, Any]]:
    key_parts = (period_mode, selected_year, start_year, end_year)

    def _loader() -> list[dict[str, Any]]:
        db_rows = _load_transfer_rows(
            period_mode=period_mode,
            selected_year=selected_year,
            start_year=start_year,
            end_year=end_year,
        )
        return _build_transfer_pairs(db_rows, period_columns)

    return cached_load("transfer_pairs", key_parts, _loader)


def _transfer_row_destination_sort_key(row: dict[str, Any]) -> tuple:
    """РЭС, затем субъект РФ, энергорайон, зарубежная страна."""
    if row.get("to_res_id") is not None:
        target_type = 0
    elif row.get("to_rd_id") is not None:
        target_type = 1
    elif row.get("to_eu_id") is not None:
        target_type = 2
    else:
        target_type = 3
    return (target_type, (row.get("to_name") or "").lower())


def _sort_transfer_pairs(transfer_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ues_names = dict(get_union_energy_systems_map())
    ues_display_orders = get_union_energy_system_display_order_map()
    res_names = dict(get_regional_energy_systems_name_map())
    res_names[-1] = "Не указано"

    rd_names = dict(get_regional_districts_map())

    def _sort_key(row: dict[str, Any]) -> tuple:
        ues_key = union_energy_system_hierarchy_sort_key(
            row.get("ues_id"), ues_names, ues_display_orders
        )
        from_res_id = row.get("from_res_id")
        from_rd_id = row.get("from_rd_id")
        if from_res_id is not None:
            from_source_key = (0, res_names.get(from_res_id, ""))
        elif from_rd_id is not None:
            from_source_key = (1, rd_names.get(from_rd_id, ""))
        else:
            from_source_key = (2, "")
        return (*ues_key, *from_source_key, *_transfer_row_destination_sort_key(row))

    return sorted(transfer_rows, key=_sort_key)


def _build_hierarchy(
    transfer_rows: list[dict[str, Any]],
    period_columns: list[tuple[int, str]],
) -> list[dict[str, Any]]:
    ues_names = dict(get_union_energy_systems_map())
    ues_display_orders = get_union_energy_system_display_order_map()
    res_names = dict(get_regional_energy_systems_name_map())
    res_names[-1] = "Не указано"
    rd_names = dict(get_regional_districts_map())

    by_ues: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in transfer_rows:
        by_ues[row["ues_id"]].append(row)

    def _sort_key_ues(uid: int) -> tuple:
        return union_energy_system_hierarchy_sort_key(uid, ues_names, ues_display_orders)

    def _sort_key_group(group_key: str) -> tuple:
        kind, _, raw_id = group_key.partition(":")
        try:
            entity_id = int(raw_id)
        except (TypeError, ValueError):
            entity_id = -1
        if kind == "res":
            return (0, res_names.get(entity_id, ""))
        if kind == "rd":
            return (1, rd_names.get(entity_id, ""))
        return (2, group_key)

    def _sort_key_row(row: dict[str, Any]) -> tuple:
        return _transfer_row_destination_sort_key(row)

    result: list[dict[str, Any]] = []
    for ues_id in sorted(by_ues.keys(), key=_sort_key_ues):
        ues_rows = by_ues[ues_id]
        by_from_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in ues_rows:
            by_from_group[row.get("from_group_key") or "unknown"].append(row)

        res_list: list[dict[str, Any]] = []
        for group_key in sorted(by_from_group.keys(), key=_sort_key_group):
            rows = sorted(by_from_group[group_key], key=_sort_key_row)
            res_list.append(
                {
                    "group_key": group_key,
                    "res_id": rows[0].get("from_res_id") or rows[0].get("from_rd_id") or -1,
                    "res_name": rows[0].get("from_name") if rows else "—",
                    "transfer_rows": rows,
                }
            )

        result.append(
            {
                "ues_id": ues_id,
                "ues_name": ues_rows[0].get("ues_name") if ues_rows else ues_names.get(ues_id, "—"),
                "res_list": res_list,
            }
        )
    return result


def _build_transfer_aggregates(
    transfer_rows: list[dict[str, Any]],
    period_columns: list[tuple[int, str]],
) -> dict[str, Any]:
    ues_totals: dict[int, dict[int, Decimal]] = defaultdict(dict)
    from_group_totals: dict[str, dict[int, Decimal]] = defaultdict(dict)
    total: dict[int, Decimal] = {}

    for row in transfer_rows:
        ues_id = row.get("ues_id")
        group_key = row.get("from_group_key") or "unknown"
        for period_key, _ in period_columns:
            value = row.get("periods", {}).get(period_key)
            if value is None:
                continue
            _add_period_sum(total, period_key, value)
            if ues_id is not None:
                _add_period_sum(ues_totals[ues_id], period_key, value)
            _add_period_sum(from_group_totals[group_key], period_key, value)

    return {
        "union_energy_systems": dict(ues_totals),
        "from_groups": dict(from_group_totals),
        "total": total,
    }


def get_ee_transfers_page_data(
    filters: dict,
    page: int,
    rounding_digits: int,
    period_mode: str = EE_PERIOD_MODE_YEARS,
    selected_year: int | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    per_page: int | str = 10,
    show_totals: bool = False,
) -> dict[str, Any]:
    show_all = isinstance(per_page, str) and str(per_page).lower() == "all"
    list_filters = dict(filters or {})
    for key in ("start_year", "end_year", "year", "page", "ee_period_mode"):
        list_filters.pop(key, None)

    if period_mode == EE_PERIOD_MODE_MONTHS:
        if selected_year is None:
            selected_year, _ = resolve_single_year_filter()
        list_start_year = selected_year
        list_end_year = selected_year
        period_columns = MONTH_COLUMNS
    else:
        if start_year is None or end_year is None:
            start_year = get_ee_default_start_year()
            end_year = get_ee_default_end_year()
        if start_year > end_year:
            start_year, end_year = end_year, start_year
        list_start_year = start_year
        list_end_year = end_year
        period_columns = build_year_columns(start_year, end_year)

    all_pairs = _get_all_transfer_pairs(
        period_mode=period_mode,
        selected_year=selected_year,
        start_year=start_year,
        end_year=end_year,
        period_columns=period_columns,
    )

    territory_maps = _get_res_territory_maps()
    res_rd_map = territory_maps["res_rd_map"]
    rd_res_map = territory_maps["rd_res_map"]
    res_fd_map = territory_maps["res_fd_map"]
    rd_fd_map = territory_maps["rd_fd_map"]
    res_ues_map = territory_maps["res_ues_map"]
    res_est_map = territory_maps["res_est_map"]
    filtered_pairs = _sort_transfer_pairs(
        [
            row
            for row in all_pairs
            if _transfer_matches_filters(
                row,
                list_filters,
                res_rd_map,
                res_fd_map,
                res_ues_map,
                res_est_map,
                rd_res_map,
                rd_fd_map,
            )
        ]
    )

    total_count = len(filtered_pairs)

    try:
        per_page_int = int(per_page)
    except (TypeError, ValueError):
        per_page_int = 10
    if per_page_int <= 0:
        per_page_int = 10

    if show_all:
        page_pairs = filtered_pairs
        total_pages = 1
        current_page = 1
    else:
        total_pages = max(1, (total_count + per_page_int - 1) // per_page_int) if total_count else 1
        current_page = min(max(page, 1), total_pages)
        start_idx = (current_page - 1) * per_page_int
        page_pairs = filtered_pairs[start_idx : start_idx + per_page_int]

    hierarchy = _build_hierarchy(page_pairs, period_columns)

    should_show_totals = {
        "union_energy_systems": {},
        "from_groups": {},
        "total": False,
    }
    transfer_aggregates: dict[str, Any] = {}

    if show_totals or show_all:
        should_show_totals["total"] = show_totals or show_all
        for ues_block in _build_hierarchy(filtered_pairs, period_columns):
            should_show_totals["union_energy_systems"][ues_block["ues_id"]] = show_totals or show_all
            for res_block in ues_block.get("res_list") or []:
                should_show_totals["from_groups"][res_block["group_key"]] = (
                    show_totals or show_all
                )
        transfer_aggregates = _build_transfer_aggregates(filtered_pairs, period_columns)

    return {
        "total_count": total_count,
        "total_pages": total_pages,
        "page": current_page,
        "per_page": per_page,
        "hierarchy": hierarchy,
        "period_columns": period_columns,
        "period_mode": period_mode,
        "rounding_digits": rounding_digits,
        "selected_year": selected_year,
        "start_year": list_start_year,
        "end_year": list_end_year,
        "should_show_totals": should_show_totals,
        "transfer_aggregates": transfer_aggregates,
        "foreign_border_country_list": cached_load(
            "foreign_border_countries",
            (),
            _load_foreign_border_country_list,
        ),
        "transfer_regional_district_list": cached_load(
            "transfer_regional_districts",
            (),
            _load_regional_district_list,
        ),
        "transfer_energy_unit_list": cached_load(
            "transfer_energy_units",
            (),
            _load_energy_unit_list,
        ),
    }
