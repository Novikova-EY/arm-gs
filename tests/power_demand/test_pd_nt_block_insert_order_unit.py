# -*- coding: utf-8 -*-
"""Позиция блока «Новые территории» после «ОЭС Юга без НТ»."""

from app.power_demand.services.demand_summary_services import (
    _south_ues_base_res_subtree_insert_index,
)


def _row(
    *,
    label: str,
    kind: str,
    ues_id: int,
    pvc: str | None = None,
    rowspan: int = 1,
    agg: bool = False,
    show: bool = True,
) -> dict:
    return {
        "entity_label": label,
        "entity_kind": kind,
        "show_entity_cell": show,
        "entity_rowspan": rowspan,
        "id_union_energy_system": ues_id,
        "perimeter_variant_code": pvc,
        "pd_pd_aggregation_level_row": agg,
    }


def test_nt_insert_index_after_without_nt_when_with_nt_follows() -> None:
    south = 10
    rows = [
        _row(label="ОЭС Центра", kind="group", ues_id=1),
        _row(
            label="ОЭС Юга без НТ",
            kind="perimeter_variant",
            ues_id=south,
            pvc="without_nt",
            rowspan=2,
        ),
        _row(label="peak", kind="perimeter_variant", ues_id=south, show=False),
        _row(label="ЭС Ростовской", kind="child", ues_id=south, rowspan=1),
        _row(
            label="ОЭС Юга с НТ",
            kind="perimeter_variant",
            ues_id=south,
            pvc="with_nt",
            rowspan=1,
        ),
        _row(label="ОЭС Урала", kind="group", ues_id=2),
    ]
    assert _south_ues_base_res_subtree_insert_index(rows, south) == 4


def test_nt_insert_index_after_without_nt_when_with_nt_precedes() -> None:
    south = 10
    rows = [
        _row(
            label="ОЭС Юга с НТ",
            kind="perimeter_variant",
            ues_id=south,
            pvc="with_nt",
            rowspan=1,
        ),
        _row(
            label="ОЭС Юга без НТ",
            kind="perimeter_variant",
            ues_id=south,
            pvc="without_nt",
            rowspan=1,
        ),
        _row(label="ЭС Ростовской", kind="child", ues_id=south, rowspan=2),
        _row(label="peak", kind="child", ues_id=south, show=False),
        _row(label="ОЭС Урала", kind="group", ues_id=2),
    ]
    assert _south_ues_base_res_subtree_insert_index(rows, south) == 4


def test_nt_insert_index_stops_before_existing_nt_header() -> None:
    south = 10
    rows = [
        _row(
            label="ОЭС Юга без НТ",
            kind="perimeter_variant",
            ues_id=south,
            pvc="without_nt",
            rowspan=1,
        ),
        _row(label="ЭС Ростовской", kind="child", ues_id=south, rowspan=1),
        _row(
            label="Новые территории",
            kind="aggregation_level",
            ues_id=south,
            agg=True,
            rowspan=1,
        ),
        _row(label="ОЭС Урала", kind="group", ues_id=2),
    ]
    assert _south_ues_base_res_subtree_insert_index(rows, south) == 2
