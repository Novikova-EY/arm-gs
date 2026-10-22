# -*- coding: utf-8 -*-
"""Страница «Импорт/Экспорт ЭЭ» – годовые перетоки ЭЭ с зарубежными странами по ОЭС."""

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
from app.energy_balance.models.ee_import_export_oes_value_model import EeImportExportOesValue
from app.energy_balance.services.ee_balance_generation_services import (
    classify_ee_balance_generation_years,
)
from app.energy_balance.services.ee_display_order_services import display_order_sort_key
from app.energy_balance.services.ee_import_export_value_services import (
    load_ee_import_export_oes_values,
)
from app.energy_balance.services.ee_transfers_page_services import (
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

IMPORT_ROW_LABEL = "Импорт"
EXPORT_ROW_LABEL = "Экспорт"


def _country_sort_key(
    country_id: int,
    country_name: str,
    display_orders: dict[int, int | None],
) -> tuple:
    """Порядок справочника стран, при равных значениях – по наименованию."""
    return display_order_sort_key(
        display_orders.get(country_id), country_name, country_id
    )


def get_ee_import_export_page_data(
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    rounding_digits: int = 1,
    direction_filter: list[str] | None = None,
    country_filter: list[int] | None = None,
    filters: dict[str, Any] | None = None,
    saved_values_only: bool = False,
) -> dict[str, Any]:
    """Годовые перетоки по зарубежным странам, сгруппированные только по ОЭС.

    При ``saved_values_only=True`` не подменять отсутствующие записи суммами по РЭС.
    """
    if start_year is None or end_year is None:
        start_year = get_ee_default_start_year()
        end_year = get_ee_default_end_year()
    if start_year > end_year:
        start_year, end_year = end_year, start_year

    period_columns = build_year_columns(start_year, end_year)
    year_features = get_year_feature_dict() or {}
    _fact_years, editable_years = classify_ee_balance_generation_years(
        [year for year, _label in period_columns], year_features
    )
    transfer_data = get_ee_transfers_page_data(
        filters=filters or {},
        page=1,
        per_page=10,
        rounding_digits=rounding_digits,
        period_mode=EE_PERIOD_MODE_YEARS,
        start_year=min(start_year, get_ee_default_start_year()),
        end_year=end_year,
        show_totals=False,
    )

    names = dict(get_union_energy_systems_map())
    names[-1] = "Не указано"
    display_orders = get_union_energy_system_display_order_map()

    # Сложить источники-РЭС в одну пару «ОЭС – страна» до определения направления.
    foreign_countries = transfer_data.get("foreign_border_country_list") or []
    country_names_by_id = {item["id"]: item["name"] for item in foreign_countries}
    country_display_orders_by_id = {
        item["id"]: item.get("display_order") for item in foreign_countries
    }
    country_totals: dict[tuple[int, int, str], dict[int, Decimal | None]] = defaultdict(dict)
    source_rows = [] if saved_values_only else transfer_data.get("all_rows") or []
    for row in source_rows:
        country_id = row.get("to_country_id")
        if country_id is None:
            continue
        country_name = country_names_by_id.get(country_id) or row.get("to_name")
        if not country_name:
            continue
        ues_id = row.get("ues_id")
        if ues_id is None:
            continue
        key = (ues_id, country_id, country_name)
        for period_key, value in (row.get("periods") or {}).items():
            if value is None:
                continue
            country_totals[key][period_key] = (
                country_totals[key].get(period_key, Decimal(0)) + Decimal(str(value))
            )

    # Введённые по ОЭС значения важнее рассчитанной суммы исходных перетоков.
    years = [year for year, _label in period_columns]
    raw_ues_filter = (filters or {}).get("union_energy_system_filter")
    if raw_ues_filter is not None and not isinstance(raw_ues_filter, (list, tuple, set)):
        raw_ues_filter = [raw_ues_filter]
    ues_filter = set(_parse_int_list(raw_ues_filter))
    regional_filter = _parse_int_list((filters or {}).get("regional_energy_system_filter"))
    # Сохраненные значения агрегированы по ОЭС и не могут быть разложены по РЭС.
    if not regional_filter:
        for (ues_id, country_id, year), value in load_ee_import_export_oes_values(years=years).items():
            if ues_filter and ues_id not in ues_filter:
                continue
            country_name = country_names_by_id.get(country_id)
            if country_name:
                country_totals[(ues_id, country_id, country_name)][year] = value

    directions = ("import", "export")
    selected_directions = set(direction_filter or []) & set(directions)
    selected_countries = set(country_filter or [])
    country_options_by_id = {
        country_id: {"id": country_id, "name": country_name}
        for _ues_id, country_id, country_name in country_totals
    }
    country_options = sorted(
        country_options_by_id.values(),
        key=lambda country: _country_sort_key(
            country["id"], country["name"], country_display_orders_by_id
        ),
    )

    by_ues: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for (ues_id, country_id, country_name), periods in country_totals.items():
        by_direction: dict[str, dict[int, Decimal]] = {
            "import": {},
            "export": {},
        }
        for period_key, _label in period_columns:
            total = periods.get(period_key)
            if total is None:
                continue
            if total > 0:
                by_direction["import"][period_key] = total
            elif total < 0:
                by_direction["export"][period_key] = total

        if not any(by_direction.values()):
            historical_values = [
                (year, total)
                for year, total in periods.items()
                if year < start_year and total is not None and total != 0
            ]
            if historical_values:
                last_year, last_value = max(historical_values)
                direction = "import" if last_value > 0 else "export"
                by_direction[direction] = {year: None for year, _label in period_columns}

        for direction, direction_periods in by_direction.items():
            if not direction_periods:
                continue
            if selected_directions and direction not in selected_directions:
                continue
            if selected_countries and country_id not in selected_countries:
                continue
            by_ues[ues_id].append(
                {
                    "direction": direction,
                    "direction_label": IMPORT_ROW_LABEL if direction == "import" else EXPORT_ROW_LABEL,
                    "country_id": country_id,
                    "country_name": country_name,
                    "periods": direction_periods,
                }
            )

    hierarchy = []
    for ues_id in sorted(
        by_ues,
        key=lambda uid: union_energy_system_hierarchy_sort_key(uid, names, display_orders),
    ):
        rows = sorted(
            by_ues[ues_id],
            key=lambda row: (
                _country_sort_key(
                    row["country_id"], row["country_name"], country_display_orders_by_id
                ),
                0 if row["direction"] == "import" else 1,
            ),
        )
        for row in rows:
            row["cell_raw_values"] = {
                period_key: str(value) if value is not None else ""
                for period_key, value in row["periods"].items()
            }
            row["cell_values"] = {
                period_key: format_transfer_cell(row["periods"].get(period_key), rounding_digits)
                for period_key, _label in period_columns
            }
        hierarchy.append(
            {
                "ues_id": ues_id,
                "ues_name": names.get(ues_id, f"id={ues_id}"),
                "rows": rows,
            }
        )

    return {
        "hierarchy": hierarchy,
        "period_columns": period_columns,
        "year_features": year_features,
        "start_year": start_year,
        "end_year": end_year,
        "editable_years": editable_years,
        "direction_options": [
            {"id": direction, "name": IMPORT_ROW_LABEL if direction == "import" else EXPORT_ROW_LABEL}
            for direction in directions
        ],
        "country_options": country_options,
        "direction_filter": sorted(selected_directions),
        "country_filter": sorted(selected_countries),
    }
