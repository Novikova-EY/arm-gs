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


def test_first_sync_zone_entity_labels_omit_kaliningrad_suffix_nt_off():
    row = _first_sync_zone_row(
        CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
        "Первая синхронная зона без НТ (с ЭС Калининградской области)",
    )
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_compact_nt"] == "Первая синхронная зона"


def test_summary_variant_entity_label_ignores_perimeter_catalog_suffix():
    binding = MagicMock()
    binding.display_label_prefix = "Первая синхронная зона"
    binding.variants = (
        MagicMock(
            code="with_nt_without_gaes_kaliningrad",
            label_suffix="с НТ без заряда ГАЭС (Калин)",
        ),
    )
    label = service._summary_variant_entity_label(
        binding,
        "Первая синхронная зона",
        "with_nt_without_gaes_kaliningrad",
        "synchronous_area",
        "Первая синхронная зона",
    )
    assert label == "Первая синхронная зона с НТ"


def test_summary_variant_entity_label_o1_code_adds_only_nt_suffix():
    binding = MagicMock()
    binding.variants = (
        MagicMock(code="o1_with_nt", label_suffix="O-1 с НТ и что угодно"),
    )
    label = service._summary_variant_entity_label(
        binding,
        "ЦЗ России",
        "o1_with_nt",
        "centralized_zone",
        "ЦЗ России",
    )
    assert label == "ЦЗ России с НТ"
    assert "O-1" not in label


def test_toggle_strips_catalog_kaliningrad_parenthetical():
    row = _first_sync_zone_row(
        "with_nt_without_gaes_kaliningrad",
        "Первая синхронная зона с НТ без заряда ГАЭС (Калин)",
    )
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_compact_nt"] == "Первая синхронная зона"
    assert row["pd_pd_entity_label_nt_detail"] == "Первая синхронная зона с НТ"
    assert row["entity_label"] == "Первая синхронная зона с НТ"


def test_first_sync_zone_entity_labels_omit_kaliningrad_suffix_nt_on():
    row = _first_sync_zone_row(
        CODE_WITHOUT_NT_WITHOUT_KALININGRAD_ES,
        "Первая синхронная зона без НТ (без ЭС Калининградской области)",
    )
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["pd_pd_entity_label_nt_detail"] == "Первая синхронная зона без НТ"


def test_first_sync_zone_entity_labels_strip_gaes_from_source_label():
    row = _first_sync_zone_row(
        CODE_WITHOUT_NT_WITH_KALININGRAD_ES,
        "Первая синхронная зона без НТ без заряда ГАЭС (с ЭС Калининградской области)",
    )
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["entity_label"] == "Первая синхронная зона без НТ"
    assert row["pd_pd_entity_label_compact_nt"] == "Первая синхронная зона"


def test_strip_gaes_text_from_perimeter_variant_label_fragment():
    assert service._pd_strip_gaes_text_from_label_fragment(
        "без НТ без заряда ГАЭС (с ЭС Калининградской области)"
    ) == "без НТ (с ЭС Калининградской области)"


def test_pd_oes_perimeter_variant_label_keeps_gaes_suffix():
    binding = MagicMock()
    binding.variants = (
        MagicMock(
            code=CODE_WITHOUT_NT_WITHOUT_GAES,
            label_suffix="без НТ",
        ),
    )
    label = service._oes_perimeter_variant_russian_label(
        CODE_WITHOUT_NT_WITHOUT_GAES,
        binding=binding,
        entity_kind="synchronous_area",
        entity_name="Первая синхронная зона",
        strip_gaes_suffix=False,
    )
    assert label == "без НТ без заряда ГАЭС"

    options = service._perimeter_variant_options_for_oes_summary(
        "synchronous_area",
        "Первая синхронная зона",
        strip_gaes_suffix=False,
    )
    without_gaes_opt = next(
        (opt for opt in options if opt.get("code") == CODE_WITHOUT_NT_WITHOUT_GAES),
        None,
    )
    if without_gaes_opt is not None:
        assert "без заряда ГАЭС" in without_gaes_opt["label"]


def test_pd_oes_perimeter_variant_label_strips_gaes_suffix_when_requested():
    label = service._oes_perimeter_variant_russian_label(
        CODE_WITHOUT_NT_WITHOUT_GAES,
        binding=None,
        entity_kind="synchronous_area",
        entity_name="Первая синхронная зона",
        strip_gaes_suffix=True,
    )
    assert "без заряда ГАЭС" not in label


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
    assert compact_export[0]["entity_label"] == "Первая синхронная зона"
    assert compact_export[1]["entity_label"] == "Первая синхронная зона"

    detail_export = service.apply_power_demand_summary_nt_export_ui(
        rows, nt_detail_on=True
    )
    assert detail_export[0]["entity_label"] == "Первая синхронная зона без НТ"
    assert detail_export[1]["entity_label"] == "Первая синхронная зона без НТ"


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


def test_build_centralized_zone_entities_prefers_o1_when_bound():
    from unittest.mock import MagicMock, patch

    binding = MagicMock()
    binding.variants = [
        MagicMock(code="with_nt"),
        MagicMock(code="without_nt"),
        MagicMock(code="o1_with_nt"),
        MagicMock(code="o1_without_nt"),
    ]
    groups = [
        ("with_nt", []),
        ("without_nt", []),
        ("o1_with_nt", []),
        ("o1_without_nt", []),
    ]
    with (
        patch.object(
            service,
            "resolve_entity_perimeter_binding",
            return_value=binding,
        ),
        patch.object(
            service,
            "_demand_row_groups_for_oes_top_aggregate",
            return_value=groups,
        ),
        patch.object(
            service,
            "_summary_variant_entity_label",
            side_effect=lambda _b, base, code, *_a: f"{base} {code}",
        ),
    ):
        entities = service._build_centralized_zone_perimeter_entities()
    entity_codes = [e.perimeter_variant_code for e in entities]
    assert entity_codes == ["o1_with_nt", "o1_without_nt"]
    assert all(is_o1_perimeter_variant_code(c) for c in entity_codes)


def test_exclude_o1_keeps_centralized_zone_russia_o1_rows():
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_kind": "centralized_zone",
            "demand_model_name": CentralizedZoneDemandParameter.__name__,
            "entity_label": "ЦЗ России О-1 с НТ",
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "max_power",
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_kind": "centralized_zone",
            "demand_model_name": CentralizedZoneDemandParameter.__name__,
            "entity_label": "ЦЗ России О-1 без НТ",
            "perimeter_variant_code": "o1_without_nt",
            "parameter_key": "max_power",
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "ЭС Магаданской области O-1",
            "perimeter_variant_code": "o1",
            "parameter_key": "max_power",
        },
    ]
    filtered = service.exclude_o1_perimeter_variant_summary_rows(rows)
    assert [r.get("perimeter_variant_code") for r in filtered] == [
        "o1_with_nt",
        "o1_without_nt",
    ]


def test_centralized_zone_o1_nt_toggle_labels():
    rows = [
        {
            "show_entity_cell": True,
            "entity_kind": "centralized_zone",
            "demand_model_name": CentralizedZoneDemandParameter.__name__,
            "entity_label": "ЦЗ России О-1 с НТ",
            "perimeter_variant_code": "o1_with_nt",
            "parameter_key": "max_power",
            "entity_depth": 0,
        },
        {
            "show_entity_cell": True,
            "entity_kind": "centralized_zone",
            "demand_model_name": CentralizedZoneDemandParameter.__name__,
            "entity_label": "ЦЗ России О-1 без НТ",
            "perimeter_variant_code": "o1_without_nt",
            "parameter_key": "max_power",
            "entity_depth": 0,
        },
    ]
    service.tag_power_demand_summary_rows_for_nt_toggle(rows)
    assert rows[0]["pd_pd_entity_label_nt_detail"] == "ЦЗ России с НТ"
    assert rows[0]["pd_pd_entity_label_compact_nt"] == "ЦЗ России"
    assert rows[0]["pd_pd_nt_extra_row"] is True
    assert rows[1]["pd_pd_entity_label_nt_detail"] == "ЦЗ России без НТ"
    assert rows[1]["pd_pd_entity_label_compact_nt"] == "ЦЗ России"
    assert rows[1]["pd_pd_nt_extra_row"] is False


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


def test_kaliningrad_sync_area_label_omits_without_nt_suffix():
    """СЗ Калининграда не пара с/без НТ — суффикс «без НТ» в названии не нужен."""
    from app.power_demand.models.energy_systems.synchronous_area_demand_parameter_model import (
        SynchronousAreaDemandParameter,
    )

    row = {
        "show_entity_cell": True,
        "entity_label": "Синхронная зона Калининградской области без НТ",
        "demand_model_name": SynchronousAreaDemandParameter.__name__,
        "parameter_key": "max_power",
        "perimeter_variant_code": "without_nt",
        "entity_kind": "synchronous_area",
        "entity_depth": 0,
    }
    service.tag_power_demand_summary_rows_for_nt_toggle([row])

    assert row["entity_label"] == "Синхронная зона Калининградской области"
    assert row["pd_pd_entity_label_nt_detail"] == "Синхронная зона Калининградской области"
    assert row["pd_pd_entity_label_compact_nt"] == "Синхронная зона Калининградской области"
    assert "без НТ" not in row["entity_label"]


def test_kaliningrad_coeff_full_label_omits_without_nt_suffix():
    label = service._pd_format_full_variant_entity_label_for_coeff(
        "Синхронная зона Калининградской области",
        "without_nt_without_gaes",
    )
    assert label == "Синхронная зона Калининградской области без заряда ГАЭС"
    assert "без НТ" not in label

def test_coeff_summary_restores_without_gaes_suffix_in_full_entity_label():
    row = {
        "show_entity_cell": True,
        "entity_label": "ОЭС Юга без НТ",
        "demand_model_name": UnionEnergySystemDemandParameter.__name__,
        "parameter_key": "max_power",
        "perimeter_variant_code": "without_nt_without_gaes",
        "entity_kind": "perimeter_variant",
        "entity_depth": 0,
    }
    service.tag_power_demand_summary_rows_for_nt_toggle([row])
    service.tag_power_demand_coeff_summary_rows_without_gaes_entity_labels([row])

    expected = "ОЭС Юга без НТ без заряда ГАЭС"
    assert row["entity_label"] == expected
    assert row["pd_pd_entity_label_nt_detail"] == expected
    assert row["pd_pd_entity_label_compact_nt"] == expected


def test_coeff_summary_without_gaes_label_omits_kaliningrad_suffix():
    row = {
        "show_entity_cell": True,
        "entity_label": "Первая синхронная зона без НТ (без ЭС Калининградской области)",
        "demand_model_name": SynchronousAreaDemandParameter.__name__,
        "parameter_key": "max_power",
        "perimeter_variant_code": "without_nt_without_gaes_without_kaliningrad_es",
        "entity_kind": "synchronous_area",
        "entity_depth": 0,
    }
    service.tag_power_demand_summary_rows_for_nt_toggle([row])
    service.tag_power_demand_coeff_summary_rows_without_gaes_entity_labels([row])

    assert row["entity_label"] == "Первая синхронная зона без НТ без заряда ГАЭС"


def test_drop_null_perimeter_variant_group_when_nt_pairs_exist():
    groups = [
        (None, [object()]),
        (CODE_WITH_NT, []),
        (CODE_WITHOUT_NT, []),
    ]
    filtered = service._drop_null_perimeter_variant_group_when_nt_pairs_exist(groups)
    assert [code for code, _rows in filtered] == [CODE_WITH_NT, CODE_WITHOUT_NT]


def test_reorder_first_synchronous_area_variant_blocks_puts_with_nt_first():
    def _block(code: str, label: str) -> list[dict]:
        return [
            {
                "show_entity_cell": True,
                "entity_rowspan": 2,
                "entity_label": label,
                "demand_model_name": SynchronousAreaDemandParameter.__name__,
                "perimeter_variant_code": code,
                "parameter_key": "max_power",
                "entity_kind": "synchronous_area",
                "entity_depth": 0,
            },
            {
                "show_entity_cell": False,
                "entity_rowspan": 2,
                "entity_label": label,
                "demand_model_name": SynchronousAreaDemandParameter.__name__,
                "perimeter_variant_code": code,
                "parameter_key": "peak_datetime",
                "entity_kind": "synchronous_area",
                "entity_depth": 0,
            },
        ]

    rows = (
        _block(CODE_WITHOUT_NT, "Первая синхронная зона без НТ")
        + _block(CODE_WITH_NT, "Первая синхронная зона с НТ")
        + [
            {
                "show_entity_cell": True,
                "entity_rowspan": 1,
                "entity_label": "Вторая синхронная зона",
                "demand_model_name": SynchronousAreaDemandParameter.__name__,
                "perimeter_variant_code": None,
                "parameter_key": "max_power",
                "entity_kind": "synchronous_area",
                "entity_depth": 0,
            }
        ]
    )
    service.reorder_first_synchronous_area_variant_blocks_in_summary_rows(rows)
    codes = [
        r["perimeter_variant_code"]
        for r in rows
        if r.get("show_entity_cell") and r.get("perimeter_variant_code")
    ]
    assert codes == [CODE_WITH_NT, CODE_WITHOUT_NT]
    assert rows[0]["entity_label"] == "Первая синхронная зона с НТ"
    assert rows[2]["entity_label"] == "Первая синхронная зона без НТ"
    assert rows[4]["entity_label"] == "Вторая синхронная зона"


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


def test_exclude_o1_perimeter_variant_summary_rows_by_entity_label():
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "ЭС Магаданской области",
            "perimeter_variant_code": "with_nt",
            "parameter_key": "max_power",
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 2,
            "entity_label": "ЭС Магаданской области O-1",
            "perimeter_variant_code": None,
            "parameter_key": "max_power",
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 2,
            "entity_label": "ЭС Магаданской области O-1",
            "parameter_key": "peak_datetime",
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 1,
            "entity_label": "ЭС Сахалинской области (О-1)",
            "pd_ec_o1_form_row": True,
            "parameter_key": "max_power",
        },
    ]

    filtered = service.exclude_o1_perimeter_variant_summary_rows(rows)

    assert len(filtered) == 1
    assert filtered[0]["entity_label"] == "ЭС Магаданской области"


def test_rebuild_summary_entity_row_blocks_splits_on_show_entity_cell():
    rows = [
        {
            "show_entity_cell": True,
            "entity_rowspan": 10,
            "entity_label": "Хабаровский край",
            "parameter_key": "max_power",
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 10,
            "entity_label": "Хабаровский край",
            "parameter_key": "peak_datetime",
        },
        {
            "show_entity_cell": True,
            "entity_rowspan": 10,
            "entity_label": "Николаевский энергорайон",
            "parameter_key": "max_power",
        },
        {
            "show_entity_cell": False,
            "entity_rowspan": 10,
            "entity_label": "Николаевский энергорайон",
            "parameter_key": "combined_on_es",
        },
    ]

    rebuilt = service._rebuild_summary_entity_row_blocks(rows)

    assert len(rebuilt) == 4
    assert rebuilt[0]["show_entity_cell"] is True
    assert rebuilt[0]["entity_rowspan"] == 2
    assert rebuilt[1]["show_entity_cell"] is False
    assert rebuilt[2]["show_entity_cell"] is True
    assert rebuilt[2]["entity_rowspan"] == 2
    assert rebuilt[3]["show_entity_cell"] is False


def test_energy_units_for_federal_district_subject_orders_dz_last():
    class _RES:
        pass

    class _EU:
        pass

    placeholder_res = _RES()
    placeholder_res.name = "не указано"
    valid_res_id = 590

    eu_regular = _EU()
    eu_regular.id = 77
    eu_regular.name = "Центральный энергорайон"
    eu_regular.id_regional_energy_system = valid_res_id

    eu_dz_a = _EU()
    eu_dz_a.id = 359
    eu_dz_a.name = "Озерновский энергорайон"
    eu_dz_a.id_regional_energy_system = 569
    eu_dz_a.regional_energy_system = placeholder_res

    eu_dz_b = _EU()
    eu_dz_b.id = 367
    eu_dz_b.name = "Южные электрические сети"
    eu_dz_b.id_regional_energy_system = 569
    eu_dz_b.regional_energy_system = placeholder_res

    result = service._energy_units_for_federal_district_subject(
        [eu_dz_a, eu_regular, eu_dz_b],
        valid_res_id,
    )
    assert [eu.id for eu in result] == [77, 359, 367]


def test_build_energy_unit_entities_preserves_decentralized_zone_order(monkeypatch):
    monkeypatch.setattr(service.dps, "get_demand_rows", lambda *args, **kwargs: [])

    class _RES:
        pass

    class _EU:
        pass

    placeholder_res = _RES()
    placeholder_res.name = "не указано"

    eu_regular = _EU()
    eu_regular.id = 77
    eu_regular.name = "Центральный энергорайон"
    eu_regular.id_regional_energy_system = 590

    eu_dz = _EU()
    eu_dz.id = 359
    eu_dz.name = "Озерновский энергорайон"
    eu_dz.id_regional_energy_system = 569
    eu_dz.regional_energy_system = placeholder_res

    ordered = service._energy_units_for_federal_district_subject(
        [eu_dz, eu_regular],
        590,
    )
    entities = service._build_energy_unit_entities(ordered, depth=3)

    assert [e.label for e in entities] == [
        "Центральный энергорайон",
        "Озерновский энергорайон",
    ]
    assert entities[0].is_decentralized_zone_energy_unit is False
    assert entities[1].is_decentralized_zone_energy_unit is True


def test_energy_unit_summary_perimeter_variant_code_uses_o1_for_dz():
    from types import SimpleNamespace

    from app.power_demand.services import demand_summary_services as service

    eu = SimpleNamespace(
        name="Новиковский энергорайон",
        regional_energy_system=SimpleNamespace(name="не указано"),
    )
    assert service._energy_unit_summary_perimeter_variant_code(eu) == "o1"


def test_demand_rows_for_energy_unit_summary_falls_back_to_base_perimeter(monkeypatch):
    from types import SimpleNamespace

    from app.power_demand.services import demand_summary_services as service

    eu = SimpleNamespace(
        id=359,
        name="Озерновский энергорайон",
        regional_energy_system=SimpleNamespace(name="не указано"),
    )
    calls: list[str | None] = []

    def fake_get_demand_rows(model, fk, parent_id, *, perimeter_variant_code=None):
        calls.append(perimeter_variant_code)
        if perimeter_variant_code == "o1":
            return []
        return [object()]

    monkeypatch.setattr(service.dps, "get_demand_rows", fake_get_demand_rows)
    rows = service._demand_rows_for_energy_unit_summary(eu)
    assert len(rows) == 1
    assert calls == ["o1", None]


def test_flatten_entity_marks_decentralized_zone_skip_empty_hide():
    from app.power_demand.services import demand_summary_services as service

    entity = service.SummaryEntity(
        label="Новиковский энергорайон",
        depth=3,
        parameters=(("max_power", "Максимальное потребление мощности, МВт"),),
        demand_rows=[],
        entity_kind="child",
        is_decentralized_zone_energy_unit=True,
    )
    rows = service._flatten_entity(entity, [2024, 2025], 1)
    assert rows[0]["pd_pd_decentralized_zone_mark"] is True
    assert rows[0]["pd_pd_skip_empty_hide_row"] is True


def test_build_federal_district_res_entity_shows_subjects_with_energy_units(monkeypatch):
    from app.power_demand.services import demand_summary_services as service

    monkeypatch.setattr(service.dps, "get_demand_rows", lambda *args, **kwargs: [])

    class _EU:
        pass

    class _RD:
        pass

    class _RES:
        pass

    eu1 = _EU()
    eu1.id = 501
    eu1.name = "Энергорайон 1"
    eu1.id_regional_energy_system = 1
    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Субъект 1"
    rd1.energy_units = [eu1]
    rd2 = _RD()
    rd2.id = 102
    rd2.name = "Субъект 2"
    rd2.energy_units = []
    res = _RES()
    res.id = 1
    res.name = "РЭС тест"
    res.id_union_energy_system = 7
    res.regional_districts = [rd1, rd2]
    res.energy_units = []

    entity = service._build_federal_district_res_entity(
        res,
        federal_district_id=10,
        fd_rd_ids={101, 102},
    )
    assert entity is not None
    assert len(entity.children) == 2
    assert entity.children[0].demand_model_name == (
        service.RegionalDistrictDemandParameter.__name__
    )
    assert entity.children[1].id_regional_district == 102
    assert len(entity.children[0].children) == 1
    assert entity.children[0].children[0].demand_model_name == (
        service.EnergyUnitDemandParameter.__name__
    )
    assert entity.children[0].children[0].id_energy_unit == 501
    assert entity.children[0].children[0].parameters == service.PARAMETERS_ENERGY_UNIT_FD_SUMMARY


def test_build_federal_district_res_entity_shows_energy_units_when_single_subject(
    monkeypatch,
):
    from app.power_demand.services import demand_summary_services as service

    monkeypatch.setattr(service.dps, "get_demand_rows", lambda *args, **kwargs: [])

    class _EU:
        pass

    class _RD:
        pass

    class _RES:
        pass

    eu1 = _EU()
    eu1.id = 501
    eu1.name = "Энергорайон 1"
    eu1.id_regional_energy_system = 1
    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Субъект 1"
    rd1.energy_units = [eu1]
    rd2 = _RD()
    rd2.id = 102
    rd2.name = "Субъект 2"
    rd2.energy_units = []
    res = _RES()
    res.id = 1
    res.name = "РЭС тест"
    res.id_union_energy_system = 7
    res.regional_districts = [rd1, rd2]
    res.energy_units = []

    entity = service._build_federal_district_res_entity(
        res,
        federal_district_id=10,
        fd_rd_ids={101},
    )
    assert entity is not None
    assert len(entity.children) == 1
    assert entity.children[0].demand_model_name == (
        service.EnergyUnitDemandParameter.__name__
    )
    assert entity.children[0].id_energy_unit == 501
    assert entity.id_regional_district == 101
    assert entity.children[0].parameters == service.PARAMETERS_ENERGY_UNIT_FD_SUMMARY
    assert entity.children[0].id_federal_district == 10


def test_build_federal_district_res_entity_appends_placeholder_energy_units(monkeypatch):
    from app.power_demand.services import demand_summary_services as service

    monkeypatch.setattr(service.dps, "get_demand_rows", lambda *args, **kwargs: [])

    class _EU:
        pass

    class _RD:
        pass

    class _RES:
        pass

    placeholder_res = _RES()
    placeholder_res.name = "не указано"

    eu_res = _EU()
    eu_res.id = 501
    eu_res.name = "ЭР РЭС"
    eu_res.id_regional_energy_system = 1

    eu_dz = _EU()
    eu_dz.id = 502
    eu_dz.name = "ЭР ДЗ"
    eu_dz.id_regional_energy_system = 569
    eu_dz.regional_energy_system = placeholder_res

    rd1 = _RD()
    rd1.id = 101
    rd1.name = "Субъект 1"
    rd1.energy_units = [eu_dz, eu_res]
    res = _RES()
    res.id = 1
    res.name = "РЭС тест"
    res.id_union_energy_system = 7
    res.regional_districts = [rd1]
    res.energy_units = []

    entity = service._build_federal_district_res_entity(
        res,
        federal_district_id=10,
        fd_rd_ids={101},
    )
    assert entity is not None
    assert [c.id_energy_unit for c in entity.children] == [501, 502]
    assert entity.children[0].is_decentralized_zone_energy_unit is False
    assert entity.children[1].is_decentralized_zone_energy_unit is True
    assert entity.children[0].parameters == service.PARAMETERS_ENERGY_UNIT_FD_SUMMARY

