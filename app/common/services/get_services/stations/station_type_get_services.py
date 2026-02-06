from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_station_type_list_full():
    """Получает полный список типов электростанций."""
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


@lru_cache(maxsize=1)
def get_station_type_list():
    """Получает список типов электростанций (кроме "не указано")."""
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