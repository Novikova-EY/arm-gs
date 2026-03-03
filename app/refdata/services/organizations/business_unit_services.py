# -*- coding: utf-8 -*-
"""Сервисный модуль: Бизнес единицы."""
from sqlalchemy import or_
import pandas as pd
from io import BytesIO

from app.fuel.models.external_mapping.fue_em_business_unit_model import (
    BusinessUnitExternalMapping,
)
from app.common.services.help_services import _dash
from app.logs.services.logging_service import log_to_db


def business_unit_query(
    business_unit_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Базовый запрос для списка сопоставлений бизнес единиц с фильтрацией и сортировкой."""
    allowed_sort_by = {
        "id",
        "external_id",
        "external_name",
    }
    sort_by = sort_by if sort_by in allowed_sort_by else "id"
    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    query = BusinessUnitExternalMapping.query

    if business_unit_filter:
        query = query.filter(
            or_(
                BusinessUnitExternalMapping.external_id.ilike(
                    f"%{business_unit_filter}%"
                ),
                BusinessUnitExternalMapping.external_name.ilike(
                    f"%{business_unit_filter}%"
                ),
            )
        )

    if sort_by == "external_id":
        sort_col = BusinessUnitExternalMapping.external_id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    elif sort_by == "external_name":
        sort_col = BusinessUnitExternalMapping.external_name
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())
    else:
        sort_col = BusinessUnitExternalMapping.id
        query = query.order_by(sort_col.desc() if sort_dir == "desc" else sort_col.asc())

    return query


def get_business_unit_list(
    page,
    per_page,
    business_unit_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Получает список бизнес единиц с пагинацией."""
    query = business_unit_query(
        business_unit_filter=business_unit_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def export_business_unit_mappings_service(
    user,
    business_unit_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Экспортирует сопоставления бизнес единиц с БД Топливо в Excel."""
    log_to_db(
        user,
        "Начата выгрузка сопоставлений бизнес единиц (Топливо)",
        entity_type="business_unit",
    )
    log_to_db(
        user,
        "Параметры экспорта",
        (
            f"Фильтр по бизнес единицам = {business_unit_filter}, "
            f"Сортировка = {sort_by}, направление = {sort_dir}."
        ),
    )

    query = business_unit_query(
        business_unit_filter=business_unit_filter,
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
                "Номер (code)": _dash(
                    _normalize_external_id(mapping.external_id) if mapping else None
                ),
                "Наименование (name)": _dash(
                    mapping.external_name if mapping else None
                ),
            }
        )

    log_to_db(
        user,
        "Подготовка данных для экспорта сопоставлений бизнес единиц",
        f"Записей для экспорта: {len(data)}",
        entity_type="business_unit",
    )

    df = pd.DataFrame(data)
    output = BytesIO()
    sheet_name = "Бизнес единицы (Топливо)"
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
        "Экспорт сопоставлений бизнес единиц завершен",
        f"Экспортировано записей: {len(data)}",
        entity_type="business_unit",
    )
    return output
