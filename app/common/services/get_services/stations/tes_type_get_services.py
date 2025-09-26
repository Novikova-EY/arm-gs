from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType


@lru_cache(maxsize=1)
def get_tes_type_list_full():
    """Получает полный список типов ТЭС."""
    return (
        TesType.query
        .order_by(
            (TesType.id != 0),
            TesType.name.asc()
        )
        .all()
    )