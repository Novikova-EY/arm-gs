# -*- coding: utf-8 -*-
"""
YearFeature model (Признак года).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin


class YearFeature(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_year_features'
    __table_args__ = {
        "schema": SCHEMA_REFDATA,
        "extend_existing": True
    }

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(80), nullable=False, index=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    years = db.relationship('Year', back_populates='year_feature')

    def __repr__(self) -> str:
        return f"<YearFeature id={self.id} name={self.name!r}>"
