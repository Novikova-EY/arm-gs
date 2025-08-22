# -*- coding: utf-8 -*-
"""
ConditionType model (Тип состояния оборудования/станции).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class ConditionType(db.Model):
    __tablename__ = 'condition_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    stations = db.relationship(
        'Station',
        back_populates='condition_type',
        primaryjoin="ConditionType.id == Station.id_condition_type"
    )

    machines = db.relationship(
        'Machine',
        back_populates='condition_type',
        primaryjoin="ConditionType.id == Machine.id_condition_type"
    )

    pgu_machines = db.relationship(
        'PGUMachine',
        back_populates='condition_type',
        primaryjoin="ConditionType.id == PGUMachine.id_condition_type"
    )

    def __repr__(self) -> str:
        return f"<ConditionType id={self.id} name={self.name!r}>"
