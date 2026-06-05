# -*- coding: utf-8 -*-
"""Уникальный индекс: одна строка на (сущность, год, версия БД)."""
from sqlalchemy import Index, text


def version_year_unique_index(index_name: str, parent_id_column: str) -> Index:
    return Index(
        index_name,
        parent_id_column,
        "year_number",
        text("COALESCE(database_version_id, -1)"),
        unique=True,
    )
