# -*- coding: utf-8 -*-
"""Годовые агрегаты приема/передачи электроэнергии между ОЭС."""

from sqlalchemy import Index, Numeric, text
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE, SCHEMA_REFDATA


class EeReceiveTransferOesValue(db.Model, AuditMixin):
    __tablename__ = "gs_bem_ee_receive_transfer_oes_values"
    __table_args__ = (
        Index("ix_ee_receive_transfer_oes_year", "year_number"),
        Index("ix_ee_receive_transfer_oes_source", "id_source_union_energy_system"),
        Index("ix_ee_receive_transfer_oes_target", "id_target_union_energy_system"),
        Index(
            "uq_ee_receive_transfer_oes_pair_year_ver",
            "id_source_union_energy_system",
            "id_target_union_energy_system",
            "year_number",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        db.ForeignKeyConstraint(
            ["id_source_union_energy_system"],
            [f"{SCHEMA_REFDATA}.gs_sys_union_energy_systems.id"],
            ondelete="RESTRICT",
            name="fk_ee_receive_transfer_oes_source",
        ),
        db.ForeignKeyConstraint(
            ["id_target_union_energy_system"],
            [f"{SCHEMA_REFDATA}.gs_sys_union_energy_systems.id"],
            ondelete="RESTRICT",
            name="fk_ee_receive_transfer_oes_target",
        ),
        db.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_ee_receive_transfer_oes_year_ver",
        ),
        db.ForeignKeyConstraint(
            ["database_version_id"],
            [f"{SCHEMA_REFDATA}.gs_database_versions.id"],
            ondelete="SET NULL",
            name="fk_ee_receive_transfer_oes_db_version",
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_source_union_energy_system = db.Column(db.Integer, nullable=False)
    id_target_union_energy_system = db.Column(db.Integer, nullable=False)
    year_number = db.Column(db.Integer, nullable=False)
    transfer_value = db.Column(Numeric(25, 16), nullable=True)
    database_version_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    source_union_energy_system = db.relationship(
        "UnionEnergySystem", foreign_keys=[id_source_union_energy_system]
    )
    target_union_energy_system = db.relationship(
        "UnionEnergySystem", foreign_keys=[id_target_union_energy_system]
    )
