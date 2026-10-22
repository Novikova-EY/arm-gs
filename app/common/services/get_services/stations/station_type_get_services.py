# Модели
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType

# Сервисы
from app.common.services.database_version_services import get_current_version


def get_station_type_list_full():
    """Полный список типов электростанций текущей версии БД.

    Не кэшируем результат: список ORM-объектов нельзя безопасно хранить в lru_cache –
    после завершения запроса сессия закрывается, и повторное обращение к атрибутам
    даёт DetachedInstanceError.
    """
    current_version = get_current_version()
    query = StationType.query
    
    if current_version:
        query = query.filter(StationType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            StationType.display_order.asc().nullslast(),
            StationType.name.asc(),
            StationType.id.asc(),
        )
        .all()
    )


def get_station_type_list():
    """Список типов электростанций (кроме «не указано»). Без LRU-кэша: иначе ORM-объекты
    после закрытия сессии отвязываются (DetachedInstanceError).
    """
    current_version = get_current_version()
    query = StationType.query
    
    if current_version:
        query = query.filter(StationType.database_version_id == current_version)
    
    return (
        query
        .filter(StationType.id.isnot(None), StationType.id > 0)
        .order_by(
            StationType.display_order.asc().nullslast(),
            StationType.name.asc(),
            StationType.id.asc(),
        )
        .all()
    )
