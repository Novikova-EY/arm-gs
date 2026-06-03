"""Страница /energy_consumption/summary-table/energy-zones/."""

from __future__ import annotations

from app.energy_consumption.pages._summary_page_common import attach_ec_summary_logs
from app.energy_consumption.pages._summary_page_transforms import (
    convert_context_to_summary_table_page,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    build_energy_zones_summary_context,
    get_demand_summary_filter_refdata,
    get_energy_consumption_ez_filter_cascade_data,
)

PAGE_TEMPLATE = "energy_consumption/pages/summary_table_ez.html"


def build_summary_table_ez_page_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    data_start_year: int,
    data_end_year: int,
    filter_year_list: list[int],
    ez_territory_ordered: tuple[list[int], list[int]],
    coeff_base_year: int,
    include_medium_years: bool,
    can_edit_summary_cells: bool,
) -> dict:
    ez_l, _res_l = ez_territory_ordered
    context = build_energy_zones_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        ez_territory_ordered=ez_territory_ordered,
        expand_entity_perimeter_variants=True,
    )
    context = convert_context_to_summary_table_page(context)
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_energy_consumption_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_summary_cells
    context["has_active_summary_filters"] = bool(ez_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = coeff_base_year
    context["summary_include_medium_years"] = include_medium_years
    attach_ec_summary_logs(context)
    return context
