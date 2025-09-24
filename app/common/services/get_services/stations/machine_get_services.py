"""Get-модуль: Агрегат электростанции."""

from app.extensions import db
from sqlalchemy.orm import joinedload

# Модели
from app.generation.models.machine.machine_model import Machine


def get_machine_by_id(machine_id):
    machine = (
        db.session.query(Machine)
        .filter_by(id=machine_id)
        .first()
    )
    
    return machine