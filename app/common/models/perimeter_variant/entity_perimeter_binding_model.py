# -*- coding: utf-8 -*-
"""Привязка варианта периметра к сущности справочника (ОЭС, СЗ, …)."""
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin
from config import SCHEMA_REFDATA


class EntityPerimeterBinding(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = "gs_sys_entity_perimeter_bindings"
    __table_args__ = (
        db.UniqueConstraint(
            "entity_kind",
            "entity_name",
            "id_perimeter_variant",
            name="uq_gs_sys_entity_perimeter_bindings_entity_variant",
        ),
        {"schema": SCHEMA_REFDATA},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_kind = db.Column(db.String(64), nullable=False, index=True)
    entity_name = db.Column(db.String(255), nullable=False, index=True)
    label_prefix = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, server_default=db.text("0"))

    id_perimeter_variant = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_perimeter_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    perimeter_variant = db.relationship("PerimeterVariant", back_populates="bindings")

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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
        return (
            f"<EntityPerimeterBinding id={self.id} "
            f"{self.entity_kind!r} {self.entity_name!r} variant_id={self.id_perimeter_variant}>"
        )
