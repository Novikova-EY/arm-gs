# -*- coding: utf-8 -*-
"""Сервисный модуль: Департаменты."""
from sqlalchemy import or_, case, cast, Integer
import pandas as pd
from io import BytesIO

from app.fuel.models.external_mapping.fue_em_department_model import (
    DepartmentExternalMapping,
)
from app.common.services.help_services import _dash
from app.logs.services.logging_service import log_to_db


def department_query(
    department_filter=None,
    sort_by="external_id",
    sort_dir="asc",
):
    """Базовый запрос для списка департаментов с фильтрацией и сортировкой."""
    allowed_sort_by = {
        "external_id",
        "external_name",
    }
    sort_by = sort_by if sort_by in allowed_sort_by else "external_id"
    sort_dir = (sort_dir or "asc").lower()
    sort_dir = "desc" if sort_dir == "desc" else "asc"

    query = DepartmentExternalMapping.query

    if department_filter:
        query = query.filter(
            or_(
                DepartmentExternalMapping.external_id.ilike(
                    f"%{department_filter}%"
                ),
                DepartmentExternalMapping.external_name.ilike(
                    f"%{department_filter}%"
                ),
            )
        )

    if sort_by == "external_id":
        sort_col = DepartmentExternalMapping.external_id
        numeric_sort = case(
            (sort_col.op("~")("^[0-9]+$"), cast(sort_col, Integer)),
            else_=None,
        )
        query = query.order_by(
            numeric_sort.desc().nullslast()
            if sort_dir == "desc"
            else numeric_sort.asc().nullslast(),
            sort_col.asc().nullslast(),
        )
    elif sort_by == "external_name":
        sort_col = DepartmentExternalMapping.external_name
        query = query.order_by(
            sort_col.desc().nullslast()
            if sort_dir == "desc"
            else sort_col.asc().nullslast()
        )
    return query


def get_department_list(
    page,
    per_page,
    department_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Получает список департаментов с пагинацией."""
    query = department_query(
        department_filter=department_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    )
    return query.paginate(page=page, per_page=per_page, error_out=False)


def export_department_mappings_service(
    user,
    department_filter=None,
    sort_by="id",
    sort_dir="asc",
):
    """Экспортирует сопоставления департаментов с БД Топливо в Excel."""
    log_to_db(
        user,
        "Начата выгрузка сопоставлений департаментов (Топливо)",
        entity_type="department",
    )
    log_to_db(
        user,
        "Параметры экспорта",
        (
            f"Фильтр по департаментам = {department_filter}, "
            f"Сортировка = {sort_by}, направление = {sort_dir}."
        ),
    )

    mappings = department_query(
        department_filter=department_filter,
        sort_by=sort_by,
        sort_dir=sort_dir,
    ).all()

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
    for mapping in mappings:
        data.append(
            {
                "Номер (dep)": _dash(_normalize_external_id(mapping.external_id)),
                "Наименование (name)": _dash(mapping.external_name),
            }
        )

    log_to_db(
        user,
        "Подготовка данных для экспорта сопоставлений департаментов",
        f"Записей для экспорта: {len(data)}",
        entity_type="department",
    )

    df = pd.DataFrame(data)
    output = BytesIO()
    sheet_name = "Департаменты (Топливо)"
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
        "Экспорт сопоставлений департаментов завершен",
        f"Экспортировано записей: {len(data)}",
        entity_type="department",
    )
    return output
