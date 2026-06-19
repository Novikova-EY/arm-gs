# -*- coding: utf-8 -*-
"""Редактирование текстов формул электроёмкости (модуль спроса)."""

from __future__ import annotations

from typing import Any

from app.energy_consumption.electrical_intensity.services.formula_text import (
    electrical_intensity_formula_text_services as eifts,
)

_AGGREGATION_LEVEL = "Строка таблицы (ВЭД)"


def _row_for_admin(raw: dict[str, Any]) -> dict[str, Any]:
    page = str(raw.get("page") or "").strip()
    page_lines = [page] if page else []
    return {
        "key": raw["formula_key"],
        "page_labels": page,
        "page_lines": page_lines,
        "aggregation_level": _AGGREGATION_LEVEL,
        "cell_name": raw["row_label"],
        "default_text": raw["default_text"],
        "formula_text": raw["formula_text"],
        "is_customized": raw["is_overridden"],
    }


def list_formulas_for_admin() -> list[dict[str, Any]]:
    return [_row_for_admin(raw) for raw in eifts.list_formulas_for_admin()]


def save_formula_text_override(*, formula_key: str, formula_text: str) -> None:
    eifts.save_formula_text_override(formula_key=formula_key, formula_text=formula_text)


def reset_formula_text_override(formula_key: str) -> None:
    eifts.reset_formula_text_override(formula_key)
