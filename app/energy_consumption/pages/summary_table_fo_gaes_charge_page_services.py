"""Страница /energy_consumption/summary_table/federal_districts/gaes_charge/."""

from __future__ import annotations

from app.energy_consumption.pages._summary_page_common import attach_ec_gaes_charge_logs
from app.energy_consumption.pages._summary_page_transforms import (
    convert_context_to_summary_table_page,
)
from app.energy_consumption.services.energy_consumption_gaes_charge_summary_services import (
    build_energy_consumption_gaes_charge_only_context,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    build_federal_district_summary_context,
    get_demand_summary_filter_refdata,
    get_energy_consumption_fo_filter_cascade_data,
)

PAGE_TEMPLATE = "energy_consumption/pages/summary_table_fo_gaes_charge.html"


def build_summary_table_fo_gaes_charge_page_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    data_start_year: int,
    data_end_year: int,
    filter_year_list: list[int],
    fo_filter_sets: tuple[frozenset[int], frozenset[int]],
    coeff_base_year: int,
    include_medium_years: bool,
    can_edit_summary_cells: bool,
) -> dict:
    f_fd, _f_res = fo_filter_sets
    context = build_federal_district_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        fo_filter_sets=fo_filter_sets,
        expand_entity_perimeter_variants=True,
    )
    context = convert_context_to_summary_table_page(
        context,
        keep_gaes_charge_territory_rows=True,
        hide_gaes_charge_aggregate_rows=False,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_fo_filters_cascade"] = get_energy_consumption_fo_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_summary_cells
    context["has_active_summary_filters"] = bool(f_fd)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = coeff_base_year
    context["summary_include_medium_years"] = include_medium_years
    attach_ec_gaes_charge_logs(context)
    return build_energy_consumption_gaes_charge_only_context(context)
