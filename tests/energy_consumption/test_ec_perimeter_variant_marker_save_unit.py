# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

from app.common.perimeter_variant.constants import CODE_WITH_NT, CODE_WITHOUT_NT
from app.energy_consumption.services import energy_consumption_parameter_services as dps


def test_reassign_seeds_year_null_marker_when_no_rows():
    model = MagicMock()
    model.__name__ = "CentralizedZoneEnergyConsumptionParameter"

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
                            "CentralizedZoneEnergyConsumptionParameter",
                            parent_fk_column=None,
                            anchor_parent_id=None,
                            from_pvc=CODE_WITHOUT_NT,
                            to_pvc="o1_without_nt",
                        )

    assert updated == 1
    ensure_mock.assert_called_once_with(
        model,
        parent_fk_column=None,
        parent_id=None,
        database_version_id=1,
        perimeter_variant_code="o1_without_nt",
    )


def test_resolve_stored_cz_includes_o1_in_same_nt_group(monkeypatch):
    model = MagicMock()
    model.__name__ = "CentralizedZoneEnergyConsumptionParameter"
    marker = MagicMock(perimeter_variant_code="o1_without_nt")

    def _get_rows(_model, _fk, _pid, *, perimeter_variant_code=None):
        if perimeter_variant_code == "o1_without_nt":
            return [marker]
        return []

    monkeypatch.setattr(dps, "model_supports_perimeter_variant", lambda _m: True)
    monkeypatch.setattr(dps, "get_demand_rows", _get_rows)

    assert (
        dps.resolve_stored_perimeter_variant_for_summary_block(
            model,
            parent_fk_column=None,
            parent_id=None,
            display_perimeter_variant_code=CODE_WITHOUT_NT,
        )
        == "o1_without_nt"
    )


def test_cz_nt_slot_resolve_codes_include_plain_and_o1():
    model = MagicMock()
    model.__name__ = "CentralizedZoneEnergyConsumptionParameter"
    codes = dps._perimeter_variant_codes_for_summary_block_resolve(model, CODE_WITH_NT)
    assert CODE_WITH_NT in codes
    assert "o1_with_nt" in codes
    assert CODE_WITHOUT_NT not in codes
    assert "o1_without_nt" not in codes


def test_ensure_marker_creates_year_null_row():
    model = MagicMock()
    model.__name__ = "CentralizedZoneEnergyConsumptionParameter"
    new_row = MagicMock(perimeter_variant_code=CODE_WITHOUT_NT)

    with patch.object(dps, "_username", return_value="tester"):
        with patch.object(dps, "find_demand_row_for_summary_slice", return_value=None):
            with patch.object(
                dps, "_list_summary_variant_markers_for_version", return_value=[]
            ):
                with patch.object(
                    dps,
                    "create_demand_row_for_summary_slice",
                    return_value=new_row,
                ) as create_mock:
                    changed = dps._ensure_summary_block_variant_marker_row(
                        model,
                        parent_fk_column=None,
                        parent_id=None,
                        database_version_id=20,
                        perimeter_variant_code=CODE_WITHOUT_NT,
                    )

    assert changed is True
    create_mock.assert_called_once()
    kwargs = create_mock.call_args.kwargs
    assert kwargs["year_n"] is None
    assert kwargs["perimeter_variant_code"] == CODE_WITHOUT_NT
    assert kwargs["database_version_id"] == 20
