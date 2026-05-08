# -*- coding: utf-8 -*-
"""
StationProspectivePlaceGES model (Перспективная площадка размещения ГЭС).

Структура полей совпадает с АЭС; таблицы отдельные (миграция будет позже).
"""
from sqlalchemy import and_
from sqlalchemy.orm import foreign
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.generation.models.station.station_model import Station


class StationProspectivePlaceGES(db.Model, AuditMixin):
    __tablename__ = 'gs_gen_station_prospective_place_ges'
    __table_args__ = (
        Index('ix_station_prospective_place_ges_site_name', 'site_name'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Стабильный код логической электростанции для связи со Station между версиями БД.
    external_code = db.Column(db.String(36), nullable=True, index=True)

    # Наименование площадки размещения ГЭС 
    site_name = db.Column(db.String(255), nullable=True)

    # Субъект РФ
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_districts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regional_district = db.relationship(
        "RegionalDistrict",
        backref="station_prospective_places_ges",
        foreign_keys=[id_regional_district],
    )
    
    # Региональное энергосистема
    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    regional_energy_system = db.relationship(
        "RegionalEnergySystem",
        backref="station_prospective_places_ges",
        foreign_keys=[id_regional_energy_system],
    )
    
    # Географическое расположение площадки (кадастровый номер земельного участка или координаты)
    geo_location = db.Column(db.String(500), nullable=True)

    # Планируемая установленная генерирующая мощность ГЭС, МВт
    planned_capacity_mw = db.Column(db.Integer, nullable=True)

    # Инициатор проекта
    project_initiator = db.Column(db.String(500), nullable=True)

    # Водный объект
    water_body = db.Column(db.String(500), nullable=True)

    # Вид регулирования
    regulation_type = db.Column(db.String(500), nullable=True)

    # Период ввода в эксплуатацию по Генеральной схеме до 2042 г.
    general_scheme_commissioning_period = db.Column(db.String(255), nullable=True)

    # Срок строительства, лет (до одного знака после запятой)
    construction_period_years = db.Column(db.Numeric(12, 1), nullable=True)

    id_prospective_place_type_ges = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_prospective_place_types_ges.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prospective_place_type_ges = db.relationship(
        "ProspectivePlaceTypeGES",
        foreign_keys=[id_prospective_place_type_ges],
    )

    # Порядок отображения площадки в списках/группировках
    display_order = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    station = db.relationship(
        "Station",
        primaryjoin=lambda: and_(
            foreign(StationProspectivePlaceGES.external_code) == Station.external_code,
            foreign(StationProspectivePlaceGES.database_version_id) == Station.database_version_id,
        ),
        viewonly=True,
        uselist=False,
        lazy="select",
    )

    ges_tep_source_indicators = db.relationship(
        "ProspectivePlaceGesTepSource",
        back_populates="station_prospective_place_ges",
        foreign_keys="ProspectivePlaceGesTepSource.id_station_prospective_place_ges",
        cascade="all, delete-orphan",
        order_by="ProspectivePlaceGesTepSource.id",
    )

    def __repr__(self) -> str:
        return f"<StationProspectivePlaceGES id={self.id} site_name={self.site_name!r}>"
