# -*- coding: utf-8 -*-
"""
PGUTesMachineType model (Тип агрегата ПГУ: ГТ/ПТ).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class PGUTesMachineType(db.Model):
    __tablename__ = 'pgu_tes_machine_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    pgu_machines = db.relationship(
        'PGUMachine',
        back_populates='pgu_tes_machine_type',
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<PGUTesMachineType id={self.id} name={self.name!r}>"
