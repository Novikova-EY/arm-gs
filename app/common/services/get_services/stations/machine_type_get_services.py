from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType


@lru_cache(maxsize=1)
def get_machine_type_list_full():
    """Получает полный список типов агрегатов электростанций'."""
    return (
        MachineType.query
        .order_by(
            (MachineType.id != 0),
            MachineType.name.asc()
        )
        .all()
    )