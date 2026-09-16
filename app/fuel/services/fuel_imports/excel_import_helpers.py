# -*- coding: utf-8 -*-
"""Shared helpers for Excel fuel import services."""

from __future__ import annotations

import logging


def get_fuel_import_logger(module_name: str | None = None) -> logging.Logger:
    """Return Flask app logger when in app context, else stdlib logger."""
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            return current_app.logger
    except Exception:
        pass
    return logging.getLogger(module_name or __name__)


def normalize_import_column_name(col) -> str:
    """Canonical column header normalizer for equipment-group Excel imports."""
    s = "" if col is None else str(col)
    s = s.replace("\r", " ").replace("\n", " ").strip().lower()
    s = s.replace("е", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


def normalize_import_column_name_with_nbsp(col) -> str:
    """Like normalize_import_column_name, but also collapses non-breaking spaces."""
    s = "" if col is None else str(col)
    s = (
        s.replace("\r", " ")
        .replace("\n", " ")
        .replace("\u00a0", " ")
        .replace("\xa0", " ")
        .strip()
        .lower()
    )
    s = s.replace("е", "е")
    s = " ".join(s.split())
    s = s.replace(" ", "_")
    s = "".join(ch for ch in s if ch.isalnum() or ch == "_")
    s = "_".join(filter(None, s.split("_")))
    return s


def normalize_refdata_column_name(value: object) -> str:
    """Column normalizer for refdata mapping imports (strips separators)."""
    return (
        str(value or "")
        .strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


def normalize_composite_flags_column_name(name: object) -> str:
    """Column normalizer for soft composite-flags Excel imports."""
    if name is None:
        return ""
    text = str(name).strip().lower().replace("ё", "е")
    out = []
    for ch in text:
        if ch.isalnum() or ch in ("_",):
            out.append(ch)
        elif ch.isspace() or ch in ("-", ".", "/", "\\"):
            out.append("_")
    return "_".join(p for p in "".join(out).split("_") if p)
