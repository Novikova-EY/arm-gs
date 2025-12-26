# -*- coding: utf-8 -*-
"""
RegionalDistrict model (Субъект РФ).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.refdata.models.energy_systems.regional_district_regional_energy_system_model import regional_district_regional_energy_system
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin


class RegionalDistrict(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_regional_districts'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    # Идентификатор субъекта РФ
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Номер региона РФ (может быть пустым)
    region_number = db.Column(db.String(3), nullable=True, index=True)

    # Номер порядковый (может быть пустым)
    region_id = db.Column(db.String(3), nullable=True, index=True)

    # Наименование сокращенное
    name = db.Column(db.String(80), nullable=False, index=True)
    
    # Полное наименование
    name_full = db.Column(db.String(255), nullable=False)
    
    # Полное наименование в родительном падеже
    name_rp = db.Column(db.String(255), nullable=False)

    # Полное наименование в дательном падеже
    name_dp = db.Column(db.String(255), nullable=False)

    # FK -> Федеральный округ
    id_federal_district = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_federal_districts.id', ondelete='RESTRICT'),
        nullable=True,
        index=True
    )
    federal_district = db.relationship('FederalDistrict', back_populates='regional_districts')

    # M2M: Региональные энергосистемы
    regional_energy_systems = db.relationship(
        "RegionalEnergySystem",
        secondary=regional_district_regional_energy_system,
        back_populates="regional_districts"
    )

    # One-to-many: Станции
    stations = db.relationship('Station', back_populates='regional_district')

    # One-to-many: Энергорайоны (каскад был сохранен)
    energy_areas = db.relationship(
        'EnergyArea',
        back_populates='regional_district',
        cascade='all, delete-orphan'
    )

    # One-to-many: Энергоузлы (каскад был сохранен)
    energy_units = db.relationship(
        'EnergyUnit',
        back_populates='regional_district',
        cascade='all, delete-orphan'
    )

    # FK -> Энергозона (EnergyZone)
    id_energy_zone = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_energy_zones.id", ondelete="SET NULL", onupdate="CASCADE"),
        nullable=True,
        index=True,
    )
    energy_zone = db.relationship(
        "EnergyZone",
        back_populates="regional_districts",
        foreign_keys=[id_energy_zone],
    )

    # FK -> Синхронная зона (SynchronousArea)
    id_synchronous_area = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_synchronous_areas.id', ondelete='SET NULL', onupdate='CASCADE'),
        nullable=True,
        index=True
    )
    synchronous_area = db.relationship(
        'SynchronousArea',
        back_populates='regional_districts',
        foreign_keys=[id_synchronous_area]
    )

    # Таймстемпы базы (UTC)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    __table_args__ = (
        db.UniqueConstraint('database_version_id', 'name', name='uq_refdata_regional_districts_ver_name'),
        db.UniqueConstraint('database_version_id', 'name_full', name='uq_refdata_regional_districts_ver_name_full'),
        {"schema": SCHEMA_REFDATA},
    )

    @property
    def regional_energy_system(self):
        """Совместимость: вернуть первую РЭС, если необходимо одиночное значение."""
        return self.regional_energy_systems[0] if self.regional_energy_systems else None

    def __repr__(self) -> str:
        return f"<RegionalDistrict id={self.id} name={self.name!r}>"
