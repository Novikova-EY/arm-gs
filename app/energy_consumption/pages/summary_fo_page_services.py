"""Страница /energy_consumption/summary/federal_districts/."""

from __future__ import annotations

from app.energy_consumption.pages._summary_page_transforms import (
    apply_max_summary_page_variant_behaviour,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    _mark_summary_table_collapsed_nt_gaes_variant_row_rules,
    _mark_summary_table_expanded_nt_gaes_variant_row_rules,
    _mark_summary_table_nt_on_gaes_off_variant_row_rules,
    append_summary_table_hub_energy_zone_footer_rows,
    apply_sipr_consumption_display_fallback_to_summary_rows,
    build_federal_district_summary_context,
    exclude_centralized_zone_russia_non_o1_summary_rows,
    get_demand_summary_filter_refdata,
    get_energy_consumption_fo_filter_cascade_data,
    inject_summary_table_cz_new_territories_reference_row,
    keep_centralized_zone_rows_in_territory_compact,
    mask_summary_rows_perimeter_variant_year_display,
    recompute_sipr_growth_metrics_for_summary_rows,
    tag_ees_russia_sipr_integer_display_rows,
    tag_energy_consumption_summary_rows_before_federal_district_blocks,
    tag_energy_consumption_summary_rows_for_territory_compact,
    tag_summary_table_energy_zone_footer_rows,
)

PAGE_TEMPLATE = "energy_consumption/pages/summary_fo.html"


def build_summary_fo_page_context(
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
    for_shell: bool = False,
) -> dict:
    f_fd, f_res = fo_filter_sets
    context = build_federal_district_summary_context(
        rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
        fo_filter_sets=fo_filter_sets,
        expand_entity_perimeter_variants=True,
        for_client_render_shell=for_shell,
    )
    if for_shell:
        context["page_title"] = "Потребление ЭЭ по ФО"
        context["summary_variant_toggle_default_off"] = True
        context.update(get_demand_summary_filter_refdata())
        context["pd_fo_filters_cascade"] = get_energy_consumption_fo_filter_cascade_data()
        context["can_edit_summary_cells"] = can_edit_summary_cells
        context["has_active_summary_filters"] = bool(f_fd or f_res)
        context["summary_route_variant"] = "max"
        context["coeff_base_year"] = coeff_base_year
        context["summary_include_medium_years"] = include_medium_years
        return context
    context = apply_max_summary_page_variant_behaviour(context)
    context["page_title"] = "Потребление ЭЭ по ФО"
    # Как на /summary/oes/: энергозоны Сибири/Востока нужны формулам ЦЗ и режиму «Сводная».
    append_summary_table_hub_energy_zone_footer_rows(
        context["summary_rows"],
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
    )
    tag_summary_table_energy_zone_footer_rows(context["summary_rows"])
    context["summary_rows"] = exclude_centralized_zone_russia_non_o1_summary_rows(
        list(context.get("summary_rows") or [])
    )
    if context.get("summary_rows") and context.get("years"):
        years = list(context["years"])
        inject_summary_table_cz_new_territories_reference_row(
            context["summary_rows"],
            years,
            rounding_digits=rounding_digits,
        )
        mask_summary_rows_perimeter_variant_year_display(
            context["summary_rows"],
            years,
            unrestricted_perimeter_variant_input=True,
        )
        apply_sipr_consumption_display_fallback_to_summary_rows(
            context["summary_rows"],
            years,
        )
        recompute_sipr_growth_metrics_for_summary_rows(
            context["summary_rows"],
            years,
            rounding_digits,
        )
        tag_ees_russia_sipr_integer_display_rows(context["summary_rows"])
    tag_energy_consumption_summary_rows_for_territory_compact(context["summary_rows"])
    keep_centralized_zone_rows_in_territory_compact(context["summary_rows"])
    _mark_summary_table_collapsed_nt_gaes_variant_row_rules(context["summary_rows"])
    _mark_summary_table_expanded_nt_gaes_variant_row_rules(context["summary_rows"])
    _mark_summary_table_nt_on_gaes_off_variant_row_rules(context["summary_rows"])
    tag_energy_consumption_summary_rows_before_federal_district_blocks(
        context["summary_rows"]
    )
    tag_summary_table_energy_zone_footer_rows(context["summary_rows"])
    context["summary_variant_toggle_default_off"] = True
    context["can_edit_summary_cells"] = can_edit_summary_cells
    context["has_active_summary_filters"] = bool(f_fd or f_res)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = coeff_base_year
    context["summary_include_medium_years"] = include_medium_years
    return context
