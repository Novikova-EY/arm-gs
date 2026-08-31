# -*- coding: utf-8 -*-
"""Максимумы потребления мощности ОЗП (осенне-зимний период) — значения по периодам ОЗП."""
from sqlalchemy import Numeric
from sqlalchemy.sql import func

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_POWER_DEMAND, SCHEMA_REFDATA


class OzpMaxPowerParameter(db.Model, AuditMixin):
    """Одна строка — один период ОЗП (например 2019–2020, ozp_end_year=2020)."""

    __tablename__ = "gs_pd_ozp_max_power_params"
    __table_args__ = ({"schema": SCHEMA_POWER_DEMAND},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Конец периода ОЗП: 2020 означает ОЗП 2019–2020 гг.
    ozp_end_year = db.Column(db.Integer, nullable=False, index=True)

    # Максимум потребления мощности ОЗП, МВт
    max_power_mw = db.Column(Numeric(25, 3), nullable=True)

    # Прирост к прошлому ОЗП, %
    growth_pct = db.Column(Numeric(12, 6), nullable=True)

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
            f"<OzpMaxPowerParameter id={self.id} ozp_end_year={self.ozp_end_year} "
            f"version={self.database_version_id}>"
        )
