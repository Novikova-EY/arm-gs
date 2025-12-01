"""Get-модуль: Агрегат электростанции."""

from app.extensions import db
from sqlalchemy.orm import joinedload

# Модели
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.generation.models.machine.machine_tes_type_model import MachineTesType
from app.refdata.models.years.year_model import Year

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
    
    # Загружаем годы и устанавливаем их вручную
    if machine:
        year_numbers = set()
        for mp in machine.machine_powers:
            if mp.year_number:
                year_numbers.add(mp.year_number)
        for mf in machine.machine_fuels:
            if mf.year_number:
                year_numbers.add(mf.year_number)
        for mt in machine.machine_tes_types:
            if mt.year_number:
                year_numbers.add(mt.year_number)
        
        if year_numbers:
            years = Year.query.filter(Year.number.in_(year_numbers)).all()
            year_dict = {y.number: y for y in years}
            
            # Устанавливаем year вручную
            for mp in machine.machine_powers:
                if mp.year_number and mp.year_number in year_dict:
                    mp.year = year_dict[mp.year_number]
            for mf in machine.machine_fuels:
                if mf.year_number and mf.year_number in year_dict:
                    mf.year = year_dict[mf.year_number]
            for mt in machine.machine_tes_types:
                if mt.year_number and mt.year_number in year_dict:
                    mt.year = year_dict[mt.year_number]
    
    return machine