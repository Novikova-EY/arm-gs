# -*- coding: utf-8 -*-
"""
BusinessUnit model (Бизнес единица).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class BusinessUnit(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = "gs_business_units"
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Порядок отображения
    display_order = db.Column(db.Integer, nullable=True)

    name = db.Column(db.String(80), nullable=False, index=True)
    name_full = db.Column(db.String(80), nullable=True)
    name_abr = db.Column(db.String(80), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    __table_args__ = (
        db.UniqueConstraint(
            "database_version_id", "name", name="uq_refdata_business_units_ver_name"
        ),
        db.UniqueConstraint(
            "database_version_id",
            "name_full",
            name="uq_refdata_business_units_ver_name_full",
        ),
        db.UniqueConstraint(
            "database_version_id",
            "name_abr",
            name="uq_refdata_business_units_ver_name_abr",
        ),
        {"schema": SCHEMA_REFDATA},
    )

    def __repr__(self) -> str:
        return f"<BusinessUnit id={self.id} name={self.name!r}>"
