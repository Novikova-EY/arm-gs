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
