"""Постобработка контекста сводки — вынесено из routes для страниц с отдельными шаблонами."""

from __future__ import annotations

from app.energy_consumption.services.energy_consumption_summary_services import (
    apply_energy_consumption_summary_table_variant_toggle_rows,
    apply_ees_russia_gaes_aggregate_formulas,
    apply_sipr_consumption_display_fallback_to_summary_rows,
    recompute_sipr_growth_metrics_for_summary_rows,
    _mark_summary_table_collapsed_nt_gaes_variant_row_rules,
    _mark_summary_table_nt_on_gaes_off_variant_row_rules,
    apply_federal_district_centralized_zone_values_from_summary_table_hub,
    apply_federal_district_formula_to_summary_rows,
    apply_fo_rd_gaes_territory_entity_labels,
    apply_gaes_without_charge_formula_to_summary_rows,
    apply_oes_territory_detail_gaes_entity_labels,
    apply_oes_tites_root_formula_to_summary_rows,
    apply_oes_ees_unified_consumption_formula_to_summary_rows,
    collapse_gaes_variant_split_for_entities_without_stations,
    tag_oes_ees_unified_summary_nt_toggle_rows,
    apply_summary_table_formula_calculations,
    apply_summary_table_russia_federation_row_rules,
    inject_summary_table_decentralized_zone_row,
    apply_union_energy_system_gaes_entity_labels,
    filter_oes_summary_hidden_tites_union_energy_system_rows,
    filter_summary_rows_for_summary_table_page,
    filter_summary_table_gaes_charge_aggregate_rows,
    inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows,
    inject_federal_district_without_gaes_summary_rows,
    inject_east_energy_zone_o1_parent_verification_row,
    inject_east_energy_zone_o1_res_energy_unit_verification_rows,
    inject_fo_summary_verification_rows,
    inject_oes_summary_verification_rows,
    inject_oes_territory_detail_without_gaes_summary_rows,
    inject_oes_tites_aggregate_verification_row,
    inject_south_fd_new_territories_summary_rows,
    inject_south_ues_new_territories_summary_rows,
    inject_union_energy_system_without_gaes_summary_rows,
    keep_centralized_zone_rows_in_territory_compact,
    mask_summary_rows_perimeter_variant_year_display,
    tag_ees_russia_sipr_integer_display_rows,
    tag_energy_consumption_summary_rows_for_territory_compact,
    tag_energy_consumption_summary_rows_perimeter_variant_labels,
)


def convert_context_to_summary_table_page(
    context: dict,
    *,
    keep_gaes_charge_territory_rows: bool = False,
    hide_gaes_charge_aggregate_rows: bool = True,
) -> dict:
    summary_rows = list(context.get("summary_rows") or [])
    source_summary_rows = list(summary_rows)
    tag_energy_consumption_summary_rows_for_territory_compact(summary_rows)
    context["summary_rows"] = filter_summary_rows_for_summary_table_page(
        summary_rows,
        keep_gaes_charge_territory_rows=keep_gaes_charge_territory_rows,
    )
    apply_energy_consumption_summary_table_variant_toggle_rows(context["summary_rows"])
    if context.get("active_summary") == "fo":
        apply_federal_district_formula_to_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_south_fd_new_territories_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_federal_district_without_gaes_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        apply_gaes_without_charge_formula_to_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        fo_res_sum_source_rows = list(source_summary_rows)
        inject_fo_summary_verification_rows(
            context["summary_rows"],
            source_rows=list(context["summary_rows"]),
            fo_res_sum_source_rows=fo_res_sum_source_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    if context.get("active_summary") == "oes":
        apply_summary_table_russia_federation_row_rules(context["summary_rows"])
        apply_oes_tites_root_formula_to_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
            eu_source_rows=source_summary_rows,
        )
        apply_summary_table_formula_calculations(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
            eu_source_rows_for_tites=source_summary_rows,
        )
        inject_summary_table_decentralized_zone_row(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_south_ues_new_territories_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        ues_res_sum_source_rows = list(source_summary_rows)
        inject_union_energy_system_without_gaes_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_oes_territory_detail_without_gaes_summary_rows(
            context["summary_rows"],
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        verification_source_rows = list(context["summary_rows"])
        inject_oes_summary_verification_rows(
            context["summary_rows"],
            source_rows=verification_source_rows,
            ues_res_sum_source_rows=ues_res_sum_source_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        context["summary_rows"] = filter_oes_summary_hidden_tites_union_energy_system_rows(
            context["summary_rows"]
        )
        inject_oes_tites_aggregate_verification_row(
            context["summary_rows"],
            source_rows=source_summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    tag_energy_consumption_summary_rows_perimeter_variant_labels(
        context["summary_rows"],
        oes_summary=context.get("active_summary") == "oes",
        use_summary_perimeter_options=True,
    )
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
        int(context.get("rounding_digits") or 1),
    )
    tag_ees_russia_sipr_integer_display_rows(context["summary_rows"])
    if context.get("active_summary") == "fo":
        apply_fo_rd_gaes_territory_entity_labels(context["summary_rows"])
        apply_oes_territory_detail_gaes_entity_labels(context["summary_rows"])
    if context.get("active_summary") == "oes":
        apply_union_energy_system_gaes_entity_labels(context["summary_rows"])
        apply_oes_territory_detail_gaes_entity_labels(context["summary_rows"])
    collapse_gaes_variant_split_for_entities_without_stations(context["summary_rows"])
    if hide_gaes_charge_aggregate_rows and context.get("active_summary") == "oes":
        context["summary_rows"] = filter_summary_table_gaes_charge_aggregate_rows(
            context["summary_rows"]
        )
    _mark_summary_table_collapsed_nt_gaes_variant_row_rules(context["summary_rows"])
    _mark_summary_table_nt_on_gaes_off_variant_row_rules(context["summary_rows"])
    context["summary_table_standalone"] = True
    context["summary_variant_toggle_default_off"] = False
    context["summary_table_hide_toggle"] = True
    context["summary_table_force_compact_mode"] = True
    context["summary_hub_endpoint"] = "energy_consumption_bp.summary_table_start"
    context["summary_oes_endpoint"] = "energy_consumption_bp.demand_summary_oes"
    context["summary_fo_endpoint"] = "energy_consumption_bp.demand_summary_federal_districts"
    context["summary_ez_endpoint"] = "energy_consumption_bp.demand_summary_energy_zones"
    if context.get("active_summary") == "oes":
        context["page_title"] = "Сводная информация по потреблению электрической энергии"
    context = dict(context)
    context["_eu_source_rows_for_tites"] = source_summary_rows
    return context


def apply_max_summary_page_variant_behaviour(context: dict) -> dict:
    """Варианты периметра и переключатели НТ/ГАЭС на страницах «максимумы» (/summary/...)."""
    summary_rows = list(context.get("summary_rows") or [])
    eu_source_rows_for_tites = list(summary_rows)
    apply_energy_consumption_summary_table_variant_toggle_rows(summary_rows)
    if context.get("active_summary") in ("oes", "fo", "ez"):
        apply_summary_table_russia_federation_row_rules(summary_rows)
    tag_oes_ees_unified_summary_nt_toggle_rows(summary_rows)
    if context.get("active_summary") == "fo":
        apply_federal_district_formula_to_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_south_fd_new_territories_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_federal_district_without_gaes_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_oes_territory_detail_without_gaes_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        apply_gaes_without_charge_formula_to_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_fo_summary_verification_rows(
            summary_rows,
            source_rows=list(summary_rows),
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    if context.get("active_summary") == "ez":
        inject_east_energy_zone_o1_res_energy_unit_verification_rows(
            summary_rows,
            source_rows=list(summary_rows),
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_east_energy_zone_o1_parent_verification_row(
            summary_rows,
            source_rows=list(summary_rows),
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    if context.get("active_summary") in ("fo", "ez"):
        # Верхние агрегаты (Россия / ЦЗ / ЭЭС / ЕЭС / СЗ) — как на /summary/oes/
        # и /summary_table/: формулы ГАЭС и СЗ, без суммы ОЭС для типа «ЕЭС».
        apply_summary_table_formula_calculations(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
            eu_source_rows_for_tites=eu_source_rows_for_tites,
        )
    if context.get("active_summary") == "oes":
        # На /summary/oes/ в режиме сводной таблицы значения «ЕЭС России» (тип ЭС)
        # должны совпадать с /summary_table/ (данные из БД + формулы ГАЭС), а не
        # пересчитываться как сумма ОЭС.
        if not context.get("skip_oes_ees_unified_consumption_formula"):
            apply_oes_ees_unified_consumption_formula_to_summary_rows(
                summary_rows,
                years=list(context.get("years") or []),
                rounding_digits=int(context.get("rounding_digits") or 1),
                ues_source_rows=eu_source_rows_for_tites,
            )
        apply_oes_tites_root_formula_to_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
            eu_source_rows=eu_source_rows_for_tites,
        )
        apply_summary_table_formula_calculations(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
            eu_source_rows_for_tites=eu_source_rows_for_tites,
        )
        inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_south_ues_new_territories_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        ues_res_sum_source_rows = list(summary_rows)
        inject_union_energy_system_without_gaes_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        inject_oes_territory_detail_without_gaes_summary_rows(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        source_summary_rows = list(summary_rows)
        inject_oes_summary_verification_rows(
            summary_rows,
            source_rows=source_summary_rows,
            ues_res_sum_source_rows=ues_res_sum_source_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
        summary_rows = filter_oes_summary_hidden_tites_union_energy_system_rows(
            summary_rows
        )
        inject_oes_tites_aggregate_verification_row(
            summary_rows,
            source_rows=ues_res_sum_source_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    tag_energy_consumption_summary_rows_perimeter_variant_labels(
        summary_rows,
        oes_summary=context.get("active_summary") == "oes",
        use_summary_perimeter_options=True,
    )
    mask_summary_rows_perimeter_variant_year_display(
        summary_rows,
        list(context.get("years") or []),
    )
    apply_sipr_consumption_display_fallback_to_summary_rows(
        summary_rows,
        list(context.get("years") or []),
    )
    recompute_sipr_growth_metrics_for_summary_rows(
        summary_rows,
        list(context.get("years") or []),
        int(context.get("rounding_digits") or 1),
    )
    tag_ees_russia_sipr_integer_display_rows(summary_rows)
    if context.get("active_summary") == "fo":
        apply_fo_rd_gaes_territory_entity_labels(summary_rows)
        apply_oes_territory_detail_gaes_entity_labels(summary_rows)
    if context.get("active_summary") == "oes":
        apply_union_energy_system_gaes_entity_labels(summary_rows)
        apply_oes_territory_detail_gaes_entity_labels(summary_rows)
    collapse_gaes_variant_split_for_entities_without_stations(summary_rows)
    tag_energy_consumption_summary_rows_for_territory_compact(summary_rows)
    if context.get("active_summary") in ("oes", "fo", "ez"):
        # Как на /power_demand/summary/oes/: «ЦЗ России» остаётся в режиме «Сводная таблица».
        keep_centralized_zone_rows_in_territory_compact(summary_rows)
    if context.get("active_summary") in ("fo", "ez"):
        # Значения «ЦЗ России …» как на /summary_table/ (формула по ОЭС недоступна без UES).
        apply_federal_district_centralized_zone_values_from_summary_table_hub(
            summary_rows,
            years=list(context.get("years") or []),
            rounding_digits=int(context.get("rounding_digits") or 1),
            start_year=int(context.get("start_year") or 0),
            end_year=int(context.get("end_year") or 0),
            filter_year_list=list(context.get("filter_year_list") or []),
        )
    _mark_summary_table_collapsed_nt_gaes_variant_row_rules(summary_rows)
    _mark_summary_table_nt_on_gaes_off_variant_row_rules(summary_rows)
    context = dict(context)
    context["summary_rows"] = summary_rows
    context["_eu_source_rows_for_tites"] = eu_source_rows_for_tites
    context["summary_variant_toggle_default_off"] = True
    return context


def finalize_oes_max_summary_tites_formula(context: dict) -> dict:
    """Повторно применяет формулу ТИТЭС после всех фильтров страницы /summary/oes/."""
    if context.get("active_summary") != "oes":
        return context
    summary_rows = list(context.get("summary_rows") or [])
    years = list(context.get("years") or [])
    if not summary_rows or not years:
        return context
    eu_source_rows = context.get("_eu_source_rows_for_tites") or summary_rows
    apply_oes_tites_root_formula_to_summary_rows(
        summary_rows,
        years=years,
        rounding_digits=int(context.get("rounding_digits") or 1),
        eu_source_rows=list(eu_source_rows),
    )
    if context.get("summary_table_standalone"):
        apply_ees_russia_gaes_aggregate_formulas(
            summary_rows,
            years,
            rounding_digits=int(context.get("rounding_digits") or 1),
            eu_source_rows_for_tites=list(eu_source_rows),
        )
    if not context.get("summary_table_standalone") and not any(
        str(row.get("entity_kind") or "") == "oes_tites_aggregate_check"
        for row in summary_rows
    ):
        inject_oes_tites_aggregate_verification_row(
            summary_rows,
            source_rows=list(eu_source_rows),
            years=years,
            rounding_digits=int(context.get("rounding_digits") or 1),
        )
    context = dict(context)
    context["summary_rows"] = summary_rows
    return context
