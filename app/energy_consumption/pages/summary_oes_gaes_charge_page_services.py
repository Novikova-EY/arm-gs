"""Страница /energy_consumption/summary/oes/gaes_charge/."""

from __future__ import annotations

from app.energy_consumption.pages._summary_page_common import attach_ec_gaes_charge_logs
from app.energy_consumption.services.energy_consumption_gaes_charge_summary_services import (
    build_energy_consumption_gaes_charge_only_context,
    remove_oes_and_subject_rows_from_gaes_charge_context,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    build_oes_summary_context,
    get_demand_summary_filter_refdata,
    get_energy_consumption_oes_filter_cascade_data,
)

PAGE_TEMPLATE = "energy_consumption/pages/summary_oes_gaes_charge.html"


def build_summary_oes_gaes_charge_page_context(
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
    ues_l, res_l, rd_l, eu_l = oes_territory_ordered
    context = build_oes_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        oes_territory_ordered=oes_territory_ordered,
        include_synchronous_area_rows=False,
        include_russia_top_row=False,
    )
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_energy_consumption_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_summary_cells
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = coeff_base_year
    context["summary_include_medium_years"] = include_medium_years
    attach_ec_gaes_charge_logs(context)
    context = build_energy_consumption_gaes_charge_only_context(context)
    return remove_oes_and_subject_rows_from_gaes_charge_context(context)
