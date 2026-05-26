# -*- coding: utf-8 -*-
"""Колонка варианта периметра для таблиц параметров (опционально на модели)."""
from sqlalchemy import String

from app.extensions import db


class PerimeterVariantColumnMixin:
    """
    NULL — обычная строка сущности без варианта периметра.
    Иначе — код из :mod:`app.common.perimeter_variant.registry`.
    """

    perimeter_variant_code = db.Column(String(64), nullable=True, index=True)
