# -*- coding: utf-8 -*-
"""Юнит-тесты расчёта ЧЧИ на сводке /power_demand/summary/oes/."""

from app.common.perimeter_variant.constants import (
    CODE_WITHOUT_NT_WITHOUT_GAES,
    CODE_WITHOUT_NT_WITH_GAES,
    CODE_WITH_NT_WITHOUT_GAES,
    CODE_WITH_NT_WITH_GAES,
)
from app.common.perimeter_variant.registry import CODE_WITH_NT, CODE_WITHOUT_NT
from app.power_demand.models.energy_systems.energy_system_type_demand_parameter_model import (
    EnergySystemTypeDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
)
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.services.pd_peak_usage_hours_services import (
    PEAK_MAX_POWER_USAGE_HOURS_KEY,
    _chi_ec_consumption_mln_for_anchor,
    _chi_ec_consumption_mln_for_south_fd_with_nt,
    _chi_ec_consumption_pvc_for_anchor,
    _chi_ec_consumption_scale_for_pd_model,
    _divide_hours,
    _ec_consumption_pvc_candidates_for_chi,
    _lookup_ec_consumption_for_chi,
    _resolve_ec_parent_id_for_chi_block,
    inject_peak_usage_hours_rows,
)


def test_ues_chi_uses_same_perimeter_variant_as_max_power():
    anchor = {
        "demand_model_name": UnionEnergySystemDemandParameter.__name__,
        "entity_kind": "perimeter_variant",
        "perimeter_variant_code": CODE_WITH_NT,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT,
    ]


def test_ees_chi_uses_same_perimeter_variant_as_max_power():
    anchor = {
        "demand_model_name": EesRussiaDemandParameter.__name__,
        "entity_kind": "oes_top_aggregate",
        "perimeter_variant_code": CODE_WITH_NT,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT,
    ]


def test_first_sa_chi_uses_same_perimeter_variant_as_max_power():
    anchor = {
        "demand_model_name": SynchronousAreaDemandParameter.__name__,
        "entity_kind": "synchronous_area",
        "entity_label": "Первая синхронная зона без НТ",
        "perimeter_variant_code": CODE_WITHOUT_NT,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT,
        None,
    ]


def test_ees_chi_uses_resolved_stored_variant_code():
    anchor = {
        "demand_model_name": EesRussiaDemandParameter.__name__,
        "entity_kind": "oes_top_aggregate",
        "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT,
        None,
    ]


def test_ees_russia_chi_keeps_without_nt_variant_without_mapping():
    anchor = {
        "demand_model_name": EesRussiaDemandParameter.__name__,
        "entity_kind": "oes_top_aggregate",
        "entity_label": "ЭЭС России без НТ",
        "perimeter_variant_code": CODE_WITHOUT_NT,
    }
    assert _chi_ec_consumption_pvc_for_anchor(anchor) == CODE_WITHOUT_NT


def test_ees_unified_chi_keeps_with_nt_variant_without_mapping():
    anchor = {
        "demand_model_name": EnergySystemTypeDemandParameter.__name__,
        "entity_kind": "oes_top_aggregate",
        "entity_label": "ЕЭС России с НТ",
        "perimeter_variant_code": CODE_WITH_NT,
    }
    assert _chi_ec_consumption_pvc_for_anchor(anchor) == CODE_WITH_NT


def test_ees_unified_chi_resolves_none_pvc_from_entity_label():
    anchor = {
        "demand_model_name": EnergySystemTypeDemandParameter.__name__,
        "entity_kind": "group-root",
        "entity_label": "ЕЭС России без НТ",
        "parent_fk_column": "id_energy_system_type",
        "parent_id": 1,
        "perimeter_variant_code": None,
        "pd_pd_nt_extra_row": False,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT,
        None,
    ]


def test_lookup_chi_does_not_fallback_to_other_variants():
    ec_index = {
        ("UnionEnergySystemEnergyConsumptionParameter", 1, CODE_WITHOUT_NT_WITHOUT_GAES, 2025): 100.0,
        ("UnionEnergySystemEnergyConsumptionParameter", 1, CODE_WITH_NT, 2025): 200.0,
    }
    anchor = {
        "demand_model_name": UnionEnergySystemDemandParameter.__name__,
        "entity_kind": "perimeter_variant",
        "perimeter_variant_code": CODE_WITH_NT,
    }
    hit = _lookup_ec_consumption_for_chi(
        "UnionEnergySystemEnergyConsumptionParameter",
        1,
        anchor,
        2025,
        ec_index=ec_index,
        parent_fk_column="id_union_energy_system",
        years=[2025],
    )
    assert hit == 200.0


def test_decentralized_zone_chi_uses_same_perimeter_variant():
    ec_index = {
        ("EnergyUnitEnergyConsumptionParameter", 42, "o1", 2025): 15.0,
        ("EnergyUnitEnergyConsumptionParameter", 42, "with_nt", 2025): 99.0,
    }
    anchor = {
        "pd_pd_decentralized_zone_mark": True,
        "id_energy_unit": 42,
        "perimeter_variant_code": "with_nt",
    }
    hit = _chi_ec_consumption_mln_for_anchor(
        anchor,
        2025,
        ec_index=ec_index,
        ec_model_name="EnergyUnitEnergyConsumptionParameter",
        ec_parent_id=42,
        fk_column="id_energy_unit",
        years=[2025],
    )
    assert hit == 99.0


def test_chukotka_rd_uses_same_variant_as_other_entities():
    anchor = {
        "demand_model_name": "RegionalDistrictDemandParameter",
        "entity_label": "Чукотский АО",
        "entity_kind": "default",
        "perimeter_variant_code": "with_nt",
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT,
    ]


def test_resolve_ec_parent_id_when_refdata_id_differs_from_ec_rows():
    anchor = {
        "demand_model_name": EnergySystemTypeDemandParameter.__name__,
        "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
    }
    ec_index = {
        (
            "EnergySystemTypeEnergyConsumptionParameter",
            72,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2024,
        ): 100.0,
    }
    resolved = _resolve_ec_parent_id_for_chi_block(
        anchor,
        ec_model_name="EnergySystemTypeEnergyConsumptionParameter",
        anchor_parent_id=87,
        fk_column="id_energy_system_type",
        years=[2024],
        ec_index=ec_index,
    )
    assert resolved == 72


def test_divide_hours_multiplies_result_by_1000():
    assert _divide_hours(100.0, 10.0) == 10000.0
    assert _divide_hours(1.5, 3.0) == 500.0
    assert _divide_hours(None, 10.0) is None
    assert _divide_hours(100.0, None) is None


def test_chi_rounding_digits_is_integer():
    from app.power_demand.services.pd_peak_usage_hours_services import _CHI_ROUNDING_DIGITS

    assert _CHI_ROUNDING_DIGITS == -1


def test_chi_hours_formatted_as_integer():
    from app.power_demand.services.demand_summary_services import _format_numeric
    from app.power_demand.services.pd_peak_usage_hours_services import _CHI_ROUNDING_DIGITS

    assert _format_numeric(6123.7, _CHI_ROUNDING_DIGITS) == "6 124"
    assert _format_numeric(500.4, _CHI_ROUNDING_DIGITS) == "500"


def test_russia_federation_chi_scales_ec_consumption_by_1000():
    assert _chi_ec_consumption_scale_for_pd_model(
        RussiaFederationDemandParameter.__name__
    ) == 1000.0
    assert _chi_ec_consumption_scale_for_pd_model(
        EnergySystemTypeDemandParameter.__name__
    ) == 1.0

    ec_index = {
        ("RussiaFederationEnergyConsumptionParameter", 0, CODE_WITH_NT, 2025): 1.5,
    }
    anchor = {
        "demand_model_name": RussiaFederationDemandParameter.__name__,
        "perimeter_variant_code": CODE_WITH_NT,
    }
    hit = _chi_ec_consumption_mln_for_anchor(
        anchor,
        2025,
        ec_index=ec_index,
        ec_model_name="RussiaFederationEnergyConsumptionParameter",
        ec_parent_id=0,
        fk_column=None,
        years=[2025],
    )
    assert hit == 1500.0


def test_centralized_zone_chi_uses_same_perimeter_variant():
    anchor = {
        "demand_model_name": CentralizedZoneDemandParameter.__name__,
        "entity_kind": "centralized_zone",
        "perimeter_variant_code": CODE_WITH_NT,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITH_NT_WITHOUT_GAES,
        CODE_WITH_NT_WITH_GAES,
        CODE_WITH_NT,
    ]


def test_inject_peak_usage_hours_rows_for_centralized_zone_without_nt():
    years = [2025]
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 3,
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
        {
            "parameter_key": "avg_temp",
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

    from app.power_demand.services import pd_peak_usage_hours_services as chi_svc

    original = chi_svc._build_ec_consumption_index
    original_hub = chi_svc._build_centralized_zone_hub_ec_chi_index
    chi_svc._build_ec_consumption_index = lambda _years: ec_index
    chi_svc._build_centralized_zone_hub_ec_chi_index = lambda _years, _rd: cz_hub_index
    try:
        inject_peak_usage_hours_rows(rows, years, 0)
    finally:
        chi_svc._build_ec_consumption_index = original
        chi_svc._build_centralized_zone_hub_ec_chi_index = original_hub

    chi_rows = [r for r in rows if r.get("parameter_key") == PEAK_MAX_POWER_USAGE_HOURS_KEY]
    assert len(chi_rows) == 1
    assert chi_rows[0]["pd_pd_chi_row"] is True
    # Числитель из сводной таблицы (100), не из БД (50).
    assert chi_rows[0]["year_values"] == ["10 000"]


def test_ec_consumption_pvc_candidates_for_without_nt_include_null_fallback():
    anchor = {
        "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITHOUT_NT_WITHOUT_GAES,
        CODE_WITHOUT_NT_WITH_GAES,
        CODE_WITHOUT_NT,
        None,
    ]


def test_lookup_chi_falls_back_to_null_perimeter_variant_for_without_nt():
    ec_index = {
        (
            "FederalDistrictEnergyConsumptionParameter",
            125,
            None,
            2018,
        ): 76487.0,
        (
            "FederalDistrictEnergyConsumptionParameter",
            125,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2024,
        ): 86150.0,
    }
    anchor = {
        "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
    }
    assert (
        _lookup_ec_consumption_for_chi(
            "FederalDistrictEnergyConsumptionParameter",
            125,
            anchor,
            2018,
            ec_index=ec_index,
            parent_fk_column="id_federal_district",
            years=[2018, 2024],
        )
        == 76487.0
    )


def test_lookup_chi_does_not_fallback_to_null_perimeter_variant_for_with_nt():
    ec_index = {
        ("FederalDistrictEnergyConsumptionParameter", 125, None, 2024): 86150.0,
    }
    anchor = {
        "perimeter_variant_code": CODE_WITH_NT,
    }
    assert (
        _lookup_ec_consumption_for_chi(
            "FederalDistrictEnergyConsumptionParameter",
            125,
            anchor,
            2024,
            ec_index=ec_index,
            parent_fk_column="id_federal_district",
            years=[2024],
        )
        is None
    )


def test_south_fd_with_nt_chi_uses_without_nt_plus_nt_subjects_from_2023():
    south_fd_id = 125
    years = [2022, 2023, 2024]
    ec_index = {
        (
            "FederalDistrictEnergyConsumptionParameter",
            south_fd_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2022,
        ): 80.0,
        (
            "FederalDistrictEnergyConsumptionParameter",
            south_fd_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2023,
        ): 100.0,
        (
            "FederalDistrictEnergyConsumptionParameter",
            south_fd_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2024,
        ): 120.0,
        (
            "FederalDistrictEnergyConsumptionParameter",
            south_fd_id,
            CODE_WITH_NT_WITHOUT_GAES,
            2024,
        ): 999.0,
        ("RegionalDistrictEnergyConsumptionParameter", 916, None, 2023): 5.0,
        ("RegionalDistrictEnergyConsumptionParameter", 916, None, 2024): 20.0,
    }
    anchor = {
        "demand_model_name": FederalDistrictDemandParameter.__name__,
        "entity_label": "Южный ФО с НТ",
        "perimeter_variant_code": CODE_WITH_NT_WITHOUT_GAES,
    }

    from unittest.mock import patch

    from app.power_demand.services import pd_peak_usage_hours_services as chi_svc

    chi_svc._south_federal_district_id_for_chi.cache_clear()
    try:
        with patch.object(
            chi_svc,
            "_south_federal_district_id_for_chi",
            return_value=south_fd_id,
        ), patch.object(
            chi_svc,
            "_sum_nt_subjects_ec_mln_for_chi",
            side_effect=lambda slice_key, **kwargs: {
                2023: 5.0,
                2024: 20.0,
            }.get(slice_key),
        ):
            assert (
                _chi_ec_consumption_mln_for_south_fd_with_nt(
                    anchor,
                    2022,
                    ec_index=ec_index,
                    ec_model_name="FederalDistrictEnergyConsumptionParameter",
                    ec_parent_id=south_fd_id,
                    fk_column="id_federal_district",
                    years=years,
                )
                is None
            )
            assert (
                _chi_ec_consumption_mln_for_anchor(
                    anchor,
                    2023,
                    ec_index=ec_index,
                    ec_model_name="FederalDistrictEnergyConsumptionParameter",
                    ec_parent_id=south_fd_id,
                    fk_column="id_federal_district",
                    years=years,
                )
                == 105.0
            )
            assert (
                _chi_ec_consumption_mln_for_anchor(
                    anchor,
                    2024,
                    ec_index=ec_index,
                    ec_model_name="FederalDistrictEnergyConsumptionParameter",
                    ec_parent_id=south_fd_id,
                    fk_column="id_federal_district",
                    years=years,
                )
                == 140.0
            )
    finally:
        chi_svc._south_federal_district_id_for_chi.cache_clear()


def test_south_fd_without_nt_chi_uses_direct_lookup_for_all_years():
    south_fd_id = 125
    years = [2022, 2023]
    ec_index = {
        (
            "FederalDistrictEnergyConsumptionParameter",
            south_fd_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2022,
        ): 80.0,
        (
            "FederalDistrictEnergyConsumptionParameter",
            south_fd_id,
            CODE_WITHOUT_NT_WITHOUT_GAES,
            2023,
        ): 100.0,
    }
    anchor = {
        "demand_model_name": FederalDistrictDemandParameter.__name__,
        "entity_label": "Южный ФО без НТ",
        "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
    }

    from unittest.mock import patch

    from app.power_demand.services import pd_peak_usage_hours_services as chi_svc

    chi_svc._south_federal_district_id_for_chi.cache_clear()
    try:
        with patch.object(
            chi_svc,
            "_south_federal_district_id_for_chi",
            return_value=south_fd_id,
        ):
            assert (
                _chi_ec_consumption_mln_for_anchor(
                    anchor,
                    2022,
                    ec_index=ec_index,
                    ec_model_name="FederalDistrictEnergyConsumptionParameter",
                    ec_parent_id=south_fd_id,
                    fk_column="id_federal_district",
                    years=years,
                )
                == 80.0
            )
    finally:
        chi_svc._south_federal_district_id_for_chi.cache_clear()
