# -*- coding: utf-8 -*-
"""
RegionalEnergySystemEnergyGeneration — контрольная выработка ЭЭ по РЭС (млн кВт·ч).

Итоговые значения строки «Выработка» из сводов ОЭС по каждой региональной
энергосистеме. Используются для проверки загруженных данных:
- до 2018 включительно: сумма по станциям (без ЭСПП) + свод ЭСПП;
- с 2019: сумма по всем станциям, включая станции с признаком ЭСПП;
должна совпадать с контрольным итогом.

Данные хранятся по годам и, при необходимости, по месяцам:
- year_number — календарный год (ссылка на Year.number вместе с database_version_id);
- month_number = 0 — годовое значение («год»);
- month_number = 1..12 — значение за соответствующий месяц года.
"""
from sqlalchemy.sql import func
from sqlalchemy import Numeric
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_ENERGY_BALANCE, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.generation.models.common.version_year_unique_index import version_year_month_unique_index

# 0 — годовое значение («год»); 1–12 — номер месяца
RES_ENERGY_GENERATION_PERIOD_YEAR = 0


class RegionalEnergySystemEnergyGeneration(db.Model, AuditMixin):
    __tablename__ = "gs_bem_regional_energy_system_energy_generations"
    __table_args__ = (
        Index("ix_res_energy_gen_id_regional_energy_system", "id_regional_energy_system"),
        Index("ix_res_energy_gen_year_number", "year_number"),
        Index("ix_res_energy_gen_month_number", "month_number"),
        Index(
            "ix_res_energy_gen_res_year_month",
            "id_regional_energy_system",
            "year_number",
            "month_number",
        ),
        version_year_month_unique_index(
            "uq_res_energy_gen_res_year_month_ver",
            "id_regional_energy_system",
        ),
        db.ForeignKeyConstraint(
            ["year_number", "database_version_id"],
            [
                f"{SCHEMA_REFDATA}.gs_sys_years.number",
                f"{SCHEMA_REFDATA}.gs_sys_years.database_version_id",
            ],
            ondelete="RESTRICT",
            name="fk_res_energy_gen_year_ver",
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    year_number = db.Column(db.Integer, nullable=True, index=True)
    year = db.relationship(
        "Year",
        back_populates="regional_energy_system_energy_generations",
        lazy="noload",
        primaryjoin=(
            "and_(Year.number==RegionalEnergySystemEnergyGeneration.year_number, "
            "Year.database_version_id==RegionalEnergySystemEnergyGeneration.database_version_id)"
        ),
    )
    month_number = db.Column(
        db.Integer,
        nullable=False,
        default=RES_ENERGY_GENERATION_PERIOD_YEAR,
        server_default="0",
        index=True,
    )

    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(
            f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id",
            ondelete="RESTRICT",
        ),
        nullable=True,
        index=True,
    )
    regional_energy_system = db.relationship(
        "RegionalEnergySystem",
        foreign_keys=[id_regional_energy_system],
    )

    # Выработка электроэнергии, млн кВт·ч
    electricity_generation = db.Column(Numeric(25, 16))

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    @property
    def is_annual(self) -> bool:
        return self.month_number == RES_ENERGY_GENERATION_PERIOD_YEAR

    def __repr__(self) -> str:
        period = "год" if self.is_annual else f"мес.{self.month_number}"
        return (
            f"<RegionalEnergySystemEnergyGeneration id={self.id} "
            f"res_id={self.id_regional_energy_system} year={self.year_number} "
            f"period={period} gen={self.electricity_generation}>"
        )
