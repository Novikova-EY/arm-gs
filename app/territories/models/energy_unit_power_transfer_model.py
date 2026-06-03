# -*- coding: utf-8 -*-
"""Переток мощности энергоузла (субъект РФ, направление)."""
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_REFDATA, SCHEMA_TERRITORIES


class EnergyUnitPowerTransfer(db.Model, AuditMixin):
    __tablename__ = "gs_ter_energy_unit_power_transfers"
    __table_args__ = {"schema": SCHEMA_TERRITORIES}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_energy_unit = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_energy_units.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    energy_unit = db.relationship(
        "EnergyUnit",
        foreign_keys=[id_energy_unit],
    )

    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_districts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    regional_district = db.relationship(
        "RegionalDistrict",
        foreign_keys=[id_regional_district],
    )

    direction = db.Column(db.Text, nullable=True)

    year_values = db.relationship(
        "EnergyUnitPowerTransferValue",
        back_populates="power_transfer",
        cascade="all, delete-orphan",
        lazy="selectin",
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
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<EnergyUnitPowerTransfer id={self.id} "
            f"energy_unit_id={self.id_energy_unit} "
            f"regional_district_id={self.id_regional_district} "
            f"direction={self.direction!r}>"
        )
