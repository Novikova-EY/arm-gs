# -*- coding: utf-8 -*-
from unittest.mock import MagicMock, patch

import pytest

from app.common.perimeter_variant.constants import (
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    CODE_WITH_NT_WITHOUT_GAES,
    perimeter_variant_codes_in_legacy_nt_group,
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
    marker_row = MagicMock()
    marker_row.perimeter_variant_code = CODE_WITH_NT_WITHOUT_GAES

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
                            "_summary_entity_demand_rows",
                            return_value=[],
                        ):
                            with patch.object(
                                dps,
                                "_seed_summary_block_variant_marker_rows",
                                return_value=[marker_row],
                            ) as seed_mock:
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

    assert updated == 1
    seed_mock.assert_called_once()


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
                "validate_perimeter_variant_for_entity",
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
