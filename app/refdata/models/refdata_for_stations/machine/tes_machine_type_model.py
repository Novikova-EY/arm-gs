# -*- coding: utf-8 -*-
"""
TesMachineType model (Тип агрегата ТЭС).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class TesMachineType(db.Model):
    __tablename__ = 'tes_machine_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    machines = db.relationship(
        'Machine',
        back_populates='tes_machine_type',
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TesMachineType id={self.id} name={self.name!r}>"
