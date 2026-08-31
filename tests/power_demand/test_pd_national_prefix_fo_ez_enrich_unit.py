# -*- coding: utf-8 -*-
"""Префикс ЕЭС/СЗ на ФО/ЭЗ заполняется теми же формулами ОЭС (скрытые источники)."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services import demand_summary_services as dss


def test_apply_national_prefix_oes_formulas_uses_hidden_ues_sources_when_absent() -> None:
    years = [2024]
    prefix_row = {
        "demand_model_name": "SynchronousAreaDemandParameter",
        "parameter_key": "max_power",
        "year_values": ["—"],
        "show_entity_cell": True,
    }
    source_row = {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": "combined_on_ees",
        "year_values": ["100"],
        "show_entity_cell": True,
        "id_union_energy_system": 7,
    }
    rows = [prefix_row]

    with (
        patch.object(
            dss,
            "_build_oes_national_prefix_source_rows",
            return_value=[source_row],
        ) as build_sources,
        patch.object(dss, "_enrich_national_prefix_calculated_max_like_oes") as enrich_calc,
        patch.object(dss, "apply_second_sa_from_ues_east_formula") as apply_second,
        patch.object(
            dss, "apply_kaliningrad_sa_from_kaliningrad_es_formula"
        ) as apply_kal,
    ):
        sources = dss._apply_national_prefix_oes_formulas(
            rows,
            years,
            rounding_digits=0,
            filter_year_list=years,
            enrich_calculated=True,
        )

    build_sources.assert_called_once()
    assert sources == [source_row]
    enrich_calc.assert_called_once()
    working = enrich_calc.call_args.args[0]
    assert working[0] is prefix_row
    assert working[1] is source_row
    assert apply_second.call_args.args[0] is working
    assert apply_kal.call_args.args[0] is working
    # Скрытые источники не остаются в исходном списке страницы.
    assert rows == [prefix_row]


def test_apply_national_prefix_oes_formulas_skips_rebuild_when_ues_already_present() -> None:
    years = [2024]
    rows = [
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "parameter_key": "combined_on_ees",
            "year_values": ["10"],
            "show_entity_cell": True,
            "id_union_energy_system": 1,
        }
    ]
    with (
        patch.object(dss, "_build_oes_national_prefix_source_rows") as build_sources,
        patch.object(dss, "_enrich_national_prefix_calculated_max_like_oes") as enrich_calc,
        patch.object(dss, "apply_second_sa_from_ues_east_formula"),
        patch.object(dss, "apply_kaliningrad_sa_from_kaliningrad_es_formula"),
    ):
        sources = dss._apply_national_prefix_oes_formulas(
            rows,
            years,
            rounding_digits=0,
            enrich_calculated=True,
        )

    build_sources.assert_not_called()
    assert sources == []
    enrich_calc.assert_called_once_with(
        rows,
        years,
        0,
        filter_year_list=years,
    )


def test_apply_national_prefix_oes_formulas_excludes_fo_territory_tree() -> None:
    """На ФО в working только префикс + скрытые ОЭС, без строк федеральных округов."""
    years = [2024]
    prefix_row = {
        "demand_model_name": "CentralizedZoneDemandParameter",
        "parameter_key": "max_power",
        "year_values": ["1"],
        "show_entity_cell": True,
        "entity_kind": "centralized_zone",
        "entity_depth": 0,
        "entity_rowspan": 1,
    }
    fo_row = {
        "demand_model_name": "FederalDistrictDemandParameter",
        "parameter_key": "max_power",
        "year_values": ["999"],
        "show_entity_cell": True,
        "entity_kind": "group",
        "entity_depth": 0,
        "entity_rowspan": 1,
        "parent_id": 3,
        "parent_fk_column": "id_federal_district",
    }
    source_row = {
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parameter_key": "combined_on_ees",
        "year_values": ["100"],
        "show_entity_cell": True,
        "id_union_energy_system": 7,
    }
    rows = [prefix_row, fo_row]

    with (
        patch.object(
            dss,
            "_build_oes_national_prefix_source_rows",
            return_value=[source_row],
        ),
        patch.object(dss, "_enrich_national_prefix_calculated_max_like_oes") as enrich_calc,
        patch.object(dss, "apply_second_sa_from_ues_east_formula"),
        patch.object(dss, "apply_kaliningrad_sa_from_kaliningrad_es_formula"),
    ):
        dss._apply_national_prefix_oes_formulas(
            rows,
            years,
            rounding_digits=0,
            enrich_calculated=True,
        )

    working = enrich_calc.call_args.args[0]
    assert prefix_row in working
    assert source_row in working
    assert fo_row not in working
    assert rows == [prefix_row, fo_row]


def test_finalize_fo_summary_context_applies_national_prefix_formulas() -> None:
    from app.power_demand.services.pd_summary_data_segments import (
        PD_SUMMARY_SEGMENT_CALC_MAX,
    )

    ctx = {
        "summary_rows": [{"show_entity_cell": True, "entity_kind": "centralized_zone"}],
        "years": [2024],
        "rounding_digits": 0,
        "filter_year_list": [2024],
        "avg_temp_uses_global_rounding": False,
        "fo_max_extended_parameters": True,
    }
    with (
        patch.object(dss, "reorder_centralized_zone_russia_variant_blocks_in_summary_rows"),
        patch.object(
            dss, "exclude_o1_perimeter_variant_summary_rows", side_effect=lambda r: r
        ),
        patch.object(dss, "_enrich_fo_summary_calculated_max_from_res"),
        patch.object(dss, "_inject_fo_max_cz_russia_calculated_max_row"),
        patch.object(
            dss, "_apply_national_prefix_oes_formulas", return_value=[]
        ) as apply_prefix,
        patch.object(dss, "_tag_common_power_demand_summary_rows"),
        patch.object(dss, "mask_power_demand_summary_rows_perimeter_variant_year_display"),
        patch.object(dss, "_clear_summary_hist_non_base_parameters"),
        patch.object(dss, "_filter_power_demand_summary_context_segments"),
        patch(
            "app.power_demand.services.pd_summary_entity_pagination.tag_summary_rows_before_section_blocks"
        ),
    ):
        dss._finalize_fo_summary_context(
            ctx, 0, frozenset({PD_SUMMARY_SEGMENT_CALC_MAX})
        )

    apply_prefix.assert_called_once()
    assert apply_prefix.call_args.kwargs.get("enrich_calculated") is True


def test_build_oes_national_prefix_source_rows_uses_page_cache(app) -> None:
    """Second call must reuse cached OES prefix sources (no flatten rebuild)."""
    years = [2024]
    fake_flat = [{"demand_model_name": "UnionEnergySystemDemandParameter", "x": 1}]
    with app.app_context():
        from app.power_demand.services import pd_summary_page_cache as page_cache

        page_cache._memory_cache = {}
        page_cache._cache_generation = 0
        with (
            patch.object(page_cache, "get_redis_client", return_value=None),
            patch.object(page_cache, "get_current_db_version_id", return_value=1),
            patch.object(dss, "_build_oes_union_energy_system_entities", return_value=[]),
            patch.object(dss, "_build_tites_entity", return_value=None),
            patch.object(dss, "_flatten_entities", return_value=fake_flat) as flatten,
            patch.object(dss, "_inject_south_ues_nt_rows_after_res"),
            patch.object(dss, "mask_sakha_yakutia_tites_oes_east_year_membership"),
        ):
            first = dss._build_oes_national_prefix_source_rows(years, 0)
            second = dss._build_oes_national_prefix_source_rows(years, 0)
        assert first == fake_flat
        assert second == fake_flat
        assert first is not second  # deepcopy from cache
        assert flatten.call_count == 1
