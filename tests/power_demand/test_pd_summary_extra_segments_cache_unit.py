from types import SimpleNamespace

from app.power_demand.services import demand_summary_services
from app.power_demand.services import pd_peak_usage_hours_services as chi_services
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
)


def test_hub_ec_indexes_are_built_once_per_request(app, monkeypatch):
    calls = []
    cz_index = {("without_nt", 2024): 1.0}
    ees_sa_index = {("model", 1, "without_nt", 2024): 2.0}

    def build_indexes(years, rounding_digits, *, need_cz, need_ees_sa):
        calls.append((tuple(years), rounding_digits, need_cz, need_ees_sa))
        return cz_index, ees_sa_index

    monkeypatch.setattr(
        chi_services, "_build_oes_top_hub_ec_indexes", build_indexes
    )
    blocks = [
        (
            0,
            1,
            [{"demand_model_name": CentralizedZoneDemandParameter.__name__}],
        )
    ]

    with app.test_request_context("/power_demand/summary/oes/data.json"):
        first = chi_services._hub_indexes_for_summary_blocks(blocks, [2024], 1)
        second = chi_services._hub_indexes_for_summary_blocks(blocks, [2024], 1)
        chi_services._hub_indexes_for_summary_blocks(blocks, [2025], 1)
        chi_services._hub_indexes_for_summary_blocks(blocks, [2024], 2)

    assert first == (cz_index, None)
    assert second == (cz_index, None)
    assert calls == [
        ((2024,), 1, True, True),
        ((2025,), 1, True, True),
        ((2024,), 2, True, True),
    ]


def test_new_territories_ids_are_loaded_once_per_request(app, monkeypatch):
    calls = []

    def load_districts():
        calls.append(1)
        return [SimpleNamespace(id=10), SimpleNamespace(id=20)]

    monkeypatch.setattr(
        demand_summary_services,
        "_load_new_territories_regional_districts",
        load_districts,
    )

    with app.test_request_context("/power_demand/summary/oes/data.json"):
        first = demand_summary_services._new_territories_regional_district_ids()
        second = demand_summary_services._new_territories_regional_district_ids()

    assert first == frozenset({10, 20})
    assert second == first
    assert calls == [1]
