# -*- coding: utf-8 -*-
from unittest.mock import MagicMock

from app.common.perimeter_variant.constants import (
    CODE_WITH_NT,
    CODE_WITHOUT_NT,
    CODE_WITH_NT_WITHOUT_GAES,
    CODE_WITHOUT_NT_WITHOUT_GAES,
)
from app.power_demand.services import demand_parameter_services as dps
from app.power_demand.services import demand_summary_services as dss


def test_summary_block_includes_null_pvc_only_for_without_nt():
    assert dps.summary_block_includes_unassigned_null_pvc(None) is True
    assert dps.summary_block_includes_unassigned_null_pvc(CODE_WITHOUT_NT) is True
    assert dps.summary_block_includes_unassigned_null_pvc(
        CODE_WITHOUT_NT_WITHOUT_GAES
    ) is True
    assert dps.summary_block_includes_unassigned_null_pvc(CODE_WITH_NT) is False
    assert dps.summary_block_includes_unassigned_null_pvc(
        CODE_WITH_NT_WITHOUT_GAES
    ) is False


def test_summary_row_pvc_compatible_null_only_for_without_nt():
    assert dps._summary_row_pvc_compatible_with_target(
        None, CODE_WITHOUT_NT_WITHOUT_GAES
    )
    assert dps._summary_row_pvc_compatible_with_target(None, CODE_WITHOUT_NT)
    assert not dps._summary_row_pvc_compatible_with_target(
        None, CODE_WITH_NT_WITHOUT_GAES
    )
    assert not dps._summary_row_pvc_compatible_with_target(None, CODE_WITH_NT)


def test_summary_row_pvc_compatible_same_nt_group_gaes():
    assert dps._summary_row_pvc_compatible_with_target(
        CODE_WITHOUT_NT, CODE_WITHOUT_NT_WITHOUT_GAES
    )
    assert dps._summary_row_pvc_compatible_with_target(
        CODE_WITH_NT_WITHOUT_GAES, CODE_WITH_NT
    )
    assert not dps._summary_row_pvc_compatible_with_target(
        CODE_WITHOUT_NT, CODE_WITH_NT
    )


def test_demand_rows_for_without_gaes_always_uses_summary_block_merge(monkeypatch):
    """Даже если уже есть строки without_nt_without_gaes, подмешиваем NULL-годы."""
    model = MagicMock()
    merged = [MagicMock(year_number=2023), MagicMock(year_number=2024)]

    def _block(_model, _fk, _pid, *, display_perimeter_variant_code=None):
        assert display_perimeter_variant_code == CODE_WITHOUT_NT
        return merged

    monkeypatch.setattr(dps, "get_demand_rows_for_summary_block", _block)
    monkeypatch.setattr(
        dps,
        "get_demand_rows",
        lambda *_a, **_k: [_ for _ in ()],  # must not short-circuit via exact PVC
    )

    rows = dss._demand_rows_for_perimeter_variant_entity(
        model,
        "id_federal_district",
        93,
        CODE_WITHOUT_NT_WITHOUT_GAES,
    )
    assert rows is merged
