# -*- coding: utf-8 -*-
"""
StationProspectivePlaceAES model (Перспективная площадка размещения АЭС).

Поля:
- Текстовые: наименование площадки, субъект РФ, географическое расположение, планируемая мощность
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin


class StationProspectivePlaceAES(db.Model, AuditMixin):
    __tablename__ = 'gs_gen_station_prospective_place_aes'
    __table_args__ = (
        Index('ix_station_prospective_place_aes_site_name', 'site_name'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Текстовые поля
    # Наименование площадки размещения АЭС
    site_name = db.Column(db.String(255), nullable=True)
    # FK -> Субъект РФ (RegionalDistrict)
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_districts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regional_district = db.relationship(
        "RegionalDistrict",
        backref="station_prospective_places_aes",
        foreign_keys=[id_regional_district],
    )
    # FK -> Региональная энергосистема (RegionalEnergySystem)
    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regional_energy_system = db.relationship(
        "RegionalEnergySystem",
        backref="station_prospective_places_aes",
        foreign_keys=[id_regional_energy_system],
    )
    # Географическое расположение площадки (кадастровый номер земельного участка или координаты)
    geo_location = db.Column(db.String(500), nullable=True)
    # Планируемая установленная генерирующая мощность АЭС, МВт
    planned_capacity_mw = db.Column(db.Integer, nullable=True)
    # Планируемая единичная мощность энергоблока, МВт
    planned_unit_capacity_mw = db.Column(db.Integer, nullable=True)
    # Фактор отбора
    selection_factor = db.Column(db.String(255), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Связь один-ко-многим: у одной площадки может быть несколько энергоблоков
    machine_prospective_places = db.relationship(
        'MachineProspectivePlaceAES',
        back_populates='station_prospective_place_aes',
        foreign_keys='MachineProspectivePlaceAES.id_station_prospective_place_aes',
        cascade='all, delete-orphan',
    )

    def __repr__(self) -> str:
        return f"<StationProspectivePlaceAES id={self.id} site_name={self.site_name!r}>"
