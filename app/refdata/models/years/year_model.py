# -*- coding: utf-8 -*-
"""
Year model (Год).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin


class Year(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_years'
    __table_args__ = (
        db.UniqueConstraint(
            "number",
            "database_version_id",
            name="uq_gs_years_number_version",
        ),
        {
            "schema": SCHEMA_REFDATA,
            "extend_existing": True,
        },
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    number = db.Column(db.Integer, nullable=False, index=True)

    # FK -> YearFeature
    id_year_feature = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_year_features.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    year_feature = db.relationship('YearFeature', back_populates='years')

    # FK -> DatabaseVersion
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Годы теперь версионируются через database_version_id

    # Relations retained as-is
    station_powers = db.relationship('StationPower', back_populates='year')
    machine_powers = db.relationship('MachinePower', back_populates='year')
    machine_fuels = db.relationship('MachineFuel', back_populates='year')
    machine_tes_types = db.relationship('MachineTesType', back_populates='year')
    machine_names = db.relationship('MachineName', back_populates='year')

    def __repr__(self) -> str:
        return f"<Year id={self.id} number={self.number}>"
