from functools import lru_cache

# Модели
from app.refdata.models.refdata_for_stations.machine.pgu_tes_machine_type_model import PGUTesMachineType


@lru_cache(maxsize=1)
def get_pgu_tes_machine_type_list_full():
    """Получает полный список типов агрегатов ТЭС."""
    return (
        PGUTesMachineType.query
        .order_by(PGUTesMachineType.name.asc())
        .all()
    )