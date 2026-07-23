# -*- coding: utf-8 -*-
"""Западный/Центральный Саха (Якутия): до 2018 под ТИТЭС, с 2019 под ОЭС Востока."""
from __future__ import annotations

from unittest.mock import patch

import app.power_demand.services.demand_summary_services as dss


def test_is_sakha_yakutia_regional_energy_system_name() -> None:
    assert dss._is_sakha_yakutia_regional_energy_system_name(
        "ЭС Республики Саха (Якутия)"
    )
    assert not dss._is_sakha_yakutia_regional_energy_system_name("ЭС Якутии")
    assert not dss._is_sakha_yakutia_regional_energy_system_name("ЭС Магаданской области")


def test_mask_sakha_yakutia_splits_years_between_tites_and_oes_east(monkeypatch) -> None:
    monkeypatch.setattr(
        dss,
        "_tites_sakha_yakutia_extra_energy_unit_ids",
        lambda: frozenset({101, 102}),
    )
    years = [2018, 2019]
    tites_row = {
        "parameter_key": "max_power",
        "id_energy_unit": 101,
        "parent_fk_column": "id_energy_unit",
        "parent_id": 101,
        "entity_kind": dss._SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND,
        "pd_pd_sakha_tites_through_year_row": True,
        "year_values": ["10", "20"],
        "year_numeric_tooltips": ["10", "20"],
        "year_row_ids": [1, 2],
    }
    oes_row = {
        "parameter_key": "max_power",
        "id_energy_unit": 101,
        "parent_fk_column": "id_energy_unit",
        "parent_id": 101,
        "entity_kind": "child",
        "year_values": ["10", "20"],
        "year_numeric_tooltips": ["10", "20"],
        "year_row_ids": [1, 2],
    }
    dss.mask_sakha_yakutia_tites_oes_east_year_membership([tites_row, oes_row], years)

    assert tites_row["year_values"] == ["10", "—"]
    assert tites_row["year_row_ids"] == [1, None]
    assert oes_row["year_values"] == ["—", "20"]
    assert oes_row["year_row_ids"] == [None, 2]
    assert oes_row.get("pd_pd_sakha_oes_east_from_year_row") is True


def test_sum_tites_branch_includes_sakha_extra_only_through_2018(monkeypatch) -> None:
    monkeypatch.setattr(dss, "_tites_union_energy_system_ids", lambda: frozenset({77}))
    monkeypatch.setattr(
        dss,
        "_tites_sakha_yakutia_extra_energy_unit_ids",
        lambda: frozenset({101}),
    )
    years = [2018, 2019]
    rows = [
        {
            "parameter_key": "max_power",
            "id_union_energy_system": 77,
            "year_values": ["5", "6"],
        },
        {
            "parameter_key": "max_power",
            "id_energy_unit": 101,
            "parent_fk_column": "id_energy_unit",
            "parent_id": 101,
            "id_union_energy_system": None,
            "pd_pd_sakha_tites_through_year_row": True,
            "year_values": ["100", "—"],
        },
        {
            "parameter_key": "max_power",
            "id_energy_unit": 101,
            "parent_fk_column": "id_energy_unit",
            "parent_id": 101,
            "id_union_energy_system": 9,
            "pd_pd_sakha_oes_east_from_year_row": True,
            "year_values": ["—", "200"],
        },
    ]
    sums = dss._sum_tites_branch_max_power_in_summary_rows(rows, years)
    assert sums == [105.0, 6.0]


def test_build_tites_entity_appends_sakha_extra_without_res(monkeypatch) -> None:
    res_child = dss.SummaryEntity(
        label="ЭС ТИТЭС",
        depth=1,
        parameters=dss.PARAMETERS_TITES_OES_SUMMARY,
        demand_rows=[],
        entity_kind="child",
        demand_model_name="RegionalEnergySystemDemandParameter",
        parent_fk_column="id_regional_energy_system",
        parent_id=1,
        id_regional_energy_system=1,
    )
    sakha_west = dss.SummaryEntity(
        label="Западный энергорайон",
        depth=1,
        parameters=dss.PARAMETERS_TITES_OES_SUMMARY,
        demand_rows=[],
        entity_kind=dss._SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND,
        demand_model_name="EnergyUnitDemandParameter",
        parent_fk_column="id_energy_unit",
        parent_id=101,
        id_energy_unit=101,
        sakha_yakutia_tites_through_year_row=True,
    )
    sakha_central = dss.SummaryEntity(
        label="Центральный энергорайон",
        depth=1,
        parameters=dss.PARAMETERS_TITES_OES_SUMMARY,
        demand_rows=[],
        entity_kind=dss._SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND,
        demand_model_name="EnergyUnitDemandParameter",
        parent_fk_column="id_energy_unit",
        parent_id=102,
        id_energy_unit=102,
        sakha_yakutia_tites_through_year_row=True,
    )
    monkeypatch.setattr(
        dss,
        "_build_ues_entities_filtered",
        lambda *a, **k: [res_child],
    )
    monkeypatch.setattr(dss, "_unwrap_hidden_tites_ues_entities", lambda xs: list(xs))
    monkeypatch.setattr(
        dss,
        "_build_tites_sakha_yakutia_extra_energy_unit_entities",
        lambda: [sakha_west, sakha_central],
    )
    monkeypatch.setattr(
        dss, "_chukotka_territorial_boundaries_variant_enabled", lambda: False
    )

    entity = dss._build_tites_entity()
    assert entity is not None
    assert len(entity.children) == 3
    extras = entity.children[1:]
    assert [c.label for c in extras] == [
        "Западный энергорайон",
        "Центральный энергорайон",
    ]
    for extra in extras:
        assert extra.sakha_yakutia_tites_through_year_row is True
        assert extra.id_regional_energy_system is None
        assert extra.id_union_energy_system is None
        assert extra.depth == 1


def test_flatten_marks_sakha_tites_through_year_flag() -> None:
    entity = dss.SummaryEntity(
        label="Западный энергорайон",
        depth=1,
        parameters=(("max_power", "Максимум"),),
        demand_rows=[],
        entity_kind=dss._SAKHA_TITES_THROUGH_YEAR_ENTITY_KIND,
        demand_model_name="EnergyUnitDemandParameter",
        parent_fk_column="id_energy_unit",
        parent_id=101,
        id_energy_unit=101,
        sakha_yakutia_tites_through_year_row=True,
    )
    with patch.object(
        dss,
        "_build_parameter_maps",
        return_value=({"max_power": {2018: "1"}}, {"max_power": {}}),
    ), patch.object(dss, "_slice_row_ids", return_value={}), patch.object(
        dss, "_indexed_demand_rows_by_slice", return_value={}
    ), patch.object(dss, "_year_coeff_k_stored_for_flat", return_value=[]):
        rows = dss._flatten_entity(entity, [2018], 1)
    assert rows
    assert rows[0]["pd_pd_sakha_tites_through_year_row"] is True
    assert rows[0]["sakha_membership_through_year"] == 2018
