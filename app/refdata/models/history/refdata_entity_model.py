# -*- coding: utf-8 -*-
"""
Реестр исторического слоя справочников.
Хранит стабильные UUID и годовые снимки данных.
"""
import uuid
from sqlalchemy import event
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin


def _refdata_entity_key(entity_type: str, entity_id: int) -> str:
    """Стабильный ключ для детерминированного UUID справочника."""
    return f"refdata|{entity_type}|{entity_id}"


class RefdataEntity(db.Model, AuditMixin):
    __tablename__ = "gs_sys_refdata_entities"
    __table_args__ = (
        db.UniqueConstraint(
            "entity_type",
            "entity_id",
            "database_version_id",
            name="uq_refdata_entities_type_id_version",
        ),
        db.UniqueConstraint("ref_uuid", name="uq_refdata_entities_uuid"),
        {"schema": SCHEMA_REFDATA},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    entity_type = db.Column(db.String(80), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=False, index=True)

    # Связь с версией набора данных (сценарий/снимок).
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Стабильный UUID сущности.
    ref_uuid = db.Column(db.String(36), nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    history_entries = db.relationship(
        "RefdataEntityYear",
        back_populates="refdata_entity",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return (
            f"<RefdataEntity id={self.id} type={self.entity_type!r} "
            f"entity_id={self.entity_id} uuid={self.ref_uuid!r}>"
        )


class RefdataEntityYear(db.Model, AuditMixin):
    __tablename__ = "gs_sys_refdata_entity_years"
    __table_args__ = (
        db.UniqueConstraint(
            "refdata_entity_id",
            "year",
            "database_version_id",
            name="uq_refdata_entity_years_entity_year_version",
        ),
        {"schema": SCHEMA_REFDATA},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    refdata_entity_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_refdata_entities.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year = db.Column(db.Integer, nullable=False, index=True)

    # Связь с версией набора данных (сценарий/снимок).
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Годовой снимок данных (структура зависит от типа сущности).
    payload = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    refdata_entity = db.relationship("RefdataEntity", back_populates="history_entries")

    def __repr__(self) -> str:
        return (
            f"<RefdataEntityYear id={self.id} refdata_entity_id={self.refdata_entity_id} "
            f"year={self.year}>"
        )


@event.listens_for(RefdataEntity, "before_insert")
def _generate_ref_uuid_before_insert(mapper, connection, target):
    """Генерирует детерминированный UUID перед вставкой."""
    if target.ref_uuid:
        return
    key = _refdata_entity_key(target.entity_type, target.entity_id)
    target.ref_uuid = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
