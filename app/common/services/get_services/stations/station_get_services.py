"""Get-модуль: Электростанция."""

from app.extensions import db
from sqlalchemy.orm import joinedload, selectinload

# Модели
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine
from app.generation.models.machine.machine_power_model import MachinePower
from app.generation.models.machine.machine_fuel_model import MachineFuel
from app.refdata.models.years.year_model import Year

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
            selectinload(Station.machines).selectinload(Machine.machine_powers),
            selectinload(Station.machines).selectinload(Machine.machine_fuels),
            selectinload(Station.machines).selectinload(Machine.machine_tes_types),
        )
        .filter_by(id=station_id)
    )
    # Фильтрация по версии БД
    query = filter_by_db_version(query, Station)
    station = query.first()
    
    # Загружаем годы и устанавливаем их вручную для всех машин
    if station:
        year_numbers = set()
        for machine in station.machines:
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
            for machine in station.machines:
                for mp in machine.machine_powers:
                    if mp.year_number and mp.year_number in year_dict:
                        mp.year = year_dict[mp.year_number]
                for mf in machine.machine_fuels:
                    if mf.year_number and mf.year_number in year_dict:
                        mf.year = year_dict[mf.year_number]
                for mt in machine.machine_tes_types:
                    if mt.year_number and mt.year_number in year_dict:
                        mt.year = year_dict[mt.year_number]
    
    return station