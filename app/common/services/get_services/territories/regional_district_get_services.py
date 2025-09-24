"""Сервисный get-модуль для RegionalDistrict."""

from app.extensions import db
from sqlalchemy.orm import selectinload
from functools import lru_cache
from typing import Union, List, Dict

# Модели
from app.refdata.models.territories.federal_district_model import FederalDistrict
from app.refdata.models.territories.regional_district_model import RegionalDistrict


@lru_cache(maxsize=1)
def get_regional_district_list_full():
    """Получает полный список субъектов РФ."""
    return (
        RegionalDistrict.query
        .order_by(RegionalDistrict.name.asc())
        .all()
    )


@lru_cache(maxsize=1)
def get_regional_district_list():
    """Получает список субъектов РФ (кроме "не указано")."""
    query = (
        RegionalDistrict.query
        .filter(RegionalDistrict.id.isnot(None), RegionalDistrict.id > 0)
        .order_by(RegionalDistrict.name.asc())
    )
    return query


def get_regional_districts_list() -> List[RegionalDistrict]:
    """Возвращает список ORM-объектов субъектов РФ с заранее загруженными ФО."""
    return (
        RegionalDistrict.query
        .options(
            selectinload(RegionalDistrict.federal_district)
            .load_only(FederalDistrict.id, FederalDistrict.name)
        )
        .order_by(RegionalDistrict.id)
        .all()
    )

# 2) DTO-список для шаблонов (плоские dict'ы)
def get_regional_districts_dto_list() -> List[dict]:
    """Возвращает список dict: {id, name, federal_district_id, federal_district_name}."""
    rows = get_regional_districts_list()
    return [
        {
            "id": rd.id,
            "name": rd.name,
            "federal_district_id": rd.id_federal_district,
            "federal_district_name": rd.federal_district.name if rd.federal_district else None,
        }
        for rd in rows
    ]

# 3) Lookup {rd_id: name} — лёгкий и кэшируемый
@lru_cache(maxsize=1)
def get_regional_districts_map() -> Dict[int, str]:
    """Возвращает отображение {Субъект.id: Субъект.name} (кэшируется)."""
    rows = (
        RegionalDistrict.query
        .with_entities(RegionalDistrict.id, RegionalDistrict.name)
        .order_by(RegionalDistrict.id)
        .all()
    )
    return {id_: name for id_, name in rows}


# 4) Маппинг {rd_id: fd_id} — часто нужен для валидации/фильтров
@lru_cache(maxsize=1)
def get_rd_to_fd_id_map() -> Dict[int, int]:
    """Возвращает отображение {Субъект.id: ФО.id} (кэшируется)."""
    rows = (
        RegionalDistrict.query
        .with_entities(RegionalDistrict.id, RegionalDistrict.id_federal_district)
        .filter(RegionalDistrict.id_federal_district.isnot(None))
        .all()
    )
    return {rd_id: fd_id for rd_id, fd_id in rows}

# 5) Инвалидатор кэшей — вызывать после CRUD по субъектам/их привязке к ФО
def invalidate_regional_district_lookups_cache() -> None:
    get_regional_districts_map.cache_clear()
    get_rd_to_fd_id_map.cache_clear()


def get_regional_district_name(regional_district_ids: Union[str, int, List[int]]) -> str:
    """
    Возвращает строку с именами субъектов РФ по списку ID (или по одному ID).
    Если передано пустое значение → "Не указано".
    """
    if not regional_district_ids:
        return "Не указано"

    # Если строка "1,2,3" → превращаем в список int
    if isinstance(regional_district_ids, str):
        ids = [int(x) for x in regional_district_ids.split(",") if x.strip().isdigit()]
    elif isinstance(regional_district_ids, int):
        ids = [regional_district_ids]
    else:
        ids = [int(x) for x in regional_district_ids if x]  # на случай list[str]

    if not ids:
        return "Не указано"

    # Берем имена из базы
    objs = RegionalDistrict.query.filter(RegionalDistrict.id.in_(ids)).all()
    id_to_name = {o.id: o.name for o in objs}

    # Возвращаем строку в порядке входных ID
    result = [id_to_name.get(i, f"ID={i}") for i in ids]
    return ", ".join(result)