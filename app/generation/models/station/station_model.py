# -*- coding: utf-8 -*-
"""
Station model (Электростанция).
- Сохранены все исходные связи и индексы/уникальные ограничения.
- Добавлены серверные таймстемпы (UTC).
"""
import uuid
from sqlalchemy import event
from sqlalchemy.sql import func
from sqlalchemy.schema import UniqueConstraint, Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.versioned_model import VersionedModelMixin

class Station(db.Model, VersionedModelMixin):
    __tablename__ = 'stations'
    __table_args__ = (
        UniqueConstraint('name', 'id_regional_district', name='uq_station_name_district'),
        Index('ix_station_id_regional_district', 'id_regional_district'),
        Index('ix_station_name', 'name'),
        Index('ix_station_external_code', 'external_code'),
        Index('ix_station_id_station_group', 'id_station_group'),
        Index('ix_station_id_station_type', 'id_station_type'),
        {"schema": SCHEMA_GENERATION},
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    external_code = db.Column(
        db.String(36),
        nullable=False,
    )

    # FK -> StationGroup
    id_station_group = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_GENERATION}.station_groups.id", ondelete="RESTRICT"),
        nullable=True,
        index=True
    )
    group = db.relationship(
        "StationGroup",
        back_populates="stations",
        foreign_keys=[id_station_group]
    )

    # FK -> ConditionType
    id_condition_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_condition_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    condition_type = db.relationship('ConditionType', back_populates='stations')

    # Наименования
    name = db.Column(db.String(255), nullable=False)
    name_so = db.Column(db.String(80), unique=True, nullable=True)
    name_combined = db.Column(db.String(80), unique=True, nullable=True)
    name_archive = db.Column(db.String(80), unique=True, nullable=True)

    # FK -> RegionalDistrict
    id_regional_district = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_regional_districts.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    regional_district = db.relationship('RegionalDistrict', back_populates='stations')

    # FK -> RegionalEnergySystem (прямая связь станции с РЭС)
    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_regional_energy_systems.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    # Отдельное имя атрибута, чтобы не конфликтовать с агрегированным свойством regional_energy_system ниже
    regional_energy_system_obj = db.relationship(
        'RegionalEnergySystem',
        foreign_keys=[id_regional_energy_system],
    )

    # FK -> EnergyUnit
    id_energy_unit = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_energy_units.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    energy_unit = db.relationship('EnergyUnit', back_populates='stations')

    # FK -> StationType
    id_station_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_station_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    station_type = db.relationship('StationType', back_populates='stations')

    # Children
    station_powers = db.relationship('StationPower', back_populates='station_power', cascade="all, delete-orphan")
    machines = db.relationship('Machine', back_populates='machine_station')
    boilers = db.relationship('Boiler', back_populates='boiler_station')
    
    # FK -> StationEquipmentGroup
    station_equipment_groups = db.relationship(
        'StationEquipmentGroup',
        back_populates='station',
        cascade="all, delete-orphan",
    )

    # Прочее
    kto = db.Column(db.String(80), unique=True, nullable=True)
    location = db.Column(db.String(255), unique=True, nullable=True)
    note = db.Column(db.String(1000), nullable=True)

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # version для оптимистической блокировки (определен в VersionedModelMixin)
    # version = db.Column(db.Integer, nullable=False, default=1)
    
    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # ----- Aggregated helpers (не маппятся в БД) -----
    @property
    def regional_energy_system(self):
        """
        Агрегированное текстовое поле с названием(ями) РЭС.
        Приоритет: прямая связь id_regional_energy_system, затем связь через субъект РФ.
        """
        # 1) Если у станции явно указана РЭС — используем её
        if self.regional_energy_system_obj:
            return self.regional_energy_system_obj.name

        # 2) Fallback: множ. связь через субъект РФ (старое поведение)
        if self.regional_district and self.regional_district.regional_energy_systems:
            return ", ".join(res.name for res in self.regional_district.regional_energy_systems)
        return None

    @property
    def union_energy_system(self):
        """
        Агрегированное текстовое поле ОЭС.
        Приоритет: прямая связь РЭС у станции, затем связь через субъект РФ.
        """
        # 1) Если у станции явно указана РЭС с ОЭС — используем её
        if self.regional_energy_system_obj and self.regional_energy_system_obj.union_energy_system:
            return self.regional_energy_system_obj.union_energy_system.name

        # 2) Fallback: собираем по всем РЭС субъекта
        if self.regional_district and self.regional_district.regional_energy_systems:
            union_systems = {
                res.union_energy_system.name
                for res in self.regional_district.regional_energy_systems
                if res.union_energy_system
            }
            return ", ".join(union_systems) if union_systems else None
        return None

    @property
    def federal_district(self):
        return self.regional_district.federal_district.name if self.regional_district and self.regional_district.federal_district else None

    @property
    def energy_system_type(self):
        """
        Агрегированное текстовое поле «Часть энергосистемы России».
        Приоритет: прямая связь РЭС у станции, затем связь через субъект РФ.
        """
        # 1) Если у станции явно указана РЭС с типом энергосистемы — используем её
        if (
            self.regional_energy_system_obj
            and self.regional_energy_system_obj.union_energy_system
            and self.regional_energy_system_obj.union_energy_system.energy_system_type
        ):
            return self.regional_energy_system_obj.union_energy_system.energy_system_type.name

        # 2) Fallback: собираем по всем РЭС субъекта
        if self.regional_district and self.regional_district.regional_energy_systems:
            types = {
                res.union_energy_system.energy_system_type.name
                for res in self.regional_district.regional_energy_systems
                if res.union_energy_system and res.union_energy_system.energy_system_type
            }
            return ", ".join(types) if types else None
        return None

    @property
    def gen_companies(self):
        if not self.machines:
            return None
        gen_companies = {machine.gen_company.name for machine in self.machines if machine.gen_company}
        return ", ".join(gen_companies) if gen_companies else None


    def __repr__(self) -> str:
        return f"<Station id={self.id} name={self.name!r}>"


def _station_key(name, name_so, name_combined, district_id) -> str:
    if name_so:
        return f"station|so|{name_so}"
    if name_combined:
        return f"station|combined|{name_combined}"
    return f"station|name|{name or ''}|district|{district_id or ''}"


@event.listens_for(Station, 'before_insert')
def generate_external_code_before_insert(mapper, connection, target):
    """Генерирует стабильный external_code перед вставкой станции."""
    if target.external_code:
        return
    key = _station_key(
        target.name,
        target.name_so,
        target.name_combined,
        target.id_regional_district,
    )
    target.external_code = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
