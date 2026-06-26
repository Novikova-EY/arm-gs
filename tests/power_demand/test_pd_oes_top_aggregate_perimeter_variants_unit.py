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
