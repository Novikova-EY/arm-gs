# -*- coding: utf-8 -*-
"""Справочник вариантов периметра (с/без НТ, Калининград и т.д.)."""
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin
from config import SCHEMA_REFDATA


class PerimeterVariant(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = "gs_sys_perimeter_variants"
    __table_args__ = (
        db.UniqueConstraint(
            "code",
            name="uq_gs_sys_perimeter_variants_code",
        ),
        {"schema": SCHEMA_REFDATA},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    code = db.Column(db.String(64), nullable=False, index=True)
    label_suffix = db.Column(db.String(255), nullable=False)
    effective_from_year = db.Column(db.Integer, nullable=True)
    effective_to_year = db.Column(db.Integer, nullable=True)
    is_territorial_base = db.Column(db.Boolean, nullable=False, server_default=db.text("false"))
    display_order = db.Column(db.Integer, nullable=True)
    note = db.Column(db.Text, nullable=True)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    bindings = db.relationship(
        "EntityPerimeterBinding",
        back_populates="perimeter_variant",
        cascade="all, delete-orphan",
    )

    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<PerimeterVariant id={self.id} code={self.code!r}>"
