"""Страница /energy_consumption/summary_table/oes/."""

from __future__ import annotations

from app.energy_consumption.pages._summary_page_common import attach_ec_summary_logs
from app.energy_consumption.pages._summary_page_transforms import (
    convert_context_to_summary_table_page,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    build_oes_summary_context,
    get_demand_summary_filter_refdata,
    get_energy_consumption_oes_filter_cascade_data,
)

PAGE_TEMPLATE = "energy_consumption/pages/summary_table_oes.html"


def build_summary_table_oes_page_context(
    rounding_digits: int,
    *,
    start_year: int,
    end_year: int,
    data_start_year: int,
    data_end_year: int,
    filter_year_list: list[int],
    oes_territory_ordered: tuple[list[int], list[int], list[int], list[int]],
    coeff_base_year: int,
    include_medium_years: bool,
    can_edit_summary_cells: bool,
) -> dict:
    ues_l, _res_l, _rd_l, eu_l = oes_territory_ordered
    context = build_oes_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        oes_territory_ordered=oes_territory_ordered,
        ees_top_from_db=True,
        russia_country_summary_ec_divisor=1,
        include_oes_summary_table_sync_sa_ees_verification=True,
        expand_south_ues_perimeter_variants=True,
        summary_table_top_order=True,
    )
    context = convert_context_to_summary_table_page(context)
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_energy_consumption_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_summary_cells
    context["has_active_summary_filters"] = bool(ues_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = coeff_base_year
    context["summary_include_medium_years"] = include_medium_years
    attach_ec_summary_logs(context)
    return context
