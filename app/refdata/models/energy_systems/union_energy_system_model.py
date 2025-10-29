# -*- coding: utf-8 -*-
"""
UnionEnergySystem model (Объединенная энергосистема, ОЭС).
- Связана с EnergySystemType (многие-к-одному).
- Имеет набор RegionalEnergySystem (один-ко-многим).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION

class UnionEnergySystem(db.Model):
    __tablename__ = 'union_energy_systems'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Порядок отображения
    display_order = db.Column(db.Integer, nullable=True)

    # Наименование и полное наименование
    name = db.Column(db.String(80), nullable=False, index=True)

    # Устанавливаем по умолчанию name_full := name на уровне Python-контекста вставки
    name_full = db.Column(
        db.String(80),
        nullable=False,
        default=lambda context: context.get_current_parameters().get("name")
    )

    # FK -> EnergySystemType
    id_energy_system_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.energy_system_types.id', ondelete='RESTRICT'),
        index=True,
        nullable=True
    )

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    __table_args__ = (
        db.UniqueConstraint('database_version_id', 'name', name='uq_refdata_ues_ver_name'),
        db.UniqueConstraint('database_version_id', 'name_full', name='uq_refdata_ues_ver_name_full'),
        {"schema": SCHEMA_REFDATA},
    )

    # Children: RegionalEnergySystem
    regional_energy_systems = db.relationship(
        'RegionalEnergySystem',
        back_populates='union_energy_system'
    )

    # Parent: EnergySystemType
    energy_system_type = db.relationship(
        'EnergySystemType',
        back_populates='union_energy_systems'
    )

    def __repr__(self) -> str:
        return f"<UnionEnergySystem id={self.id} name={self.name!r}>"
