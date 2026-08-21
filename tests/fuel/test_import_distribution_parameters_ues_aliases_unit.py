# -*- coding: utf-8 -*-
from types import SimpleNamespace

from app.fuel.services.distribution_parameters.import_distribution_parameters_services import (
    _apply_access_ues_aliases,
    _resolve_union_energy_system_id,
)
from app.fuel.services.fuel_imports.import_fuel_refdata_services import (
    _apply_ues_access_name_aliases,
    _normalize_name,
)


def test_access_norilsk_alias_resolves_by_name_and_oes():
    label_to_ues_id: dict[str, int] = {}
    oes_to_ues_id: dict[str, int] = {}
    name_to_ues_id = {"титэс сибири": 120}
    unmatched = [
        SimpleNamespace(
            external_id="10",
            external_name="Норильск.эн.р-н",
            external_nameoes="Норильск.эн.р-н",
        )
    ]

    _apply_access_ues_aliases(
        label_to_ues_id=label_to_ues_id,
        oes_to_ues_id=oes_to_ues_id,
        name_to_ues_id=name_to_ues_id,
        unmatched_mappings=unmatched,
    )

    assert _resolve_union_energy_system_id(
        name_raw="Норильск",
        filter_text="(oes=10) and (ved>0)",
        oes_to_ues_id=oes_to_ues_id,
        label_to_ues_id=label_to_ues_id,
    ) == 120
    assert _resolve_union_energy_system_id(
        name_raw="Норильск",
        filter_text=None,
        oes_to_ues_id={},
        label_to_ues_id=label_to_ues_id,
    ) == 120


def test_mapping_import_aliases_norilsk_to_tites_siberia():
    tites = SimpleNamespace(id=9, name="ТИТЭС Сибири")
    name_map = {_normalize_name("ТИТЭС Сибири"): tites}
    _apply_ues_access_name_aliases(name_map)
    assert name_map[_normalize_name("Норильск")] is tites
    assert name_map[_normalize_name("Норильск.эн.р-н")] is tites
