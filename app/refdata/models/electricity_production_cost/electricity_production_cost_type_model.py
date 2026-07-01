# -*- coding: utf-8 -*-
"""
ElectricityProductionCostType model
(Типы затрат на производство ЭЭ и ТЭ).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class ElectricityProductionCostType(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_sys_electricity_production_cost_types'
    __table_args__ = (
        db.UniqueConstraint(
            'database_version_id',
            'name',
            name='uq_gs_sys_electricity_production_cost_types_ver_name',
        ),
        {"schema": SCHEMA_REFDATA},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cost_code = db.Column(db.Integer, nullable=True)
    name = db.Column(db.String(255), nullable=True, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    def __repr__(self) -> str:
        return f"<ElectricityProductionCostType id={self.id} name={self.name!r}>"
