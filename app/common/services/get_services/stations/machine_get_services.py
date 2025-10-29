"""Get-модуль: Агрегат электростанции."""

from app.extensions import db
from sqlalchemy.orm import joinedload, selectinload

# Модели
from app.generation.models.machine.machine_model import Machine

# Функции для работы с версионированием БД
from app.common.services.database_version_filter import filter_by_db_version
from app.common.services.database_version_services import get_current_version


def get_machine_by_id(machine_id):
    """
    Загружает агрегат с предзагрузкой всех связанных данных.
    Оптимизировано для избежания N+1 запросов.
    """
    query = (
        db.session.query(Machine)
        .options(
            # Предзагружаем все связанные данные
            selectinload(Machine.machine_powers),
            selectinload(Machine.machine_fuels),
            selectinload(Machine.machine_tes_types),
            joinedload(Machine.gen_company),
            joinedload(Machine.machine_type),
            joinedload(Machine.tes_machine_type),
            joinedload(Machine.condition_type),
            joinedload(Machine.equipment_group),
        )
        .filter_by(id=machine_id)
    )
    # Фильтрация по версии БД
    query = filter_by_db_version(query, Machine)
    machine = query.first()
    
    return machine