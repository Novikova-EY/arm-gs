"""Сервисный get-модуль для FederalDistrict."""

from sqlalchemy import text, or_
from sqlalchemy.orm import joinedload
from typing import Union, List

# Модели
from app.refdata.models.territories.federal_district_model import FederalDistrict


def get_federal_district_list_full():
    """Получает полный список федеральных округов.."""
    return FederalDistrict.query.all()


def get_federal_district_list():
    """Получает список федеральных округов (кроме "не указано")."""
    query = (
        FederalDistrict.query
        .filter(FederalDistrict.id.isnot(None), FederalDistrict.id > 0)
    )
    return query


def get_federal_district_name(federal_district_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами федеральных округов по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not federal_district_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(federal_district_ids, str):
        ids = [int(x) for x in federal_district_ids.split(",") if x.strip().isdigit()]
    elif isinstance(federal_district_ids, int):
        ids = [federal_district_ids]
    else:
        ids = [int(x) for x in federal_district_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = FederalDistrict.query.filter(FederalDistrict.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)