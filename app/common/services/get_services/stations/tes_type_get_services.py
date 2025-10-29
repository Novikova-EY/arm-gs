from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.machine.tes_type_model import TesType

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_tes_type_list_full():
    """Получает полный список типов ТЭС."""
    current_version = get_current_version()
    query = TesType.query
    
    if current_version:
        query = query.filter(TesType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (TesType.id != 0),
            TesType.name.asc()
        )
        .all()
    )