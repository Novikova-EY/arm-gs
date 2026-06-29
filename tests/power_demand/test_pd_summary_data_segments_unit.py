# -*- coding: utf-8 -*-
"""Юнит-тесты сегментов ленивой подгрузки сводки нагрузок."""

from __future__ import annotations

from app.power_demand.services.pd_summary_data_segments import (
    PD_SUMMARY_SEGMENT_CALC_MAX,
    PD_SUMMARY_SEGMENT_CHI,
    PD_SUMMARY_SEGMENT_CORE,
    PD_SUMMARY_SEGMENT_NT_EXTRA,
    PD_SUMMARY_SEGMENT_VERIFY,
    filter_summary_rows_for_data_segments,
    segment_for_parameter_key,
)


def _block(*rows: dict) -> list[dict]:
    out: list[dict] = []
    for i, row in enumerate(rows):
        rc = dict(row)
        rc["show_entity_cell"] = i == 0
        rc["entity_rowspan"] = len(rows)
        out.append(rc)
    return out


def test_segment_for_parameter_key_fo():
    assert segment_for_parameter_key("combined_on_ees", scope="fo") is None
    assert (
        segment_for_parameter_key("calculated_max_power_mw", scope="fo")
        == PD_SUMMARY_SEGMENT_CALC_MAX
    )
    assert (
        segment_for_parameter_key("peak_max_power_usage_hours", scope="fo")
        == PD_SUMMARY_SEGMENT_CHI
    )
    assert (
        segment_for_parameter_key("verify_for_calculated_max_power_mw", scope="fo")
        == PD_SUMMARY_SEGMENT_VERIFY
    )


def test_segment_for_parameter_key_oes():
    assert segment_for_parameter_key("max_power", scope="oes") == PD_SUMMARY_SEGMENT_CORE
    assert (
        segment_for_parameter_key("calculated_max_power_mw", scope="oes")
        == PD_SUMMARY_SEGMENT_CALC_MAX
    )
    assert (
        segment_for_parameter_key("peak_max_power_usage_hours", scope="oes")
        == PD_SUMMARY_SEGMENT_CHI
    )
    assert (
        segment_for_parameter_key("verify_for_calculated_max_power_mw", scope="oes")
        == PD_SUMMARY_SEGMENT_VERIFY
    )


def test_filter_core_only_excludes_calc_chi_verify_nt():
    rows = _block(
        {"parameter_key": "max_power", "entity_label": "ОЭС"},
        {"parameter_key": "calculated_max_power_mw"},
        {"parameter_key": "peak_max_power_usage_hours", "pd_pd_chi_row": True},
        {"parameter_key": "verify_for_calculated_max_power_mw", "pd_pd_verify_for_row": True},
    )
    nt_block = _block(
        {
            "parameter_key": "max_power",
            "entity_label": "Россия с НТ",
            "pd_pd_nt_extra_row": True,
        },
    )
    filtered = filter_summary_rows_for_data_segments(
        rows + nt_block,
        frozenset({PD_SUMMARY_SEGMENT_CORE}),
        scope="oes",
    )
    assert len(filtered) == 1
    assert filtered[0]["parameter_key"] == "max_power"
    assert not filtered[0].get("pd_pd_nt_extra_row")


def test_filter_core_includes_summary_perimeter_variant_rows():
    """Варианты из /perimeter_variants/ всегда в core — даже «с НТ» и без данных в БД."""
    binding_block = _block(
        {
            "parameter_key": "max_power",
            "entity_label": "Россия с НТ",
            "pd_pd_nt_extra_row": True,
            "pd_pd_summary_perimeter_variant_row": True,
            "perimeter_variant_code": "with_nt",
        },
        {"parameter_key": "peak_datetime"},
    )
    filtered = filter_summary_rows_for_data_segments(
        binding_block,
        frozenset({PD_SUMMARY_SEGMENT_CORE}),
        scope="oes",
    )
    assert len(filtered) == 2
    assert filtered[0]["entity_label"] == "Россия с НТ"


def test_filter_perimeter_variant_calc_rows_in_calc_max_not_core():
    """Расчётные строки варианта периметра — сегмент calc_max (с обогащением), не core."""
    binding_block = _block(
        {
            "parameter_key": "max_power",
            "entity_label": "ОЭС Юга с НТ",
            "pd_pd_summary_perimeter_variant_row": True,
            "perimeter_variant_code": "with_nt",
        },
        {"parameter_key": "calculated_max_power_mw", "pd_pd_summary_perimeter_variant_row": True},
        {
            "parameter_key": "calculated_combined_on_ees_mw",
            "pd_pd_summary_perimeter_variant_row": True,
        },
    )
    core = filter_summary_rows_for_data_segments(
        binding_block,
        frozenset({PD_SUMMARY_SEGMENT_CORE}),
        scope="oes",
    )
    calc = filter_summary_rows_for_data_segments(
        binding_block,
        frozenset({PD_SUMMARY_SEGMENT_CALC_MAX}),
        scope="oes",
    )
    assert len(core) == 1
    assert core[0]["parameter_key"] == "max_power"
    assert len(calc) == 2
    assert {r["parameter_key"] for r in calc} == {
        "calculated_max_power_mw",
        "calculated_combined_on_ees_mw",
    }


def test_filter_calc_max_segment():
    rows = _block(
        {"parameter_key": "max_power"},
        {"parameter_key": "calculated_max_power_mw"},
    )
    filtered = filter_summary_rows_for_data_segments(
        rows,
        frozenset({PD_SUMMARY_SEGMENT_CALC_MAX}),
        scope="oes",
    )
    assert len(filtered) == 1
    assert filtered[0]["parameter_key"] == "calculated_max_power_mw"


def test_filter_nt_extra_segment():
    rows = _block({"parameter_key": "max_power", "pd_pd_nt_extra_row": True})
    filtered = filter_summary_rows_for_data_segments(
        rows,
        frozenset({PD_SUMMARY_SEGMENT_NT_EXTRA}),
        scope="oes",
    )
    assert len(filtered) == 1
    assert filtered[0].get("pd_pd_nt_extra_row")


def test_filter_nt_aggregation_level_header_in_core_not_nt_extra():
    """Заголовок «Новые территории» под ОЭС Юга — в core (позиция дерева), не в nt_extra."""
    agg_row = {
        "entity_label": "Новые территории",
        "entity_kind": "aggregation_level",
        "parameter_key": "",
        "show_entity_cell": True,
        "entity_rowspan": 1,
        "pd_pd_aggregation_level_row": True,
        "pd_pd_aggregation_level_full_row": True,
        "pd_pd_nt_extra_row": True,
        "pd_pd_nt_subtree_root": True,
        "id_union_energy_system": 151,
    }
    core = filter_summary_rows_for_data_segments(
        [agg_row],
        frozenset({PD_SUMMARY_SEGMENT_CORE}),
        scope="oes",
    )
    nt_extra = filter_summary_rows_for_data_segments(
        [agg_row],
        frozenset({PD_SUMMARY_SEGMENT_NT_EXTRA}),
        scope="oes",
    )
    assert len(core) == 1
    assert core[0]["entity_label"] == "Новые территории"
    assert not nt_extra


def test_filter_chi_segment_includes_nt_extra_chi_rows():
    rows = _block(
        {"parameter_key": "peak_max_power_usage_hours", "pd_pd_chi_row": True},
    )
    rows[0]["pd_pd_nt_extra_row"] = True
    filtered = filter_summary_rows_for_data_segments(
        rows,
        frozenset({PD_SUMMARY_SEGMENT_CHI}),
        scope="oes",
    )
    assert len(filtered) == 1
    assert filtered[0]["parameter_key"] == "peak_max_power_usage_hours"
    assert filtered[0].get("pd_pd_nt_extra_row")


def test_filter_verify_segment_includes_nt_extra_verify_rows():
    """Строки «Проверка …» для «ОЭС Юга с НТ» — сегмент verify (как ЧЧИ), не nt_extra."""
    rows = _block(
        {
            "parameter_key": "verify_for_calculated_max_power_mw",
            "entity_label": "ОЭС Юга с НТ",
            "pd_pd_verify_for_row": True,
            "pd_pd_nt_extra_row": True,
        },
        {
            "parameter_key": "verify_for_calculated_combined_on_ees_mw",
            "pd_pd_verify_for_row": True,
            "pd_pd_nt_extra_row": True,
        },
    )
    verify = filter_summary_rows_for_data_segments(
        rows,
        frozenset({PD_SUMMARY_SEGMENT_VERIFY}),
        scope="oes",
    )
    nt_extra = filter_summary_rows_for_data_segments(
        rows,
        frozenset({PD_SUMMARY_SEGMENT_NT_EXTRA}),
        scope="oes",
    )
    assert len(verify) == 2
    assert verify[0]["parameter_key"] == "verify_for_calculated_max_power_mw"
    assert verify[0].get("pd_pd_nt_extra_row")
    assert not nt_extra
