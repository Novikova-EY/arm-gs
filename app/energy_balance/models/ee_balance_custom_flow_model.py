# -*- coding: utf-8 -*-
"""Пользовательские строки перетоков на страницах баланса электрической энергии."""
from sqlalchemy.sql import func
from sqlalchemy import Index, Numeric, text

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE

CUSTOM_FLOW_IN = "flow_in"
CUSTOM_FLOW_OUT = "flow_out"
CUSTOM_FLOW_DIRECTIONS = (CUSTOM_FLOW_IN, CUSTOM_FLOW_OUT)


class EeBalanceCustomFlowRow(db.Model, AuditMixin):
    __tablename__ = "gs_bem_ee_balance_custom_flow_rows"
    __table_args__ = (
        Index("ix_gs_bem_eb_cfr_sheet", "sheet_slug"),
        Index("ix_gs_bem_eb_cfr_direction", "direction"),
        Index("ix_gs_bem_eb_cfr_dbver", "database_version_id"),
        Index("ix_gs_bem_eb_cfr_parent_key", "parent_key"),
        Index(
            "ix_gs_bem_eb_cfr_sheet_dir_ord",
            "sheet_slug",
            "direction",
            "sort_order",
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sheet_slug = db.Column(db.String(128), nullable=False, index=True)
    direction = db.Column(db.String(16), nullable=False)
    parent_key = db.Column(db.String(128), nullable=True, index=True)
    label = db.Column(db.String(500), nullable=False, default="", server_default="")
    sort_order = db.Column(db.Integer, nullable=False, default=0, server_default="0")

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    database_version_id = db.Column(db.Integer, nullable=True, index=True)

    values = db.relationship(
        "EeBalanceCustomFlowValue",
        back_populates="row",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class EeBalanceCustomFlowValue(db.Model, AuditMixin):
    __tablename__ = "gs_bem_ee_balance_custom_flow_values"
    __table_args__ = (
        Index("ix_gs_bem_eb_cfv_row", "id_row"),
        Index("ix_gs_bem_eb_cfv_year", "year_number"),
        Index("ix_gs_bem_eb_cfv_dbver", "database_version_id"),
        Index(
            "uq_gs_bem_eb_cfv_row_year_ver",
            "id_row",
            "year_number",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    id_row = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_ENERGY_BALANCE}.gs_bem_ee_balance_custom_flow_rows.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )
    year_number = db.Column(db.Integer, nullable=False, index=True)
    value_mln_kvtch = db.Column(Numeric(25, 16), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    database_version_id = db.Column(db.Integer, nullable=True, index=True)

    row = db.relationship("EeBalanceCustomFlowRow", back_populates="values")
