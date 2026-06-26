# -*- coding: utf-8 -*-
"""Строки «Проверка …» на сводке /power_demand/summary/oes/."""

from __future__ import annotations

from unittest.mock import patch

from app.power_demand.services.demand_summary_services import (
    _finalize_oes_summary_context,
    _inject_oes_summary_verification_rows,
    enrich_oes_summary_calculated_max_power_from_res_combined,
)
from app.power_demand.services.pd_summary_data_segments import PD_SUMMARY_SEGMENT_VERIFY


def _param_row(
    *,
    pk: str,
    year_values: list[str],
    show_entity_cell: bool = False,
    ues_id: int = 1,
    res_id: int | None = None,
    dm: str = "UnionEnergySystemDemandParameter",
) -> dict:
    row: dict = {
        "demand_model_name": dm,
        "parameter_key": pk,
        "parent_fk_column": "id_union_energy_system",
        "parent_id": ues_id,
        "id_union_energy_system": ues_id,
        "year_values": list(year_values),
        "year_numeric_tooltips": list(year_values),
        "show_entity_cell": show_entity_cell,
        "entity_rowspan": 1,
        "entity_label": "ОЭС тест",
        "entity_kind": "union_energy_system",
    }
    if res_id is not None:
        row["demand_model_name"] = "RegionalEnergySystemDemandParameter"
        row["parent_fk_column"] = "id_regional_energy_system"
        row["parent_id"] = res_id
        row["id_regional_energy_system"] = res_id
        row["id_union_energy_system"] = ues_id
    return row


def test_oes_verify_row_values_after_res_aggregation() -> None:
    """Проверка ОЭС = расчётный максимум (сумма combined_on_oes по РЭС) − max_power."""
    years = [2024]
    rows = [
        _param_row(
            pk="max_power",
            year_values=["100"],
            show_entity_cell=True,
            ues_id=10,
        ),
        _param_row(pk="calculated_max_power_mw", year_values=["—"], ues_id=10),
        _param_row(pk="peak_datetime", year_values=[""], ues_id=10),
        _param_row(pk="avg_temp", year_values=[""], ues_id=10),
        _param_row(pk="combined_on_ees", year_values=[""], ues_id=10),
        _param_row(pk="calculated_combined_on_ees_mw", year_values=["—"], ues_id=10),
        _param_row(
            pk="combined_on_oes",
            year_values=["110"],
            ues_id=10,
            res_id=101,
            dm="RegionalEnergySystemDemandParameter",
        ),
    ]
    rows[0]["entity_rowspan"] = len(rows)

    enrich_oes_summary_calculated_max_power_from_res_combined(rows, years, rounding_digits=1)
    _inject_oes_summary_verification_rows(rows, years)

    calc_row = next(r for r in rows if r.get("parameter_key") == "calculated_max_power_mw")
    verify_row = next(
        r for r in rows if r.get("parameter_key") == "verify_for_calculated_max_power_mw"
    )

    assert calc_row["year_values"] == ["110"]
    assert verify_row["year_values"] == ["10"]
    assert verify_row.get("pd_pd_verify_for_row") is True
    assert verify_row.get("demand_model_name") == "UnionEnergySystemDemandParameter"


@patch(
    "app.power_demand.services.demand_summary_services._attach_oes_summary_live_calc_context",
)
@patch(
    "app.power_demand.services.demand_summary_services._inject_oes_summary_verification_rows",
)
@patch(
    "app.power_demand.services.demand_summary_services._inject_chukotka_rd_calculated_max_rows",
)
@patch(
    "app.power_demand.services.demand_summary_services._filter_power_demand_summary_context_segments",
)
@patch(
    "app.power_demand.services.demand_summary_services._tag_common_power_demand_summary_rows",
)
@patch(
    "app.power_demand.services.demand_summary_services._enrich_oes_summary_calculated_max_from_res",
)
def test_finalize_oes_summary_verify_segment_triggers_calc_max_enrichment(
    enrich_mock,
    _tag_mock,
    _filter_mock,
    _chukotka_mock,
    _inject_mock,
    _live_mock,
) -> None:
    ctx = {"summary_rows": [], "years": [2024], "filter_year_list": [2024]}

    _finalize_oes_summary_context(
        ctx, rounding_digits=1, data_segments=frozenset({PD_SUMMARY_SEGMENT_VERIFY})
    )

    enrich_mock.assert_called_once_with(ctx, 1)
