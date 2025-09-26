from functools import lru_cache


# Модели
from app.generation.models.station.station_group_model import StationGroup


@lru_cache(maxsize=1)
def get_station_group_list_full():
    """Получает полный список групп электростанций'."""
    return (
        StationGroup.query
        .order_by(
            (StationGroup.id != 0),
            StationGroup.name.asc()
        )
        .all()
    )