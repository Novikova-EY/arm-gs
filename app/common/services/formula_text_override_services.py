# -*- coding: utf-8 -*-
"""Общая инфраструктура переопределений текстов формул (кэш Flask g + БД)."""

from __future__ import annotations

from typing import Any

import logging

from flask import g

from app.extensions import db

_logger = logging.getLogger(__name__)


def normalize_formula_text(text: str) -> str:
    return " ".join(str(text or "").split())


class FormulaTextOverrideStore:
    def __init__(
        self,
        model_class: Any,
        cache_key: str,
        *,
        tolerate_no_app_context: bool = False,
    ) -> None:
        self._model_class = model_class
        self._cache_key = cache_key
        self._tolerate_no_app_context = tolerate_no_app_context

    def load_from_db(self) -> dict[str, str]:
        rows = self._model_class.query.all()
        return {str(r.formula_key): str(r.formula_text or "") for r in rows}

    def clear_cache(self) -> None:
        try:
            if hasattr(g, self._cache_key):
                delattr(g, self._cache_key)
        except RuntimeError:
            if not self._tolerate_no_app_context:
                raise

    def get_overrides(self) -> dict[str, str]:
        cached = None
        try:
            cached = getattr(g, self._cache_key, None)
        except RuntimeError:
            if not self._tolerate_no_app_context:
                raise
        if cached is not None:
            return cached
        try:
            overrides = self.load_from_db()
        except Exception:
            _logger.exception(
                "formula text overrides load failed (cache_key=%s)", self._cache_key
            )
            overrides = {}
        try:
            setattr(g, self._cache_key, overrides)
        except RuntimeError:
            if not self._tolerate_no_app_context:
                raise
        return overrides

    def save_override(self, *, formula_key: str, formula_text: str) -> None:
        key = str(formula_key or "").strip()
        text = str(formula_text or "").strip()
        if not text:
            raise ValueError("Текст формулы не может быть пустым.")
        row = self._model_class.query.filter_by(formula_key=key).first()
        if row is None:
            row = self._model_class(formula_key=key, formula_text=text)
            db.session.add(row)
        else:
            row.formula_text = text
        self.clear_cache()

    def reset_override(
        self,
        formula_key: str,
        *,
        skip_empty_key: bool = False,
        bulk_delete: bool = False,
    ) -> None:
        key = str(formula_key or "").strip()
        if skip_empty_key and not key:
            return
        if bulk_delete:
            self._model_class.query.filter_by(formula_key=key).delete(
                synchronize_session=False
            )
        else:
            row = self._model_class.query.filter_by(formula_key=key).first()
            if row is not None:
                db.session.delete(row)
        self.clear_cache()
