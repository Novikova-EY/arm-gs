"""Страница /energy_consumption/summary_table/ (сводная таблица, корень — разрез ОЭС)."""

from __future__ import annotations

from app.energy_consumption.pages._summary_page_common import attach_ec_summary_logs
from app.energy_consumption.pages._summary_page_transforms import (
    _mark_summary_table_collapsed_nt_gaes_variant_row_rules,
    _mark_summary_table_nt_on_gaes_off_variant_row_rules,
    convert_context_to_summary_table_page,
    finalize_oes_max_summary_tites_formula,
)
from app.energy_consumption.services.energy_consumption_summary_services import (
    append_summary_table_hub_energy_zone_footer_rows,
    apply_centralized_zone_with_nt_sum_formula,
    apply_centralized_zone_without_nt_sum_formula,
    build_oes_summary_context,
    inject_summary_table_cz_new_territories_reference_row,
    filter_summary_table_hub_oes_and_tites_verification_rows,
    get_demand_summary_filter_refdata,
    get_energy_consumption_oes_filter_cascade_data,
    apply_sipr_consumption_display_fallback_to_summary_rows,
    recompute_sipr_growth_metrics_for_summary_rows,
    mask_summary_rows_perimeter_variant_year_display,
    tag_ees_russia_sipr_integer_display_rows,
    tag_energy_consumption_summary_rows_for_territory_compact,
    tag_energy_consumption_summary_rows_perimeter_variant_labels,
)

PAGE_TEMPLATE = "energy_consumption/pages/summary_table_hub.html"


def build_summary_table_hub_page_context(
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
        include_oes_summary_table_sync_sa_ees_verification=True,
        expand_south_ues_perimeter_variants=True,
        summary_table_top_order=True,
    )
    context = convert_context_to_summary_table_page(context)
    context["page_title"] = "Потребление ЭЭ (свод)"
    append_summary_table_hub_energy_zone_footer_rows(
        context["summary_rows"],
        rounding_digits=rounding_digits,
        start_year=start_year,
        end_year=end_year,
        data_start_year=data_start_year,
        data_end_year=data_end_year,
        filter_year_list=filter_year_list,
    )
    if context.get("summary_rows") and context.get("years"):
        apply_centralized_zone_with_nt_sum_formula(
            context["summary_rows"],
            years=list(context["years"]),
            rounding_digits=rounding_digits,
        )
        apply_centralized_zone_without_nt_sum_formula(
            context["summary_rows"],
            years=list(context["years"]),
            rounding_digits=rounding_digits,
        )
        inject_summary_table_cz_new_territories_reference_row(
            context["summary_rows"],
            years=list(context["years"]),
            rounding_digits=rounding_digits,
        )
    if context.get("summary_rows"):
        tag_energy_consumption_summary_rows_for_territory_compact(context["summary_rows"])
        mask_summary_rows_perimeter_variant_year_display(
            context["summary_rows"],
            list(context.get("years") or []),
        )
        apply_sipr_consumption_display_fallback_to_summary_rows(
            context["summary_rows"],
            list(context.get("years") or []),
        )
        recompute_sipr_growth_metrics_for_summary_rows(
            context["summary_rows"],
            list(context.get("years") or []),
            rounding_digits,
        )
        tag_ees_russia_sipr_integer_display_rows(context["summary_rows"])
        _mark_summary_table_collapsed_nt_gaes_variant_row_rules(context["summary_rows"])
        _mark_summary_table_nt_on_gaes_off_variant_row_rules(context["summary_rows"])
    context = finalize_oes_max_summary_tites_formula(context)
    context["summary_variant_toggle_default_off"] = False
    if context.get("summary_rows"):
        context["summary_rows"] = filter_summary_table_hub_oes_and_tites_verification_rows(
            context["summary_rows"]
        )
        tag_energy_consumption_summary_rows_perimeter_variant_labels(
            context["summary_rows"],
            oes_summary=True,
            use_summary_perimeter_options=True,
        )
    context.update(get_demand_summary_filter_refdata())
    context["pd_oes_filters_cascade"] = get_energy_consumption_oes_filter_cascade_data()
    context["can_edit_summary_cells"] = can_edit_summary_cells
    context["has_active_summary_filters"] = bool(ues_l or eu_l)
    context["summary_route_variant"] = "max"
    context["coeff_base_year"] = coeff_base_year
    context["summary_include_medium_years"] = include_medium_years
    attach_ec_summary_logs(context)
    return context
