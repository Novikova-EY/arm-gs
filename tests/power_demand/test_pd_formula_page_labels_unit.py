# -*- coding: utf-8 -*-
"""Фильтр «Страница» на /power_demand/formulas/ не должен дублировать подписи из‑за «;»."""

from __future__ import annotations

from app.energy_consumption.services.energy_consumption_summary_formula_registry import (
    EC_SUMMARY_FORMULA_REGISTRY,
)
from app.power_demand.services.pd_summary_formula_template_vars import (
    PD_FORMULA_TEMPLATE_VAR_KEYS,
)
from app.power_demand.services.power_demand_summary_formula_registry import (
    PAGE_LABELS,
    PD_SUMMARY_FORMULA_REGISTRY,
    get_formula_def,
)


def test_pd_page_label_lines_have_no_trailing_semicolon() -> None:
    seen: set[str] = set()
    for item in PD_SUMMARY_FORMULA_REGISTRY:
        for line in item.page_label_lines():
            assert not line.endswith(";"), repr(line)
            seen.add(line)
    # Каждая реальная страница сводки — ровно одна подпись в фильтре.
    for label in PAGE_LABELS.values():
        assert label in seen


def test_ec_page_label_lines_have_no_trailing_semicolon() -> None:
    from app.energy_consumption.services.energy_consumption_summary_formula_registry import (
        PAGE_ELECTRICAL_INTENSITY,
        PAGE_LABELS,
        iter_formula_defs,
    )

    for item in EC_SUMMARY_FORMULA_REGISTRY:
        for line in item.page_label_lines():
            assert not line.endswith(";"), repr(line)

    # Уникальные значения фильтра «Страница» на /energy_consumption/formulas/:
    # без дублей из «;» и без лишних подписей.
    admin_lines: set[str] = set()
    for item in iter_formula_defs(exclude_page=PAGE_ELECTRICAL_INTENSITY):
        admin_lines.update(item.page_label_lines())
    expected = {"Все перечисленные сводки"} | {
        label for key, label in PAGE_LABELS.items() if key != PAGE_ELECTRICAL_INTENSITY
    }
    assert admin_lines == expected


def test_pd_template_formula_vars_resolve_to_registry_keys() -> None:
    missing = [
        (var, key)
        for var, key in PD_FORMULA_TEMPLATE_VAR_KEYS.items()
        if get_formula_def(key) is None
    ]
    assert missing == [], missing


def test_fo_combined_on_ees_formulas_present_for_summary_tooltips() -> None:
    assert get_formula_def("fo_calc_combined_on_ees_mw") is not None
    assert get_formula_def("fo_verify_combined_ees_mw_without_nt") is not None
    assert get_formula_def("fo_verify_combined_ees_mw_with_nt") is not None
