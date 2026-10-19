# -*- coding: utf-8 -*-
"""Нормативы удельных выбросов расчёта по новым ТЭС (кг/т у.т., т/т у.т.)."""
from sqlalchemy import ForeignKeyConstraint, Numeric, UniqueConstraint
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY, SCHEMA_REFDATA


class NewTesNorm(db.Model, AuditMixin):
    """Удельный выброс по виду топлива, классу мощности и году."""

    __tablename__ = "gs_eco_new_tes_norms"
    __table_args__ = (
        UniqueConstraint(
            "fuel_key",
            "capacity_class",
            "year_number",
            "database_version_id",
            name="uq_eco_nt_norm_fuel_class_year_ver",
        ),
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_nt_norm_year_ver",
        ),
        {"schema": SCHEMA_ECOLOGY},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Ключ вида топлива (как в расчёте по действующим ТЭС)
    fuel_key = db.Column(db.String(80), nullable=False, index=True)

    # le100 — агрегаты до 100 МВт включительно; gt100 — более 100 МВт
    capacity_class = db.Column(db.String(16), nullable=False, index=True)

    year_number = db.Column(db.Integer, nullable=False, index=True)
    year = db.relationship(
        "Year",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==NewTesNorm.year_number, "
            "Year.database_version_id==NewTesNorm.database_version_id)"
        ),
        foreign_keys="[NewTesNorm.year_number, NewTesNorm.database_version_id]",
        viewonly=True,
    )

    # Зола, кг/т у.т.
    ash = db.Column(Numeric(36, 16), nullable=True)
    # Сера (SO2), кг/т у.т.
    so2 = db.Column(Numeric(36, 16), nullable=True)
    # Азот (NOx), кг/т у.т.
    nox = db.Column(Numeric(36, 16), nullable=True)
    # Монооксид углерода, кг/т у.т.
    co = db.Column(Numeric(36, 16), nullable=True)
    # Парниковые газы (CO2), т/т у.т.
    pg = db.Column(Numeric(36, 16), nullable=True)

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
            f"<NewTesNorm id={self.id} fuel={self.fuel_key} "
            f"class={self.capacity_class} year={self.year_number}>"
        )
