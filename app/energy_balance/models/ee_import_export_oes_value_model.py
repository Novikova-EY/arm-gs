# -*- coding: utf-8 -*-
"""Годовые агрегаты импорта/экспорта ЭЭ по ОЭС и зарубежным странам."""

from sqlalchemy import Index, Numeric, text
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE, SCHEMA_REFDATA


class EeImportExportOesValue(db.Model, AuditMixin):
    __tablename__ = "gs_bem_ee_import_export_oes_values"
    __table_args__ = (
        Index("ix_ee_import_export_oes_year", "year_number"),
        Index("ix_ee_import_export_oes_ues", "id_union_energy_system"),
        Index("ix_ee_import_export_oes_country", "id_foreign_border_country"),
        Index(
            "uq_ee_import_export_oes_country_year_ver",
            "id_union_energy_system",
            "id_foreign_border_country",
            "year_number",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        db.ForeignKeyConstraint(
            ["id_union_energy_system"],
            [f"{SCHEMA_REFDATA}.gs_sys_union_energy_systems.id"],
            ondelete="RESTRICT",
            name="fk_ee_import_export_oes_ues",
        ),
        db.ForeignKeyConstraint(
            ["id_foreign_border_country"],
            [f"{SCHEMA_REFDATA}.gs_sys_foreign_border_countries.id"],
            ondelete="RESTRICT",
            name="fk_ee_import_export_oes_country",
        ),
        db.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_ee_import_export_oes_year_ver",
        ),
        db.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
            name="fk_ee_import_export_oes_db_version",
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_union_energy_system = db.Column(db.Integer, nullable=False)
    id_foreign_border_country = db.Column(db.Integer, nullable=False)
    year_number = db.Column(db.Integer, nullable=False)
    transfer_value = db.Column(Numeric(25, 16), nullable=True)
    database_version_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    union_energy_system = db.relationship("UnionEnergySystem")
    foreign_border_country = db.relationship("ForeignBorderCountry")
