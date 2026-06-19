# -*- coding: utf-8 -*-
"""Коэффициент k строк «Потери в сетях» и «С.н. электростанций» блока «Всего» (ФО)."""
from sqlalchemy import Numeric, String
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ENERGY_CONSUMPTION, SCHEMA_REFDATA


class FederalDistrictFdTotalConsumptionCoefficient(db.Model, AuditMixin):
    __tablename__ = "gs_ec_federal_district_fd_total_consumption_coefficients"
    __table_args__ = {"schema": SCHEMA_ENERGY_CONSUMPTION}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_federal_district = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_federal_districts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    federal_district = db.relationship(
        "FederalDistrict",
        foreign_keys=[id_federal_district],
    )

    row_kind = db.Column(String(length=32), nullable=False, index=True)

    coefficient_k = db.Column(Numeric(25, 16), nullable=True)
    note = db.Column(db.Text, nullable=True)

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
            f"<FederalDistrictFdTotalConsumptionCoefficient id={self.id} "
            f"fd={self.id_federal_district} row_kind={self.row_kind!r}>"
        )
