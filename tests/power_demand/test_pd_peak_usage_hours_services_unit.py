# -*- coding: utf-8 -*-
"""Юнит-тесты расчёта ЧЧИ на сводке /power_demand/summary/oes/."""

from app.common.perimeter_variant.constants import CODE_WITHOUT_NT_WITHOUT_GAES
from app.common.perimeter_variant.registry import CODE_WITH_NT, CODE_WITHOUT_NT
from app.power_demand.models.energy_systems.ees_demand_parameter_model import (
    EesDemandParameter,
)
from app.power_demand.models.energy_systems.ees_russia_demand_parameter_model import (
    EesRussiaDemandParameter,
)
from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
    SynchronousAreaDemandParameter,
)
from app.power_demand.models.energy_systems.union_energy_system_demand_parameter_model import (
    UnionEnergySystemDemandParameter,
)
from app.power_demand.services.pd_peak_usage_hours_services import (
    _chi_ec_consumption_mln_for_anchor,
    _chi_ec_consumption_pvc_for_anchor,
    _ec_consumption_pvc_candidates_for_chi,
    _lookup_ec_consumption_for_chi,
)


def test_ues_chi_uses_same_perimeter_variant_as_max_power():
    anchor = {
        "demand_model_name": UnionEnergySystemDemandParameter.__name__,
        "entity_kind": "perimeter_variant",
        "perimeter_variant_code": CODE_WITH_NT,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [CODE_WITH_NT]


def test_ees_chi_uses_same_perimeter_variant_as_max_power():
    anchor = {
        "demand_model_name": EesDemandParameter.__name__,
        "entity_kind": "oes_top_aggregate",
        "perimeter_variant_code": CODE_WITH_NT,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [CODE_WITH_NT]


def test_first_sa_chi_uses_same_perimeter_variant_as_max_power():
    anchor = {
        "demand_model_name": SynchronousAreaDemandParameter.__name__,
        "entity_kind": "synchronous_area",
        "entity_label": "Первая синхронная зона без НТ",
        "perimeter_variant_code": CODE_WITHOUT_NT,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [CODE_WITHOUT_NT]


def test_ees_chi_uses_resolved_stored_variant_code():
    anchor = {
        "demand_model_name": EesDemandParameter.__name__,
        "entity_kind": "oes_top_aggregate",
        "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == [
        CODE_WITHOUT_NT_WITHOUT_GAES
    ]


def test_ees_chi_maps_without_nt_to_without_nt_without_gaes():
    anchor = {
        "demand_model_name": EesDemandParameter.__name__,
        "entity_kind": "oes_top_aggregate",
        "entity_label": "ЭЭС России без НТ",
        "perimeter_variant_code": CODE_WITHOUT_NT,
    }
    assert _chi_ec_consumption_pvc_for_anchor(anchor) == CODE_WITHOUT_NT_WITHOUT_GAES


def test_ues_russia_chi_resolves_none_pvc_to_without_nt_without_gaes():
    anchor = {
        "demand_model_name": EesRussiaDemandParameter.__name__,
        "entity_kind": "group-root",
        "entity_label": "ЕЭС России без НТ",
        "parent_fk_column": None,
        "parent_id": None,
        "perimeter_variant_code": None,
        "pd_pd_nt_extra_row": False,
    }
    assert _chi_ec_consumption_pvc_for_anchor(anchor) == CODE_WITHOUT_NT_WITHOUT_GAES


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


def test_decentralized_zone_chi_uses_o1_consumption():
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
    assert hit == 15.0


def test_chukotka_rd_uses_same_variant_as_other_entities():
    anchor = {
        "demand_model_name": "RegionalDistrictDemandParameter",
        "entity_label": "Чукотский АО",
        "entity_kind": "default",
        "perimeter_variant_code": "with_nt",
    }
    assert _ec_consumption_pvc_candidates_for_chi(anchor) == ["with_nt"]
