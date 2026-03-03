# -*- coding: utf-8 -*-
"""
EquipmentGroupSet model (общая сущность группы оборудования).
"""
import uuid
from sqlalchemy import cast, Integer, event

from app.fuel.models.external_mapping.fue_em_cities_model import CitiesExternalMapping
from sqlalchemy.sql import func
from sqlalchemy.sql import text as sql_text
from app.extensions import db
from config import SCHEMA_FUEL, SCHEMA_REFDATA, SCHEMA_FUE_EM
from app.common.models.audit_mixin import AuditMixin
from app.common.models.versioned_model import VersionedModelMixin
from app.fuel.models.fue_equipment_group_set_station_model import EquipmentGroupSetStation


class EquipmentGroupSet(db.Model, AuditMixin, VersionedModelMixin):
    __tablename__ = "gs_fue_equipment_group_sets"
    __table_args__ = ({"schema": SCHEMA_FUEL},)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # FK -> EquipmentGroup
    id_equipment_group = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_equipment_groups.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    equipment_group = db.relationship("EquipmentGroup", back_populates="equipment_group_sets")

    # Пользовательский идентификатор/название группы
    name = db.Column(db.String(255), nullable=True)

    # Название (Топливо)
    name_ext = db.Column(db.String(255), nullable=True)

    # Признак группы оборудования
    niv = db.Column(db.String(255), nullable=True)

    # Признак станции, разбитой на группы оборудования
    comp = db.Column(db.String(255), nullable=True)

    # Код станции, в которую входит группа оборудования
    main = db.Column(db.String(255), nullable=True)

    # Признак действующей станции
    d = db.Column(db.String(255), nullable=True)

    # Признак расширяемой станции
    r = db.Column(db.String(255), nullable=True)

    # Признак ФОРЭМ
    forem = db.Column(db.String(255), nullable=True)

    # Ведомство
    vedomstvo = db.Column(db.String(255), nullable=True)

    # Код субъекта РФ (FK -> TerritoriesEnergyExternalMapping.external_id)
    obl = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_territories_energy.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    territories_energy_external_mapping = db.relationship(
        "TerritoriesEnergyExternalMapping",
        foreign_keys=[obl],
        backref="equipment_group_sets",
    )

    # Код департамента (FK -> DepartmentExternalMapping)
    dep = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_department.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    department_external_mapping = db.relationship(
        "DepartmentExternalMapping",
        foreign_keys=[dep],
        backref="equipment_group_sets",
    )

    # FK -> Department
    id_department = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    department = db.relationship("Department", backref="equipment_group_sets")

    # Код ОЭС (FK -> UnionEnergySystemExternalMapping.external_id)
    oes = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_union_energy_system.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    union_energy_system_external_mapping = db.relationship(
        "UnionEnergySystemExternalMapping",
        foreign_keys=[oes],
        backref="equipment_group_sets",
    )

    # Код экономического района (FK -> EconomicRegionExternalMapping.external_id)
    er = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_economic_region.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    economic_region_external_mapping = db.relationship(
        "EconomicRegionExternalMapping",
        foreign_keys=[er],
        backref="equipment_group_sets",
    )

    # Код федерального округа (FK -> FederalDistrictExternalMapping.external_id)
    fo = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_federal_district.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    federal_district_external_mapping = db.relationship(
        "FederalDistrictExternalMapping",
        foreign_keys=[fo],
        backref="equipment_group_sets",
    )

    # Код станции
    numb = db.Column(db.String(255), nullable=True)

    # Название типов турбин, которое соответствует коду (необязательное)
    tm = db.Column(db.String(255), nullable=True)

    # Мощность блока в группе оборудования_вариант 1
    n1 = db.Column(db.String(255), nullable=True)

    # Мощность блока в группе оборудования_вариант 2
    n2 = db.Column(db.String(255), nullable=True)

    # Давление пара перед турбиной_вариант 1
    p1 = db.Column(db.String(255), nullable=True)

    # Давление пара перед турбиной_вариант 2
    p2 = db.Column(db.String(255), nullable=True)

    # Порядковый номер станции
    ordnumb = db.Column(db.String(255), nullable=True)

    # Адрес
    addr = db.Column(db.String(255), nullable=True)

    # Примечание
    note = db.Column(db.String(1000), nullable=True)

    # Код города (связь по code -> CitiesExternalMapping.code, viewonly)
    codegor = db.Column(db.String(255), nullable=True)
    cities_external_mapping = db.relationship(
        "CitiesExternalMapping",
        primaryjoin=cast(codegor, Integer) == CitiesExternalMapping.code,
        foreign_keys=[codegor],
        viewonly=True,
        uselist=False,
        lazy="select",
    )

    # Тип генерирующей компании (FK -> BusinessUnitExternalMapping.external_id)
    be = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_business_unit.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    business_unit_external_mapping = db.relationship(
        "BusinessUnitExternalMapping",
        foreign_keys=[be],
        backref="equipment_group_sets",
    )

    # Код генерирующей компании (FK -> GenCompanyExternalMapping.external_id)
    gk = db.Column(
        db.String(80),
        db.ForeignKey(f"{SCHEMA_FUE_EM}.gs_fue_em_gen_company.external_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    gen_company_external_mapping = db.relationship(
        "GenCompanyExternalMapping",
        foreign_keys=[gk],
        backref="equipment_group_sets",
    )

    # Код филиала генерирующей компании (связь по external_id -> GenCompanyBranchExternalMapping, без FK в БД)
    gkf = db.Column(db.String(80), nullable=True, index=True)
    gen_company_branch_external_mapping = db.relationship(
        "GenCompanyBranchExternalMapping",
        primaryjoin="EquipmentGroupSet.gkf == GenCompanyBranchExternalMapping.external_id",
        foreign_keys="[EquipmentGroupSet.gkf]",
        viewonly=True,
        uselist=False,
        lazy="select",
    )

    # Универсальный внешний код для интеграции с другими системами
    external_code = db.Column(db.String(36), nullable=True, index=True)

    # Поле для связи с версией БД
    database_version_id = db.Column(
        db.Integer,
        db.ForeignKey(f"{SCHEMA_REFDATA}.gs_database_versions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # timestamps (UTC, server-side)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Связи
    station_links = db.relationship(
        "EquipmentGroupSetStation",
        back_populates="equipment_group_set",
        cascade="all, delete-orphan",
    )
    stations = db.relationship(
        "Station",
        secondary=EquipmentGroupSetStation.__table__,
        back_populates="equipment_group_sets",
        overlaps="equipment_group_set,station_links,station",
    )

    machines = db.relationship(
        "Machine",
        back_populates="equipment_group_set",
    )

    extra_fuel_params = db.relationship(
        "EquipmentGroupExtraFuelParam",
        back_populates="equipment_group_set",
        foreign_keys="EquipmentGroupExtraFuelParam.id_equipment_group_set",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<EquipmentGroupSet id={self.id} equipment_group_id={self.id_equipment_group}>"


@event.listens_for(EquipmentGroupSet, 'before_insert')
def generate_external_code_before_insert(mapper, connection, target):
    """
    Генерирует external_code перед вставкой записи.
    Ключ: station_external_code + equipment_group_id — стабильно для одного entity
    во всех версиях БД (см. docs/EXTERNAL_CODES_API.md).
    Можно передать _station_external_code_for_key при создании (напр. в import).
    """
    if target.external_code:
        return

    # При создании через import вызывающий код передаёт _station_external_code_for_key.
    # При before_insert связь EquipmentGroupSetStation ещё не создана.
    station_code = getattr(target, "_station_external_code_for_key", None)
    equipment_group_id = target.id_equipment_group or 0

    if not station_code:
        # Fallback: name + equipment_group_id (менее стабильно)
        name = target.name or f"equipment_group_set_id_{target.id or 0}"
        key = f"equipment_group_set|name|{name}|equipment_group_id|{equipment_group_id}"
    else:
        key = f"equipment_group_set|station|{station_code}|equipment_group_id|{equipment_group_id}"
    target.external_code = str(uuid.uuid5(uuid.NAMESPACE_URL, key))
