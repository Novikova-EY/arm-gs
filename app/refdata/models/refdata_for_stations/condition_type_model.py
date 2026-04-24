# -*- coding: utf-8 -*-
"""
ConditionType model (Тип состояния оборудования/станции).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class ConditionType(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_sys_condition_types'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

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
