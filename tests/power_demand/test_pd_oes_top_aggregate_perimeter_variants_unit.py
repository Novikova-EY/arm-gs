# -*- coding: utf-8 -*-
"""Верхние агрегаты на /power_demand/summary/oes/: без варианта «не указано»."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.power_demand.services import demand_summary_services as dss


def test_oes_top_aggregate_row_groups_exclude_unspecified_perimeter_variant() -> None:
    groups = [
        (None, []),
        ("without_nt_without_gaes", [object()]),
        ("with_nt_without_gaes", [object()]),
    ]
    with patch.object(
        dss,
        "_demand_row_groups_for_all_binding_variants",
        return_value=groups,
    ):
        filtered = dss._demand_row_groups_for_oes_top_aggregate(
            object(),
            None,
            None,
            binding=SimpleNamespace(),
        )
    assert filtered == [
        ("without_nt_without_gaes", groups[1][1]),
        ("with_nt_without_gaes", groups[2][1]),
    ]


def test_build_russia_perimeter_entities_skips_unspecified_variant() -> None:
    groups = [
        (None, []),
        ("without_nt_without_gaes", []),
    ]
    with patch.object(
        dss,
        "_demand_row_groups_for_all_binding_variants",
        return_value=groups,
    ):
        entities = dss._build_russia_perimeter_entities()
    assert len(entities) == 1
    assert entities[0].perimeter_variant_code == "without_nt_without_gaes"


def test_build_centralized_zone_perimeter_entities_prefers_o1_variants() -> None:
    groups = [
        ("with_nt", []),
        ("without_nt", []),
        ("o1_with_nt", []),
        ("o1_without_nt", []),
    ]
    with patch.object(
        dss,
        "_demand_row_groups_for_oes_top_aggregate",
        return_value=groups,
    ):
        entities = dss._build_centralized_zone_perimeter_entities(
            parameters=dss.PARAMETERS_CZ_OES_SUMMARY,
        )
    assert [e.perimeter_variant_code for e in entities] == [
        "o1_with_nt",
        "o1_without_nt",
    ]


def test_build_centralized_zone_perimeter_entities_skips_unspecified_variant() -> None:
    groups = [
        (None, []),
        ("without_nt_without_gaes", []),
        ("with_nt_without_gaes", []),
    ]
    with patch.object(
        dss,
        "_demand_row_groups_for_all_binding_variants",
        return_value=groups,
    ):
        entities = dss._build_centralized_zone_perimeter_entities(
            parameters=dss.PARAMETERS_CZ_OES_SUMMARY,
        )
    assert len(entities) == 2
    assert [e.perimeter_variant_code for e in entities] == [
        "without_nt_without_gaes",
        "with_nt_without_gaes",
    ]
    assert entities[0].demand_model_name == "CentralizedZoneDemandParameter"
    assert entities[0].entity_kind == "centralized_zone"
    assert entities[0].parameters == dss.PARAMETERS_CZ_OES_SUMMARY


def test_synchronous_area_summary_parameters_omit_combined_on_ees() -> None:
    """На сводной таблице у СЗ нет совмещённого на ЕЭС, расчёта и проверки к нему."""
    for params in (
        dss.PARAMETERS_SYNCHRONOUS_AREA,
        dss.PARAMETERS_FIRST_SYNCHRONOUS_AREA_OES_SUMMARY,
    ):
        keys = {k for k, _ in params}
        assert "combined_on_ees" not in keys
        assert "calculated_max_sa_mw" not in keys
        assert "max_power" in keys
        assert "calculated_max_power_mw" in keys


def test_build_national_and_sync_zone_prefix_entities_order() -> None:
    cz = object()
    ees = object()
    est = object()
    sa = object()
    with (
        patch.object(dss, "_build_centralized_zone_perimeter_entities", return_value=[cz]) as build_cz,
        patch.object(dss, "_build_ees_perimeter_entities", return_value=[ees]),
        patch.object(dss, "_build_ees_russia_perimeter_entities", return_value=[est]),
        patch.object(dss, "_build_synchronous_area_entities", return_value=[sa]),
    ):
        entities = dss._build_national_and_sync_zone_prefix_entities(
            cz_parameters=dss.PARAMETERS_CZ_OES_SUMMARY,
        )
    assert entities == [cz, ees, est, sa]
    build_cz.assert_called_once_with(parameters=dss.PARAMETERS_CZ_OES_SUMMARY)


def test_build_oes_raw_entities_starts_with_centralized_zone() -> None:
    cz = object()
    ees = object()
    est = object()
    sa = object()
    ues = object()
    with (
        patch.object(dss, "_build_centralized_zone_perimeter_entities", return_value=[cz]) as build_cz,
        patch.object(dss, "_build_ees_perimeter_entities", return_value=[ees]),
        patch.object(dss, "_build_ees_russia_perimeter_entities", return_value=[est]),
        patch.object(dss, "_build_synchronous_area_entities", return_value=[sa]),
        patch.object(dss, "_build_oes_union_energy_system_entities", return_value=[ues]),
        patch.object(dss, "_build_tites_entity", return_value=None),
    ):
        entities = dss._build_oes_raw_entities()
    assert entities == [cz, ees, est, sa, ues]
    build_cz.assert_called_once_with(parameters=dss.PARAMETERS_CZ_OES_SUMMARY)


def test_build_ez_raw_entities_uses_shared_national_prefix() -> None:
    prefix = [object(), object()]
    ez = object()
    with (
        patch.object(
            dss,
            "_build_national_and_sync_zone_prefix_entities",
            return_value=prefix,
        ) as build_prefix,
        patch.object(dss, "_build_energy_zone_entities", return_value=[ez]),
        patch.object(dss, "_build_tites_entity") as build_tites,
    ):
        entities = dss._build_ez_raw_entities(ez_max_extended_parameters=True)
    assert entities == prefix + [ez]
    build_prefix.assert_called_once_with(
        cz_parameters=dss.PARAMETERS_CZ_OES_SUMMARY,
        ees_russia_parameters=dss.PARAMETERS_EES_RUSSIA_OES_SUMMARY,
    )
    build_tites.assert_not_called()


def test_fo_summary_always_uses_shared_national_prefix() -> None:
    """И max, и coeff/ФО берут префикс ЦЗ→ЭЭС→ЕЭС→СЗ (не только ЦЗ)."""
    prefix = [object()]
    fo = [object()]
    with (
        patch.object(
            dss,
            "_build_national_and_sync_zone_prefix_entities",
            return_value=prefix,
        ) as build_prefix,
        patch.object(dss, "_build_federal_district_entities", return_value=fo),
        patch.object(dss, "_build_tites_entity") as build_tites,
        patch.object(dss, "_prepare_summary_demand_bulk_load"),
        patch.object(dss, "_expand_summary_entities_perimeter_variants", side_effect=lambda x: x),
        patch.object(
            dss,
            "_build_summary_context",
            return_value={"summary_rows": [], "years": [2024], "rounding_digits": 1},
        ),
        patch.object(dss, "_finalize_fo_summary_context"),
    ):
        dss.build_federal_district_summary_context(
            1,
            start_year=2024,
            end_year=2024,
            filter_year_list=[2024],
            fo_max_extended_parameters=False,
        )
    build_prefix.assert_called_once_with(cz_parameters=dss.PARAMETERS_CZ_OES_SUMMARY)
    build_tites.assert_not_called()
