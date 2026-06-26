# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import pytest

from app.common.perimeter_variant.constants import (
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    CODE_WITH_NT_WITHOUT_GAES,
    CODE_WITHOUT_NT_WITHOUT_GAES,
    ENTITY_KIND_RUSSIA_FEDERATION,
    RUSSIA_FEDERATION_AGGREGATE_NAME,
    perimeter_variant_codes_in_legacy_nt_group,
)
from app.common.perimeter_variant.registry import (
    perimeter_variant_codes_for_summary_entity,
    validate_perimeter_variant_for_summary_entity,
)
from app.power_demand.services import demand_parameter_services as dps


def test_perimeter_variant_codes_in_legacy_nt_group_includes_gaes_variants():
    codes = perimeter_variant_codes_in_legacy_nt_group(CODE_WITH_NT)
    assert codes[0] == CODE_WITH_NT
    assert CODE_WITH_NT_WITHOUT_GAES in codes


def test_perimeter_variant_codes_in_legacy_nt_group_from_gaes_code():
    codes = perimeter_variant_codes_in_legacy_nt_group(CODE_WITH_NT_WITHOUT_GAES)
    assert CODE_WITH_NT in codes
    assert CODE_WITH_NT_WITHOUT_GAES in codes


def test_parse_reassign_variant_code_payload_empty_is_none():
    assert dps._parse_reassign_variant_code_payload(None) is None
    assert dps._parse_reassign_variant_code_payload("") is None


def test_parse_reassign_variant_code_payload_normalizes_code(monkeypatch):
    monkeypatch.setattr(
        dps,
        "normalize_perimeter_variant_code",
        lambda raw, **kwargs: str(raw),
    )
    assert (
        dps._parse_reassign_variant_code_payload(CODE_WITH_NT_WITHOUT_GAES)
        == CODE_WITH_NT_WITHOUT_GAES
    )


def test_resolve_summary_block_source_skips_entity_validation_for_legacy_from():
    model = MagicMock()
    model.__name__ = "EesDemandParameter"

    with patch.object(dps, "model_supports_perimeter_variant", return_value=True):
        with patch.object(
            dps,
            "_summary_entity_demand_rows",
            return_value=[],
        ):
            with patch.object(
                dps,
                "resolve_stored_perimeter_variant_for_summary_block",
                return_value=CODE_WITH_NT,
            ):
                with patch.object(
                    dps,
                    "validate_perimeter_variant_for_entity",
                    side_effect=ValueError("should not be called"),
                ) as validate_mock:
                    result = dps._resolve_summary_block_source_perimeter_variant_code(
                        CODE_WITH_NT,
                        model,
                        None,
                        None,
                    )

    assert result == CODE_WITH_NT
    validate_mock.assert_not_called()


def test_reassign_summary_entity_perimeter_variant_seeds_marker_when_no_rows(monkeypatch):
    model = MagicMock()
    model.__name__ = "EesDemandParameter"

    with patch.object(dps, "model_supports_perimeter_variant", return_value=True):
        with patch.object(dps, "_summary_demand_model_class", return_value=model):
            with patch.object(dps, "_validate_summary_parent_binding"):
                with patch.object(
                    dps,
                    "_resolve_summary_block_source_perimeter_variant_code",
                    return_value=None,
                ):
                    with patch.object(
                        dps,
                        "_resolve_summary_block_perimeter_variant_code",
                        return_value=CODE_WITH_NT_WITHOUT_GAES,
                    ):
                        with patch.object(
                            dps,
                            "_reassign_summary_entity_perimeter_variant_all_versions",
                            return_value=2,
                        ) as reassign_mock:
                            with patch.object(dps, "_commit_summary_perimeter_variant_change"):
                                with patch.object(
                                    dps,
                                    "_maybe_log_pd_summary_perimeter_variant_change",
                                ):
                                    updated = dps.reassign_summary_entity_perimeter_variant(
                                        "EesDemandParameter",
                                        parent_fk_column=None,
                                        parent_id=None,
                                        from_variant_code=None,
                                        to_variant_code=CODE_WITH_NT_WITHOUT_GAES,
                                        summary_log_scope="oes",
                                    )

    assert updated == 2
    reassign_mock.assert_called_once()


def test_reassign_summary_entity_perimeter_variant_all_versions_updates_each_version():
    model = MagicMock()
    model.__name__ = "EnergySystemTypeDemandParameter"
    row_v1 = MagicMock(perimeter_variant_code=CODE_WITH_NT, year_number=2024)
    row_v1.database_version_id = 1
    row_v2 = MagicMock(perimeter_variant_code=CODE_WITH_NT, year_number=2024)
    row_v2.database_version_id = 2

    with patch.object(dps, "_username", return_value="tester"):
        with patch.object(dps, "all_database_version_ids_for_refdata", return_value=[1, 2]):
            with patch.object(
                dps,
                "_resolve_summary_parent_id_for_all_versions",
                return_value=10,
            ):
                with patch.object(
                    dps,
                    "_find_source_rows_for_reassign_in_version",
                    side_effect=[[row_v1], [row_v2]],
                ):
                    with patch.object(
                        dps, "_assert_summary_perimeter_variant_reassign_allowed"
                    ):
                        updated = dps._reassign_summary_entity_perimeter_variant_all_versions(
                            model,
                            "EnergySystemTypeDemandParameter",
                            parent_fk_column="id_energy_system_type",
                            anchor_parent_id=5,
                            from_pvc=CODE_WITH_NT,
                            to_pvc=CODE_WITH_NT_WITHOUT_GAES,
                        )

    assert updated == 2
    assert row_v1.perimeter_variant_code == CODE_WITH_NT_WITHOUT_GAES
    assert row_v2.perimeter_variant_code == CODE_WITH_NT_WITHOUT_GAES


def test_reassign_summary_entity_perimeter_variant_seeds_null_marker_when_no_rows():
    model = MagicMock()
    model.__name__ = "RussiaFederationDemandParameter"

    with patch.object(dps, "_username", return_value="tester"):
        with patch.object(dps, "all_database_version_ids_for_refdata", return_value=[1]):
            with patch.object(
                dps,
                "_resolve_summary_parent_id_for_all_versions",
                return_value=None,
            ):
                with patch.object(
                    dps,
                    "_find_source_rows_for_reassign_in_version",
                    return_value=[],
                ):
                    with patch.object(
                        dps,
                        "_ensure_summary_block_variant_marker_row",
                        return_value=True,
                    ) as ensure_mock:
                        updated = dps._reassign_summary_entity_perimeter_variant_all_versions(
                            model,
                            "RussiaFederationDemandParameter",
                            parent_fk_column=None,
                            anchor_parent_id=None,
                            from_pvc=CODE_WITHOUT_NT,
                            to_pvc=None,
                        )

    assert updated == 1
    ensure_mock.assert_called_once_with(
        model,
        parent_fk_column=None,
        parent_id=None,
        database_version_id=1,
        perimeter_variant_code=None,
    )


def test_ensure_summary_block_variant_marker_reuses_single_hist_row():
    model = MagicMock()
    model.__name__ = "SynchronousAreaDemandParameter"
    existing = MagicMock(
        perimeter_variant_code="without_nt_without_kaliningrad_es",
        year_number=None,
        is_historical_maximum=True,
    )

    with patch.object(dps, "_username", return_value="tester"):
        with patch.object(
            dps,
            "find_demand_row_for_summary_slice",
            side_effect=[None, existing],
        ) as find_mock:
            with patch.object(
                dps,
                "_list_summary_hist_markers_for_version",
                return_value=[existing],
            ):
                with patch.object(
                    dps, "create_demand_row_for_summary_slice"
                ) as create_mock:
                    changed = dps._ensure_summary_block_variant_marker_row(
                        model,
                        parent_fk_column="id_synchronous_area",
                        parent_id=147,
                        database_version_id=46,
                        perimeter_variant_code="without_nt_with_kaliningrad_es",
                    )

    assert changed is True
    assert (
        existing.perimeter_variant_code == "without_nt_with_kaliningrad_es"
    )
    create_mock.assert_not_called()
    assert find_mock.call_count == 1


def test_ensure_summary_block_variant_marker_creates_second_nt_hist_row():
    model = MagicMock()
    model.__name__ = "UnionEnergySystemDemandParameter"
    without_nt = MagicMock(
        perimeter_variant_code="without_nt_without_gaes",
        year_number=None,
        is_historical_maximum=True,
    )
    new_row = MagicMock(perimeter_variant_code="with_nt_without_gaes")

    with patch.object(dps, "_username", return_value="tester"):
        with patch.object(
            dps, "find_demand_row_for_summary_slice", return_value=None
        ):
            with patch.object(
                dps,
                "_list_summary_hist_markers_for_version",
                return_value=[without_nt],
            ):
                with patch.object(
                    dps,
                    "create_demand_row_for_summary_slice",
                    return_value=new_row,
                ) as create_mock:
                    changed = dps._ensure_summary_block_variant_marker_row(
                        model,
                        parent_fk_column="id_union_energy_system",
                        parent_id=415,
                        database_version_id=46,
                        perimeter_variant_code="with_nt_without_gaes",
                    )

    assert changed is True
    assert without_nt.perimeter_variant_code == "without_nt_without_gaes"
    create_mock.assert_called_once()


def test_find_demand_row_for_summary_slice_resolving_pvc_adopts_unassigned_row():
    model = MagicMock()
    model.__name__ = "UnionEnergySystemDemandParameter"
    legacy = MagicMock(perimeter_variant_code=None, year_number=2016)

    def _find_side_effect(*_args, **kwargs):
        if kwargs.get("perimeter_variant_code") is None:
            return legacy
        return None

    with patch.object(dps, "model_supports_perimeter_variant", return_value=True):
        with patch.object(
            dps, "find_demand_row_for_summary_slice", side_effect=_find_side_effect
        ):
            row = dps.find_demand_row_for_summary_slice_resolving_pvc(
                model,
                parent_fk_column="id_union_energy_system",
                parent_id=415,
                is_hist=False,
                year_n=2016,
                database_version_id=46,
                perimeter_variant_code="without_nt_without_gaes",
            )

    assert row is legacy
    assert legacy.perimeter_variant_code == "without_nt_without_gaes"


def test_find_demand_row_for_summary_slice_resolving_pvc_does_not_steal_other_variant():
    model = MagicMock()
    model.__name__ = "UnionEnergySystemDemandParameter"
    without_nt_row = MagicMock(
        perimeter_variant_code="without_nt_without_gaes", year_number=2024
    )

    with patch.object(dps, "model_supports_perimeter_variant", return_value=True):
        with patch.object(
            dps, "find_demand_row_for_summary_slice", return_value=None
        ):
            with patch.object(
                dps,
                "_list_demand_rows_for_summary_slice",
                return_value=[without_nt_row],
            ):
                row = dps.find_demand_row_for_summary_slice_resolving_pvc(
                    model,
                    parent_fk_column="id_union_energy_system",
                    parent_id=415,
                    is_hist=False,
                    year_n=2024,
                    database_version_id=46,
                    perimeter_variant_code="with_nt_without_gaes",
                )

    assert row is None
    assert without_nt_row.perimeter_variant_code == "without_nt_without_gaes"


def test_perimeter_variant_codes_for_summary_russia_includes_plain_nt_variants():
    codes = perimeter_variant_codes_for_summary_entity(
        ENTITY_KIND_RUSSIA_FEDERATION,
        RUSSIA_FEDERATION_AGGREGATE_NAME,
    )
    assert CODE_WITH_NT in codes
    assert CODE_WITHOUT_NT in codes
    assert not any("_with_gaes" in code for code in codes)


def test_validate_perimeter_variant_for_summary_russia_allows_with_nt():
    assert (
        validate_perimeter_variant_for_summary_entity(
            ENTITY_KIND_RUSSIA_FEDERATION,
            RUSSIA_FEDERATION_AGGREGATE_NAME,
            CODE_WITH_NT,
        )
        == CODE_WITH_NT
    )


def test_ues_row_included_for_ees_russia_aggregate_variant_matches_gaes_subvariant():
    from app.power_demand.services import demand_summary_services as dss

    row = {"perimeter_variant_code": CODE_WITH_NT}
    assert dss._ues_row_included_for_ees_russia_aggregate_variant(
        row, CODE_WITH_NT_WITHOUT_GAES
    )
    assert not dss._ues_row_included_for_ees_russia_aggregate_variant(
        {"perimeter_variant_code": CODE_WITHOUT_NT},
        CODE_WITH_NT_WITHOUT_GAES,
    )
    model = MagicMock()
    model.__name__ = "EesDemandParameter"

    with patch.object(dps, "model_supports_perimeter_variant", return_value=True):
        with patch.object(
            dps,
            "perimeter_entity_context_for_model",
            return_value=("ees_russia", "ЭЭС России"),
        ):
            with patch.object(
                dps,
                "validate_perimeter_variant_for_summary_entity",
                side_effect=ValueError("not allowed"),
            ):
                with pytest.raises(ValueError, match="not allowed"):
                    dps._resolve_summary_block_perimeter_variant_code(
                        CODE_WITH_NT,
                        model,
                        None,
                        None,
                        validate_entity_binding=True,
                    )


def test_perimeter_variant_codes_match_kaliningrad_composite_without_nt():
    from app.common.perimeter_variant.constants import CODE_WITHOUT_NT
    from app.power_demand.services import demand_summary_services as dss

    row_code = "without_nt_without_gaes_with_kaliningrad_es"
    assert dss._perimeter_variant_codes_match_nt_target(row_code, CODE_WITHOUT_NT)
    assert dss._perimeter_variant_codes_match_nt_target(
        row_code, CODE_WITHOUT_NT_WITHOUT_GAES
    )


def test_ues_row_included_for_ees_russia_aggregate_uses_base_row_when_no_explicit_variant():
    from app.common.perimeter_variant.constants import CODE_WITHOUT_NT
    from app.power_demand.services import demand_summary_services as dss

    summary_rows = [
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
            "id_union_energy_system": 151,
        },
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "perimeter_variant_code": None,
            "id_union_energy_system": 150,
        },
    ]
    filt = dss._make_ues_perimeter_filter_for_ees_russia_aggregate(
        summary_rows, CODE_WITHOUT_NT_WITHOUT_GAES
    )
    assert filt(
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "perimeter_variant_code": CODE_WITHOUT_NT_WITHOUT_GAES,
            "id_union_energy_system": 151,
        }
    )
    assert filt(
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "perimeter_variant_code": None,
            "id_union_energy_system": 150,
        }
    )
    assert not filt(
        {
            "demand_model_name": "UnionEnergySystemDemandParameter",
            "perimeter_variant_code": None,
            "id_union_energy_system": 151,
        }
    )
