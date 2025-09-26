"""Сервисный get-модуль для SynchronousArea."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea


@lru_cache(maxsize=1)
def get_synchronous_area_list_full():
    """Получает полный список синхронных зон."""
    return (
        SynchronousArea.query
        .order_by(
            (SynchronousArea.id != 0),
            SynchronousArea.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_synchronous_area_list():
    """Получает список синхронных зон (кроме "не указано")."""
    query = (
        SynchronousArea.query
        .filter(SynchronousArea.id.isnot(None), SynchronousArea.id > 0)
        .order_by(SynchronousArea.name.asc())
    )
    return query


def get_synchronous_area_name(synchronous_area_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами синхронных зон по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not synchronous_area_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(synchronous_area_ids, str):
        ids = [int(x) for x in synchronous_area_ids.split(",") if x.strip().isdigit()]
    elif isinstance(synchronous_area_ids, int):
        ids = [synchronous_area_ids]
    else:
        ids = [int(x) for x in synchronous_area_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = SynchronousArea.query.filter(SynchronousArea.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)
