"""Сервисный get-модуль для TechnologyType."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.refdata_for_stations.technologies.technology_type_model import TechnologyType


@lru_cache(maxsize=1)
def get_technology_type_list_full():
    """Получает полный список типов технологий'."""
    return (
        TechnologyType.query
        .order_by(
            (TechnologyType.id != 0),
            TechnologyType.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_technology_type_list():
    """Получает список типов технологий (кроме "не указано")."""
    query = (
        TechnologyType.query
        .filter(TechnologyType.id.isnot(None), TechnologyType.id > 0)
        .order_by(TechnologyType.name.asc())
    )
    return query


def get_technology_type_name(technology_type_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами типов технологий по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not technology_type_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(technology_type_ids, str):
        ids = [int(x) for x in technology_type_ids.split(",") if x.strip().isdigit()]
    elif isinstance(technology_type_ids, int):
        ids = [technology_type_ids]
    else:
        ids = [int(x) for x in technology_type_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = TechnologyType.query.filter(TechnologyType.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)