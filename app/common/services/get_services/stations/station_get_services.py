"""Get-модуль: Электростанция."""

from app.extensions import db
from sqlalchemy.orm import joinedload, selectinload

# Модели
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine

# Функции для работы с версионированием БД
from app.common.services.database_version_filter import filter_by_db_version
from app.common.services.database_version_services import get_current_version

def get_station_by_id(station_id):
    """
    Загружает станцию с предзагрузкой всех связанных данных.
    Оптимизировано для избежания N+1 запросов.
    """
    query = (
        db.session.query(Station)
        .options(
            joinedload(Station.station_type),
            selectinload(Station.machines).joinedload(Machine.gen_company),
            # Предзагружаем мощности, топливо и типы ТЭС для всех агрегатов
            selectinload(Station.machines).selectinload(Machine.machine_powers),
            selectinload(Station.machines).selectinload(Machine.machine_fuels),
            selectinload(Station.machines).selectinload(Machine.machine_tes_types),
        )
        .filter_by(id=station_id)
    )
    # Фильтрация по версии БД
    query = filter_by_db_version(query, Station)
    return query.first()