from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.common.perimeter_variant import registry


def test_preload_perimeter_entity_contexts_batches_ids_and_serves_request_cache(app) -> None:
    class IdColumn:
        @staticmethod
        def in_(ids):
            return list(ids)

    class Query:
        def __init__(self):
            self.selected_ids = None
            self.filter_calls = 0

        def filter(self, selected_ids):
            self.selected_ids = selected_ids
            self.filter_calls += 1
            return self

        def all(self):
            return [
                SimpleNamespace(id=10, name="ОЭС Севера"),
                SimpleNamespace(id=11, name="ОЭС Юга"),
            ]

    query = Query()
    model = SimpleNamespace(id=IdColumn(), query=query)
    imported_module = SimpleNamespace(RegionalEnergySystem=model)
    requests = [
        ("RegionalEnergySystemDemandParameter", "id_regional_energy_system", 10),
        ("RegionalEnergySystemDemandParameter", "id_regional_energy_system", 11),
        ("RegionalEnergySystemDemandParameter", "id_regional_energy_system", 10),
    ]

    with app.test_request_context("/"):
        with patch.object(registry, "import_module", return_value=imported_module):
            registry.preload_perimeter_entity_contexts(requests)
            assert query.filter_calls == 1
            assert set(query.selected_ids) == {10, 11}
            assert registry.perimeter_entity_context_for_model(
                "RegionalEnergySystemDemandParameter",
                parent_fk_column="id_regional_energy_system",
                parent_id=10,
            ) == ("regional_energy_system", "ОЭС Севера")
            assert query.filter_calls == 1
