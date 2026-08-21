# -*- coding: utf-8 -*-
"""
EnergyUnit model (Энергорайон).
"""
from sqlalchemy.sql import func
from app.extensions import db
from config import SCHEMA_REFDATA, SCHEMA_GENERATION
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.refdata.models.refdata_uuid_mixin import RefdataUuidMixin


class EnergyUnit(db.Model, AuditMixin, VersionedModelMixin, RefdataUuidMixin):
    __tablename__ = 'gs_sys_energy_units'
    __table_args__ = {"schema": SCHEMA_REFDATA}

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(256), nullable=False, index=True)

    # Полное наименование в родительном падеже
    name_rp = db.Column(db.String(255), nullable=False)
    # Полное наименование в предложном падеже
    name_dp = db.Column(db.String(255), nullable=False)
    # Наименование в дательном падеже (для «Итого по …»)
    name_dat = db.Column(db.String(255), nullable=False, server_default="")

    # FK -> RegionalDistrict
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_regional_districts.id', ondelete='RESTRICT'),
        index=True,
        nullable=False
    )
    regional_district = db.relationship(
        'RegionalDistrict',
        back_populates='energy_units'
    )

    # FK -> RegionalEnergySystem
    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id', ondelete='RESTRICT'),
        index=True,
        nullable=False
    )
    regional_energy_system = db.relationship(
        'RegionalEnergySystem',
        back_populates='energy_units'
    )

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
        db.UniqueConstraint('database_version_id', 'name', name='uq_refdata_energy_units_ver_name'),
        {"schema": SCHEMA_REFDATA},
    )

    # связь со станциями
    stations = db.relationship(
        'Station',
        back_populates='energy_unit'
    )

    demand_parameters = db.relationship(
        'EnergyUnitDemandParameter',
        back_populates='energy_unit',
        cascade='all, delete-orphan',
    )

    @property
    def union_energy_system(self):
        if self.regional_energy_system and self.regional_energy_system.union_energy_system:
            return self.regional_energy_system.union_energy_system
        return None

    def __repr__(self) -> str:
        return f"<EnergyUnit id={self.id} name={self.name!r}>"
