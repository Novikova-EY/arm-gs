# -*- coding: utf-8 -*-
"""
Контрольная выработка ЭЭ по уровням иерархии, кроме РЭС (млн кВтч).

Строки РЭС хранятся в RegionalEnergySystemEnergyGeneration.
Эта таблица – тот же параметр для Россия / типа ЭС / СЗ / ОЭС.
"""
from sqlalchemy.sql import func
from sqlalchemy import Numeric, Index, text

from app.extensions import db
from app.common.models.audit_mixin import AuditMixin
from config import SCHEMA_ENERGY_BALANCE, SCHEMA_REFDATA

HIERARCHY_CONTROL_PERIOD_YEAR = 0
HIERARCHY_CONTROL_LEVELS = frozenset({"russia", "est", "sa", "ues"})


class EnergySystemEnergyGenerationControl(db.Model, AuditMixin):
    __tablename__ = "gs_bem_energy_system_energy_generation_controls"
    __table_args__ = (
        Index("ix_es_energy_gen_ctrl_level", "level"),
        Index("ix_es_energy_gen_ctrl_entity", "entity_id"),
        Index("ix_es_energy_gen_ctrl_year", "year_number"),
        Index("ix_es_energy_gen_ctrl_month", "month_number"),
        Index(
            "uq_es_energy_gen_ctrl_level_entity_year_month_ver",
            "level",
            text("COALESCE(entity_id, -1)"),
            "year_number",
            "month_number",
            text("COALESCE(database_version_id, -1)"),
            unique=True,
        ),
        {"schema": SCHEMA_ENERGY_BALANCE},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    level = db.Column(db.String(16), nullable=False, index=True)
    entity_id = db.Column(db.Integer, nullable=True, index=True)
    year_number = db.Column(db.Integer, nullable=True, index=True)
    month_number = db.Column(
        db.Integer,
        nullable=False,
        default=HIERARCHY_CONTROL_PERIOD_YEAR,
        server_default="0",
        index=True,
    )
    electricity_generation = db.Column(Numeric(25, 16))
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
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
            f"<EnergySystemEnergyGenerationControl id={self.id} "
            f"level={self.level!r} entity_id={self.entity_id} "
            f"year={self.year_number} gen={self.electricity_generation}>"
        )
