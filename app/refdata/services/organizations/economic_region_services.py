# -*- coding: utf-8 -*-
"""Сервисный модуль: Экономические районы."""
from sqlalchemy import or_
import pandas as pd
from io import BytesIO

from app.fuel.models.external_mapping.fue_em_economic_region_model import (
    EconomicRegionExternalMapping,
)
from app.common.services.help_services import _dash
from app.logs.services.logging_service import log_to_db


def economic_region_query(
    economic_region_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Базовый запрос для списка сопоставлений экономических районов."""
    allowed_sort_by = {
        "id",
        "external_id",
        "external_name",
    }
    sort_by = sort_by if sort_by in allowed_sort_by else "id"
    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    query = EconomicRegionExternalMapping.query

    if economic_region_filter:
        query = query.filter(
            or_(
                EconomicRegionExternalMapping.external_id.ilike(
                    f"%{economic_region_filter}%"
                ),
                EconomicRegionExternalMapping.external_name.ilike(
                    f"%{economic_region_filter}%"
                ),
            )
        )

    if sort_by == "external_id":
        sort_col = EconomicRegionExternalMapping.external_id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    elif sort_by == "external_name":
        sort_col = EconomicRegionExternalMapping.external_name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    else:
        sort_col = EconomicRegionExternalMapping.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


def get_economic_region_list(
    page,
    per_page,
    economic_region_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Получает список экономических районов с пагинацией."""
    query = economic_region_query(
        economic_region_filter=economic_region_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def export_economic_region_mappings_service(
    user,
    economic_region_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Экспортирует сопоставления экономических районов с БД Топливо в Excel."""
    log_to_db(
        user,
        "Начата выгрузка сопоставлений экономических районов (Топливо)",
        entity_type="economic_region",
    )
    log_to_db(
        user,
        "Параметры экспорта",
        (
            f"Фильтр по экономическим районам = {economic_region_filter}, "
            f"Сортировка = {sort_by}, направление = {sort_dir}."
        ),
    )

    query = economic_region_query(
        economic_region_filter=economic_region_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    items = query.all()

    def _normalize_external_id(value):
        if value is None:
            return None
        if isinstance(value, (int, float)):
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value)
        raw = str(value).strip()
        try:
            as_float = float(raw.replace(",", "."))
            if as_float.is_integer():
                return str(int(as_float))
        except ValueError:
            pass
        return raw

    data = []
    for mapping in items:
        data.append(
            {
                "ID в БД Топливо": _dash(
                    _normalize_external_id(mapping.external_id) if mapping else None
                ),
                "Название в БД Топливо": _dash(
                    mapping.external_name if mapping else None
                ),
            }
        )

    log_to_db(
        user,
        "Подготовка данных для экспорта сопоставлений экономических районов",
        f"Записей для экспорта: {len(data)}",
        entity_type="economic_region",
    )

    df = pd.DataFrame(data)
    output = BytesIO()
    sheet_name = "Экономические районы (Топливо)"
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]
        for i, col in enumerate(df.columns):
            max_len = (
                max(len(str(col)), *(len(str(v)) for v in df[col].values))
                if not df.empty
                else len(str(col))
            )
            ws.set_column(i, i, min(max_len + 2, 60))

    output.seek(0)
    log_to_db(
        user,
        "Экспорт сопоставлений экономических районов завершен",
        f"Экспортировано записей: {len(data)}",
        entity_type="economic_region",
    )
    return output
