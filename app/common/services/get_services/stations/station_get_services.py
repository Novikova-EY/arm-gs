"""Get-модуль: Электростанция."""

from app.extensions import db
from sqlalchemy.orm import joinedload

# Модели
from app.generation.models.station.station_model import Station

def get_station_by_id(station_id):
    return (
        db.session.query(Station)
        .options(joinedload(Station.machines))
        .filter_by(id=station_id)
        .first()
    )