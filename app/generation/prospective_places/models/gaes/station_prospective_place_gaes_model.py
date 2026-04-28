# -*- coding: utf-8 -*-
"""
StationProspectivePlaceGAES model (Перспективная площадка размещения ГАЭС).

Структура полей совпадает с ГЭС; отдельные таблицы (миграция будет позже).
"""
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin


class StationProspectivePlaceGAES(db.Model, AuditMixin):
    __tablename__ = "gs_gen_station_prospective_place_gaes"
    __table_args__ = (
        Index("ix_station_prospective_place_gaes_site_name", "site_name"),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    site_name = db.Column(db.String(255), nullable=True)

    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_districts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regional_district = db.relationship(
        "RegionalDistrict",
        backref="station_prospective_places_gaes",
        foreign_keys=[id_regional_district],
    )

    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regional_energy_system = db.relationship(
        "RegionalEnergySystem",
        backref="station_prospective_places_gaes",
        foreign_keys=[id_regional_energy_system],
    )

    # Координаты
    geo_location = db.Column(db.String(500), nullable=True)
    
    # Установленная мощность
    planned_capacity_mw = db.Column(db.String(500), nullable=True)

    # Инициатор проекта
    project_initiator = db.Column(db.String(500), nullable=True)

    # Водохранилище
    water_body = db.Column(db.String(500), nullable=True)

    # Срок строительства по Генеральной схеме
    general_scheme_commissioning_period = db.Column(db.String(255), nullable=True)

    # Срок строительства (до одного знака после запятой)
    construction_period_years = db.Column(db.Numeric(12, 1), nullable=True)

    id_prospective_place_type_gaes = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_prospective_place_types_gaes.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prospective_place_type_gaes = db.relationship(
        "ProspectivePlaceTypeGAES",
        foreign_keys=[id_prospective_place_type_gaes],
    )

    # Порядок отображения площадки в списках/группировках
    display_order = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    gaes_tep_source_indicators = db.relationship(
        "ProspectivePlaceGaesTepSource",
        back_populates="station_prospective_place_gaes",
        foreign_keys="ProspectivePlaceGaesTepSource.id_station_prospective_place_gaes",
        cascade="all, delete-orphan",
        order_by="ProspectivePlaceGaesTepSource.id",
    )

    def __repr__(self) -> str:
        return f"<StationProspectivePlaceGAES id={self.id} site_name={self.site_name!r}>"
