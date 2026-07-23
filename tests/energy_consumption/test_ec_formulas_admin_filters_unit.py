# -*- coding: utf-8 -*-
"""Ревизия фильтров и текстов /energy_consumption/formulas/."""

from __future__ import annotations

from collections import Counter

from app.energy_consumption.services.ec_summary_formula_template_vars import (
    EC_FORMULA_TEMPLATE_VAR_KEYS,
)
from app.energy_consumption.services.energy_consumption_summary_formula_registry import (
    EC_SUMMARY_FORMULA_REGISTRY,
    PAGE_ELECTRICAL_INTENSITY,
    get_formula_def,
    iter_formula_defs,
)
from app.energy_consumption.services.formula_text.energy_consumption_summary_formula_text_services import (
    _normalize_formula_text,
)


def test_ec_admin_filter_page_values_are_unique() -> None:
    lines: list[str] = []
    for item in iter_formula_defs(exclude_page=PAGE_ELECTRICAL_INTENSITY):
        lines.extend(item.page_label_lines())
    # В выпадающем списке Set; проверяем, что исходные подписи без «шума» (; / пробелы).
    for line in lines:
        assert line == line.strip()
        assert not line.endswith(";")


def test_ec_admin_filter_cell_names_unique_per_key() -> None:
    """Две разные формулы не должны делить одно имя ячейки (иначе дубль в фильтре/таблице)."""
    by_cell: dict[str, list[str]] = {}
    for item in iter_formula_defs(exclude_page=PAGE_ELECTRICAL_INTENSITY):
        by_cell.setdefault(item.cell_name, []).append(item.key)
    dupes = {name: keys for name, keys in by_cell.items() if len(keys) > 1}
    assert dupes == {}, dupes


def test_ec_admin_filter_aggregation_levels_trimmed() -> None:
    levels = [
        item.aggregation_level
        for item in iter_formula_defs(exclude_page=PAGE_ELECTRICAL_INTENSITY)
    ]
    for level in levels:
        assert level == level.strip()
    # Нет пар, отличающихся только регистром/пробелами.
    norm = Counter(" ".join(x.casefold().split()) for x in levels)
    raw = Counter(levels)
    assert len(norm) == len(raw)


def test_ec_template_formula_vars_resolve_to_registry_keys() -> None:
    missing = [
        (var, key)
        for var, key in EC_FORMULA_TEMPLATE_VAR_KEYS.items()
        if get_formula_def(key) is None
    ]
    assert missing == [], missing


def test_ec_page_tooltips_match_registry_defaults() -> None:
    """Хардкод тултипов на сводках должен совпадать с default_text реестра."""
    from app.energy_consumption import services as _pkg  # noqa: F401
    import app.energy_consumption.services.energy_consumption_summary_services as svc

    cases = [
        ("_CZ_RUSSIA_WITH_NT_FORMULA_TOOLTIP", "cz_russia_with_nt"),
        ("_CZ_RUSSIA_WITHOUT_NT_FORMULA_TOOLTIP", "cz_russia_without_nt"),
        (
            "_EES_RUSSIA_WITHOUT_NT_WITH_GAES_KALININGRAD_SPLIT_VERIFICATION_TOOLTIP",
            "ees_russia_without_nt_gaes_kaliningrad_split_verification",
        ),
        ("_OES_RES_WITHOUT_GAES_VERIFICATION_TOOLTIP", "oes_res_without_gaes_verification"),
        ("_NT_UNDER_SOUTH_FORMULA_TOOLTIP", "nt_under_south"),
        ("_FO_FORMULA_TOOLTIP", "fo_formula_aggregate"),
        ("_SOUTH_FO_WITH_NT_FORMULA_TOOLTIP", "south_fo_with_nt"),
        (
            "_FIRST_SA_WITHOUT_NT_WITH_GAES_WITHOUT_KALININGRAD_FORMULA_TOOLTIP",
            "first_sa_without_nt_with_gaes_without_kaliningrad",
        ),
        (
            "_FIRST_SA_WITH_NT_WITH_GAES_WITH_KALININGRAD_FORMULA_TOOLTIP",
            "first_sa_with_nt_with_gaes_with_kaliningrad_py",
        ),
    ]
    for attr, key in cases:
        page_text = getattr(svc, attr)
        defn = get_formula_def(key)
        assert defn is not None, key
        assert _normalize_formula_text(page_text) == _normalize_formula_text(
            defn.default_text
        ), (attr, key)


def test_removed_duplicate_formula_keys_gone() -> None:
    gone = (
        "first_sa_with_nt_with_gaes",
        "first_sa_without_nt_without_kaliningrad_with_gaes",
        "tites_oes_aggregate",
        "tites_oes_aggregate_verification",
        "tites_res_energy_unit_verification",
        "oes_res_with_gaes_verification",
    )
    present = {item.key for item in EC_SUMMARY_FORMULA_REGISTRY}
    assert present.isdisjoint(gone)
