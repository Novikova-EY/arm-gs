# -*- coding: utf-8 -*-
"""Накопленные Накопленные инвестиции в основной капитал по ВЭД для федерального округа (долгосрочный прогноз)."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ECONOMICS, SCHEMA_REFDATA


class FederalDistrictAccumFixedCapitalParameter(db.Model, AuditMixin):
    __tablename__ = "gs_ekp_federal_district_accum_fixed_capital_params"
    __table_args__ = (
        db.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_ekp_fd_afci_year_ver",
        ),
        {"schema": SCHEMA_ECONOMICS},
    )

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

    id_economic_activity_type = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_economic_activity_types.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    economic_activity_type = db.relationship(
        "EconomicActivityType",
        foreign_keys=[id_economic_activity_type],
    )

    year_number = db.Column(db.Integer, nullable=True, index=True)
    year = db.relationship(
        "Year",
        back_populates="fd_economic_activity_accum_fixed_capital_parameters",
        lazy="noload",
    )
    accumulated_fixed_capital_investment_mln_rub = db.Column(Numeric(25, 16), nullable=True)
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
            f"<FederalDistrictAccumFixedCapitalParameter id={self.id} "
            f"fd={self.id_federal_district} ved={self.id_economic_activity_type} "
            f"year={self.year_number}>"
        )
