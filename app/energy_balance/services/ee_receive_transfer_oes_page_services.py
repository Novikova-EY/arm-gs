# -*- coding: utf-8 -*-
"""Страница годового приема/передачи электроэнергии между ОЭС."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.common.services.get_services.energy_systems.union_energy_system_get_services import (
    get_union_energy_system_display_order_map,
    get_union_energy_systems_map,
    union_energy_system_hierarchy_sort_key,
)
from app.common.services.get_services.years.year_feature_services import get_year_feature_dict
from app.energy_balance.services.ee_balance_generation_services import (
    classify_ee_balance_generation_years,
)
from app.energy_balance.services.ee_display_order_services import display_order_sort_key
from app.energy_balance.services.ee_receive_transfer_oes_value_services import (
    load_ee_receive_transfer_oes_values,
)
from app.energy_balance.services.ee_transfers_page_services import (
    _get_res_territory_maps,
    _infer_transfer_target_res_id,
    _parse_int_list,
    format_transfer_cell,
    get_ee_transfers_page_data,
)
from app.energy_balance.services.energy_balance_year_filter_services import (
    get_ee_default_end_year,
    get_ee_default_start_year,
)
from app.energy_balance.services.station_ee_generation_page_services import (
    EE_PERIOD_MODE_YEARS,
    build_year_columns,
)

RECEIVE_LABEL = "Прием"
TRANSFER_LABEL = "Передача"


def _oes_display_sort_key(
    ues_id: int,
    ues_names: dict[int, str],
    display_orders: dict[int, int | None],
) -> tuple:
    """Порядок ОЭС как в справочнике: сначала display_order, затем наименование."""
    return display_order_sort_key(
        display_orders.get(ues_id), ues_names.get(ues_id), ues_id
    )


def get_ee_receive_transfer_oes_page_data(
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    rounding_digits: int = 1,
    direction_filter: list[str] | None = None,
    oes_filter: list[int] | None = None,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if start_year is None or end_year is None:
        start_year = get_ee_default_start_year()
        end_year = get_ee_default_end_year()
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    period_columns = build_year_columns(start_year, end_year)
    years = [year for year, _label in period_columns]
    year_features = get_year_feature_dict() or {}
    _fact_years, editable_years = classify_ee_balance_generation_years(
        years, year_features
    )
    transfer_data = get_ee_transfers_page_data(
        filters=filters or {},
        page=1,
        per_page="all",
        rounding_digits=rounding_digits,
        period_mode=EE_PERIOD_MODE_YEARS,
        start_year=min(start_year, get_ee_default_start_year()),
        end_year=end_year,
        show_totals=False,
    )

    ues_names = dict(get_union_energy_systems_map())
    ues_names[-1] = "Не указано"
    display_orders = get_union_energy_system_display_order_map()
    territory_maps = _get_res_territory_maps()
    res_ues_map = territory_maps["res_ues_map"]

    pair_totals: dict[tuple[int, int], dict[int, Decimal]] = defaultdict(dict)
    for transfer_row in transfer_data.get("all_rows") or []:
        source_ues_id = transfer_row.get("ues_id")
        target_res_id = _infer_transfer_target_res_id(
            transfer_row,
            territory_maps=territory_maps,
            ues_names=ues_names,
            display_orders=display_orders,
        )
        target_ues_id = res_ues_map.get(target_res_id)
        if source_ues_id is None or target_ues_id is None:
            continue
        pair = (source_ues_id, target_ues_id)
        if source_ues_id == target_ues_id:
            # Перетоки РЭС внутри одной ОЭС не суммируем.
            continue
        for year, value in (transfer_row.get("periods") or {}).items():
            if value is None:
                continue
            pair_totals[pair][year] = pair_totals[pair].get(year, Decimal(0)) + Decimal(str(value))

    raw_source_filter = (filters or {}).get("union_energy_system_filter")
    if raw_source_filter is not None and not isinstance(raw_source_filter, (list, tuple, set)):
        raw_source_filter = [raw_source_filter]
    source_filter = set(_parse_int_list(raw_source_filter))
    regional_filter = _parse_int_list((filters or {}).get("regional_energy_system_filter"))
    target_res_filter = _parse_int_list((filters or {}).get("transfer_to_res_filter"))
    # Сохраненные перетоки агрегированы по ОЭС, а фильтр РЭС выбирает исходные
    # записи, которые нельзя корректно заменить агрегатом всего ОЭС.
    if not regional_filter and not target_res_filter:
        for (source_ues_id, target_ues_id, year), value in load_ee_receive_transfer_oes_values(
            years=years
        ).items():
            if source_ues_id == target_ues_id:
                continue
            if source_filter and source_ues_id not in source_filter:
                continue
            pair_totals[(source_ues_id, target_ues_id)][year] = value

    selected_directions = set(direction_filter or []) & {"receive", "transfer"}
    selected_oes = set(oes_filter or [])
    target_options = sorted(
        {
            target_id: {"id": target_id, "name": ues_names.get(target_id, f"id={target_id}")}
            for _source_id, target_id in pair_totals
        }.values(),
        key=lambda item: _oes_display_sort_key(item["id"], ues_names, display_orders),
    )

    by_source: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for (source_ues_id, target_ues_id), values in pair_totals.items():
        if source_filter and source_ues_id not in source_filter:
            continue
        if selected_oes and target_ues_id not in selected_oes:
            continue
        by_direction: dict[str, dict[int, Decimal | None]] = {"receive": {}, "transfer": {}}
        for year in years:
            value = values.get(year)
            if value is None:
                continue
            direction = "receive" if value >= 0 else "transfer"
            by_direction[direction][year] = value
        if not any(by_direction.values()):
            history = [(year, value) for year, value in values.items() if year < start_year and value]
            if history:
                _, last_value = max(history)
                direction = "receive" if last_value > 0 else "transfer"
                by_direction[direction] = {year: None for year in years}

        for direction, direction_values in by_direction.items():
            if not direction_values or (selected_directions and direction not in selected_directions):
                continue
            by_source[source_ues_id].append(
                {
                    "direction": direction,
                    "direction_label": RECEIVE_LABEL if direction == "receive" else TRANSFER_LABEL,
                    "country_id": target_ues_id,
                    "country_name": ues_names.get(target_ues_id, f"id={target_ues_id}"),
                    "periods": direction_values,
                }
            )

    hierarchy = []
    for source_ues_id in sorted(
        by_source,
        key=lambda uid: union_energy_system_hierarchy_sort_key(uid, ues_names, display_orders),
    ):
        rows = sorted(
            by_source[source_ues_id],
            key=lambda row: (
                _oes_display_sort_key(row["country_id"], ues_names, display_orders),
                0 if row["direction"] == "receive" else 1,
            ),
        )
        for row in rows:
            row["cell_raw_values"] = {
                year: str(value) if value is not None else "" for year, value in row["periods"].items()
            }
            row["cell_values"] = {
                year: format_transfer_cell(row["periods"].get(year), rounding_digits)
                for year in years
            }
        hierarchy.append(
            {"ues_id": source_ues_id, "ues_name": ues_names.get(source_ues_id, f"id={source_ues_id}"), "rows": rows}
        )

    return {
        "hierarchy": hierarchy,
        "period_columns": period_columns,
        "year_features": year_features,
        "start_year": start_year,
        "end_year": end_year,
        "editable_years": editable_years,
        "direction_options": [
            {"id": "receive", "name": RECEIVE_LABEL},
            {"id": "transfer", "name": TRANSFER_LABEL},
        ],
        "country_options": target_options,
        "direction_filter": sorted(selected_directions),
        "country_filter": sorted(selected_oes),
    }
