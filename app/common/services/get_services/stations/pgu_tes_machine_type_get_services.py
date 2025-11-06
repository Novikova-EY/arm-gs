from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import PGUTesMachineType

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_pgu_tes_machine_type_list_full():
    """Получает полный список типов агрегатов ПГУ."""
    current_version = get_current_version()
    query = PGUTesMachineType.query
    
    if current_version:
        query = query.filter(PGUTesMachineType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (PGUTesMachineType.id != 0),
            PGUTesMachineType.name.asc()
        )
        .all()
    )


@lru_cache(maxsize=1)
def get_pgu_tes_machine_type_list():
    """Получает список типов агрегатов ПГУ для использования в кэше."""
    return get_pgu_tes_machine_type_list_full()