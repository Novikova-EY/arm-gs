from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.condition_type_model import ConditionType


def get_condition_type_list_full():
    """Получает полный список типов состояний."""
    return (
        ConditionType.query
        .order_by(ConditionType.name.asc())
        .all()
    )