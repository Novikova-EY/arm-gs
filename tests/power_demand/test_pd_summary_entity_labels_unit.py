# -*- coding: utf-8 -*-
"""Подписи строк «Первая синхронная зона» на сводке /power_demand/summary/oes/."""

from unittest.mock import MagicMock

from app.common.perimeter_variant.constants import (
    CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
    CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
    CODE_WITHOUT_NT_WITHOUT_GAES,
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    CENTRALIZED_ZONE_AGGREGATE_NAME,
    ENTITY_KIND_CENTRALIZED_ZONE,
)
from app.common.perimeter_variant.registry import (
    is_o1_perimeter_variant_code,
    resolve_entity_perimeter_variants,
)
from app.power_demand.models.energy_systems.centralized_zone_demand_parameter_model import (
    CentralizedZoneDemandParameter,
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
from app.power_demand.models.territories.federal_district_demand_parameter_model import (
    FederalDistrictDemandParameter,
)
from app.power_demand.models.territories.russia_federation_demand_parameter_model import (
    RussiaFederationDemandParameter,
)
from app.power_demand.services import demand_summary_services as service


def _first_sync_zone_row(perimeter_variant_code: str, entity_label: str) -> dict:
    return {
        "show_entity_cell": True,
        "entity_label": entity_label,
        "demand_model_name": SynchronousAreaDemandParameter.__name__,
        "parent_fk_column": "id_synchronous_area",
        "parent_id": 39,
        "parameter_key": "max_power",
        "perimeter_variant_code": perimeter_variant_code,
        "entity_kind": "synchronous_area",
        "entity_depth": 0,
    }


def _aggregate_row(
    *,
    model_name: str,
    entity_label: str,
    perimeter_variant_code: str | None,
    entity_kind: str = "oes_top_aggregate",
    parent_fk_column: str | None = None,
    parent_id: int | None = None,
) -> dict:
    row = {
        "show_entity_cell": True,
        "entity_label": entity_label,
        "demand_model_name": model_name,
        "parameter_key": "max_power",
        "perimeter_variant_code": perimeter_variant_code,
        "entity_kind": entity_kind,
        "entity_depth": 0,
        "pd_pd_summary_perimeter_variant_row": True,
    }
    if parent_fk_column is not None:
        row["parent_fk_column"] = parent_fk_column
    if parent_id is not None:
        row["parent_id"] = parent_id
    return row


def test_first_sync_zone_entity_labels_include_kaliningrad_suffix_nt_off():
    row = _first_sync_zone_row(
        CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
        "Первая синхронная зона без НТ (с ЭС Калининградской области)",
    )
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_compact_nt"] == (
        "Первая синхронная зона (с ЭС Калининградской области)"
    )


def test_first_sync_zone_entity_labels_include_kaliningrad_suffix_nt_on():
    row = _first_sync_zone_row(
        CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
        "Первая синхронная зона без НТ (без ЭС Калининградской области)",
    )
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_nt_detail"] == (
        "Первая синхронная зона без НТ (без ЭС Калининградской области)"
    )


def test_first_sync_zone_entity_labels_strip_gaes_from_source_label():
    row = _first_sync_zone_row(
        CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
        "Первая синхронная зона без НТ без заряда ГАЭС (с ЭС Калининградской области)",
    )
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["entity_label"] == (
        "Первая синхронная зона без НТ (с ЭС Калининградской области)"
    )
    assert row["pd_pd_entity_label_compact_nt"] == (
        "Первая синхронная зона (с ЭС Калининградской области)"
    )


def test_strip_gaes_text_from_perimeter_variant_label_fragment():
    assert service._pd_strip_gaes_text_from_label_fragment(
        "без НТ без заряда ГАЭС (с ЭС Калининградской области)"
    ) == "без НТ (с ЭС Калининградской области)"


def test_first_sync_zone_export_labels_match_screen_toggle():
    rows = [
        _first_sync_zone_row(
            CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
            "Первая синхронная зона без НТ (с ЭС Калининградской области)",
        ),
        _first_sync_zone_row(
            CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
            "Первая синхронная зона без НТ (без ЭС Калининградской области)",
        ),
    ]
    service.tag_power_demand_summary_rows_for_nt_toggle(rows)

    compact_export = service.apply_power_demand_summary_nt_export_ui(
        rows, nt_detail_on=False
    )
    assert compact_export[0]["entity_label"] == (
        "Первая синхронная зона (с ЭС Калининградской области)"
    )
    assert compact_export[1]["entity_label"] == (
        "Первая синхронная зона (без ЭС Калининградской области)"
    )

    detail_export = service.apply_power_demand_summary_nt_export_ui(
        rows, nt_detail_on=True
    )
    assert detail_export[0]["entity_label"] == (
        "Первая синхронная зона без НТ (с ЭС Калининградской области)"
    )
    assert detail_export[1]["entity_label"] == (
        "Первая синхронная зона без НТ (без ЭС Калининградской области)"
    )


def test_oes_aggregate_with_nt_rows_get_nt_detail_label_and_stay_nt_extra():
    rows = [
        _aggregate_row(
            model_name=RussiaFederationDemandParameter.__name__,
            entity_label="Россия",
            perimeter_variant_code=CODE_WITH_NT,
        ),
        _aggregate_row(
            model_name=EesRussiaDemandParameter.__name__,
            entity_label="ЭЭС России",
            perimeter_variant_code="with_nt_without_gaes",
        ),
        _aggregate_row(
            model_name=UnionEnergySystemDemandParameter.__name__,
            entity_label="ОЭС Юга",
            perimeter_variant_code="with_nt_without_gaes",
            entity_kind="perimeter_variant",
            parent_fk_column="id_union_energy_system",
            parent_id=7,
        ),
    ]
    service.tag_power_demand_summary_rows_for_nt_toggle(rows)

    assert rows[0]["pd_pd_entity_label_nt_detail"] == "Россия с НТ"
    assert rows[0]["pd_pd_entity_label_compact_nt"] == "Россия"
    assert rows[0]["pd_pd_nt_extra_row"] is True

    assert rows[1]["pd_pd_entity_label_nt_detail"] == "ЭЭС России с НТ"
    assert rows[1]["pd_pd_nt_extra_row"] is True

    assert rows[2]["pd_pd_entity_label_nt_detail"] == "ОЭС Юга с НТ"
    assert rows[2]["pd_pd_nt_extra_row"] is True


def test_oes_aggregate_without_nt_rows_are_not_nt_extra():
    row = _aggregate_row(
        model_name=RussiaFederationDemandParameter.__name__,
        entity_label="Россия без НТ",
        perimeter_variant_code=CODE_WITHOUT_NT,
    )
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_nt_detail"] == "Россия без НТ"
    assert row["pd_pd_entity_label_compact_nt"] == "Россия"
    assert row["pd_pd_nt_extra_row"] is False


def test_oes_aggregate_with_nt_label_without_code_infers_nt_detail_suffix():
    row = {
        "show_entity_cell": True,
        "entity_label": "Россия с НТ",
        "demand_model_name": RussiaFederationDemandParameter.__name__,
        "parameter_key": "max_power",
        "perimeter_variant_code": None,
        "entity_kind": "oes_top_aggregate",
        "entity_depth": 0,
        "pd_pd_nt_extra_row": True,
    }
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_nt_detail"] == "Россия с НТ"
    assert row["pd_pd_entity_label_compact_nt"] == "Россия"


def test_demand_row_groups_skip_null_variant_when_binding_has_codes(monkeypatch):
    from app.power_demand.services import demand_summary_services as dss

    binding = MagicMock()
    binding.variants = (MagicMock(code="with_nt"), MagicMock(code="without_nt"))
    monkeypatch.setattr(
        dss,
        "_oes_perimeter_variant_codes_for_summary",
        lambda _binding: ("with_nt", "without_nt"),
    )
    monkeypatch.setattr(
        dss,
        "_demand_rows_for_perimeter_variant_entity",
        lambda *_a, **_k: [],
    )
    groups = dss._demand_row_groups_for_all_binding_variants(
        MagicMock(),
        "id_union_energy_system",
        1,
        binding=binding,
    )
    assert [code for code, _rows in groups] == ["with_nt", "without_nt"]


def test_demand_row_groups_keep_null_variant_when_null_rows_exist(monkeypatch):
    from app.power_demand.services import demand_summary_services as dss

    binding = MagicMock()
    binding.variants = (MagicMock(code="with_nt"),)
    sentinel = object()
    monkeypatch.setattr(
        dss,
        "_oes_perimeter_variant_codes_for_summary",
        lambda _binding: ("with_nt",),
    )

    def _rows_for_pvc(model, parent_fk, parent_id, pvc):
        return [sentinel] if pvc is None else []

    monkeypatch.setattr(dss, "_demand_rows_for_perimeter_variant_entity", _rows_for_pvc)
    groups = dss._demand_row_groups_for_all_binding_variants(
        MagicMock(),
        "id_union_energy_system",
        1,
        binding=binding,
    )
    assert [code for code, _rows in groups] == [None, "with_nt"]
    assert groups[0][1] == [sentinel]


def test_pd_summary_row_allows_perimeter_variant_select_res_with_options():
    row = {
        "show_entity_cell": True,
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "perimeter_variant_options": [
            {"code": "with_nt_without_gaes", "label": "с НТ"},
            {"code": "without_nt_without_gaes", "label": "без НТ"},
        ],
        "pd_ec_perimeter_entity_kind": "regional_energy_system",
    }
    assert service._pd_summary_row_allows_perimeter_variant_select(row) is True


def test_pd_summary_row_allows_perimeter_variant_select_res_without_context():
    row = {
        "show_entity_cell": True,
        "demand_model_name": "RegionalEnergySystemDemandParameter",
        "perimeter_variant_options": [],
    }
    assert service._pd_summary_row_allows_perimeter_variant_select(row) is False


def test_pd_summary_row_allows_perimeter_variant_select_ues_with_options():
    row = {
        "show_entity_cell": True,
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "perimeter_variant_options": [
            {"code": "with_nt_without_gaes", "label": "с НТ"},
            {"code": "without_nt_without_gaes", "label": "без НТ"},
        ],
    }
    assert service._pd_summary_row_allows_perimeter_variant_select(row) is True


def test_pd_summary_row_allows_perimeter_variant_select_energy_zone_with_context():
    row = {
        "show_entity_cell": True,
        "demand_model_name": "EnergyZoneDemandParameter",
        "perimeter_variant_options": [],
        "pd_ec_perimeter_entity_kind": "energy_zone",
    }
    assert service._pd_summary_row_allows_perimeter_variant_select(row) is True


def test_pd_summary_row_allows_perimeter_variant_select_energy_unit_with_context():
    row = {
        "show_entity_cell": True,
        "demand_model_name": "EnergyUnitDemandParameter",
        "perimeter_variant_options": [],
        "pd_ec_perimeter_entity_kind": "energy_unit",
    }
    assert service._pd_summary_row_allows_perimeter_variant_select(row) is True


def test_centralized_zone_with_nt_compact_label_for_fo_summary():
    row = {
        "show_entity_cell": True,
        "entity_label": f"{CENTRALIZED_ZONE_AGGREGATE_NAME} с НТ",
        "demand_model_name": CentralizedZoneDemandParameter.__name__,
        "parameter_key": "max_power",
        "perimeter_variant_code": CODE_WITH_NT,
        "entity_kind": "centralized_zone",
        "entity_depth": 0,
    }
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_compact_nt"] == CENTRALIZED_ZONE_AGGREGATE_NAME
    assert row["pd_pd_entity_label_nt_detail"] == f"{CENTRALIZED_ZONE_AGGREGATE_NAME} с НТ"
    assert row["pd_pd_nt_extra_row"] is True


def test_centralized_zone_without_nt_compact_label_for_fo_summary():
    row = {
        "show_entity_cell": True,
        "entity_label": f"{CENTRALIZED_ZONE_AGGREGATE_NAME} без НТ",
        "demand_model_name": CentralizedZoneDemandParameter.__name__,
        "parameter_key": "max_power",
        "perimeter_variant_code": CODE_WITHOUT_NT,
        "entity_kind": "centralized_zone",
        "entity_depth": 0,
    }
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_compact_nt"] == CENTRALIZED_ZONE_AGGREGATE_NAME
    assert row["pd_pd_entity_label_nt_detail"] == f"{CENTRALIZED_ZONE_AGGREGATE_NAME} без НТ"
    assert row["pd_pd_nt_extra_row"] is False


def test_build_centralized_zone_entities_prefers_non_o1_when_bound(app):
    with app.app_context():
        binding = resolve_entity_perimeter_variants(
            ENTITY_KIND_CENTRALIZED_ZONE,
            CENTRALIZED_ZONE_AGGREGATE_NAME,
        )
        if binding is None:
            return
        codes = {v.code for v in binding.variants}
        if "o1_with_nt" not in codes:
            return
        entities = service._build_centralized_zone_perimeter_entities()
    entity_codes = [e.perimeter_variant_code for e in entities]
    assert all(not is_o1_perimeter_variant_code(c) for c in entity_codes if c)
    assert "with_nt" in entity_codes or "without_nt" in entity_codes
    assert all(
        not getattr(e, "centralized_zone_o1_display_row", False) for e in entities
    )
    assert all("O-1" not in e.label for e in entities)


def test_south_federal_district_without_nt_compact_label_for_fo_summary():
    row = {
        "show_entity_cell": True,
        "entity_label": "Южный ФО без НТ",
        "demand_model_name": FederalDistrictDemandParameter.__name__,
        "parameter_key": "max_power",
        "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
        "entity_kind": "perimeter_variant",
        "entity_depth": 0,
    }
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_compact_nt"] == "Южный ФО"
    assert row["pd_pd_entity_label_nt_detail"] == "Южный ФО без НТ"
    assert row["pd_pd_nt_extra_row"] is False


def test_drop_null_perimeter_variant_group_when_nt_pairs_exist():
    groups = [
        (None, [object()]),
        (CODE_WITH_NT, []),
        (CODE_WITHOUT_NT, []),
    ]
    filtered = service._drop_null_perimeter_variant_group_when_nt_pairs_exist(groups)
    assert [code for code, _rows in filtered] == [CODE_WITH_NT, CODE_WITHOUT_NT]


def test_exclude_o1_perimeter_variant_summary_rows():
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "perimeter_variant_code": "with_nt",
            "parameter_key": "max_power",
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 2,
            "perimeter_variant_code": "with_nt",
            "parameter_key": "peak_datetime",
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "max_power",
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "perimeter_variant_code": "without_nt",
            "parameter_key": "max_power",
        },
    ]

    filtered = service.exclude_o1_perimeter_variant_summary_rows(rows)

    assert len(filtered) == 3
    assert [r.get("perimeter_variant_code") for r in filtered] == [
        "with_nt",
        "with_nt",
        "without_nt",
    ]
    assert filtered[0]["show_entity_cell"] is True
    assert filtered[0]["entity_rowspan"] == 2
    assert filtered[1]["show_entity_cell"] is False
    assert filtered[2]["show_entity_cell"] is True

