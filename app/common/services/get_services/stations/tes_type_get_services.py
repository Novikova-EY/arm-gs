from functools import lru_cache
from sqlalchemy import func, or_

# Модели
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType

# Сервисы
from app.common.services.database_version_services import get_current_version
from app.common.services.database_version_filter import filter_by_db_version


@lru_cache(maxsize=1)
def get_tes_type_list_full():
    """Получает полный список типов ТЭС."""
    current_version = get_current_version()
    query = TesType.query
    
    if current_version:
        query = query.filter(TesType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            TesType.display_order.asc().nullslast(),
            TesType.name.asc(),
            TesType.id.asc(),
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_tes_type_list():
    """Получает список типов ТЭС (кроме "не указано")."""
    current_version = get_current_version()
    query = TesType.query
    
    if current_version:
        query = query.filter(TesType.database_version_id == current_version)
    
    return (
        query
        .filter(TesType.id.isnot(None), TesType.id > 0)
        .order_by(
            TesType.display_order.asc().nullslast(),
            TesType.name.asc(),
            TesType.id.asc(),
        )
        .all()
    )


_UNKNOWN_NAME_VARIANTS = (
    "не известно",
    "неизвестно",
    "не указано",
    "не указан",
)


@lru_cache(maxsize=1)
def get_unknown_tes_type_id():
    """
    Возвращает ID типа ТЭС со значением «не известно» (или его синонимом)
    для текущей версии БД. Если такого значения нет, используется запись с id=0
    или первый доступный элемент.
    """
    query = filter_by_db_version(TesType.query, TesType)

    normalized_variants = tuple(
        variant.strip().lower() for variant in _UNKNOWN_NAME_VARIANTS if variant
    )

    if normalized_variants:
        filters = [func.lower(TesType.name) == variant for variant in normalized_variants]
        unknown = query.filter(or_(*filters)).first()
        if unknown:
            return unknown.id

    zero_candidate = query.filter(TesType.id == 0).first()
    if zero_candidate:
        return zero_candidate.id

    fallback = query.order_by(TesType.id.asc()).first()
    return fallback.id if fallback else 0