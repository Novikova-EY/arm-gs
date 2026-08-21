"""Unit-тесты страницы /energy_consumption/summary/oes/."""

from app.energy_consumption.pages import _summary_page_transforms as transforms
from app.energy_consumption.services import energy_consumption_summary_services as service


def test_tag_summary_table_energy_zone_footer_rows_for_compact():
    rows = [
        {"entity_label": "ЦЗ России с НТ"},
        {"entity_label": "Энергозона Сибири", "show_entity_cell": True, "entity_depth": 0},
        {"entity_label": "Энергозона Востока", "show_entity_cell": True, "entity_depth": 0},
        {"entity_label": "ОЭС Центра", "show_entity_cell": True, "entity_depth": 0},
    ]
    service.tag_summary_table_energy_zone_footer_rows(rows)
    assert "pd_ec_summary_table_only_row" not in rows[0]
    assert rows[1].get("pd_ec_summary_table_only_row") is True
    assert rows[1].get("pd_ec_o1_form_row") is True
    assert rows[1].get("pd_ec_show_o1_badge") is True
    assert rows[2].get("pd_ec_summary_table_only_row") is True
    assert rows[2].get("pd_ec_o1_form_row") is True
    assert rows[2].get("pd_ec_show_o1_badge") is True
    assert "pd_ec_summary_table_only_row" not in rows[3]


def test_apply_max_skips_oes_ees_unified_formula_when_flag_set(monkeypatch):
    calls: list[str] = []

    monkeypatch.setattr(
        transforms,
        "mask_sakha_yakutia_tites_oes_east_year_membership",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "collapse_gaes_variant_split_for_entities_without_stations",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "apply_energy_consumption_summary_table_variant_toggle_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "apply_summary_table_russia_federation_row_rules",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "tag_oes_ees_unified_summary_nt_toggle_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "apply_oes_ees_unified_consumption_formula_to_summary_rows",
        lambda *_a, **_k: calls.append("unified"),
    )
    monkeypatch.setattr(
        transforms,
        "apply_oes_tites_root_formula_to_summary_rows",
        lambda *_a, **_k: calls.append("tites"),
    )
    monkeypatch.setattr(
        transforms,
        "apply_summary_table_formula_calculations",
        lambda *_a, **_k: calls.append("formulas"),
    )
    monkeypatch.setattr(
        transforms,
        "inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "inject_south_ues_new_territories_summary_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "inject_union_energy_system_without_gaes_summary_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "inject_oes_territory_detail_without_gaes_summary_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "inject_oes_summary_verification_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "filter_oes_summary_hidden_tites_union_energy_system_rows",
        lambda rows: rows,
    )
    monkeypatch.setattr(
        transforms,
        "inject_oes_tites_aggregate_verification_row",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "mask_summary_rows_perimeter_variant_year_display",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "apply_sipr_consumption_display_fallback_to_summary_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "recompute_sipr_growth_metrics_for_summary_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "tag_ees_russia_sipr_integer_display_rows",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "apply_union_energy_system_gaes_entity_labels",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "apply_oes_territory_detail_gaes_entity_labels",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "tag_energy_consumption_summary_rows_for_territory_compact",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "keep_centralized_zone_rows_in_territory_compact",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "_mark_summary_table_collapsed_nt_gaes_variant_row_rules",
        lambda *_a, **_k: None,
    )
    monkeypatch.setattr(
        transforms,
        "_mark_summary_table_nt_on_gaes_off_variant_row_rules",
        lambda *_a, **_k: None,
    )

    context = {
        "active_summary": "oes",
        "summary_rows": [{"entity_label": "ЕЭС России"}],
        "years": [2026],
        "rounding_digits": 1,
        "skip_oes_ees_unified_consumption_formula": True,
    }
    transforms.apply_max_summary_page_variant_behaviour(context)
    assert "unified" not in calls
    assert "tites" in calls
    assert "formulas" in calls

    calls.clear()
    context_no_skip = {
        "active_summary": "oes",
        "summary_rows": [{"entity_label": "ЕЭС России"}],
        "years": [2026],
        "rounding_digits": 1,
    }
    transforms.apply_max_summary_page_variant_behaviour(context_no_skip)
    assert calls[:3] == ["unified", "tites", "formulas"]


def test_apply_max_fo_and_ez_inject_shared_top_verification(monkeypatch):
    """ФО/ЭЗ получают те же проверки ЕЭС/первой СЗ, что и общий верх ОЭС."""
    inject_calls: list[str] = []

    def _noop(*_a, **_k):
        return None

    for name in (
        "apply_energy_consumption_summary_table_variant_toggle_rows",
        "apply_summary_table_russia_federation_row_rules",
        "tag_oes_ees_unified_summary_nt_toggle_rows",
        "apply_federal_district_formula_to_summary_rows",
        "apply_energy_zone_formula_to_summary_rows",
        "inject_south_fd_new_territories_summary_rows",
        "inject_federal_district_without_gaes_summary_rows",
        "inject_oes_territory_detail_without_gaes_summary_rows",
        "apply_gaes_without_charge_formula_to_summary_rows",
        "inject_east_energy_zone_o1_res_energy_unit_verification_rows",
        "inject_east_energy_zone_o1_parent_verification_row",
        "apply_summary_table_formula_calculations",
        "tag_energy_consumption_summary_rows_perimeter_variant_labels",
        "mask_summary_rows_perimeter_variant_year_display",
        "apply_sipr_consumption_display_fallback_to_summary_rows",
        "recompute_sipr_growth_metrics_for_summary_rows",
        "tag_ees_russia_sipr_integer_display_rows",
        "apply_fo_rd_gaes_territory_entity_labels",
        "apply_oes_territory_detail_gaes_entity_labels",
        "collapse_gaes_variant_split_for_entities_without_stations",
        "tag_energy_consumption_summary_rows_for_territory_compact",
        "keep_centralized_zone_rows_in_territory_compact",
        "apply_summary_page_shared_top_aggregate_values_from_summary_table_hub",
        "_mark_summary_table_collapsed_nt_gaes_variant_row_rules",
        "_mark_summary_table_nt_on_gaes_off_variant_row_rules",
    ):
        monkeypatch.setattr(transforms, name, _noop)

    monkeypatch.setattr(
        transforms,
        "inject_first_sa_without_nt_with_gaes_with_kaliningrad_ues_verification_after_ees_russia_rows",
        lambda *_a, **_k: inject_calls.append("verify"),
    )

    for active in ("fo", "ez", "oes"):
        inject_calls.clear()
        ctx = {
            "active_summary": active,
            "summary_rows": [{"entity_label": "ЕЭС России"}],
            "years": [2026],
            "rounding_digits": 1,
            "start_year": 2026,
            "end_year": 2026,
            "filter_year_list": [2026],
        }
        if active == "oes":
            for name in (
                "mask_sakha_yakutia_tites_oes_east_year_membership",
                "apply_oes_tites_root_formula_to_summary_rows",
                "inject_south_ues_new_territories_summary_rows",
                "inject_union_energy_system_without_gaes_summary_rows",
                "inject_oes_summary_verification_rows",
                "filter_oes_summary_hidden_tites_union_energy_system_rows",
                "inject_oes_tites_aggregate_verification_row",
                "apply_union_energy_system_gaes_entity_labels",
            ):
                monkeypatch.setattr(transforms, name, _noop)
            monkeypatch.setattr(
                transforms,
                "filter_oes_summary_hidden_tites_union_energy_system_rows",
                lambda rows: rows,
            )
        transforms.apply_max_summary_page_variant_behaviour(ctx)
        assert inject_calls == ["verify"], active
