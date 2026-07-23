# -*- coding: utf-8 -*-
"""Режим «Сводная таблица» на сводке /power_demand/summary/oes/."""

from app.power_demand.services import demand_summary_services as service


def test_filter_oes_summary_hidden_chukotka_rd_rows(monkeypatch):
    monkeypatch.setattr(
        service,
        "_chukotka_territorial_boundaries_variant_enabled",
        lambda: True,
    )
    rows = [
        {
            "entity_label": "ЭС Чукотского АО",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "parameter_key": "max_power",
        },
        {
            "entity_label": "Чукотский АО (в территориальных границах)",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_kind": "chukotka_territorial_boundaries",
            "demand_model_name": "RegionalDistrictDemandParameter",
            "parameter_key": "max_power",
        },
        {
            "entity_label": "Чукотский АО (в территориальных границах)",
            "show_entity_cell": False,
            "parameter_key": "peak_datetime",
        },
        {
            "entity_label": "Чукотский АО",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_kind": "child",
            "demand_model_name": "RegionalDistrictDemandParameter",
            "parameter_key": "max_power",
        },
        {
            "entity_label": "Чукотский АО",
            "show_entity_cell": False,
            "parameter_key": "peak_datetime",
        },
        {
            "entity_label": "Чаун-Билибинский",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "demand_model_name": "EnergyUnitDemandParameter",
            "parameter_key": "max_power",
        },
    ]

    filtered = service.filter_oes_summary_hidden_chukotka_rd_rows(rows)

    labels = [r["entity_label"] for r in filtered if r.get("show_entity_cell")]
    assert labels == [
        "ЭС Чукотского АО",
        "Чукотский АО (в территориальных границах)",
        "Чаун-Билибинский",
    ]
    assert not any(
        r.get("entity_label") == "Чукотский АО"
        and r.get("entity_kind") != "chukotka_territorial_boundaries"
        for r in filtered
    )


def test_filter_oes_summary_hides_chukotka_territorial_when_variant_absent(monkeypatch):
    monkeypatch.setattr(
        service,
        "_chukotka_territorial_boundaries_variant_enabled",
        lambda: False,
    )
    rows = [
        {
            "entity_label": "ЭС Чукотского АО",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "parameter_key": "max_power",
        },
        {
            "entity_label": "Чукотский АО (в территориальных границах)",
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_kind": "chukotka_territorial_boundaries",
            "demand_model_name": "RegionalDistrictDemandParameter",
            "parameter_key": "max_power",
        },
        {
            "entity_label": "Чукотский АО (в территориальных границах)",
            "show_entity_cell": False,
            "parameter_key": "peak_datetime",
        },
        {
            "entity_label": "Чаун-Билибинский",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "demand_model_name": "EnergyUnitDemandParameter",
            "parameter_key": "max_power",
        },
    ]

    filtered = service.filter_oes_summary_hidden_chukotka_rd_rows(rows)

    labels = [r["entity_label"] for r in filtered if r.get("show_entity_cell")]
    assert labels == ["ЭС Чукотского АО", "Чаун-Билибинский"]
    assert not any(
        "территориальных границах" in str(r.get("entity_label") or "")
        for r in filtered
    )


def test_territory_compact_keeps_new_territories_block_for_nt_toggle():
    """В «Сводной таблице» блок НТ не скрывается compact — только кнопкой «+ НТ»."""
    rows = [
        {
            "entity_label": "Новые территории",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 1,
            "pd_pd_nt_extra_row": True,
            "pd_pd_aggregation_level_row": True,
            "demand_model_name": None,
        },
        {
            "entity_label": "Запорожская область",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 2,
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

    assert rows[0].get("pd_pd_territory_compact_hide_row") is not True
    assert rows[0].get("pd_pd_territory_detail_row") is not True
    assert rows[1].get("pd_pd_territory_compact_hide_row") is not True
    assert rows[1].get("pd_pd_territory_detail_row") is not True
    assert rows[2]["pd_pd_territory_compact_hide_row"] is True
    assert rows[3]["pd_pd_territory_compact_hide_row"] is True
    assert rows[4]["pd_pd_territory_detail_row"] is True

    exported = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=True,
    )
    assert [r["entity_label"] for r in exported] == [
        "Новые территории",
        "Запорожская область",
    ]


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


def test_territory_compact_keeps_top_level_nt_aggregate_rows():
    rows = [
        {
            "entity_label": "Россия",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "pd_pd_nt_extra_row": True,
            "demand_model_name": "RussiaFederationDemandParameter",
        },
        {
            "entity_label": "ЭЭС России",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "pd_pd_nt_extra_row": True,
            "demand_model_name": "EesRussiaDemandParameter",
        },
    ]
    service.tag_power_demand_summary_rows_for_territory_compact(rows)

    assert rows[0].get("pd_pd_territory_compact_hide_row") is not True
    assert rows[0].get("pd_pd_territory_detail_row") is not True
    assert rows[1].get("pd_pd_territory_compact_hide_row") is not True

    exported = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=True,
    )
    assert [r["entity_label"] for r in exported] == ["Россия", "ЭЭС России"]


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


def test_territory_compact_keeps_nt_aggregation_subtree_on_ez_summary_with_nt_flag():
    """На ЭЗ блок «Новые территории» в compact не скрывается — видимость через «+ НТ»."""
    rows = [
        {
            "entity_label": "1 — ОЭС Юга",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 0,
            "demand_model_name": "EnergyZoneDemandParameter",
        },
        {
            "entity_label": "Новые территории",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 1,
            "pd_pd_aggregation_level_row": True,
            "pd_pd_nt_extra_row": True,
            "demand_model_name": None,
        },
        {
            "entity_label": "Запорожская область",
            "show_entity_cell": True,
            "entity_rowspan": 3,
            "entity_depth": 2,
            "pd_pd_nt_extra_row": True,
            "demand_model_name": "RegionalDistrictDemandParameter",
        },
        {
            "entity_label": "Запорожская область",
            "show_entity_cell": False,
            "entity_depth": 2,
            "parameter_key": "peak_datetime",
            "pd_pd_nt_extra_row": True,
            "demand_model_name": "RegionalDistrictDemandParameter",
        },
        {
            "entity_label": "РЭС обычный",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 1,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
        },
    ]

    service.tag_power_demand_summary_rows_for_territory_compact(rows)

    assert rows[1].get("pd_pd_territory_compact_hide_row") is not True
    assert rows[2].get("pd_pd_territory_compact_hide_row") is not True
    assert rows[2].get("pd_pd_territory_detail_row") is not True
    assert rows[4]["pd_pd_territory_detail_row"] is True
    assert rows[0].get("pd_pd_territory_compact_hide_row") is not True

    exported = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=True,
    )
    assert [r.get("entity_label") for r in exported] == [
        "1 — ОЭС Юга",
        "Новые территории",
        "Запорожская область",
        "Запорожская область",
    ]

def test_territory_compact_tites_block_shows_res_only_and_renames_header(monkeypatch):
    tites_ues_id = 77
    tites_res_id = 701
    norilsk_res_id = 702
    taimyr_label = (
        "Таймырский Долгано-Ненецкий муниципальный район, Туруханский район "
        "и городской округ г. Норильск Красноярского края"
    )

    monkeypatch.setattr(
        service,
        "_tites_union_energy_system_ids",
        lambda: frozenset({tites_ues_id}),
    )

    rows = [
        {
            "entity_label": "ТИТЭС и децентрализованная зона",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 0,
            "pd_pd_aggregation_level_row": True,
            "demand_model_name": None,
        },
        {
            "entity_label": "ЭС г. Норильска Красноярского края",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 1,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": norilsk_res_id,
            "parameter_key": "max_power",
        },
        {
            "entity_label": taimyr_label,
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 2,
            "demand_model_name": "EnergyUnitDemandParameter",
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": norilsk_res_id,
            "parameter_key": "max_power",
        },
        {
            "entity_label": "ЭС ТИТЭС Востока",
            "show_entity_cell": True,
            "entity_rowspan": 3,
            "entity_depth": 1,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": tites_res_id,
            "parameter_key": "max_power",
        },
        {
            "entity_label": "ЭС ТИТЭС Востока",
            "show_entity_cell": False,
            "entity_depth": 1,
            "demand_model_name": "RegionalEnergySystemDemandParameter",
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": tites_res_id,
            "parameter_key": "peak_datetime",
        },
        {
            "entity_label": "Таймырский",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 2,
            "demand_model_name": "EnergyUnitDemandParameter",
            "id_union_energy_system": tites_ues_id,
            "id_regional_energy_system": tites_res_id,
            "parameter_key": "max_power",
        },
        {
            "entity_label": "ДЗ энергорайон",
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_depth": 1,
            "demand_model_name": "EnergyUnitDemandParameter",
            "pd_pd_decentralized_zone_mark": True,
            "parameter_key": "max_power",
        },
    ]

    service.tag_power_demand_summary_rows_for_territory_compact(rows)

    assert rows[0]["pd_pd_entity_label_territory_compact"] == "ТИТЭС"
    assert rows[1]["pd_pd_territory_compact_hide_row"] is True
    assert rows[2].get("pd_pd_territory_detail_row") is not True
    assert rows[3].get("pd_pd_territory_detail_row") is not True
    assert rows[5]["pd_pd_territory_detail_row"] is True
    assert rows[6]["pd_pd_territory_compact_hide_row"] is True

    exported = service.apply_power_demand_summary_territory_compact_export_ui(
        rows,
        territory_compact_on=True,
    )
    labels = [r.get("entity_label") for r in exported if r.get("show_entity_cell")]
    assert labels == ["ТИТЭС", taimyr_label, "ЭС ТИТЭС Востока"]
