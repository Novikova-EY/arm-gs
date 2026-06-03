"""Страница /energy_consumption/summary/oes/."""

from __future__ import annotations

from app.energy_consumption.pages._summary_page_common import attach_ec_summary_logs
from app.energy_consumption.pages._summary_page_transforms import (
    apply_max_summary_page_variant_behaviour,
    finalize_oes_max_summary_tites_formula,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    build_oes_summary_context,
    filter_oes_max_summary_page_hidden_rows,
    get_demand_summary_filter_refdata,
    get_energy_consumption_oes_filter_cascade_data,
)

PAGE_TEMPLATE = "energy_consumption/pages/summary_oes.html"


def build_summary_oes_page_context(
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
        ees_top_from_db=True,
        russia_country_summary_ec_divisor=1,
        include_ees_russia_rows=False,
        include_synchronous_area_rows=False,
        include_oes_summary_table_sync_sa_ees_verification=False,
        expand_south_ues_perimeter_variants=True,
        summary_table_top_order=True,
    )
    context = apply_max_summary_page_variant_behaviour(context)
    context["summary_rows"] = filter_oes_max_summary_page_hidden_rows(
        list(context.get("summary_rows") or [])
    )
    context = finalize_oes_max_summary_tites_formula(context)
    context["summary_variant_toggle_default_off"] = False
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_energy_consumption_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_summary_cells
    context["has_active_summary_filters"] = bool(ues_l or res_l or rd_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = coeff_base_year
    context["summary_include_medium_years"] = include_medium_years
    attach_ec_summary_logs(context)
    return context
