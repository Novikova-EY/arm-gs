# -*- coding: utf-8 -*-
"""Тексты формул расчёта по действующим ТЭС: чтение переопределений и администрирование."""

from __future__ import annotations

from typing import Any

from markupsafe import Markup, escape

from app.common.services.formula_text_override_services import FormulaTextOverrideStore
from app.ecology.models.formula_text.operating_tes_formula_text_model import (
    OperatingTesFormulaText,
)
from app.ecology.services.operating_tes_formula_registry import (
    OperatingTesFormulaDef,
    get_formula_def,
    iter_formula_defs,
)

_OVERRIDE_STORE = FormulaTextOverrideStore(
    OperatingTesFormulaText,
    "eco_ot_formula_text_overrides",
    tolerate_no_app_context=True,
)


def clear_formula_text_override_cache() -> None:
    _OVERRIDE_STORE.clear_cache()


def get_formula_text_overrides() -> dict[str, str]:
    return _OVERRIDE_STORE.get_overrides()


def ot_formula_text(formula_key: str, default: str | None = None) -> str:
    """Эффективный текст формулы: переопределение из БД или значение по умолчанию."""
    definition = get_formula_def(formula_key)
    fallback = default if default is not None else (definition.default_text if definition else "")
    overrides = get_formula_text_overrides()
    override = overrides.get(formula_key)
    if override is not None and str(override).strip() != "":
        return str(override).strip()
    return str(fallback).strip()


def formula_text_for_sheet(sheet_slug: str) -> str:
    from app.ecology.services.operating_tes_formula_registry import SHEET_FORMULA_KEYS

    key = SHEET_FORMULA_KEYS.get(str(sheet_slug or "").strip())
    if not key:
        return ""
    return ot_formula_text(key)


def format_natural_fuel_formula(text: str) -> Markup:
    """Единое обозначение натурального топлива, включая сохраненные тексты формул."""
    for old_symbol in ("Перевод в натур.", "Вн", "ВН"):
        text = text.replace(old_symbol, "BH")
    return escape(text).replace("BH", Markup("B<sup>H</sup>"))


def format_emission_formula(text: str) -> Markup:
    formatted = format_natural_fuel_formula(text)
    for symbol, html in (
        ("МотхNOx", "М<sub>отх</sub><sup>NOx</sup>"),
        ("МотхCO2", "М<sub>отх</sub><sup>CO<sub>2</sub></sup>"),
        ("Мотхco2", "М<sub>отх</sub><sup>CO<sub>2</sub></sup>"),
        ("KCO2", "K<sub>CO<sub>2</sub></sub>"),
        ("Kco2", "K<sub>CO<sub>2</sub></sub>"),
        ("МотхCO", "М<sub>отх</sub><sup>CO</sup>"),
        ("Мотхco", "М<sub>отх</sub><sup>CO</sup>"),
        ("Мотх", "М<sub>отх</sub>"),
        ("МвыбSO2", "М<sub>выб</sub><sup>SO<sub>2</sub></sup>"),
        ("МвыбNOx", "М<sub>выб</sub><sup>NO<sub>x</sub></sup>"),
        ("МвыбCO2", "М<sub>выб</sub><sup>CO<sub>2</sub></sup>"),
        ("МвыбCO", "М<sub>выб</sub><sup>CO</sup>"),
        ("Мвыб", "М<sub>выб</sub>"),
        ("аун", "a<sub>ун</sub>"),
        ("Aр", "A<sup>р</sup>"),
        ("Ар", "A<sup>р</sup>"),
        ("Sp", "S<sup>p</sup>"),
        ("qч", "q<sub>ч</sub>"),
        ("bj", "b<sub>j</sub>"),
        ("q3", "q<sub>3</sub>"),
        ("q4", "q<sub>4</sub>"),
        ("Qн", "Q<sub>н</sub>"),
        ("QH", "Q<sub>н</sub>"),
    ):
        formatted = formatted.replace(symbol, Markup(html))
    return formatted


def list_formulas_for_admin(*, page: str | None = None) -> list[dict[str, Any]]:
    overrides = get_formula_text_overrides()
    out: list[dict[str, Any]] = []
    for item in iter_formula_defs(page=page):
        out.append(
            {
                "key": item.key,
                "page_labels": item.page_labels(),
                "page_lines": list(item.page_label_lines()),
                "aggregation_level": item.aggregation_level,
                "cell_name": item.cell_name,
                "default_text": item.default_text,
                "formula_text": ot_formula_text(item.key),
                "is_customized": item.key in overrides,
            }
        )
    return out


def save_formula_text_override(*, formula_key: str, formula_text: str) -> OperatingTesFormulaDef:
    key = str(formula_key or "").strip()
    definition = get_formula_def(key)
    if not definition:
        raise ValueError(f"Неизвестный ключ формулы: {key}")
    _OVERRIDE_STORE.save_override(formula_key=key, formula_text=formula_text)
    return definition


def reset_formula_text_override(formula_key: str) -> None:
    key = str(formula_key or "").strip()
    _OVERRIDE_STORE.reset_override(key)
