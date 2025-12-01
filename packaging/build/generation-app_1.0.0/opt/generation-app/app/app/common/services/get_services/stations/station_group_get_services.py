from functools import lru_cache

# Модели
from app.generation.models.station.station_group_model import StationGroup

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_station_group_list_full():
    """Получает полный список групп электростанций."""
    current_version = get_current_version()
    query = StationGroup.query
    
    if current_version:
        query = query.filter(StationGroup.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (StationGroup.id != 0),
            StationGroup.name.asc()
        )
        .all()
    )