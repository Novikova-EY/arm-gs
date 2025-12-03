# -*- coding: utf-8 -*-
"""
EquipmentGroup model (Группа оборудования).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from sqlalchemy.dialects.postgresql import ENUM as PGEnum
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin


class EquipmentGroup(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_equipment_groups'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    # FK -> TechnologyAvailability
    id_technology_availability = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_technology_availabilities.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    technology_availability = db.relationship('TechnologyAvailability', back_populates='equipment_groups')

    # FK -> TechnologyType
    id_technology_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_technology_types.id', ondelete='SET NULL'),
        nullable=True,
        index=True,
    )
    technology_type = db.relationship('TechnologyType', back_populates='equipment_groups')

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    machines = db.relationship(
        'Machine',
        back_populates='equipment_group',
        primaryjoin="EquipmentGroup.id == Machine.id_equipment_group"
    )

    def __repr__(self) -> str:
        return f"<EquipmentGroup id={self.id} name={self.name!r}>"
