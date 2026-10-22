# -*- coding: utf-8 -*-
"""КПД очистки и коэффициенты подавления (лист «Коэфф.»)."""
from sqlalchemy import ForeignKeyConstraint, Numeric, UniqueConstraint
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY, SCHEMA_REFDATA


class OperatingTesCoefficient(db.Model, AuditMixin):
    """КПД / коэффициент подавления по территории, году и виду."""

    __tablename__ = "gs_eco_operating_tes_coefficients"
    __table_args__ = (
        UniqueConstraint(
            "territory_slug",
            "affiliation",
            "year_number",
            "kind",
            "database_version_id",
            name="uq_eco_ot_coeff_slice_year_kind_ver",
        ),
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_ot_coeff_year_ver",
        ),
        {"schema": SCHEMA_ECOLOGY},
    )

    # Уникальный идентификатор записи
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Идентификатор территории (vsego, minen, severo-zapad, …)
    territory_slug = db.Column(db.String(80), nullable=False, index=True)

    affiliation = db.Column(
        db.String(20), nullable=False, default="all", server_default="all"
    )

    # Год: Year.number + database_version_id (composite FK)
    year_number = db.Column(db.Integer, nullable=False, index=True)
    year = db.relationship(
        "Year",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==OperatingTesCoefficient.year_number, "
            "Year.database_version_id==OperatingTesCoefficient.database_version_id)"
        ),
        foreign_keys="[OperatingTesCoefficient.year_number, OperatingTesCoefficient.database_version_id]",
        viewonly=True,
    )

    # Вид: ash_eta (КПД золоулавливания), sulfur_eta (КПД сероочистки), nox_n / co_k / pg_k (коэф. подавления)
    kind = db.Column(db.String(40), nullable=False, index=True)

    # Значение КПД или коэффициента подавления, д.ед. (0–1)
    value = db.Column(Numeric(36, 16), nullable=True)
    
    # Примечание
    note = db.Column(db.Text, nullable=True)

    # Дата и время создания записи
    created_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # Дата и время последнего изменения записи
    updated_at = db.Column(
        db.DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    # Версия базы данных, FK -> gs_sys.gs_database_versions
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<OperatingTesCoefficient id={self.id} "
            f"terr={self.territory_slug} year={self.year_number} kind={self.kind}>"
        )
