from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.machine.tes_machine_type_model import TesMachineType

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_tes_machine_type_list_full():
    """Получает полный список типов агрегатов ТЭС."""
    current_version = get_current_version()
    query = TesMachineType.query
    
    if current_version:
        query = query.filter(TesMachineType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            TesMachineType.display_order.asc().nullslast(),
            TesMachineType.name.asc(),
            TesMachineType.id.asc(),
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_tes_machine_type_list():
    """Получает список типов агрегатов ТЭС для использования в кэше."""
    return get_tes_machine_type_list_full()