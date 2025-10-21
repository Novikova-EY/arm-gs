"""Get-модуль: Электростанция."""

from app.extensions import db
from sqlalchemy.orm import joinedload, selectinload

# Модели
from app.generation.models.station.station_model import Station
from app.generation.models.machine.machine_model import Machine

def get_station_by_id(station_id):
    return (
        db.session.query(Station)
        .options(
            joinedload(Station.station_type),
            selectinload(Station.machines).joinedload(Machine.gen_company)
        )
        .filter_by(id=station_id)
        .first()
    )