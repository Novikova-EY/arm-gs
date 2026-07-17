# -*- coding: utf-8 -*-
"""Юнит-тесты строк «Потребление ЭЭ» на сводках /power_demand/summary/."""

from app.common.perimeter_variant.registry import CODE_WITHOUT_NT
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.services.pd_peak_usage_hours_services import (
    ENERGY_CONSUMPTION_MLN_KVT_CH_KEY,
    ENERGY_CONSUMPTION_MLN_KVT_CH_LABEL,
    inject_energy_consumption_rows,
)
from app.power_demand.services.pd_summary_data_segments import (
    PD_SUMMARY_SEGMENT_EE,
    segment_for_parameter_key,
)


def test_ee_segment_maps_energy_consumption_key():
    assert (
        segment_for_parameter_key(ENERGY_CONSUMPTION_MLN_KVT_CH_KEY, scope="oes")
        == PD_SUMMARY_SEGMENT_EE
    )


def test_inject_energy_consumption_rows_before_max_power():
    years = [2025]
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 3,
            "entity_label": "ОЭС Центра",
            "entity_kind": "union_energy_system",
            "entity_depth": 0,
            "demand_model_name": UnionEnergySystemDemandParameter.__name__,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": 10,
            "perimeter_variant_code": CODE_WITHOUT_NT,
            "parameter_key": "max_power",
            "hist_value": "100",
            "year_values": ["100"],
        },
        {
            "parameter_key": "peak_datetime",
            "year_values": ["—"],
        },
        {
            "parameter_key": "avg_temp",
            "year_values": ["—"],
        },
    ]
    ec_index = {
        (
            "UnionEnergySystemEnergyConsumptionParameter",
            10,
            CODE_WITHOUT_NT,
            2025,
        ): 1234.5,
    }

    from app.power_demand.services import pd_peak_usage_hours_services as svc

    original = svc._build_ec_consumption_index
    svc._build_ec_consumption_index = lambda _years: ec_index
    try:
        inject_energy_consumption_rows(rows, years, 1)
    finally:
        svc._build_ec_consumption_index = original

    assert rows[0]["parameter_key"] == ENERGY_CONSUMPTION_MLN_KVT_CH_KEY
    assert rows[0]["parameter_label"] == ENERGY_CONSUMPTION_MLN_KVT_CH_LABEL
    assert rows[0]["pd_pd_ee_row"] is True
    assert rows[0]["show_entity_cell"] is True
    assert rows[0]["year_values"] == ["1 234,5"]
    assert rows[1]["parameter_key"] == "max_power"
    assert rows[1].get("show_entity_cell") is False
    assert all(r["entity_rowspan"] == 4 for r in rows)


def test_inject_energy_consumption_rows_for_centralized_zone_uses_hub_index():
    years = [2025]
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "ЦЗ России без НТ",
            "entity_kind": "centralized_zone",
            "entity_depth": 0,
            "demand_model_name": CentralizedZoneDemandParameter.__name__,
            "perimeter_variant_code": CODE_WITHOUT_NT,
            "parameter_key": "max_power",
            "hist_value": "10",
            "year_values": ["10"],
        },
        {
            "parameter_key": "peak_datetime",
            "year_values": ["—"],
        },
    ]
    ec_index = {
        (
            "CentralizedZoneEnergyConsumptionParameter",
            0,
            CODE_WITHOUT_NT,
            2025,
        ): 50.0,
    }
    cz_hub_index = {
        (CODE_WITHOUT_NT, 2025): 100.0,
    }

    from app.power_demand.services import pd_peak_usage_hours_services as svc

    original = svc._build_ec_consumption_index
    original_hub = svc._build_oes_top_hub_ec_indexes
    svc._build_ec_consumption_index = lambda _years: ec_index
    svc._build_oes_top_hub_ec_indexes = (
        lambda _years, _rd, *, need_cz, need_ees_sa, pipeline_rows=None: (
            cz_hub_index if need_cz else None,
            None,
        )
    )
    try:
        inject_energy_consumption_rows(rows, years, 0)
    finally:
        svc._build_ec_consumption_index = original
        svc._build_oes_top_hub_ec_indexes = original_hub

    ee_rows = [r for r in rows if r.get("parameter_key") == ENERGY_CONSUMPTION_MLN_KVT_CH_KEY]
    assert len(ee_rows) == 1
    assert ee_rows[0]["pd_pd_ee_row"] is True
    assert ee_rows[0]["year_values"] == ["100"]


def test_inject_energy_consumption_rows_for_ees_russia_uses_summary_table_hub():
    from app.common.perimeter_variant.constants import CODE_WITHOUT_NT_WITHOUT_GAES
    from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
        EesRussiaDemandParameter,
    )

    years = [2025]
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "ЭЭС России без НТ",
            "entity_kind": "oes_top_aggregate",
            "entity_depth": 0,
            "demand_model_name": EesRussiaDemandParameter.__name__,
            "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
            "parameter_key": "max_power",
            "hist_value": "10",
            "year_values": ["10"],
        },
        {
            "parameter_key": "peak_datetime",
            "year_values": ["—"],
        },
    ]
    ees_sa_hub_index = {
        (
            "EesRussiaEnergyConsumptionParameter",
            0,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2025,
        ): 1170079.9,
    }

    from app.power_demand.services import pd_peak_usage_hours_services as svc

    original = svc._build_ec_consumption_index
    original_hub = svc._build_oes_top_hub_ec_indexes
    svc._build_ec_consumption_index = lambda _years: {}
    svc._build_oes_top_hub_ec_indexes = (
        lambda _years, _rd, *, need_cz, need_ees_sa, pipeline_rows=None: (
            None,
            ees_sa_hub_index if need_ees_sa else None,
        )
    )
    try:
        inject_energy_consumption_rows(rows, years, 1)
    finally:
        svc._build_ec_consumption_index = original
        svc._build_oes_top_hub_ec_indexes = original_hub

    ee_rows = [r for r in rows if r.get("parameter_key") == ENERGY_CONSUMPTION_MLN_KVT_CH_KEY]
    assert len(ee_rows) == 1
    assert ee_rows[0]["year_values"] == ["1 170 079,9"]


def test_inject_energy_consumption_rows_for_second_sa_uses_hub_null_pvc():
    from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
        SynchronousAreaDemandParameter,
    )

    years = [2025]
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "Вторая синхронная зона",
            "entity_kind": "synchronous_area",
            "entity_depth": 0,
            "demand_model_name": SynchronousAreaDemandParameter.__name__,
            "parent_fk_column": "id_synchronous_area",
            "parent_id": 40,
            "perimeter_variant_code": None,
            "parameter_key": "max_power",
            "hist_value": "10",
            "year_values": ["10"],
        },
        {
            "parameter_key": "peak_datetime",
            "year_values": ["—"],
        },
    ]
    ees_sa_hub_index = {
        (
            "SynchronousAreaEnergyConsumptionParameter",
            40,
            None,
            2025,
        ): 50551.3,
    }

    from app.power_demand.services import pd_peak_usage_hours_services as svc

    original = svc._build_ec_consumption_index
    original_hub = svc._build_oes_top_hub_ec_indexes
    svc._build_ec_consumption_index = lambda _years: {}
    svc._build_oes_top_hub_ec_indexes = (
        lambda _years, _rd, *, need_cz, need_ees_sa, pipeline_rows=None: (
            None,
            ees_sa_hub_index if need_ees_sa else None,
        )
    )
    try:
        inject_energy_consumption_rows(rows, years, 1)
    finally:
        svc._build_ec_consumption_index = original
        svc._build_oes_top_hub_ec_indexes = original_hub

    ee_rows = [r for r in rows if r.get("parameter_key") == ENERGY_CONSUMPTION_MLN_KVT_CH_KEY]
    assert len(ee_rows) == 1
    assert ee_rows[0]["year_values"] == ["50 551,3"]
