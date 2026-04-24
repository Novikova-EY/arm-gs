# -*- coding: utf-8 -*-
"""
Коэффициенты для перевода цен исходных данных ТЭП в цены текущего года
(характеристика актуальных площадок размещения новых электростанций: АЭС, ГЭС, ГАЭС, ТЭС и др.).
По одному значению на пару (версия БД, справочный год Year).
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index

from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin


class TepPriceConversionCoefficient(db.Model, AuditMixin):
    __tablename__ = "gs_gen_tep_price_conversion_coefficients"
    __table_args__ = (
        db.UniqueConstraint(
            "database_version_id",
            "id_year",
            name="uq_tep_price_conv_coeff_version_year",
        ),
        Index(
            "ix_tep_price_conv_coeff_id_year",
            "id_year",
        ),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    id_year = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_years.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    year = db.relationship("Year", foreign_keys=[id_year])

    # Множитель: цена_в_текущем_году = коэффициент * цена_исходная
    coefficient = db.Column(db.Numeric(24, 10), nullable=True)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return (
            f"<TepPriceConversionCoefficient id={self.id} id_year={self.id_year!r} "
            f"coefficient={self.coefficient!r}>"
        )
