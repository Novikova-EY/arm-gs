# -*- coding: utf-8 -*-
"""Режим «Сводная таблица» на сводке /power_demand/summary/oes/."""

from app.power_demand.services import demand_summary_services as service


def test_territory_compact_hides_nt_block_and_chukotka_territorial_rows():
    rows = [
        {
            "entity_label": "Новые территории",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "pd_pd_nt_extra_row": True,
            "pd_pd_aggregation_level_row": True,
            "demand_model_name": None,
        },
        {
            "entity_label": "Запорожская область",
            "show_entity_cell": False,
            "pd_pd_nt_extra_row": True,
            "demand_model_name": "RegionalDistrictDemandParameter",
        },
        {
            "entity_label": "Чукотский АО (в территориальных границах)",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_kind": "chukotka_territorial_boundaries",
            "demand_model_name": "RegionalDistrictDemandParameter",
        },
        {
            "entity_label": "Чукотский АО (в территориальных границах)",
            "show_entity_cell": False,
            "parameter_key": "calculated_max_power_mw",
            "demand_model_name": None,
        },
        {
            "entity_label": "Чукотский АО",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_kind": "child",
            "demand_model_name": "RegionalDistrictDemandParameter",
        },
    ]

    service.tag_power_demand_summary_rows_for_territory_compact(rows)

    assert rows[0]["pd_pd_territory_compact_hide_row"] is True
    assert rows[1]["pd_pd_territory_compact_hide_row"] is True
    assert rows[2]["pd_pd_territory_compact_hide_row"] is True
    assert rows[3]["pd_pd_territory_compact_hide_row"] is True
    assert rows[4].get("pd_pd_territory_compact_hide_row") is not True
    assert rows[4]["pd_pd_territory_detail_row"] is True

    exported = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=True,
    )
    assert len(exported) == 0


def test_territory_compact_hides_chi_and_verify_at_territory_detail_levels():
    rows = [
        {
            "entity_label": "РЭС-1",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
        },
        {
            "entity_label": "РЭС-1",
            "show_entity_cell": False,
            "pd_pd_chi_row": True,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "parameter_key": "peak_max_power_usage_hours",
        },
        {
            "entity_label": "Чукотский АО (в территориальных границах)",
            "show_entity_cell": True,
            "entity_rowspan": 3,
            "entity_kind": "chukotka_territorial_boundaries",
            "demand_model_name": "RegionalDistrictDemandParameter",
        },
        {
            "entity_label": "Чукотский АО (в территориальных границах)",
            "show_entity_cell": False,
            "pd_pd_verify_for_row": True,
            "demand_model_name": "RegionalDistrictDemandParameter",
            "parameter_key": "verify_for_calculated_max_power_mw",
        },
        {
            "entity_label": "ОЭС Сибири",
            "show_entity_cell": True,
            "demand_model_name": "UnionEnergySystemDemandParameter",
        },
        {
            "entity_label": "ОЭС Сибири",
            "show_entity_cell": False,
            "pd_pd_chi_row": True,
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "parameter_key": "peak_max_power_usage_hours",
        },
    ]

    service.tag_power_demand_summary_rows_for_territory_compact(rows)

    assert rows[1]["pd_pd_territory_compact_hide_row"] is True
    assert rows[3]["pd_pd_territory_compact_hide_row"] is True
    assert rows[1].get("pd_pd_territory_detail_row") is True
    assert rows[3].get("pd_pd_territory_detail_row") is True
    assert rows[5].get("pd_pd_territory_compact_hide_row") is not True

    exported = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=True,
    )
    assert [r.get("parameter_key") for r in exported] == ["peak_max_power_usage_hours"]
    assert exported[0]["entity_label"] == "ОЭС Сибири"


def test_territory_compact_export_keeps_top_level_rows():
    rows = [
        {
            "entity_label": "ОЭС Юга",
            "show_entity_cell": True,
            "demand_model_name": "UnionEnergySystemDemandParameter",
        },
        {
            "entity_label": "РЭС Юга",
            "show_entity_cell": True,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
        },
    ]
    service.tag_power_demand_summary_rows_for_territory_compact(rows)

    exported = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=True,
    )
    assert [r["entity_label"] for r in exported] == ["ОЭС Юга"]
