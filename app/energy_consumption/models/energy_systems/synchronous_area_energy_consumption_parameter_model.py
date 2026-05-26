# -*- coding: utf-8 -*-
"""Параметры потребления для синхронной зоны."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from app.common.models.perimeter_variant_mixin import PerimeterVariantColumnMixin
from config import SCHEMA_ENERGY_CONSUMPTION, SCHEMA_REFDATA


class SynchronousAreaEnergyConsumptionParameter(db.Model, AuditMixin, PerimeterVariantColumnMixin):
    __tablename__ = "gs_ec_synchronous_area_consumption_params"
    __table_args__ = {"schema": SCHEMA_ENERGY_CONSUMPTION}


    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_synchronous_area = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_synchronous_areas.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    synchronous_area = db.relationship(
        "SynchronousArea",
        foreign_keys=[id_synchronous_area],
    )


    year_number = db.Column(db.Integer, nullable=True, index=True)

    energy_consumption_mln_kvt_ch = db.Column(Numeric(25, 16), nullable=True)

    energy_consumption_sipr_mln_kvt_ch = db.Column(Numeric(25, 16), nullable=True)

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
            f"<SynchronousAreaEnergyConsumptionParameter(ec) id={self.id} "
            f"synchronous_area_id={self.id_synchronous_area} "
            f"year={self.year_number}>"
        )
