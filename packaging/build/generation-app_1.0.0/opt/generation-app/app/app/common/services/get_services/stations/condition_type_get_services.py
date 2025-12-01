from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType

# Сервисы
from app.common.services.database_version_services import get_current_version


@lru_cache(maxsize=1)
def get_condition_type_list_full():
    """Получает полный список типов состояний."""
    current_version = get_current_version()
    query = ConditionType.query
    
    if current_version:
        query = query.filter(ConditionType.database_version_id == current_version)
    
    return (
        query
        .order_by(
            (ConditionType.id != 0),
            ConditionType.name.asc()
        )
        .all()
    )