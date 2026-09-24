# -*- coding: utf-8 -*-
"""Сохранённые значения ввода расчёта по действующим ТЭС (топливо, выработка, тепло)."""
from sqlalchemy import ForeignKeyConstraint, Numeric, UniqueConstraint
from sqlalchemy.sql import func

from app.common.models.audit_mixin import AuditMixin
from app.extensions import db
from config import SCHEMA_ECOLOGY, SCHEMA_REFDATA


class OperatingTesInputValue(db.Model, AuditMixin):
    """Переопределение расхода топлива / выработки / тепла по территории и году."""

    __tablename__ = "gs_eco_operating_tes_inputs"
    __table_args__ = (
        UniqueConstraint(
            "territory_slug",
            "year_number",
            "row_key",
            "database_version_id",
            name="uq_eco_ot_input_terr_year_key_ver",
        ),
        ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_eco_ot_input_year_ver",
        ),
        {"schema": SCHEMA_ECOLOGY},
    )

    # Уникальный идентификатор записи
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Идентификатор территории (vsego, minen, severo-zapad, …)
    territory_slug = db.Column(db.String(80), nullable=False, index=True)

    # Год: Year.number + database_version_id (composite FK)
    year_number = db.Column(db.Integer, nullable=False, index=True)
    year = db.relationship(
        "Year",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==OperatingTesInputValue.year_number, "
            "Year.database_version_id==OperatingTesInputValue.database_version_id)"
        ),
        foreign_keys="[OperatingTesInputValue.year_number, OperatingTesInputValue.database_version_id]",
        viewonly=True,
    )

    # Ключ строки: вид топлива, ee_generation, heat_output, fuel_total
    row_key = db.Column(db.String(80), nullable=False, index=True)

    # Значение: топливо — тыс. тут; выработка ЭЭ — млрд.кВтч; отпуск тепла — тыс.Гкал
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
            f"<OperatingTesInputValue id={self.id} "
            f"terr={self.territory_slug} year={self.year_number} key={self.row_key}>"
        )
