from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType


@lru_cache(maxsize=1)
def get_tes_machine_type_list_full():
    """Получает полный список типов агрегатов ТЭС."""
    return (
        TesMachineType.query
        .order_by(
            (TesMachineType.id != 0),
            TesMachineType.name.asc()
        )
        .all()
    )