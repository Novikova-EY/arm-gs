# -*- coding: utf-8 -*-
"""
EnergySystemType (Тип энергосистемы).
- Двусторонняя связь с UnionEnergySystem.
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin


class EnergySystemType(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = "gs_energy_system_types"
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # двусторонняя связь c UnionEnergySystem
    union_energy_systems = db.relationship(
        "UnionEnergySystem",
        back_populates="energy_system_type",
        foreign_keys="UnionEnergySystem.id_energy_system_type"
    )

    def __repr__(self) -> str:
        return f"<EnergySystemType id={self.id} name={self.name!r}>"