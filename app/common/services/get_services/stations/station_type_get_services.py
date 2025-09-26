from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.station.station_type_model import StationType


@lru_cache(maxsize=1)
def get_station_type_list_full():
    """Получает полный список типов электростанций'."""
    return (
        StationType.query
        .order_by(
            (StationType.id != 0),
            StationType.name.asc()
        )
        .all()
    )