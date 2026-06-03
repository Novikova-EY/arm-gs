# -*- coding: utf-8 -*-
"""Значения перетока электроэнергии по годам (млн кВт·ч)."""
from sqlalchemy import Numeric, UniqueConstraint
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_REFDATA, SCHEMA_TERRITORIES


class EnergyUnitPowerTransferValue(db.Model, AuditMixin):
    __tablename__ = "gs_ter_energy_unit_power_transfer_values"
    __table_args__ = (
        UniqueConstraint(
            "id_energy_unit_power_transfer",
            "year_number",
            "database_version_id",
            name="uq_gs_ter_eu_pt_val_transfer_year_ver",
        ),
        {"schema": SCHEMA_TERRITORIES},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_energy_unit_power_transfer = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_TERRITORIES}.gs_ter_energy_unit_power_transfers.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    power_transfer = db.relationship(
        "EnergyUnitPowerTransfer",
        foreign_keys=[id_energy_unit_power_transfer],
        back_populates="year_values",
    )

    year_number = db.Column(db.Integer, nullable=False, index=True)

    transfer_mln_kvt_ch = db.Column(Numeric(25, 16), nullable=True)

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
            f"<EnergyUnitPowerTransferValue id={self.id} "
            f"transfer_id={self.id_energy_unit_power_transfer} "
            f"year={self.year_number}>"
        )
