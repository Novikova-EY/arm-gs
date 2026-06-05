"""Страница /energy_consumption/summary/energy-zones/."""

from __future__ import annotations

from app.energy_consumption.pages._summary_page_common import attach_ec_summary_logs
from app.energy_consumption.pages._summary_page_transforms import (
    apply_max_summary_page_variant_behaviour,
)
from app.energy_consumption.services.energy_consumption_gaes_charge_summary_services import (
    remove_gaes_charge_rows_from_summary_context,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    build_energy_zones_summary_context,
    exclude_centralized_zone_russia_o1_summary_rows,
    get_demand_summary_filter_refdata,
    get_energy_consumption_ez_filter_cascade_data,
)

PAGE_TEMPLATE = "energy_consumption/pages/summary_ez.html"


def build_summary_ez_page_context(
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
    ez_l, res_l = ez_territory_ordered
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
    context = apply_max_summary_page_variant_behaviour(context)
    context["page_title"] = "Потребление ЭЭ по ЭЗ"
    context = remove_gaes_charge_rows_from_summary_context(context)
    out = dict(context)
    out["summary_rows"] = exclude_centralized_zone_russia_o1_summary_rows(
        list(context.get("summary_rows") or [])
    )
    context = out
    context.update(get_demand_summary_filter_refdata())
    context["pd_ez_filters_cascade"] = get_energy_consumption_ez_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_summary_cells
    context["has_active_summary_filters"] = bool(ez_l or res_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = coeff_base_year
    context["summary_include_medium_years"] = include_medium_years
    attach_ec_summary_logs(context)
    return context
