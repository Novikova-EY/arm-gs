# -*- coding: utf-8 -*-
"""Тексты формул страницы электроёмкости (хранение — сводки потребления ЭЭ)."""

from __future__ import annotations

from typing import Any

from app.energy_consumption.services.formula_text.energy_consumption_summary_formula_text_services import (
    ec_formula_text,
    list_formulas_for_admin as list_ec_formulas_for_admin,
    migrate_legacy_electrical_intensity_formula_texts,
    reset_formula_text_override as reset_ec_formula_text_override,
    save_formula_text_override as save_ec_formula_text_override,
)
from app.energy_consumption.services.energy_consumption_summary_formula_registry import (
    PAGE_ELECTRICAL_INTENSITY,
)


def ei_formula_text(formula_key: str, default: str | None = None) -> str:
    migrate_legacy_electrical_intensity_formula_texts()
    return ec_formula_text(formula_key, default)


def list_formulas_for_admin() -> list[dict[str, Any]]:
    """Совместимость: отдельная админ-страница электроёмкости перенесена в summary-formulas."""
    migrate_legacy_electrical_intensity_formula_texts()
    rows: list[dict[str, Any]] = []
    for raw in list_ec_formulas_for_admin(page=PAGE_ELECTRICAL_INTENSITY):
        rows.append(
            {
                "formula_key": raw["key"],
                "page": raw["page_labels"],
                "row_label": raw["cell_name"],
                "default_text": raw["default_text"],
                "formula_text": raw["formula_text"],
                "is_overridden": raw["is_customized"],
            }
        )
    return rows


def save_formula_text_override(*, formula_key: str, formula_text: str) -> None:
    migrate_legacy_electrical_intensity_formula_texts()
    save_ec_formula_text_override(formula_key=formula_key, formula_text=formula_text)


def reset_formula_text_override(formula_key: str) -> None:
    migrate_legacy_electrical_intensity_formula_texts()
    reset_ec_formula_text_override(formula_key)
