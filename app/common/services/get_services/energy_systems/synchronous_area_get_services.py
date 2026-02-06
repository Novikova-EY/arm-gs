"""Сервисный get-модуль для SynchronousArea."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.energy_systems.synchronous_area_model import SynchronousArea

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_synchronous_area_list_full():
    """Получает полный список синхронных зон."""
    current_version = get_current_version()
    query = SynchronousArea.query
    
    if current_version:
        query = query.filter(SynchronousArea.database_version_id == current_version)
    
    return (
        query
        .order_by(
            SynchronousArea.display_order.asc().nullslast(),
            SynchronousArea.name.asc(),
            SynchronousArea.id.asc(),
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_synchronous_area_list():
    """Получает список синхронных зон (кроме "не указано")."""
    current_version = get_current_version()
    query = SynchronousArea.query
    
    if current_version:
        query = query.filter(SynchronousArea.database_version_id == current_version)
    
    return (
        query
        .filter(SynchronousArea.id.isnot(None), SynchronousArea.id > 0)
        .order_by(
            SynchronousArea.display_order.asc().nullslast(),
            SynchronousArea.name.asc(),
            SynchronousArea.id.asc(),
        )
    )


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

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = SynchronousArea.query.filter(SynchronousArea.id.in_(ids))
    
    if current_version:
        query = query.filter(SynchronousArea.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)
