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
    original_hub = svc._build_oes_top_hub_ec_indexes
    svc._build_ec_consumption_index = lambda _years: ec_index
    # Пустой hub → fallback к сырому индексу EC (как раньше для ОЭС без формулы).
    svc._build_oes_top_hub_ec_indexes = (
        lambda _years, _rd, *, need_cz, need_ees_sa, pipeline_rows=None: (
            None,
            {} if need_ees_sa else None,
        )
    )
    try:
        inject_energy_consumption_rows(rows, years, 1)
    finally:
        svc._build_ec_consumption_index = original
        svc._build_oes_top_hub_ec_indexes = original_hub

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


def test_inject_energy_consumption_rows_for_ees_unified_uses_without_gaes_hub():
    """ЕЭС России (EnergySystemType): потребление без ГАЭС из hub, не with_gaes из БД."""
    from app.common.perimeter_variant.constants import (
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT_WITHOUT_GAES,
    )
    from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
        EnergySystemTypeDemandParameter,
    )

    years = [2025]
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "ЕЭС России без НТ",
            "entity_kind": "oes_top_aggregate",
            "entity_depth": 0,
            "demand_model_name": EnergySystemTypeDemandParameter.__name__,
            "parent_fk_column": "id_energy_system_type",
            "parent_id": 7,
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
    # В сыром индексе есть только «с ГАЭС» — раньше ошибочно подставлялось сюда.
    ec_index = {
        (
            "EnergySystemTypeEnergyConsumptionParameter",
            7,
            CODE_WITHOUT_NT_WITH_GAES,
            2025,
        ): 999999.0,
    }
    ees_sa_hub_index = {
        (
            "EnergySystemTypeEnergyConsumptionParameter",
            7,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2025,
        ): 1165000.5,
        (
            "EnergySystemTypeEnergyConsumptionParameter",
            7,
            CODE_WITHOUT_NT_WITH_GAES,
            2025,
        ): 999999.0,
    }

    from app.power_demand.services import pd_peak_usage_hours_services as svc

    original = svc._build_ec_consumption_index
    original_hub = svc._build_oes_top_hub_ec_indexes
    svc._build_ec_consumption_index = lambda _years: ec_index
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
    assert ee_rows[0]["year_values"] == ["1 165 000,5"]


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


def test_inject_energy_consumption_rows_for_ues_uses_without_gaes_hub():
    """ОЭС: потребление как на EC «без заряда ГАЭС», не устаревшие *_without_gaes из БД."""
    from app.common.perimeter_variant.constants import (
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT_WITHOUT_GAES,
    )

    years = [2016, 2017]
    ues_id = 42
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "ОЭС Юга без НТ",
            "entity_kind": "union_energy_system",
            "entity_depth": 0,
            "demand_model_name": UnionEnergySystemDemandParameter.__name__,
            "parent_fk_column": "id_union_energy_system",
            "parent_id": ues_id,
            "perimeter_variant_code": CODE_WITHOUT_NT,
            "parameter_key": "max_power",
            "hist_value": "10",
            "year_values": ["10", "10"],
        },
        {
            "parameter_key": "peak_datetime",
            "year_values": ["—", "—"],
        },
    ]
    # Сырой индекс: устаревшие/битые without_gaes (как 90 947.7 вместо 98 947.7).
    ec_index = {
        (
            "UnionEnergySystemEnergyConsumptionParameter",
            ues_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2016,
        ): 90_658.8,
        (
            "UnionEnergySystemEnergyConsumptionParameter",
            ues_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2017,
        ): 90_947.7,
        (
            "UnionEnergySystemEnergyConsumptionParameter",
            ues_id,
            CODE_WITHOUT_NT_WITH_GAES,
            2016,
        ): 90_700.3,
        (
            "UnionEnergySystemEnergyConsumptionParameter",
            ues_id,
            CODE_WITHOUT_NT_WITH_GAES,
            2017,
        ): 99_093.5,
    }
    # Hub: формула with_gaes − заряд ГАЭС (как /energy_consumption/summary/oes/).
    ees_sa_hub_index = {
        (
            "UnionEnergySystemEnergyConsumptionParameter",
            ues_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2016,
        ): 90_658.8,
        (
            "UnionEnergySystemEnergyConsumptionParameter",
            ues_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2017,
        ): 98_947.7,
    }

    from app.power_demand.services import pd_peak_usage_hours_services as svc

    original = svc._build_ec_consumption_index
    original_hub = svc._build_oes_top_hub_ec_indexes
    svc._build_ec_consumption_index = lambda _years: ec_index
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
    assert ee_rows[0]["year_values"] == ["90 658,8", "98 947,7"]


def test_first_sa_without_nt_ee_not_cut_by_kaliningrad_from_year_2025():
    """Первая СЗ без НТ: потребление по всем годам, даже если у варианта «Год с»=2025."""
    from app.common.perimeter_variant.constants import (
        CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
    )
    from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
        SynchronousAreaDemandParameter,
    )
    from app.power_demand.services.pd_peak_usage_hours_services import (
        _chi_ec_consumption_mln_for_anchor,
    )

    years = [2024, 2025, 2026]
    first_sa_id = 39
    pvc = CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES
    anchor = {
        "show_entity_cell": True,
        "entity_rowspan": 2,
        "entity_label": "Первая синхронная зона без НТ",
        "entity_kind": "synchronous_area",
        "entity_depth": 0,
        "demand_model_name": SynchronousAreaDemandParameter.__name__,
        "parent_fk_column": "id_synchronous_area",
        "parent_id": first_sa_id,
        "perimeter_variant_code": pvc,
        "parameter_key": "max_power",
        "hist_value": "10",
        "year_values": ["10", "11", "12"],
    }
    rows = [
        dict(anchor),
        {"parameter_key": "peak_datetime", "year_values": ["—", "—", "—"]},
    ]
    ees_sa_hub_index = {
        (
            "SynchronousAreaEnergyConsumptionParameter",
            first_sa_id,
            pvc,
            2024,
        ): 1_100_000.0,
        (
            "SynchronousAreaEnergyConsumptionParameter",
            first_sa_id,
            pvc,
            2025,
        ): 1_087_532.4,
        (
            "SynchronousAreaEnergyConsumptionParameter",
            first_sa_id,
            pvc,
            2026,
        ): 1_090_000.1,
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
        for year, expected in (
            (2024, 1_100_000.0),
            (2025, 1_087_532.4),
            (2026, 1_090_000.1),
        ):
            assert (
                _chi_ec_consumption_mln_for_anchor(
                    anchor,
                    year,
                    ec_index={},
                    ec_model_name="SynchronousAreaEnergyConsumptionParameter",
                    ec_parent_id=first_sa_id,
                    fk_column="id_synchronous_area",
                    years=years,
                    ees_sa_hub_index=ees_sa_hub_index,
                )
                == expected
            )
        inject_energy_consumption_rows(rows, years, 1)
    finally:
        svc._build_ec_consumption_index = original
        svc._build_oes_top_hub_ec_indexes = original_hub

    ee_rows = [r for r in rows if r.get("parameter_key") == ENERGY_CONSUMPTION_MLN_KVT_CH_KEY]
    assert len(ee_rows) == 1
    assert ee_rows[0]["year_values"] == ["1 100 000", "1 087 532,4", "1 090 000,1"]


def test_with_nt_ee_empty_until_nt_subjects_have_data():
    """Все «с НТ»: потребление пусто, пока нет данных по субъектам НТ."""
    from unittest.mock import patch

    from app.common.perimeter_variant.constants import CODE_WITH_NT_WITHOUT_GAES
    from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
        SynchronousAreaDemandParameter,
    )
    from app.power_demand.services.pd_peak_usage_hours_services import (
        _chi_ec_consumption_mln_for_anchor,
    )
    from app.power_demand.services import pd_peak_usage_hours_services as svc

    years = [2022, 2023]
    first_sa_id = 39
    pvc = CODE_WITH_NT_WITHOUT_GAES
    anchor = {
        "entity_label": "Первая синхронная зона с НТ",
        "demand_model_name": SynchronousAreaDemandParameter.__name__,
        "parent_id": first_sa_id,
        "perimeter_variant_code": pvc,
    }
    ees_sa_hub_index = {
        (
            "SynchronousAreaEnergyConsumptionParameter",
            first_sa_id,
            pvc,
            2022,
        ): 1_120_000.0,
        (
            "SynchronousAreaEnergyConsumptionParameter",
            first_sa_id,
            pvc,
            2023,
        ): 1_125_781.0,
    }

    with patch.object(
        svc,
        "_sum_nt_subjects_ec_mln_for_chi",
        side_effect=lambda slice_key, **kwargs: (
            None if int(slice_key) < 2023 else 23_214.6
        ),
    ):
        assert (
            _chi_ec_consumption_mln_for_anchor(
                anchor,
                2022,
                ec_index={},
                ec_model_name="SynchronousAreaEnergyConsumptionParameter",
                ec_parent_id=first_sa_id,
                fk_column="id_synchronous_area",
                years=years,
                ees_sa_hub_index=ees_sa_hub_index,
            )
            is None
        )
        assert (
            _chi_ec_consumption_mln_for_anchor(
                anchor,
                2023,
                ec_index={},
                ec_model_name="SynchronousAreaEnergyConsumptionParameter",
                ec_parent_id=first_sa_id,
                fk_column="id_synchronous_area",
                years=years,
                ees_sa_hub_index=ees_sa_hub_index,
            )
            == 1_125_781.0
        )


def test_with_nt_ee_shows_before_2023_when_nt_data_exists():
    """«с НТ» не жёстко с 2023: если по НТ есть данные за 2022 — считаем 2022."""
    from unittest.mock import patch

    from app.common.perimeter_variant.constants import CODE_WITH_NT_WITHOUT_GAES
    from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
        UnionEnergySystemDemandParameter,
    )
    from app.power_demand.services.pd_peak_usage_hours_services import (
        _chi_ec_consumption_mln_for_anchor,
    )
    from app.power_demand.services import pd_peak_usage_hours_services as svc

    years = [2022, 2023]
    ues_id = 5
    pvc = CODE_WITH_NT_WITHOUT_GAES
    anchor = {
        "entity_label": "ОЭС Юга с НТ",
        "demand_model_name": UnionEnergySystemDemandParameter.__name__,
        "parent_id": ues_id,
        "perimeter_variant_code": pvc,
    }
    ees_sa_hub_index = {
        (
            "UnionEnergySystemEnergyConsumptionParameter",
            ues_id,
            pvc,
            2022,
        ): 136_421.7,
    }

    with patch.object(svc, "_sum_nt_subjects_ec_mln_for_chi", return_value=45_000.0):
        assert (
            _chi_ec_consumption_mln_for_anchor(
                anchor,
                2022,
                ec_index={},
                ec_model_name="UnionEnergySystemEnergyConsumptionParameter",
                ec_parent_id=ues_id,
                fk_column="id_union_energy_system",
                years=years,
                ees_sa_hub_index=ees_sa_hub_index,
            )
            == 136_421.7
        )
