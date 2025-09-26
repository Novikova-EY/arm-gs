"""Сервисный get-модуль для GenCompany."""

from functools import lru_cache
from typing import Union, List

# Модели
from app.refdata.models.gen_companies.gen_company_model import GenCompany


@lru_cache(maxsize=1)
def get_gen_company_list_full():
    """Получает полный список генерирующих компаний'."""
    return (
        GenCompany.query
        .order_by(
            (GenCompany.id != 0),
            GenCompany.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_gen_company_list():
    """Получает список генерирующих компаний (кроме "не указано")."""
    query = (
        GenCompany.query
        .filter(GenCompany.id.isnot(None), GenCompany.id > 0)
        .order_by(GenCompany.name.asc())
    )
    return query


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

    # Берем имена из базы
    objs = GenCompany.query.filter(GenCompany.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)