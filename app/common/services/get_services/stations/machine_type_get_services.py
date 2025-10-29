from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.machine.machine_type_model import MachineType

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_machine_type_list_full():
    """Получает полный список типов агрегатов электростанций."""
    current_version = get_current_version()
    query = MachineType.query
    
    if current_version:
        query = query.filter(MachineType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (MachineType.id != 0),
            MachineType.name.asc()
        )
        .all()
    )