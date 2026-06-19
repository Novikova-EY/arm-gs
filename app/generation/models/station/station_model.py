# -*- coding: utf-8 -*-
"""
Station model (Электростанция).
- Сохранены все исходные связи и индексы/уникальные ограничения.
- Добавлены серверные таймстемпы (UTC).
"""
import uuid
from sqlalchemy import event, text as sql_text
from sqlalchemy.sql import func
from sqlalchemy.schema import Index
from app.extensions import db
from config import SCHEMA_GENERATION, SCHEMA_REFDATA
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.generation.models.station.station_constants import (
    STATION_SIGN_ESPP,
    STATION_SIGN_UNSPECIFIED,
)

class Station(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = 'gs_gen_stations'
    __table_args__ = (
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
        db.ForeignKey(f"{SCHEMA_GENERATION}.gs_gen_station_groups.id", ondelete="RESTRICT"),
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
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_condition_types.id', ondelete='RESTRICT'),
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
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_regional_districts.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    regional_district = db.relationship('RegionalDistrict', back_populates='stations')

    # FK -> RegionalEnergySystem (прямая связь электростанции с РЭС)
    id_regional_energy_system = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_regional_energy_systems.id', ondelete='RESTRICT'),
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
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_energy_units.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    energy_unit = db.relationship('EnergyUnit', back_populates='stations')

    # FK -> StationType
    id_station_type = db.Column(
        db.Integer,
        db.ForeignKey(f'{SCHEMA_REFDATA}.gs_sys_station_types.id', ondelete='RESTRICT'),
        nullable=True,
        index=True,
    )
    station_type = db.relationship('StationType', back_populates='stations')

    # Children
    station_powers = db.relationship('StationPower', back_populates='station_power', cascade="all, delete-orphan")
    station_energy_generations = db.relationship(
        'StationEnergyGeneration',
        back_populates='station',
        cascade="all, delete-orphan",
    )
    station_gaes_charge_consumptions = db.relationship(
        'StationGaesChargeConsumption',
        back_populates='station',
        cascade="all, delete-orphan",
    )
    machines = db.relationship('Machine', back_populates='machine_station')
    boilers = db.relationship('Boiler', back_populates='boiler_station')
    equipment_group_type_links_v2 = db.relationship(
        "EquipmentGroupSetStation",
        back_populates="station",
        foreign_keys="EquipmentGroupSetStation.station_id",
    )
    
    # Прочее
    kto = db.Column(db.String(80), unique=True, nullable=True)
    location = db.Column(db.String(255), unique=True, nullable=True)
    note = db.Column(db.String(1000), nullable=True)
    
    # Признак электростанции: «ЭСПП» или не указано (NULL)
    station_sign = db.Column(db.String(20), nullable=True)

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
        # 1) Если у электростанции явно указана РЭС — используем ее
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
        Приоритет: прямая связь РЭС у электростанции, затем связь через субъект РФ.
        """
        # 1) Если у электростанции явно указана РЭС с ОЭС — используем ее
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
        Приоритет: прямая связь РЭС у электростанции, затем связь через субъект РФ.
        """
        # 1) Если у электростанции явно указана РЭС с типом энергосистемы — используем ее
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

    @property
    def station_sign_display(self) -> str:
        if self.station_sign == STATION_SIGN_ESPP:
            return STATION_SIGN_ESPP
        return STATION_SIGN_UNSPECIFIED

    def __repr__(self) -> str:
        return f"<Station id={self.id} name={self.name!r}>"


def _station_key(name, name_so, name_combined, district_id) -> str:
    district_key = _normalize_station_key_part(district_id)
    normalized_name = _normalize_station_key_part(name)
    normalized_name_so = _normalize_station_key_part(name_so)
    normalized_name_combined = _normalize_station_key_part(name_combined)

    if normalized_name and district_key:
        return f"station|name|{normalized_name}|district|{district_key}"
    if normalized_name:
        return f"station|name|{normalized_name}"
    if normalized_name_combined and district_key:
        return f"station|combined|{normalized_name_combined}|district|{district_key}"
    if normalized_name_combined:
        return f"station|combined|{normalized_name_combined}"
    if normalized_name_so and district_key:
        return f"station|so|{normalized_name_so}|district|{district_key}"
    if normalized_name_so:
        return f"station|so|{normalized_name_so}"
    return f"station|name||district|{district_key}"


def _normalize_station_key_part(value) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split()).strip().lower()


def _build_regional_district_key(region_number=None, name=None, name_full=None, ref_uuid=None) -> str:
    parts = []

    normalized_region_number = _normalize_station_key_part(region_number)
    normalized_name = _normalize_station_key_part(name)
    normalized_name_full = _normalize_station_key_part(name_full)

    if normalized_region_number:
        parts.append(f"num|{normalized_region_number}")
    if normalized_name:
        parts.append(f"name|{normalized_name}")
    elif normalized_name_full:
        parts.append(f"full|{normalized_name_full}")

    # Стабильный идентификатор субъекта между версиями БД (см. RefdataUuidMixin.ref_uuid).
    # Без него разные субъекты могли давать одинаковый ключ, если num/name совпадали.
    ru = _normalize_station_key_part(ref_uuid)
    if ru:
        parts.append(f"ref_uuid|{ru}")

    return "|".join(parts)


def _resolve_regional_district_key(connection, target) -> str:
    district = getattr(target, "regional_district", None)
    if district is not None:
        return _build_regional_district_key(
            region_number=getattr(district, "region_number", None),
            name=getattr(district, "name", None),
            name_full=getattr(district, "name_full", None),
            ref_uuid=getattr(district, "ref_uuid", None),
        )

    if not target.id_regional_district:
        return ""

    row = connection.execute(
        sql_text(
            f"""
            SELECT region_number, name, name_full, ref_uuid
            FROM {SCHEMA_REFDATA}.gs_sys_regional_districts
            WHERE id = :district_id
            """
        ),
        {"district_id": target.id_regional_district},
    ).fetchone()

    if not row:
        return ""

    return _build_regional_district_key(
        region_number=row[0],
        name=row[1],
        name_full=row[2],
        ref_uuid=row[3],
    )


def _find_existing_station_external_code(connection, target, district_key) -> str | None:
    normalized_name = _normalize_station_key_part(target.name)
    if not normalized_name:
        return None

    rows = connection.execute(
        sql_text(
            f"""
            SELECT
                s.external_code,
                rd.region_number,
                rd.name,
                rd.name_full,
                rd.ref_uuid
            FROM {SCHEMA_GENERATION}.gs_gen_stations s
            LEFT JOIN {SCHEMA_REFDATA}.gs_sys_regional_districts rd
                ON rd.id = s.id_regional_district
            WHERE lower(trim(s.name)) = :station_name
            """
        ),
        {"station_name": normalized_name},
    ).fetchall()

    if not rows:
        return None

    district_keys_by_external_code = {}
    for row in rows:
        row_district_key = _build_regional_district_key(
            region_number=row[1],
            name=row[2],
            name_full=row[3],
            ref_uuid=row[4],
        )
        district_keys_by_external_code.setdefault(row[0], set()).add(row_district_key)

    has_legacy_collision = any(len(keys) > 1 for keys in district_keys_by_external_code.values())
    if has_legacy_collision and district_key:
        return None

    matching_codes = {
        row[0]
        for row in rows
        if _build_regional_district_key(
            region_number=row[1],
            name=row[2],
            name_full=row[3],
            ref_uuid=row[4],
        ) == district_key
    }
    if len(matching_codes) == 1:
        return next(iter(matching_codes))

    all_codes = {row[0] for row in rows if row[0]}
    if len(all_codes) == 1 and not has_legacy_collision:
        return next(iter(all_codes))

    return None


@event.listens_for(Station, 'before_insert')
def generate_external_code_before_insert(mapper, connection, target):
    """Генерирует стабильный external_code перед вставкой электростанции."""
    if target.external_code:
        return
    district_key = _resolve_regional_district_key(connection, target)
    existing_external_code = _find_existing_station_external_code(connection, target, district_key)
    if existing_external_code:
        target.external_code = existing_external_code
        return
    key = _station_key(
        target.name,
        target.name_so,
        target.name_combined,
        district_key,
    )
    target.external_code = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
