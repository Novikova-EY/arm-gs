# -*- coding: utf-8 -*-
"""
EquipmentGroup model (Группа оборудования).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA

class EquipmentGroup(db.Model):
    __tablename__ = 'equipment_groups'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    machines = db.relationship(
        'Machine',
        back_populates='equipment_group',
        primaryjoin="EquipmentGroup.id == Machine.id_equipment_group"
    )

    pgu_machines = db.relationship(
        'PGUMachine',
        back_populates='equipment_group_pgu',
        primaryjoin="EquipmentGroup.id == PGUMachine.id_equipment_group_pgu"
    )

    def __repr__(self) -> str:
        return f"<EquipmentGroup id={self.id} name={self.name!r}>"
