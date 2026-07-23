# -*- coding: utf-8 -*-
"""Выгрузка Excel сводок нагрузок: те же строки, что видны на экране."""

from __future__ import annotations

from app.power_demand.services import demand_summary_services as service


def _block(
    *,
    entity_label: str,
    parameter_key: str,
    year_values: list,
    hist_value: str = "",
    show_entity_cell: bool = True,
    rowspan: int = 1,
    **flags,
) -> dict:
    row = {
        "entity_label": entity_label,
        "parameter_key": parameter_key,
        "year_values": list(year_values),
        "hist_value": hist_value,
        "show_entity_cell": show_entity_cell,
        "entity_rowspan": rowspan,
    }
    row.update(flags)
    return row


def test_hide_empty_entity_blocks_keeps_nonzero_and_skip_flag():
    rows = [
        _block(
            entity_label="Пустая",
            parameter_key="max_power",
            year_values=["0", "—", ""],
            rowspan=1,
        ),
        _block(
            entity_label="С данными",
            parameter_key="max_power",
            year_values=["1,5", "0"],
            rowspan=1,
        ),
        _block(
            entity_label="Служебная",
            parameter_key="max_power",
            year_values=["0"],
            rowspan=1,
            pd_pd_skip_empty_hide_row=True,
        ),
    ]
    kept = service.filter_summary_rows_hide_empty_entity_blocks(
        rows, hide_empty=True
    )
    labels = [r["entity_label"] for r in kept]
    assert labels == ["С данными", "Служебная"]


def test_hide_empty_ignores_ee_chi_verify_and_calc_max_when_judging():
    rows = [
        _block(
            entity_label="Только ЭЭ",
            parameter_key="max_power",
            year_values=["0"],
            rowspan=2,
        ),
        _block(
            entity_label="Только ЭЭ",
            parameter_key="energy_consumption_mln_kvt_ch",
            year_values=["100"],
            show_entity_cell=False,
            rowspan=2,
            pd_pd_ee_row=True,
        ),
    ]
    kept = service.filter_summary_rows_hide_empty_entity_blocks(
        rows, hide_empty=True
    )
    assert kept == []


def test_filter_parameter_keys_keeps_ee_and_verify_when_requested():
    rows = [
        _block(
            entity_label="ОЭС",
            parameter_key="max_power",
            year_values=["10"],
            rowspan=3,
        ),
        _block(
            entity_label="ОЭС",
            parameter_key="energy_consumption_mln_kvt_ch",
            year_values=["20"],
            show_entity_cell=False,
            rowspan=3,
            pd_pd_ee_row=True,
        ),
        _block(
            entity_label="ОЭС",
            parameter_key="verify_for_calculated_max_power_mw",
            year_values=["0"],
            show_entity_cell=False,
            rowspan=3,
            pd_pd_verify_for_row=True,
        ),
    ]
    filtered = service.filter_summary_rows_for_parameter_keys(
        rows,
        frozenset(
            {
                "max_power",
                "energy_consumption_mln_kvt_ch",
                "verify_for_calculated_max_power_mw",
            }
        ),
    )
    keys = [r["parameter_key"] for r in filtered]
    assert keys == [
        "max_power",
        "energy_consumption_mln_kvt_ch",
        "verify_for_calculated_max_power_mw",
    ]
    assert filtered[0]["entity_rowspan"] == 3
    assert filtered[0]["show_entity_cell"] is True
    assert filtered[1]["show_entity_cell"] is False


def test_oes_export_keys_include_toggle_rows():
    assert "energy_consumption_mln_kvt_ch" in service.OES_EXPORT_PARAMETER_KEYS
    assert "peak_max_power_usage_hours" in service.OES_EXPORT_PARAMETER_KEYS
    assert "verify_for_calculated_max_power_mw" in service.OES_EXPORT_PARAMETER_KEYS
    assert "peak_combined_on_oes_usage_hours" in service.OES_EXPORT_PARAMETER_KEYS


def test_screen_entity_labels_prefer_territory_compact_over_nt():
    row = {
        "entity_label": "ТИТЭС и ДЗ без НТ",
        "pd_pd_entity_label_nt_detail": "ТИТЭС и ДЗ без НТ",
        "pd_pd_entity_label_compact_nt": "ТИТЭС и ДЗ",
        "pd_pd_entity_label_territory_compact": "ТИТЭС",
        "show_entity_cell": True,
        "entity_rowspan": 1,
    }
    labeled = service.apply_power_demand_summary_screen_entity_labels(
        [row],
        nt_detail_on=False,
        territory_compact_on=True,
    )
    assert labeled[0]["entity_label"] == "ТИТЭС"


def test_export_entity_label_overrides_by_block_key():
    row = {
        "entity_label": "Старое имя",
        "demand_model_name": "UnionEnergySystemDemandParameter",
        "parent_fk_column": "id_union_energy_system",
        "parent_id": 7,
        "id_union_energy_system": 7,
        "show_entity_cell": True,
        "entity_rowspan": 1,
    }
    key = service._power_demand_summary_export_entity_key(row)
    out = service.apply_power_demand_summary_export_entity_label_overrides(
        [row],
        {key: "ОЭС Юга"},
    )
    assert out[0]["entity_label"] == "ОЭС Юга"
