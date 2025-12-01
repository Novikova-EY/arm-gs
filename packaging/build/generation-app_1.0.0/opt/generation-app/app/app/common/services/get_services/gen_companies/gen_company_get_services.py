"""Сервисный get-модуль для GenCompany."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.gen_companies.gen_company_model import GenCompany

# Функции для работы с версионированием БД
from app.common.services.database_version_filter import filter_by_db_version
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_gen_company_list_full():
    """Получает полный список генерирующих компаний'."""
    current_version = get_current_version()
    query = GenCompany.query
    if current_version:
        query = query.filter(GenCompany.database_version_id == current_version)
    # Фильтрация по версии БД
    return (
        query
        .order_by(
            (GenCompany.id != 0),
            GenCompany.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_gen_company_list():
    """Получает список генерирующих компаний (кроме "не указано")."""
    current_version = get_current_version()
    query = GenCompany.query
    
    if current_version:
        query = query.filter(GenCompany.database_version_id == current_version)
    
    return (
        query
        .filter(GenCompany.id.isnot(None), GenCompany.id > 0)
        .order_by(GenCompany.name.asc())
    )


def get_gen_company_name(gen_company_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами генерирующих компаний по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not gen_company_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(gen_company_ids, str):
        ids = [int(x) for x in gen_company_ids.split(",") if x.strip().isdigit()]
    elif isinstance(gen_company_ids, int):
        ids = [gen_company_ids]
    else:
        ids = [int(x) for x in gen_company_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы с фильтром по версии
    current_version = get_current_version()
    query = GenCompany.query.filter(GenCompany.id.in_(ids))
    
    if current_version:
        query = query.filter(GenCompany.database_version_id == current_version)
    
    objs = query.all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)